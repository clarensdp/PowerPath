"""
Decision layer: customer inputs -> candidate portfolios -> recommendation + explanation.

Must-haves (hard) are constraints; a portfolio that breaks one is never recommended.
  * full-demand / opening deadline     -> limits the opening months searched
  * emissions cap, clean share, merchant share, budget, zero Tier 2 -> MILP constraints,
    re-checked on the full chronological dispatch with the packet checker
  * premium cap                        -> filter vs. cheapest portfolio opening at month 20
Nice-to-haves (soft) become two dollar exchange rates the customer can read and override:
  * value of opening one month earlier ($/month)
  * internal carbon price ($/t CO2)
Both are customer valuations, reported separately from common benchmark cost.
Opening months are compared per requested MWh, so a later opening never looks cheaper just
because the campus runs fewer months within the fixed 120-month horizon.
"""
from __future__ import annotations

import hashlib
import os
import pickle
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, asdict, field, replace
from pathlib import Path

import numpy as np

from .engine import Scenario, run, Result, RES, LABELS, OPT, CASE, cs

STRESS_HOURS = int(cs.hourly.stress_active.sum())

ANCHOR_VALUE_PER_MONTH = 5_000_000   # $/month at equal weight (see README for the basis)
ANCHOR_CARBON_PRICE = 100.0          # $/t at equal weight
MAX_VALUE_PER_MONTH = 20_000_000     # slider cap ($/month)
MAX_CARBON_PRICE = 500.0             # slider cap ($/t)
CACHE_DIR = Path(os.environ.get("GRIDPILOT_CACHE", Path(__file__).resolve().parents[1] / ".cache"))
RAMP = CASE["ramp_duration_months"]


# ------------------------------------------------------------------------------------
@dataclass
class Preferences:
    speed: float = 34.0
    cost: float = 33.0
    env: float = 33.0
    override_value: float | None = None
    override_carbon: float | None = None

    def implied(self):
        # cost sits in the denominator; floor it and cap the outputs so extreme slider
        # positions cannot produce absurd valuations (overrides are taken as typed)
        c = max(self.cost, 10.0)
        v = min(ANCHOR_VALUE_PER_MONTH * self.speed / c, MAX_VALUE_PER_MONTH)
        lam = min(ANCHOR_CARBON_PRICE * self.env / c, MAX_CARBON_PRICE)
        if self.override_value is not None:
            v = self.override_value
        if self.override_carbon is not None:
            lam = self.override_carbon
        # round the carbon price so nearby slider settings share cached portfolios
        return float(v), float(round(lam / 10) * 10)


@dataclass
class Requirements:
    full_demand_by: int | None = None
    open_by: int | None = None
    max_intensity_kg: float | None = None
    min_clean_share: float | None = None
    max_merchant_share: float | None = None
    budget_musd: float | None = None
    no_tier2: bool = False
    allow_tier1: bool = True
    excluded: tuple = ()
    max_premium_pct: float | None = None
    premium_ref_open: int = 20
    n_minus_1: bool = False


@dataclass
class Options:
    earliest_open: int = 14
    latest_open: int = 26
    step: int = 2
    grid_delay: int = 0
    slips: tuple = ()          # ((resource, months_late), ...) execution sensitivity
    workers: int = 0
    execution_aware: bool = False   # resources usable no earlier than today + permit/procure/build
    today: int = 0                  # development month "now" for execution-aware mode
    lead_overrides: tuple = ()      # ((resource, permit, procure, build), ...)
    refine: bool = True             # also test the months either side of the winner
    region: str = ""                # '' = benchmark site; else a screener location key (US-VA, C-IE)


# ------------------------------------------------------------------------------------
# cached runs
# ------------------------------------------------------------------------------------
_ENGINE_SRC = (Path(__file__).resolve().parent / "engine.py").read_bytes()
CODE_VERSION = hashlib.sha1(_ENGINE_SRC).hexdigest()[:8]   # cached results expire when the engine changes


def _ckey(sc: Scenario):
    return hashlib.sha1((CODE_VERSION + repr(sc.key())).encode()).hexdigest()[:16]


