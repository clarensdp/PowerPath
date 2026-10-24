"""
Stage 2 · Interconnect: wait for the grid, bridge with onsite power, or walk away.

Screening assumptions (labelled; not utility studies): per grid region, a P50 grid-connection
wait (the location's delay vs the benchmark schedule), a P10/P90 spread, an indicative network
upgrade cost and study requirements. The decision itself uses the engine: it sizes and dispatches
"wait for grid" and "bridge to target" plans on the full 87,600 hours and compares them at the
customer's value of time. Upgrade cost is shown separately; it is not in the common benchmark cost.
"""
from __future__ import annotations

import numpy as np

from .engine import OPT, THERMAL, BATT, CASE

GRID_MILESTONES = [(18, 25.0), (24, 50.0), (30, 75.0)]

# region keyword -> (spread months, upgrade $/kW, study path)
IC_PROFILES = [
    ("ERCOT", 6, 60, "Large-load interconnection request to the TSP; screening study (≥$100k under SB 6) and "
                     "facilities study; financial security; ERCOT curtailment equipment."),
    ("SPP", 6, 80, "Load addition through the transmission owner; SPP planning studies for large loads."),
    ("MISO", 9, 100, "Utility load-interconnection study; MISO expedited resource and transmission reviews."),
    ("PJM", 12, 150, "Utility large-load study plus PJM transmission review; long upgrade lead times in constrained zones."),
    ("NYISO", 12, 180, "Utility and NYISO load interconnection; deliverability studies."),
    ("ISO-NE", 12, 180, "Utility load study; ISO-NE transmission planning."),
    ("CAISO", 12, 200, "Utility Rule 30 / large-load process; CAISO transmission planning."),
    ("SERC", 6, 100, "Vertically integrated utility: large-load tariff, service agreement and system impact study."),
    ("TVA", 6, 100, "TVA local power company and TVA transmission review."),
    ("Non-RTO", 9, 120, "Utility system impact and facilities studies (non-RTO)."),
    ("WestTEC", 9, 120, "Utility system impact and facilities studies (western non-RTO)."),
]
DEFAULT_PROFILE = (12, 150, "National TSO/DSO connection application; confirm queue rules and connection reform status.")


def profile_for(grid: str):
    for key, spread, usd, path in IC_PROFILES:
        if key.lower() in (grid or "").lower():
            return spread, usd, path
    return DEFAULT_PROFILE


def energization(delay_p50: int, spread: int):
    p10, p50, p90 = max(0, delay_p50 - spread), delay_p50, delay_p50 + spread
    return {"P10": p10, "P50": p50, "P90": p90}


def grid_mw_by_month(delay: int, months=None):
    months = np.arange(CASE["horizon_months"]) if months is None else months
    mw = np.zeros(len(months))
    for m0, cap in GRID_MILESTONES:
        mw = np.where(months >= m0 + delay, cap, mw)
    return mw


def deliverable_power(result, delay: int):
    """MW available by development month: grid import cap + onsite firm (thermal x availability
    + battery power) vs the demand ramp's peak. 'Power gap' = demand the grid cannot carry."""
    months = np.arange(CASE["horizon_months"])
    s = result.scenario.initial_service_month
    rel = months - s
    frac = np.where(rel < 0, 0.0, np.minimum(1.0, 1 / 3 + rel / 15))
    demand = 75.0 * frac
    grid = grid_mw_by_month(delay, months)
    onsite = np.zeros(len(months))
    shift = dict(result.scenario.avail_shift)
    for k in THERMAL + [BATT]:
        mw = result.caps.get(k, 0.0)
        if mw <= 0:
            continue
        start = max(s, int(OPT.loc[k, "available_month"]) + int(shift.get(k, 0)))
        onsite += np.where(months >= start, mw, 0.0)
    gap = np.clip(demand - grid, 0, None)
    grid_full = next((int(m) for m in months if grid[m] >= 75.0), None)
    return dict(months=months, demand=demand, grid=grid, onsite=onsite, gap=gap,
                bridge_mw=float(gap.max()), bridge_mw_months=float(gap.sum()), grid_full_month=grid_full)


def decide(plan, wait, bridge, value_per_month: float, ref_mwh: float):
    """Compare wait-for-grid vs bridge plans (both engine results, may be None/infeasible)."""
    ok = lambda r: r is not None and r.status == "ok"
    if ok(wait) and ok(bridge):
        dm = wait.scenario.initial_service_month - bridge.scenario.initial_service_month
        dcost = (bridge.metrics["decision_cost_usd_per_requested_mwh"] -
                 wait.metrics["decision_cost_usd_per_requested_mwh"]) * ref_mwh
        if dm <= 0:
            return dict(verdict="WAIT", text="The grid arrives in time for the target opening; no bridge power is needed.",
                        breakeven=None, dm=dm, dcost=dcost)
        be = dcost / dm
        if dcost <= 0:
            return dict(verdict="BRIDGE", text=f"Bridging is cheaper and {dm} months faster.", breakeven=be, dm=dm, dcost=dcost)
        verdict = "BRIDGE" if value_per_month >= be else "WAIT"
        return dict(verdict=verdict, dm=dm, dcost=dcost, breakeven=be,
                    text=(f"Bridging opens {dm} months sooner for ${dcost / 1e6:,.1f}M more "
                          f"(${be / 1e6:,.1f}M per month gained). Your value of time is ${value_per_month / 1e6:,.1f}M/month, so "
                          + ("bridge." if verdict == "BRIDGE" else "wait for the grid.")))
    if ok(bridge):
        return dict(verdict="BRIDGE", text="Waiting for the grid does not meet your must-haves; bridge with onsite power.",
                    breakeven=None, dm=None, dcost=None)
    if ok(wait):
        return dict(verdict="WAIT", text="No bridge portfolio meets your must-haves at the target date; wait for the grid.",
                    breakeven=None, dm=None, dcost=None)
    return dict(verdict="WALK AWAY / RELAX", text="Neither waiting nor bridging meets your must-haves at this site.",
                breakeven=None, dm=None, dcost=None)
