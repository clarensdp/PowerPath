"""
PowerPath engine (packet v5.5.1).

Pipeline for one candidate (opening month, customer settings):
  1. Inputs: the packet's own `prepare_inputs()` builds the 87,600-hour table.
  2. Sizing MILP on representative days (HiGHS): integer blocks for all seven resources,
     land limit, availability dates, exact horizon capacity/contract charges, sampled
     variable costs, stress-day import limits, Tier 1/Tier 2 limits, hard requirements.
  3. Chronological dispatch: one LP per 730-hour model month, battery SOC carried from
     month to month, SOC 0 at the start and end of the horizon, annual cycle cap.
  4. Accounting: the packet checker's `check()` and `score()` on our own dispatch, so every
     figure the product shows is the common benchmark figure.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.optimize import linprog, milp, LinearConstraint, Bounds

PACKET = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKET / "starter"))
import check_submission as cs  # noqa: E402  (packet utility, unchanged)

OPT = cs.options.set_index("option_id")
CASE, RESP = cs.case, cs.response
RES = list(OPT.index)                     # utility_solar, wind, battery_4h, gas_turbine, nuclear, gas_engine, fuel_cell
THERMAL = [k for k in RES if OPT.loc[k, "kind"] == "dispatchable"]
OFFSITE = [k for k in RES if OPT.loc[k, "location"] == "offsite"]
ONSITE = [k for k in RES if OPT.loc[k, "location"] == "onsite"]
BATT = "battery_4h"
ETA = math.sqrt(OPT.loc[BATT, "round_trip_efficiency"])
DUR = float(OPT.loc[BATT, "duration_hours"])
HPM = CASE["hours_per_model_month"]
H = CASE["horizon_months"] * HPM
LAND = CASE["onsite_energy_land_acres"]
REMOTE_MULT = RESP["remote_energy_multiplier"]
LABELS = {"utility_solar": "Solar contract", "wind": "Wind contract", "battery_4h": "Battery (4h)",
          "gas_turbine": "Gas turbine", "nuclear": "Nuclear PPA", "gas_engine": "Gas engines",
          "fuel_cell": "Fuel cells"}
UNMET_PEN = 200_000.0


def crf(life, r=CASE["discount_rate_real"]):
    return r / (1 - (1 + r) ** (-life))


def fixed_annual_per_mw(k):
    o = OPT.loc[k]
    return 1000 * (o.capex_usd_per_kw * crf(o.life_years) + o.fom_usd_per_kw_year)


@dataclass
class Scenario:
    initial_service_month: int = 20
    grid_delay_months: int = 0
    carbon_price: float = 0.0          # $/t customer valuation (steers choice; not a cash cost)
    allowed: tuple = tuple(RES)
    max_intensity_kg: float | None = None   # combined_electricity_co2_kg_per_mwh
    min_clean_share: float | None = None
    max_merchant_share: float | None = None
    budget_musd: float | None = None        # total decision cost cap
    no_tier2: bool = False
    allow_tier1: bool = True
    # reliability must-have: every hour stays servable if the largest onsite unit (one block)
    # is out, using only permitted flexibility, the import limit and the other onsite units
    n_minus_1: bool = False
    # location screening: '' = benchmark (Williamson County, official checker accounting);
    # 'US-VA', 'C-IE', ... = same engine on regionally scaled inputs (own accounting, labelled)
    region: str = ""
    # execution sensitivity: ((resource, months_late), ...) - equipment or permit slip.
    # Shifts when a resource can run; the benchmark case (no slips) stays the anchor.
    avail_shift: tuple = ()

    @property
    def full_demand_month(self):
        return self.initial_service_month + CASE["ramp_duration_months"]

    def key(self):
        d = asdict(self)
        d["allowed"] = tuple(sorted(d["allowed"]))
        return tuple(sorted(d.items()))


# ------------------------------------------------------------------------------------
# Inputs
# ------------------------------------------------------------------------------------
_CTX_CACHE: dict = {}


def avail_month(r, shift=()):
    return int(OPT.loc[r, "available_month"]) + int(dict(shift).get(r, 0))


def context(start, delay, shift=(), region=""):
    shift = tuple(sorted(shift))
    k = (start, delay, shift, region)
    if k not in _CTX_CACHE:
        ctx = cs.prepare_inputs({"initial_service_month": int(start), "grid_delay_months": int(delay),
                                 "capacities_mw": {}})
        f = ctx["frame"]
        prof = {}
        for r in RES:
            col = OPT.loc[r, "profile_column"]
            base = cs.hourly[col].to_numpy(float)[ctx["ref"]] if col else np.ones(H)
            mask = ctx["month"] >= max(start, avail_month(r, shift))
            prof[r] = base * mask
            prof[r + "_mask"] = mask
        ctx["prof"] = prof
        ctx["shift"] = shift
        ctx["region"] = region
        if region:
            from .regions import region_params
            rp = region_params(region)
            if rp:
                adder = float(cs.hourly["grid_adder_usd_per_mwh"].iloc[0])
                ctx["grid_price"] = (ctx["grid_price"] - adder) * rp["price_index"] + adder
                ctx["grid_co2"] = ctx["grid_co2"] * rp["co2_ratio"]
                ctx["remote_co2"] = ctx["remote_co2"] * rp["co2_ratio"]
                for r_, ratio in (("utility_solar", rp["solar_ratio"]), ("wind", rp["wind_ratio"])):
                    prof[r_] = np.clip(prof[r_] * ratio, 0, 1.0)
        ctx["gas_price"] = f.delivered_gas_price_usd_per_mmbtu.to_numpy()
        if len(_CTX_CACHE) > 24:
            _CTX_CACHE.pop(next(iter(_CTX_CACHE)))
        _CTX_CACHE[k] = ctx
    return _CTX_CACHE[k]


def capacity_cost_per_mw(ctx, k):
    """Exact horizon $ per MW selected: capacity charges or available-generation payments."""
    o = OPT.loc[k]
    mask = ctx["prof"][k + "_mask"]
    fixed = fixed_annual_per_mw(k) / 8760 * mask.sum()
    pay = o.payment_usd_per_mwh * ctx["prof"][k].sum() if o.payment_basis == "available_generation" else 0.0
    return fixed + pay


# ------------------------------------------------------------------------------------
# Representative days for sizing
# ------------------------------------------------------------------------------------
def sample_days(ctx, start, extra_days=()):
    """Return list of (first_hour, weight). Every month for the first 12 months after opening
    and around grid milestones, then every 5th month (coprime with 12 so all seasons are
    covered); 3 days per sampled month (low/median/high renewable). All stress days."""
    f = ctx["frame"]
    re = (f.wind_proxy_cf.to_numpy() * 0.5 + f.solar_proxy_cf.to_numpy() * 0.5)
    stress_day = ctx["active"].reshape(-1, 24).any(axis=1)
    re_day = re.reshape(-1, 24).mean(axis=1)
    month_of_day = (np.arange(H // 24) * 24) // HPM
    months = list(range(start, CASE["horizon_months"]))
    dense = set(range(start, min(start + 13, 120)))
    for m0, _ in cs.grid_schedule.values:
        mm = int(m0) + (ctx["delay"] if m0 > 0 else 0)
        dense |= {mm - 1, mm, mm + 1}
    for r in RES:
        dense.add(avail_month(r, ctx.get("shift", ())))
    sampled, w_month = [], {}
    i = 0
    rest = [m for m in months if m not in dense]
    for m in months:
        if m in dense:
            sampled.append(m); w_month[m] = 1.0
    for j in range(0, len(rest), 5):
        grp = rest[j:j + 5]
        m = grp[len(grp) // 2]
        sampled.append(m); w_month[m] = float(len(grp))
    days = []
    for m in sorted(sampled):
        d_in = np.nonzero((month_of_day == m) & ~stress_day)[0]
        # hours in month m that fall in whole days
        if len(d_in) == 0:
            continue
        order = d_in[np.argsort(re_day[d_in])]
        reps = [order[int(q * (len(order) - 1))] for q in (1 / 6, 0.5, 5 / 6)]
        w = HPM / 24.0 * w_month[m] / len(reps)
        days += [(int(d) * 24, w) for d in reps]
    for d in np.nonzero(stress_day & (month_of_day >= start))[0]:
        days.append((int(d) * 24, 1.0))
    for d in extra_days:
        days.append((int(d) * 24, 1.0))
    # de-duplicate keeping max weight
    out = {}
    for h0, w in days:
        out[h0] = max(out.get(h0, 0), w)
    return sorted(out.items())


# ------------------------------------------------------------------------------------
# Sparse LP builder
# ------------------------------------------------------------------------------------
class Model:
    def __init__(self):
        self.n = 0
        self.c, self.lb, self.ub, self.integ = [], [], [], []
        self.R, self.C, self.V, self.lo, self.hi = [], [], [], [], []
        self.m = 0
        self.tags = {}

    def var(self, size, cost=0.0, lb=0.0, ub=np.inf, integer=False):
        idx = np.arange(self.n, self.n + size)
        self.n += size
        self.c.append(np.broadcast_to(np.asarray(cost, float), (size,)).astype(float))
        self.lb.append(np.broadcast_to(np.asarray(lb, float), (size,)).astype(float))
        self.ub.append(np.broadcast_to(np.asarray(ub, float), (size,)).astype(float))
        self.integ.append(np.full(size, 1 if integer else 0))
        return idx

    def rows(self, terms, lo, hi, nrows, tag=None):
        """nrows constraints: lo <= sum_terms coef*x <= hi. A term index of size 1 is
        broadcast to every row (capacity variables)."""
        r0 = self.m
        for idx, coef in terms:
            idx = np.asarray(idx).ravel()
            if idx.size == 0:
                continue
            idx = np.broadcast_to(idx, (nrows,)) if idx.size == 1 else idx
            self.R.append(np.arange(r0, r0 + nrows)); self.C.append(idx)
            self.V.append(np.broadcast_to(np.asarray(coef, float), (nrows,)).astype(float))
        self.lo.append(np.broadcast_to(np.asarray(lo, float), (nrows,)).astype(float))
        self.hi.append(np.broadcast_to(np.asarray(hi, float), (nrows,)).astype(float))
        if tag:
            self.tags[tag] = (r0, nrows)
        self.m += nrows

    def row_sum(self, terms, lo, hi, tag=None):
        r0 = self.m
        for idx, coef in terms:
            idx = np.asarray(idx).ravel()
            if idx.size == 0:
                continue
            self.R.append(np.full(idx.size, r0)); self.C.append(idx)
            self.V.append(np.broadcast_to(np.asarray(coef, float), (idx.size,)).astype(float))
        self.lo.append(np.array([lo], float)); self.hi.append(np.array([hi], float))
        if tag:
            self.tags[tag] = (r0, 1)
        self.m += 1

    def matrix(self):
        return sp.csr_matrix((np.concatenate(self.V), (np.concatenate(self.R), np.concatenate(self.C))),
                             shape=(self.m, self.n))

    def solve(self, integer=True, time_limit=12, gap=0.01):
        c = np.concatenate(self.c); lb = np.concatenate(self.lb); ub = np.concatenate(self.ub)
        A = self.matrix(); lo = np.concatenate(self.lo); hi = np.concatenate(self.hi)
        if integer:
            res = milp(c, integrality=np.concatenate(self.integ), bounds=Bounds(lb, ub),
                       constraints=LinearConstraint(A, lo, hi),
                       options=dict(time_limit=time_limit, mip_rel_gap=gap, disp=False))
            return res
        # LP with duals: split two-sided rows into <= rows for linprog
        eq = np.isclose(lo, hi)
        A_eq, b_eq = A[eq], lo[eq]
        up = ~eq & np.isfinite(hi); dn = ~eq & np.isfinite(lo)
        A_ub = sp.vstack([A[up], -A[dn]]).tocsr(); b_ub = np.concatenate([hi[up], -lo[dn]])
        res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                      bounds=np.column_stack([lb, ub]), method="highs")
        res.row_up = np.nonzero(up)[0]
        return res


# ------------------------------------------------------------------------------------
# Hourly block shared by sizing and dispatch
# ------------------------------------------------------------------------------------
def hourly_block(M: Model, ctx, sc: Scenario, hrs, w, cap, adders=None, soc_mode="daily",
                 soc0=0.0, soc_end=None, cycle_cap=None, allow_unmet=False):
    """Adds dispatch variables/constraints for hours `hrs` (weights w).
    cap[k] = column index of capacity var (sizing) or a float MW (dispatch)."""
    adders = adders or {}
    lam = sc.carbon_price + adders.get("carbon", 0.0)
    m_add = adders.get("merchant", 0.0)
    c_cred = adders.get("clean", 0.0)
    T = len(hrs)
    f = ctx["frame"]
    load = ctx["load"][hrs]
    glim = ctx["grid_limit"][hrs]
    price = ctx["grid_price"][hrs]
    gco2 = ctx["grid_co2"][hrs]
    rco2 = ctx["remote_co2"][hrs]
    gas = ctx["gas_price"][hrs]
    v, acc = {}, dict(cost=[], co2=[], clean=[], merch=[], r1=[], i2=[], ch=[], dis=[])

    def capterm(k):
        return cap[k] if not isinstance(cap[k], (int, float, np.floating)) else None

    def capval(k):
        return cap[k] if isinstance(cap[k], (int, float, np.floating)) else None

    imp_ub = np.where(glim > 1e-9, np.inf, 0.0)
    for k in RES:
        if k == BATT or k not in sc.allowed:
            continue
        prof = ctx["prof"][k][hrs]
        o = OPT.loc[k]
        if prof.max() <= 0:
            continue
        if o.kind == "dispatchable":
            mc = o.payment_usd_per_mwh + o.heat_rate_mmbtu_per_mwh_hhv * gas
            v[k] = M.var(T, w * (mc + lam * o.co2_t_per_mwh))
            acc["cost"].append((v[k], w * mc)); acc["co2"].append((v[k], w * o.co2_t_per_mwh))
        else:
            v[k] = M.var(T, -w * c_cred, 0.0, imp_ub)
            acc["clean"].append((v[k], w))
        if capterm(k) is not None:
            M.rows([(v[k], 1.0), (capterm(k), -prof)], -np.inf, 0.0, T)
        else:
            M.ub[-1] = np.minimum(M.ub[-1], capval(k) * prof)
    v["grid"] = M.var(T, w * (price + lam * gco2 + m_add), 0.0, imp_ub)
    acc["cost"].append((v["grid"], w * price)); acc["co2"].append((v["grid"], w * gco2))
    acc["merch"].append((v["grid"], w))
    r1u = ctx["relocation_limit"][hrs] if sc.allow_tier1 else 0.0
    i2u = 0.0 if sc.no_tier2 else ctx["interruption_limit"][hrs]
    rp, ip = ctx["relocation_price"], ctx["interruption_price"]
    v["r1"] = M.var(T, w * (rp + lam * REMOTE_MULT * rco2), 0.0, r1u)
    v["i2"] = M.var(T, w * ip, 0.0, i2u)
    acc["cost"] += [(v["r1"], w * rp), (v["i2"], w * ip)]
    acc["co2"].append((v["r1"], w * REMOTE_MULT * rco2))
    acc["r1"].append((v["r1"], w)); acc["i2"].append((v["i2"], w))
    if allow_unmet:
        v["unmet"] = M.var(T, w * UNMET_PEN)
    has_batt = BATT in sc.allowed and ctx["prof"][BATT + "_mask"][hrs].any() and \
        (capterm(BATT) is not None or (capval(BATT) or 0) > 0)
    if has_batt:
        bm = ctx["prof"][BATT + "_mask"][hrs].astype(float)
        v["ch"] = M.var(T, w * (0.02 + (1 - ETA * ETA) * c_cred))
        v["dis"] = M.var(T, w * 0.01)
        v["soc"] = M.var(T)
        acc["ch"].append((v["ch"], w)); acc["dis"].append((v["dis"], w))
        if capterm(BATT) is not None:
            B = capterm(BATT)
            M.rows([(v["ch"], 1.0), (B, -bm)], -np.inf, 0.0, T)
            M.rows([(v["dis"], 1.0), (B, -bm)], -np.inf, 0.0, T)
            M.rows([(v["soc"], 1.0), (B, -DUR * bm)], -np.inf, 0.0, T)
        else:
            Bv = capval(BATT)
            M.ub[-3] = np.minimum(M.ub[-3], Bv * bm)  # ch
            M.ub[-2] = np.minimum(M.ub[-2], Bv * bm)  # dis
            M.ub[-1] = np.minimum(M.ub[-1], Bv * DUR * bm)
        clean_terms = [(v[k], -1.0) for k in OFFSITE if k in v]
        M.rows([(v["ch"], 1.0)] + clean_terms, -np.inf, 0.0, T)
        if soc_mode == "daily":
            prev = np.roll(v["soc"].reshape(-1, 24), 1, axis=1).ravel()
            M.rows([(v["soc"], 1.0), (prev, -1.0), (v["ch"], -ETA), (v["dis"], 1 / ETA)], 0.0, 0.0, T)
            nd = T // 24
            day = np.repeat(np.arange(nd), 24)
            r0 = M.m
            M.R.append(r0 + day); M.C.append(v["dis"]); M.V.append(np.full(T, 1 / ETA))
            if capterm(BATT) is not None:
                M.R.append(r0 + np.arange(nd)); M.C.append(np.full(nd, capterm(BATT)))
                M.V.append(np.full(nd, -DUR))
                M.lo.append(np.full(nd, -np.inf)); M.hi.append(np.zeros(nd))
            else:
                M.lo.append(np.full(nd, -np.inf)); M.hi.append(np.full(nd, DUR * capval(BATT)))
            M.m += nd
        else:  # chronological chunk
            M.rows([(v["soc"][1:], 1.0), (v["soc"][:-1], -1.0), (v["ch"][1:], -ETA),
                    (v["dis"][1:], 1 / ETA)], 0.0, 0.0, T - 1)
            M.rows([(v["soc"][:1], 1.0), (v["ch"][:1], -ETA), (v["dis"][:1], 1 / ETA)], soc0, soc0, 1)
            if soc_end is not None:
                M.rows([(v["soc"][-1:], 1.0)], soc_end, soc_end, 1)
            if cycle_cap is not None:
                M.row_sum([(v["dis"], 1 / ETA)], -np.inf, cycle_cap)
    # balance: supply = load - r1 - i2 + ch
    terms = [(v[k], 1.0) for k in RES if k in v] + [(v["grid"], 1.0), (v["r1"], 1.0), (v["i2"], 1.0)]
    if has_batt:
        terms += [(v["dis"], 1.0), (v["ch"], -1.0)]
    if allow_unmet:
        terms.append((v["unmet"], 1.0))
    M.rows(terms, load, load, T)
    # protected: local served >= tier0 is implied by r1/i2 bounds (tier1+tier2 caps)
    imp = [(v[k], 1.0) for k in OFFSITE if k in v] + [(v["grid"], 1.0)]
    M.rows(imp, -np.inf, glim, T, tag=None)
    return v, acc, float((w * load).sum())


# ------------------------------------------------------------------------------------
# Sizing
# ------------------------------------------------------------------------------------
def size(sc: Scenario, extra_days=(), want_duals=False, fixed_caps=None):
    ctx = context(sc.initial_service_month, sc.grid_delay_months, sc.avail_shift, sc.region)
    days = sample_days(ctx, sc.initial_service_month, extra_days)
    hrs = np.concatenate([np.arange(h0, h0 + 24) for h0, _ in days])
    w = np.concatenate([np.full(24, wt) for _, wt in days])
    M = Model()
    cap, nblk = {}, {}
    for k in RES:
        o = OPT.loc[k]
        usable = k in sc.allowed and ctx["prof"][k + "_mask"].any()
        maxb = int(o.max_mw // o.block_mw) if usable else 0
        if fixed_caps is not None:
            nb = fixed_caps.get(k, 0) / o.block_mw
            nblk[k] = M.var(1, 0.0, nb, nb)
        else:
            nblk[k] = M.var(1, capacity_cost_per_mw(ctx, k) * o.block_mw, 0, maxb, integer=True)
        cap[k] = None
    # capacity MW expressions: we use block vars directly with coefficient block_mw
    # -> create MW vars tied by equality for readability of hourly constraints
    for k in RES:
        o = OPT.loc[k]
        cap[k] = M.var(1, 0.0, 0.0, o.max_mw)
        M.rows([(cap[k], 1.0), (nblk[k], -o.block_mw)], 0.0, 0.0, 1)
    M.row_sum([(cap[k], OPT.loc[k, "land_acres_per_mw"]) for k in ONSITE], -np.inf, LAND, tag="land")
    if sc.n_minus_1:
        # need_h = load - permitted flex - import limit; onsite firm MW minus the block of any
        # selected thermal resource must cover it (battery excluded: conservative)
        need = ctx["load"][hrs] - ctx["relocation_limit"][hrs] - ctx["interruption_limit"][hrs] \
            - ctx["grid_limit"][hrs]
        sel = need > 1e-6
        if sel.any():
            hh = hrs[sel]
            ndv = need[sel]
            ys = {}
            for k in THERMAL:
                o = OPT.loc[k]
                if k in sc.allowed and ctx["prof"][k + "_mask"].any():
                    y = M.var(1, 0.0, 0, 1, integer=True)
                    maxb = int(o.max_mw // o.block_mw)
                    M.rows([(nblk[k], 1.0), (y, -maxb)], -np.inf, 0.0, 1)   # selected -> y = 1
                    ys[k] = y
            for k, y in ys.items():
                terms = [(cap[j], ctx["prof"][j][hh]) for j in THERMAL if j in ys]
                terms.append((y, -float(OPT.loc[k, "block_mw"]) * ctx["prof"][k + "_mask"][hh]))
                M.rows(terms, ndv, np.inf, len(hh))
    v, acc, Dw = hourly_block(M, ctx, sc, hrs, w, cap, soc_mode="daily", allow_unmet=False)
    # ---- hard requirements -------------------------------------------------------
    served_terms = lambda coef: [(i, -coef * c) for i, c in acc["r1"] + acc["i2"]]
    if sc.max_intensity_kg is not None:
        # combined CO2 <= cap * (local served + remote) = cap*(D - r1 - i2 + 1.05 r1)
        k_ = sc.max_intensity_kg / 1000
        terms = list(acc["co2"]) + [(i, k_ * c) for i, c in acc["i2"]] + \
                [(i, -k_ * (REMOTE_MULT - 1) * c) for i, c in acc["r1"]]
        M.row_sum(terms, -np.inf, k_ * Dw, tag="intensity")
    if sc.max_merchant_share is not None:
        x = sc.max_merchant_share
        M.row_sum(list(acc["merch"]) + [(i, x * c) for i, c in acc["r1"] + acc["i2"]], -np.inf, x * Dw,
                  tag="merchant")
    if sc.min_clean_share is not None:
        y = sc.min_clean_share
        terms = [(i, -c) for i, c in acc["clean"]] + [(i, c) for i, c in acc["ch"]] + \
                [(i, -c) for i, c in acc["dis"]] + [(i, -y * c) for i, c in acc["r1"] + acc["i2"]]
        M.row_sum(terms, -np.inf, -y * Dw, tag="clean")
    if sc.budget_musd is not None:
        terms = list(acc["cost"]) + [(nblk[k], capacity_cost_per_mw(ctx, k) * OPT.loc[k, "block_mw"])
                                     for k in RES]
        M.row_sum(terms, -np.inf, sc.budget_musd * 1e6, tag="budget")
    lp_bound = None
    if want_duals:
        res = M.solve(integer=False)
    else:
        # 1) LP relaxation (fast); 2) MILP restricted to floor/ceil of each block count
        #    around the relaxation (at most 2^7 block combinations); 3) full MILP fallback
        lp = M.solve(integer=False)
        if lp.status != 0:
            return None, lp, M
        lbs, ubs = M.lb, M.ub
        saved = [(lbs[i].copy(), ubs[i].copy()) for i in range(len(lbs))]
        flat_lb = np.concatenate(M.lb); flat_ub = np.concatenate(M.ub)
        for k in RES:
            j = int(nblk[k][0])
            val = max(lp.x[j], 0.0)
            flat_lb[j] = max(flat_lb[j], math.floor(val + 1e-6))
            flat_ub[j] = min(flat_ub[j], math.ceil(val - 1e-6))
        M.lb, M.ub = [flat_lb], [flat_ub]
        res = M.solve(integer=True, gap=0.0005)
        if res.x is None:
            M.lb, M.ub = [a for a, _ in saved], [b for _, b in saved]
            res = M.solve(integer=True, time_limit=30)
        lp_bound = float(lp.fun)
    if res.x is None or (hasattr(res, "status") and res.status not in (0, 1) and res.x is None):
        return None, res, M
    caps = {k: float(round(res.x[cap[k]][0] / OPT.loc[k, "block_mw"]) * OPT.loc[k, "block_mw"])
            for k in RES}
    duals = {}
    if want_duals and res.status == 0:
        marg = res.ineqlin.marginals
        pos = {r: j for j, r in enumerate(res.row_up)}
        for tag, (r0, n) in M.tags.items():
            if r0 in pos:
                duals[tag] = float(marg[pos[r0]])
    return dict(caps=caps, obj=float(res.fun), lp_bound=lp_bound, duals=duals, n_hours=len(hrs)), res, M


# ------------------------------------------------------------------------------------
# Chronological dispatch
# ------------------------------------------------------------------------------------
def dispatch(sc: Scenario, caps: dict, adders=None):
    ctx = context(sc.initial_service_month, sc.grid_delay_months, sc.avail_shift, sc.region)
    cols = ["grid_mw", "tier1_relocated_mw", "tier2_curtailed_mw"] + \
           [k + "_mw" for k in RES if k != BATT] + [BATT + "_charge_mw", BATT + "_discharge_mw", BATT + "_soc_mwh"]
    out = {c: np.zeros(H) for c in cols}
    unmet = np.zeros(H)
    soc = 0.0
    year_used = {}
    start = sc.initial_service_month
    bmw = caps.get(BATT, 0.0)
    for m in range(start, CASE["horizon_months"]):
        hrs = np.arange(m * HPM, (m + 1) * HPM)
        yr = (m * HPM) // 8760
        cap_cyc = None
        if bmw > 0:
            mask = ctx["prof"][BATT + "_mask"]
            allowed_year = bmw * DUR * OPT.loc[BATT, "max_cycles_per_year"] * \
                float(mask[ctx["year"] == yr].sum()) / 8760
            # spread evenly over the months of the year that are available
            months_left = sum(1 for mm in range(m, min((yr + 1) * 12, CASE["horizon_months"])))
            cap_cyc = max(allowed_year - year_used.get(yr, 0.0), 0.0) / max(months_left, 1)
            cap_cyc = min(cap_cyc * 1.0, allowed_year)
        last = m == CASE["horizon_months"] - 1
        M = Model()
        v, acc, _ = hourly_block(M, ctx, sc, hrs, np.ones(HPM), caps, adders=adders, soc_mode="chrono",
                                 soc0=soc, soc_end=0.0 if last else None, cycle_cap=cap_cyc,
                                 allow_unmet=True)
        res = M.solve(integer=False)
        if res.status != 0:
            raise RuntimeError(f"dispatch failed month {m}: {res.message}")
        x = res.x
        out["grid_mw"][hrs] = x[v["grid"]]
        out["tier1_relocated_mw"][hrs] = x[v["r1"]]
        out["tier2_curtailed_mw"][hrs] = x[v["i2"]]
        for k in RES:
            if k != BATT and k in v:
                out[k + "_mw"][hrs] = x[v[k]]
        if "ch" in v:
            ch, di = x[v["ch"]], x[v["dis"]]
            out[BATT + "_charge_mw"][hrs] = ch
            out[BATT + "_discharge_mw"][hrs] = di
            soc = float(x[v["soc"]][-1])
            year_used[yr] = year_used.get(yr, 0.0) + di.sum() / ETA
        unmet[hrs] = x[v["unmet"]]
    df = pd.DataFrame({"model_hour": np.arange(H), **out})
    _clean_battery(df)
    _snap(df, ctx, caps)
    return df, unmet


def _clean_battery(df):
    """Remove simultaneous charge/discharge (keeps SOC path; surplus supply is taken out of
    clean contract dispatch, which by construction exceeded the charge)."""
    ch = df[BATT + "_charge_mw"].to_numpy().copy()
    di = df[BATT + "_discharge_mw"].to_numpy().copy()
    both = (ch > 1e-9) & (di > 1e-9)
    if not both.any():
        return
    net = ETA * ch - di / ETA
    new_ch = np.where(both & (net >= 0), net / ETA, ch)
    new_di = np.where(both & (net < 0), -net * ETA, di)
    new_ch = np.where(both & (net < 0), 0.0, new_ch)
    new_di = np.where(both & (net >= 0), 0.0, new_di)
    surplus = (new_di - new_ch) - (di - ch)  # extra supply created, >= 0
    for k in ["utility_solar_mw", "wind_mw", "nuclear_mw"]:
        take = np.minimum(df[k].to_numpy(), surplus)
        df[k] = df[k].to_numpy() - take
        surplus = surplus - take
    df[BATT + "_charge_mw"] = new_ch
    df[BATT + "_discharge_mw"] = new_di


def _snap(df, ctx, caps):
    """Clip solver noise to the checker's exact bounds and rebuild SOC exactly."""
    for c in df.columns:
        if c != "model_hour":
            df[c] = df[c].clip(lower=0.0)
    df["tier1_relocated_mw"] = np.minimum(df.tier1_relocated_mw, ctx["relocation_limit"])
    df["tier2_curtailed_mw"] = np.minimum(df.tier2_curtailed_mw, ctx["interruption_limit"])
    for k in RES:
        if k != BATT:
            df[k + "_mw"] = np.minimum(df[k + "_mw"], caps.get(k, 0.0) * ctx["prof"][k])
    ch = df[BATT + "_charge_mw"].to_numpy(); di = df[BATT + "_discharge_mw"].to_numpy()
    soc = np.cumsum(ETA * ch - di / ETA)
    soc[np.abs(soc) < 1e-7] = 0.0
    df[BATT + "_soc_mwh"] = np.clip(soc, 0, None)
    # re-balance any residual with grid where import headroom allows (tiny solver noise)
    supply = df.grid_mw + df[BATT + "_discharge_mw"] - df[BATT + "_charge_mw"] + \
        sum(df[k + "_mw"] for k in RES if k != BATT)
    need = ctx["load"] - df.tier1_relocated_mw - df.tier2_curtailed_mw
    gap = (need - supply).to_numpy()
    df["grid_mw"] = np.clip(df.grid_mw.to_numpy() + gap, 0, None)