def cached_run(sc: Scenario) -> Result:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = CACHE_DIR / f"{_ckey(sc)}.pkl"
    if f.exists():
        try:
            r = pickle.loads(f.read_bytes())
            r.scenario = sc
            return r
        except Exception:
            pass
    r = run(sc)
    try:
        if r.dispatch is not None:
            r.dispatch = r.dispatch.astype({c: "float64" for c in r.dispatch.columns if c != "model_hour"})
        f.write_bytes(pickle.dumps(r))
    except Exception:
        pass
    return r


def run_many(scs, workers=0):
    todo = [s for s in scs if not (CACHE_DIR / f"{_ckey(s)}.pkl").exists()]
    if workers and workers > 1 and len(todo) > 1:
        try:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                list(ex.map(cached_run, todo))
        except Exception:
            pass
    return [cached_run(s) for s in scs]


# ------------------------------------------------------------------------------------
def execution_shifts(opt: Options) -> dict:
    """Months each resource is pushed back when execution-aware: a resource cannot run before
    today + its permit/procurement/build lead time (planning assumptions, editable)."""
    from .execution import DEFAULT_STEPS
    from .engine import avail_month
    ov = {r[0]: dict(permit=r[1], procure=r[2], build=r[3]) for r in opt.lead_overrides}
    out = {}
    for k in RES:
        st_ = {**DEFAULT_STEPS[k], **ov.get(k, {})}
        if OPT.loc[k, "location"] == "onsite":
            earliest = opt.today + st_["build"] + max(st_["permit"], st_["procure"])
        else:
            earliest = opt.today + st_["procure"]
        out[k] = max(0, earliest - avail_month(k))
    return out


def scenario_shifts(opt: Options) -> tuple:
    sh = {k: int(v) for k, v in opt.slips if v}
    if opt.execution_aware:
        for k, v in execution_shifts(opt).items():
            sh[k] = max(sh.get(k, 0), v)
    return tuple(sorted((k, v) for k, v in sh.items() if v))


def region_delay(opt: Options) -> int:
    if not opt.region:
        return 0
    from .regions import region_params
    rp = region_params(opt.region)
    return int(rp["delay"]) if rp else 0


def make_scenario(s, req: Requirements, opt: Options, lam: float) -> Scenario:
    return Scenario(initial_service_month=int(s), grid_delay_months=opt.grid_delay + region_delay(opt),
                    region=opt.region,
                    carbon_price=lam, allowed=tuple(k for k in RES if k not in req.excluded),
                    max_intensity_kg=req.max_intensity_kg, min_clean_share=req.min_clean_share,
                    max_merchant_share=req.max_merchant_share, budget_musd=req.budget_musd,
                    no_tier2=req.no_tier2, allow_tier1=req.allow_tier1,
                    n_minus_1=req.n_minus_1, avail_shift=scenario_shifts(opt))


def latest_allowed_open(req: Requirements):
    lim = [x for x in [req.open_by, (req.full_demand_by - RAMP) if req.full_demand_by else None]
           if x is not None]
    return min(lim) if lim else None


def candidate_opens(req: Requirements, opt: Options):
    hi = opt.latest_open
    la = latest_allowed_open(req)
    if la is not None:
        hi = min(hi, la)
    lo = max(14, opt.earliest_open)
    if hi < lo:
        return []  # contradictory bounds: never silently relax a hard requirement
    months = list(range(lo, hi + 1, max(1, opt.step)))
    if hi >= 14 and hi not in months:
        months.append(hi)
    return sorted(set(months))


def ok_for(r: Result, req: Requirements):
    return r.status == "ok" and (latest_allowed_open(req) is None or
                                 r.scenario.initial_service_month <= latest_allowed_open(req))


def ref_mwh():
    return float(CASE["full_load_year_mwh"]) * 90 / 12   # 90 mature months: fixed comparison basis


def score(r: Result, v, lam, t_ref):
    m = r.metrics
    R = ref_mwh()
    common = R * m["decision_cost_usd_per_requested_mwh"]
    carbon = R * lam * m["combined_electricity_co2_kg_per_mwh"] / 1000
    delay = v * (r.scenario.initial_service_month - t_ref)
    return dict(common=common, carbon=carbon, delay=delay, total=common + carbon + delay)


