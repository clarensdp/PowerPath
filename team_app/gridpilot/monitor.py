"""
Stage 5 · Monitor: what would change the decision, and how close are we to it?

Triggers are derived from the chosen plan. Price and fuel triggers are computed analytically from
the dispatch (exact for the fixed portfolio); grid-date triggers reuse the Interconnect stage's
P90 engine run. Each trigger states its threshold, the impact if it fires, and the action.
"""
from __future__ import annotations

import numpy as np

from .engine import OPT, THERMAL, context


def triggers(result, ic_p90=None, ic_info=None, value_per_month=0.0, ref_mwh=1.0):
    m, d = result.metrics, result.dispatch
    ctx = context(result.scenario.initial_service_month, result.scenario.grid_delay_months,
                  result.scenario.avail_shift, result.scenario.region)
    req = m["requested_mwh"]
    base = m["decision_cost_usd_per_requested_mwh"]
    merch_usd = float((d.grid_mw.to_numpy() * ctx["grid_price"]).sum())
    fuel_usd = sum(float((d[k + "_mw"].to_numpy() * ctx["gas_price"]).sum()) * OPT.loc[k, "heat_rate_mmbtu_per_mwh_hhv"]
                   for k in THERMAL if result.caps.get(k, 0) > 0)
    rows = []
    # merchant price
    d20 = 0.2 * merch_usd / req
    rows.append(dict(trigger="Merchant prices run 20% above forecast", watch="ERCOT/ISO forwards vs packet trajectory",
                     impact=f"+{d20:.2f} $/MWh ({d20 / base:.1%})",
                     action="Add contracted clean MW or onsite capacity; re-run Generate" if d20 / base > 0.03 else "Hold; exposure is small",
                     severity="high" if d20 / base > 0.05 else ("medium" if d20 / base > 0.02 else "low")))
    # gas price
    g30 = 0.3 * fuel_usd / req
    rows.append(dict(trigger="Delivered gas 30% above forecast", watch="Henry Hub strip + basis",
                     impact=f"+{g30:.2f} $/MWh ({g30 / base:.1%})" if fuel_usd > 0 else "none (no onsite gas)",
                     action="Hedge fuel or shift to tolling with fuel pass-through caps" if fuel_usd > 0 else "—",
                     severity="medium" if fuel_usd > 0 and g30 / base > 0.03 else "low"))
    # grid date
    if ic_p90 is not None and ic_info is not None:
        if ic_p90.status == "ok":
            dc = ic_p90.metrics["decision_cost_usd_per_requested_mwh"] - base
            rows.append(dict(trigger=f"Grid energization slips to P90 (+{ic_info['P90'] - ic_info['P50']} months)",
                             watch="Utility study milestones, upgrade construction",
                             impact=f"{dc:+.2f} $/MWh; plan re-sized to " +
                                    ", ".join(f"{v:.0f} MW {k.replace('_', ' ')}" for k, v in ic_p90.caps.items() if v > 0),
                             action="Pre-order bridge capacity now if the P90 plan needs more onsite MW",
                             severity="high" if dc / base > 0.05 else "medium"))
        else:
            rows.append(dict(trigger=f"Grid energization slips to P90 (+{ic_info['P90'] - ic_info['P50']} months)",
                             watch="Utility study milestones", impact="Plan becomes infeasible at the current opening",
                             action="Secure bridge capacity or move the opening date", severity="high"))
    # largest unit
    big = max((OPT.loc[k, "block_mw"] for k in THERMAL if result.caps.get(k, 0) > 0), default=0)
    if big:
        rows.append(dict(trigger=f"Largest onsite unit ({big:.0f} MW) unavailable", watch="Vendor delivery, forced outages",
                         impact="See Stress & N-1 for unservable hours", action="Make N-1 a must-have or contract standby",
                         severity="medium"))
    # curtailment
    rows.append(dict(trigger="Clean curtailment above plan", watch="Import-cap congestion, renewable output",
                     impact="Paying for unused MWh under available-generation contracts",
                     action="Add storage or resize PPAs at next contract window", severity="low"))
    return rows