# ------------------------------------------------------------------------------------
# Full run
# ------------------------------------------------------------------------------------
@dataclass
class Result:
    scenario: Scenario
    status: str                 # ok | infeasible | check
    caps: dict = field(default_factory=dict)
    dispatch: pd.DataFrame | None = None
    metrics: dict = field(default_factory=dict)
    message: str = ""
    duals: dict = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def feasible(self):
        return self.status == "ok"

    def portfolio(self):
        return {"initial_service_month": int(self.scenario.initial_service_month),
                "grid_delay_months": int(self.scenario.grid_delay_months),
                "capacities_mw": {k: float(self.caps.get(k, 0.0)) for k in RES}}


def regional_score(sc: Scenario, caps: dict, d: pd.DataFrame):
    """Mirror of the packet checker's accounting, applied to regionally scaled inputs.
    Used only for location screening; the benchmark always uses cs.score()."""
    ctx = context(sc.initial_service_month, sc.grid_delay_months, sc.avail_shift, sc.region)
    n = H
    cost = np.zeros(n); co2 = np.zeros(n); clean = np.zeros(n); ledger = []
    for k in RES:
        o = OPT.loc[k]; mw = caps.get(k, 0.0); mask = ctx["prof"][k + "_mask"]
        fixed = mask * fixed_annual_per_mw(k) * mw / 8760
        gen = np.zeros(n) if o.kind == "storage" else d[k + "_mw"].to_numpy(float)
        billed = mw * ctx["prof"][k] if o.payment_basis == "available_generation" else gen
        pay = billed * o.payment_usd_per_mwh
        fuel = gen * ctx["gas_price"] * o.heat_rate_mmbtu_per_mwh_hhv
        cost += fixed + pay + fuel; co2 += gen * o.co2_t_per_mwh
        if o.clean_credit and o.kind != "storage":
            clean += gen
        if o.kind == "storage":
            clean += d[k + "_discharge_mw"].to_numpy() - d[k + "_charge_mw"].to_numpy()
        ledger.append(dict(option_id=k, selected_mw=float(mw),
                           commitment_start_month=int(max(sc.initial_service_month, avail_month(k, sc.avail_shift))),
                           capacity_charges_usd=float(fixed.sum()), energy_payment_or_variable_om_usd=float(pay.sum()),
                           fuel_cost_usd=float(fuel.sum()), total_cost_usd=float((fixed + pay + fuel).sum())))
    grid = d.grid_mw.to_numpy(float); cost += grid * ctx["grid_price"]; co2 += grid * ctx["grid_co2"]
    reloc = d.tier1_relocated_mw.to_numpy(float); intr = d.tier2_curtailed_mw.to_numpy(float)
    remote = reloc * REMOTE_MULT; local = ctx["load"] - reloc - intr
    rcost = reloc * ctx["relocation_price"]; icost = intr * ctx["interruption_price"]; rco2 = remote * ctx["remote_co2"]
    imports = grid + sum(d[k + "_mw"].to_numpy() for k in OFFSITE)

    def agg(m):
        req = float(ctx["load"][m].sum()); srv = float(local[m].sum()); rem = float(remote[m].sum())
        lc = float(cost[m].sum()); rr = float(rcost[m].sum()); ii = float(icost[m].sum())
        ce = float(co2[m].sum()); re_ = float(rco2[m].sum()); cm = float(clean[m].sum())
        dv = lambda a, b: a / b if b > 0 else None
        return dict(requested_mwh=req, local_served_mwh=srv, relocated_local_equivalent_mwh=float(reloc[m].sum()),
                    remote_electricity_mwh=rem, interrupted_mwh=float(intr[m].sum()),
                    local_energy_cost_usd=lc, relocation_cost_usd=rr, interruption_consequence_usd=ii,
                    total_decision_cost_usd=lc + rr + ii, local_energy_cost_usd_per_mwh=dv(lc, srv),
                    decision_cost_usd_per_requested_mwh=dv(lc + rr + ii, req),
                    local_operational_co2_t=ce, remote_operational_co2_t=re_, combined_operational_co2_t=ce + re_,
                    combined_electricity_co2_kg_per_mwh=dv(1000 * (ce + re_), srv + rem),
                    clean_energy_mwh=cm, clean_energy_share=dv(cm, srv), merchant_mwh=float(grid[m].sum()))
    yr = np.arange(n) // 8760
    out = dict(physical_checks_passed=bool((imports - ctx["grid_limit"]).max() < 1e-4),
               accounting="regional screening (checker formulas on scaled inputs)",
               initial_service_month=int(sc.initial_service_month),
               full_demand_month=int(sc.initial_service_month + CASE["ramp_duration_months"]),
               grid_delay_months=int(sc.grid_delay_months), max_grid_import_mw=float(imports.max()),
               **agg(np.ones(n, bool)), capacity_cost_ledger=ledger,
               annual_results=[dict(model_year=y + 1, **agg(yr == y)) for y in range(CASE["horizon_months"] // 12)])
    return out


def evaluate(sc: Scenario, caps: dict, df: pd.DataFrame):
    if sc.region:
        return regional_score(sc, caps, df)
    port = {"initial_service_month": int(sc.initial_service_month),
            "grid_delay_months": int(sc.grid_delay_months),
            "capacities_mw": {k: float(caps.get(k, 0.0)) for k in RES}}
    return cs.score(port, df)


def _req_failures(sc, m):
    f = []
    if sc.max_intensity_kg is not None and m["combined_electricity_co2_kg_per_mwh"] > sc.max_intensity_kg + 1e-6:
        f.append(f"intensity {m['combined_electricity_co2_kg_per_mwh']:.1f} > {sc.max_intensity_kg:.0f} kg/MWh")
    if sc.min_clean_share is not None and m["clean_energy_share"] < sc.min_clean_share - 1e-6:
        f.append(f"clean share {m['clean_energy_share']:.1%} < {sc.min_clean_share:.0%}")
    if sc.max_merchant_share is not None and m["merchant_mwh"] / m["local_served_mwh"] > sc.max_merchant_share + 1e-6:
        f.append("merchant share above cap")
    if sc.budget_musd is not None and m["total_decision_cost_usd"] > sc.budget_musd * 1e6:
        f.append("total decision cost above budget")
    if sc.no_tier2 and m["interrupted_mwh"] > 1e-3:
        f.append("Tier 2 interrupted")
    return f


VERBOSE = bool(__import__("os").environ.get("GRIDPILOT_VERBOSE"))


def _log(*a):
    if VERBOSE:
        print("  [engine]", *a, flush=True)


def run(sc: Scenario, _depth=0) -> Result:
    import time
    t0 = time.time()
    extra = []
    sized = None
    for it in range(3):
        sized, res, _ = size(sc, extra_days=extra)
        _log(f"size it={it} depth={_depth} {time.time()-t0:.1f}s", sized and sized["caps"])
        if sized is None:
            return Result(sc, "infeasible", message="No combination of catalog resources meets the "
                          "hourly demand and your must-haves at this opening month (MILP infeasible "
                          "on the representative days).", seconds=time.time() - t0)
        adders = {}
        hard = any(x is not None for x in (sc.max_intensity_kg, sc.min_clean_share, sc.max_merchant_share))
        if hard:
            d, rr, _ = size(sc, extra_days=extra, want_duals=True, fixed_caps=sized["caps"])
            if d is not None:
                du = d["duals"]
                adders = {"carbon": -du.get("intensity", 0.0), "merchant": -du.get("merchant", 0.0),
                          "clean": -du.get("clean", 0.0)}
                sized["duals"] = du
        _log(f"duals {time.time()-t0:.1f}s", adders)
        df, unmet = dispatch(sc, sized["caps"], adders)
        _log(f"dispatch {time.time()-t0:.1f}s unmet={unmet.sum():.2f}")
        if unmet.sum() < 1e-4:
            break
        bad_days = pd.Series(unmet).groupby(np.arange(H) // 24).sum()
        extra += [int(d) for d in bad_days[bad_days > 1e-6].sort_values(ascending=False).index[:8]]
    if unmet.sum() > 1e-4:
        return Result(sc, "infeasible", sized["caps"], message=f"{unmet.sum():,.0f} MWh could not be "
                      "served in the full chronological check.", seconds=time.time() - t0)
    try:
        m = evaluate(sc, sized["caps"], df)
    except ValueError as e:
        return Result(sc, "infeasible", sized["caps"], df, message=f"Checker rejected: {e}",
                      seconds=time.time() - t0)
    fails = _req_failures(sc, m)
    # first try: same capacities, stronger shadow prices in dispatch (cheap, ~4 s each)
    tries = 0
    while fails and tries < 3 and not any("budget" in f or "Tier 2" in f for f in fails):
        tries += 1
        if sc.max_intensity_kg is not None:
            adders["carbon"] = max(adders.get("carbon", 0.0) * 2, 40.0 * tries)
        if sc.min_clean_share is not None:
            adders["clean"] = max(adders.get("clean", 0.0) * 2, 10.0 * tries)
        if sc.max_merchant_share is not None:
            adders["merchant"] = max(adders.get("merchant", 0.0) * 2, 10.0 * tries)
        df2, un2 = dispatch(sc, sized["caps"], adders)
        if un2.sum() > 1e-4:
            break
        try:
            m2 = evaluate(sc, sized["caps"], df2)
        except ValueError:
            break
        _log(f"re-dispatch {tries} {time.time()-t0:.1f}s adders={adders}")
        df, m, fails = df2, m2, _req_failures(sc, m2)
    if fails and _depth < 2:
        # representative days understated a portfolio-level metric: tighten and re-solve
        tw = {}
        if sc.max_intensity_kg is not None and m["combined_electricity_co2_kg_per_mwh"] > sc.max_intensity_kg:
            tw["max_intensity_kg"] = 0.98 * sc.max_intensity_kg ** 2 / m["combined_electricity_co2_kg_per_mwh"]
        if sc.min_clean_share is not None and m["clean_energy_share"] < sc.min_clean_share:
            tw["min_clean_share"] = min(0.995, sc.min_clean_share + 1.2 * (sc.min_clean_share - m["clean_energy_share"]))
        if sc.max_merchant_share is not None:
            ms = m["merchant_mwh"] / m["local_served_mwh"]
            if ms > sc.max_merchant_share:
                tw["max_merchant_share"] = max(0, sc.max_merchant_share - 1.2 * (ms - sc.max_merchant_share))
        if tw:
            r2 = run(Scenario(**{**asdict(sc), **tw}), _depth + 1)
            r2.scenario = sc
            if r2.metrics:
                f2 = _req_failures(sc, r2.metrics)
                r2.status = "ok" if not f2 else "check"
                r2.message = "; ".join(f2)
            r2.seconds = time.time() - t0
            return r2
    return Result(sc, "ok" if not fails else "check", sized["caps"], df, m, "; ".join(fails),
                  sized.get("duals", {}), time.time() - t0)