@dataclass
class Recommendation:
    best: Result | None
    candidates: list
    scores: dict
    value_per_month: float
    carbon_price: float
    t_ref: int
    explanation: list = field(default_factory=list)
    alternatives: list = field(default_factory=list)
    relaxations: list = field(default_factory=list)
    premium_ref: float | None = None
    tested: list = field(default_factory=list)
    shifts: tuple = ()


def recommend(prefs: Preferences, req: Requirements, opt: Options) -> Recommendation:
    v, lam = prefs.implied()
    opens = candidate_opens(req, opt)
    results = run_many([make_scenario(s, req, opt, lam) for s in opens], opt.workers) if opens else []
    ok = [r for r in results if ok_for(r, req)]
    premium_ref = None
    if req.max_premium_pct is not None:
        cheap = cached_run(make_scenario(req.premium_ref_open, replace(req, max_intensity_kg=None,
                           min_clean_share=None, max_merchant_share=None, budget_musd=None), opt, 0.0))
        if cheap.status == "ok":
            premium_ref = cheap.metrics["decision_cost_usd_per_requested_mwh"]
            ok = [r for r in ok if r.metrics["decision_cost_usd_per_requested_mwh"]
                  <= premium_ref * (1 + req.max_premium_pct / 100) + 1e-9]
    t_ref = min(opens) if opens else 14
    scores = {r.scenario.initial_service_month: score(r, v, lam, t_ref) for r in ok}
    best = min(ok, key=lambda r: scores[r.scenario.initial_service_month]["total"]) if ok else None
    # refinement: the grid is coarse (step > 1), so also test the months either side of the winner
    if best is not None and opt.refine and opt.step > 1:
        la = latest_allowed_open(req)
        hi = min(opt.latest_open, la) if la is not None else opt.latest_open
        s0 = best.scenario.initial_service_month
        extra = [m for m in (s0 - 1, s0 + 1) if max(14, opt.earliest_open) <= m <= hi and m not in opens]
        if extra:
            more = run_many([make_scenario(m, req, opt, lam) for m in extra], opt.workers)
            more_ok = [r for r in more if ok_for(r, req)]
            if premium_ref:
                more_ok = [r for r in more_ok if r.metrics["decision_cost_usd_per_requested_mwh"]
                           <= premium_ref * (1 + req.max_premium_pct / 100) + 1e-9]
            results = sorted(results + more, key=lambda r: r.scenario.initial_service_month)
            ok = ok + more_ok
            opens = sorted(opens + extra)
            scores.update({r.scenario.initial_service_month: score(r, v, lam, t_ref) for r in more_ok})
            best = min(ok, key=lambda r: scores[r.scenario.initial_service_month]["total"])
    rec = Recommendation(best, results, scores, v, lam, t_ref, premium_ref=premium_ref, tested=opens)
    rec.shifts = scenario_shifts(opt)
    if best is None:
        rec.relaxations = suggest_relaxations(prefs, req, opt, results)
    else:
        rec.explanation = explain(best, req, v, lam, results)
        rec.alternatives = build_alternatives(best, ok, req, opt, v, lam)
    return rec


# ------------------------------------------------------------------------------------
def money(x, d=1):
    return f"${x / 1e6:,.{d}f}M"


