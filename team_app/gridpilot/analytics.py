"""
v4 analytics on a finished, checker-validated result (no re-optimization):
  * curtailment     - clean energy paid for but not used (available-generation contracts)
  * clean_coverage  - hourly clean matching, distinct from the annual clean share
  * spikes          - merchant price-spike exposure by model year vs. an all-merchant baseline
  * n1_check        - what happens in each hour if the largest onsite unit is out
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .engine import OPT, LABELS, RES, THERMAL, BATT, ETA, context, fixed_annual_per_mw, CASE

SPIKE_USD = 200.0
FORCED_OUTAGE_RATE = 0.03   # labelled planning assumption: share of hours a given unit is unavailable


def _ctx(r):
    return context(r.scenario.initial_service_month, r.scenario.grid_delay_months, r.scenario.avail_shift, r.scenario.region)


def curtailment(r):
    ctx, d = _ctx(r), r.dispatch
    rows = []
    for k in ("utility_solar", "wind", "nuclear"):
        mw = r.caps.get(k, 0.0)
        if mw <= 0:
            continue
        avail = mw * ctx["prof"][k]
        used = d[f"{k}_mw"].to_numpy()
        curt = np.clip(avail - used, 0, None)
        price = OPT.loc[k, "payment_usd_per_mwh"]
        rows.append(dict(resource=LABELS[k], available_mwh=avail.sum(), dispatched_mwh=used.sum(),
                         curtailed_mwh=curt.sum(), curtailed_share=curt.sum() / max(avail.sum(), 1),
                         paid_for_curtailed_usd=curt.sum() * price))
    df = pd.DataFrame(rows)
    by_year = None
    if len(df):
        tot = sum(np.clip(r.caps.get(k, 0) * ctx["prof"][k] - d[f"{k}_mw"].to_numpy(), 0, None)
                  for k in ("utility_solar", "wind", "nuclear") if r.caps.get(k, 0) > 0)
        by_year = pd.Series(tot).groupby(np.arange(len(tot)) // 8760 + 1).sum()
    return df, by_year


def clean_coverage(r):
    ctx, d = _ctx(r), r.dispatch
    local = ctx["load"] - d.tier1_relocated_mw.to_numpy() - d.tier2_curtailed_mw.to_numpy()
    clean = (d.utility_solar_mw + d.wind_mw + d.nuclear_mw - d[BATT + "_charge_mw"]
             + d[BATT + "_discharge_mw"]).to_numpy()
    op = local > 1e-6
    matched = np.minimum(np.clip(clean, 0, None), local)
    full_hours = (clean >= local - 1e-6) & op
    yr = np.arange(len(local)) // 8760 + 1
    ann = pd.DataFrame({"year": yr[op], "matched": matched[op], "local": local[op],
                        "full": full_hours[op]}).groupby("year").agg(
        matched=("matched", "sum"), local=("local", "sum"), full=("full", "mean"))
    ann["hourly_matched_share"] = ann.matched / ann.local
    return dict(hours_fully_clean=float(full_hours[op].mean()),
                hourly_matched_share=float(matched[op].sum() / local[op].sum()),
                annual=ann.reset_index())


def spikes(r):
    ctx, d = _ctx(r), r.dispatch
    price = ctx["grid_price"]
    prem = np.clip(price - SPIKE_USD, 0, None)
    yr = np.arange(len(price)) // 8760 + 1
    op = ctx["load"] > 0
    port = d.grid_mw.to_numpy() * prem
    base = ctx["load"] * prem * op             # buy every MWh at merchant (ignores import cap)
    df = pd.DataFrame({"year": yr, "port": port, "base": base,
                       "spike_hour": (prem > 0) & op, "bought": (d.grid_mw.to_numpy() > 1e-6) & (prem > 0)})
    out = df.groupby("year").agg(portfolio_premium_usd=("port", "sum"), merchant_only_premium_usd=("base", "sum"),
                                 spike_hours=("spike_hour", "sum"), spike_hours_buying=("bought", "sum"))
    return out.reset_index(), float(port.sum()), float(base.sum()), float(price[op].max())


def n1_check(r):
    """Largest single onsite unit out (one block of the onsite resource with the biggest block).
    Uses packet limits: in stress hours all eligible Tier 1/Tier 2 flexibility may be used; Tier 0
    must stay served. Battery support uses the state of charge actually available in that hour."""
    ctx, d = _ctx(r), r.dispatch
    units = [(k, float(OPT.loc[k, "block_mw"])) for k in THERMAL if r.caps.get(k, 0) > 0]
    if not units:
        return None
    lost_k, lost_mw = max(units, key=lambda x: x[1])
    onsite = sum(r.caps[k] * ctx["prof"][k] for k in THERMAL if r.caps.get(k, 0) > 0)
    onsite_after = onsite - lost_mw * ctx["prof"][lost_k + "_mask"]
    bmw = r.caps.get(BATT, 0.0)
    soc_prev = np.r_[0.0, d[BATT + "_soc_mwh"].to_numpy()[:-1]]
    batt = np.minimum(bmw * ctx["prof"][BATT + "_mask"], soc_prev * ETA) if bmw > 0 else 0.0
    load = ctx["load"]
    flex = ctx["relocation_limit"] + ctx["interruption_limit"]
    supply = ctx["grid_limit"] + onsite_after + batt
    hard = np.clip(load - flex - supply, 0, None)                 # cannot be served even with all flex
    extra_flex = np.clip(np.minimum(load - supply, flex) - (d.tier1_relocated_mw + d.tier2_curtailed_mw).to_numpy(), 0, None)
    op = load > 0
    stress = ctx["active"] & op
    # covering options: one more block of an onsite resource, within max and land
    land_used = sum(r.caps.get(k, 0) * OPT.loc[k, "land_acres_per_mw"] for k in RES)
    opts = []
    for k in THERMAL:
        o = OPT.loc[k]
        add = float(o.block_mw)
        ok_max = r.caps.get(k, 0) + add <= o.max_mw
        ok_land = land_used + add * o.land_acres_per_mw <= CASE["onsite_energy_land_acres"] + 1e-9
        if ok_max and ok_land:
            opts.append(dict(resource=LABELS[k], block_mw=add,
                             annual_cost_usd=fixed_annual_per_mw(k) * add,
                             covers_worst_hour=add >= hard.max() - 1e-9,
                             available_month=int(o.available_month)))
    opts.sort(key=lambda x: (not x["covers_worst_hour"], x["annual_cost_usd"]))
    exp_unserved = FORCED_OUTAGE_RATE * hard[op].sum()
    exp_flex_cost = FORCED_OUTAGE_RATE * (extra_flex[stress].sum()) * 1000.0
    return dict(lost=LABELS[lost_k], lost_mw=lost_mw,
                hours_short=int((hard > 1e-6).sum()), hours_short_stress=int((hard[stress] > 1e-6).sum()),
                worst_mw=float(hard.max()), short_mwh=float(hard.sum()),
                extra_flex_mwh=float(extra_flex[stress].sum()),
                expected_unserved_mwh=float(exp_unserved),
                expected_consequence_usd=float(exp_unserved * 1000.0 + exp_flex_cost),
                options=opts, worst_hour=int(np.argmax(hard)) if hard.max() > 0 else None)