def explain(r: Result, req, v, lam, results):
    m, caps, s = r.metrics, r.caps, r.scenario.initial_service_month
    out = []
    grid_from = 18 + r.scenario.grid_delay_months
    onsite = {k: c for k, c in caps.items() if c > 0 and OPT.loc[k, "location"] == "onsite"
              and OPT.loc[k, "available_month"] <= s}
    if s < grid_from:
        mix = ", ".join(f"{c:.0f} MW {LABELS[k].lower()}" for k, c in onsite.items()) or "onsite units"
        out.append(f"**Opening at month {s} is before the grid arrives (month {grid_from})**, so "
                   f"{mix} must carry the first 25 MW alone. That is what buys the early date.")
    earlier = [x for x in results if x.scenario.initial_service_month < s and x.status != "ok"]
    if earlier:
        e = max(earlier, key=lambda x: x.scenario.initial_service_month)
        out.append(f"**Opening at month {e.scenario.initial_service_month} was tested and fails**: "
                   f"{e.message.split('(')[0].strip() or 'a must-have is broken'}.")
    for k, c in caps.items():
        if c <= 0:
            continue
        o = OPT.loc[k]
        if k == "gas_turbine":
            out.append(f"**{c:.0f} MW gas turbine** (from month {o.available_month}): cheapest firm "
                       f"onsite MW; covers stress windows when imports drop to 60% of the connection.")
        elif k == "gas_engine":
            out.append(f"**{c:.0f} MW gas engines** (from month {o.available_month}, 5 MW blocks): "
                       f"more efficient than the turbine and available earlier.")
        elif k == "fuel_cell":
            out.append(f"**{c:.0f} MW fuel cells** (from month 14): the only gas unit available at "
                       f"month 14 and the lowest-emitting, but ${o.capex_usd_per_kw:,.0f}/kW.")
        elif k == "battery_4h":
            out.append(f"**{c:.0f} MW / {c * 4:.0f} MWh battery**: charged only from clean contract "
                       f"energy; shifts it into stress windows and price spikes.")
        elif k == "utility_solar":
            out.append(f"**{c:.0f} MW solar contract** at ${o.payment_usd_per_mwh:.0f}/MWh on all "
                       f"available energy from month {max(s, o.available_month)}.")
        elif k == "wind":
            out.append(f"**{c:.0f} MW wind contract** at ${o.payment_usd_per_mwh:.0f}/MWh, the cheapest "
                       f"clean energy; oversized beyond load because night wind fills hours solar cannot.")
        elif k == "nuclear":
            out.append(f"**{c:.0f} MW nuclear PPA** from month 60: clean firm supply at "
                       f"${o.payment_usd_per_mwh:.0f}/MWh, take-or-pay.")
    out.append(f"**Grid stress**: imports fall to 60% of the connection in {STRESS_HOURS} hours "
               f"a year. Over the horizon {m['relocated_local_equivalent_mwh']:,.0f} MWh of Tier 1 "
               f"is relocated and {m['interrupted_mwh']:,.0f} MWh of Tier 2 interrupted; Tier 0 is "
               f"always served on site.")
    if "intensity" in r.duals and abs(r.duals["intensity"]) > 1e-6:
        out.append(f"**Your emissions cap is binding**: the optimizer is paying an implied "
                   f"${abs(r.duals['intensity']):,.0f}/t to stay under it.")
    if lam > 0:
        out.append(f"**Your clean weight** adds an internal carbon price of ${lam:,.0f}/t when "
                   f"choosing resources. This is a valuation, not a cash cost.")
    if v > 0:
        out.append(f"**Your speed weight** values each month of earlier opening at {money(v)}.")
    return out


def _cmp(a: Result, b: Result):
    ma, mb = a.metrics, b.metrics
    gains, gives = [], []
    dc = mb["decision_cost_usd_per_requested_mwh"] - ma["decision_cost_usd_per_requested_mwh"]
    di = mb["combined_electricity_co2_kg_per_mwh"] - ma["combined_electricity_co2_kg_per_mwh"]
    dt = b.scenario.initial_service_month - a.scenario.initial_service_month
    (gains if dc < 0 else gives).append(f"{abs(dc):.2f} $/MWh {'cheaper' if dc < 0 else 'dearer'}")
    (gains if di < 0 else gives).append(f"{abs(di):.0f} kg/MWh {'cleaner' if di < 0 else 'dirtier'}")
    if dt:
        (gains if dt < 0 else gives).append(f"opens {abs(dt)} months {'earlier' if dt < 0 else 'later'}")
    d2 = mb["interrupted_mwh"] - ma["interrupted_mwh"]
    if abs(d2) > 1:
        (gains if d2 < 0 else gives).append(f"{abs(d2):,.0f} MWh {'less' if d2 < 0 else 'more'} Tier 2 interruption")
    return gains, gives


def _alt(best, r, name, tagline, when):
    g, gv = _cmp(best, r)
    return dict(name=name, tagline=tagline, result=r, gains=g, gives=gv, when=when,
                same=(r.caps == best.caps and r.scenario.initial_service_month == best.scenario.initial_service_month))


def build_alternatives(best, ok, req, opt, v, lam):
    """Three named, checker-validated alternatives: Fast Track, Lower Cost, Cleaner."""
    alts = []
    s0 = best.scenario.initial_service_month
    mb = best.metrics
    R = ref_mwh()
    # Fast Track: earliest opening that meets every must-have
    fast = min(ok, key=lambda r: (r.scenario.initial_service_month,
                                  r.metrics["decision_cost_usd_per_requested_mwh"]))
    if fast.scenario.initial_service_month < s0:
        dm = s0 - fast.scenario.initial_service_month
        dcost = R * (fast.metrics["decision_cost_usd_per_requested_mwh"] - mb["decision_cost_usd_per_requested_mwh"])
        when = (f"Wins if a month of earlier opening is worth more than {money(dcost / dm)}"
                if dcost > 0 else "Earlier and no dearer: wins outright on cost and speed")
    else:
        when = "The recommendation is already the earliest opening that meets your must-haves"
    alts.append(_alt(best, fast, "Fast Track", f"Earliest feasible opening: month {fast.scenario.initial_service_month}", when))
    # Lower Cost: cheapest $/MWh across tested dates, re-sized with no carbon weight
    cheap_date = min(ok, key=lambda r: r.metrics["decision_cost_usd_per_requested_mwh"]).scenario.initial_service_month
    cheap = cached_run(make_scenario(cheap_date, req, opt, 0.0))
    if not ok_for(cheap, req):
        cheap = min(ok, key=lambda r: r.metrics["decision_cost_usd_per_requested_mwh"])
    dcost = R * (cheap.metrics["decision_cost_usd_per_requested_mwh"] - mb["decision_cost_usd_per_requested_mwh"])
    dem = R * (cheap.metrics["combined_electricity_co2_kg_per_mwh"] - mb["combined_electricity_co2_kg_per_mwh"]) / 1000
    if dcost < -1 and dem > 1:
        when = f"Wins if avoiding CO₂ is worth less than ${-dcost / dem:,.0f}/t to you"
    elif dcost < -1:
        when = "Cheaper without being dirtier: wins unless timing matters more"
    else:
        when = "The recommendation is already the lowest-cost option tested"
    alts.append(_alt(best, cheap, "Lower Cost", f"Lowest $/MWh found: opens month {cheap.scenario.initial_service_month}, no carbon weight", when))
    # Cleaner: same opening, internal carbon price + $150/t
    clean = cached_run(make_scenario(s0, req, opt, lam + 150.0))
    if ok_for(clean, req):
        dcost = R * (clean.metrics["decision_cost_usd_per_requested_mwh"] - mb["decision_cost_usd_per_requested_mwh"])
        dem = R * (clean.metrics["combined_electricity_co2_kg_per_mwh"] - mb["combined_electricity_co2_kg_per_mwh"]) / 1000
        when = (f"Costs ${dcost / -dem:,.0f} per tonne avoided. Wins if your carbon value is above that"
                if dem < -1 and dcost > 0 else "No cleaner portfolio found at this opening for a moderate premium")
        alts.append(_alt(best, clean, "Cleaner", f"Same opening (month {s0}), +$150/t internal carbon price", when))
    return alts


def suggest_relaxations(prefs, req, opt, results):
    out = []
    v, lam = prefs.implied()
    la = latest_allowed_open(req)
    if la is not None and la < max(14, opt.earliest_open):
        out.append(dict(change=f"Widen the search window: start testing at month {max(14, la)} or earlier",
                        result=None,
                        note=f"Your deadline requires opening by month {la}, but the search window starts "
                             f"at month {opt.earliest_open}. No dates were tested, so nothing was relaxed."))
    if la is not None:
        later = replace(req, full_demand_by=None, open_by=None)
        tests = list(range(la + 2, min(la + 14, 40), 2))
        res = run_many([make_scenario(s, later, opt, lam) for s in tests], opt.workers)
        okr = [r for r in res if r.status == "ok"]
        if okr:
            r = okr[0]
            out.append(dict(change=f"Open at month {r.scenario.initial_service_month} (full demand "
                                   f"month {r.scenario.full_demand_month}) instead",
                            result=r, note=f"Earliest of the opening months tested ({tests[0]}–{tests[-1]}) "
                                           "that meets your other must-haves."))
        else:
            out.append(dict(change=f"Later openings (tested months {tests[0]}–{tests[-1]}) do not help",
                            result=None, note="Timing is not the binding requirement."))
    s = la if la is not None else opt.latest_open
    if req.max_intensity_kg is not None:
        r = cached_run(make_scenario(s, replace(req, max_intensity_kg=None), opt, 1000.0))
        if r.status == "ok":
            out.append(dict(change=f"Raise the emissions cap to "
                                   f"{np.ceil(r.metrics['combined_electricity_co2_kg_per_mwh']):.0f} kg/MWh",
                            result=r, note=f"Cleanest portfolio found opening at month {s} "
                                           "(searched with a $1,000/t internal price)."))
    if req.no_tier2:
        r = cached_run(make_scenario(s, replace(req, no_tier2=False), opt, lam))
        if r.status == "ok":
            out.append(dict(change="Allow Tier 2 interruption in stress hours", result=r,
                            note=f"{r.metrics['interrupted_mwh']:,.0f} MWh interrupted over the horizon."))
    if req.budget_musd is not None or req.max_premium_pct is not None:
        r = cached_run(make_scenario(s, replace(req, budget_musd=None), opt, 0.0))
        if r.status == "ok":
            out.append(dict(change=f"Allow a total cost of {money(r.metrics['total_decision_cost_usd'])}",
                            result=r, note="Lowest-cost portfolio meeting your other must-haves."))
    if req.excluded:
        r = cached_run(make_scenario(s, replace(req, excluded=()), opt, lam))
        if r.status == "ok":
            out.append(dict(change="Allow the excluded resources", result=r, note=""))
    msgs = [r.message for r in results if r.message]
    if msgs:
        out.append(dict(change="Why the search failed", result=None,
                        note=msgs[0] + " Infeasible here means infeasible within this catalog, "
                                       "data and the dates tested, not impossible in the real world."))
    return out


def decision_flips(rec: Recommendation):
    """Where would the answer change? Holding each tested portfolio fixed, find the value of a
    month (and the carbon price) at which another feasible opening month overtakes the winner."""
    if rec.best is None or len(rec.scores) < 2:
        return dict(value=[], carbon=[])
    b = rec.best.scenario.initial_service_month
    R = ref_mwh()
    res = {r.scenario.initial_service_month: r for r in rec.candidates}
    sb = rec.scores[b]
    vflips, cflips = [], []
    for d, sd in rec.scores.items():
        if d == b:
            continue
        dm = d - b
        diff = (sb["common"] + sb["carbon"]) - (sd["common"] + sd["carbon"])
        vstar = diff / dm      # winner holds while V*dm > diff ... sign handled below
        # total_d - total_b = (common/carbon gap) + V*(d-b) ; d wins when this is < 0
        if dm > 0 and vstar > 0:
            vflips.append(dict(month=d, below=True, value=vstar,
                               text=f"opening at month {d} wins if a month earlier is worth less than ${vstar / 1e6:,.1f}M"))
        elif dm < 0 and vstar > 0:
            vflips.append(dict(month=d, below=False, value=vstar,
                               text=f"opening at month {d} wins if a month earlier is worth more than ${vstar / 1e6:,.1f}M"))
        kb = res[b].metrics["combined_electricity_co2_kg_per_mwh"]
        kd = res[d].metrics["combined_electricity_co2_kg_per_mwh"]
        dk = R * (kd - kb) / 1000
        other = (sb["common"] + sb["delay"]) - (sd["common"] + sd["delay"])
        if abs(dk) > 1:
            lstar = other / dk + 0.0
            # d wins when (sd.common+sd.delay) + lam*R*kd < (sb...) + lam*R*kb  -> lam*dk < other
            if dk < 0 and lstar >= 0:
                cflips.append(dict(month=d, value=lstar,
                                   text=f"month {d} (cleaner) wins above ${lstar:,.0f}/t"))
            elif dk > 0 and lstar > 0:
                cflips.append(dict(month=d, value=lstar,
                                   text=f"month {d} (dirtier) wins below ${lstar:,.0f}/t"))
    vflips.sort(key=lambda x: abs(x["value"] - rec.value_per_month))
    cflips.sort(key=lambda x: abs(x["value"] - rec.carbon_price))
    return dict(value=vflips[:2], carbon=cflips[:2])
