"""
Stage 4 · Structure: how to own and pay for the chosen portfolio.

Starts from the engine's portfolio and the common benchmark cost ledger (annualized capital at 8%
real), then re-expresses it under four structures. Everything beyond the ledger (third-party
return, margin, tariff demand charge, tenors) is a labelled screening assumption the user can edit.
Common benchmark cost is unchanged by structure for "Own"; other structures add a counterparty
return or tariff terms, shown separately so structure never hides the physical result.
"""
from __future__ import annotations

from dataclasses import dataclass

from .engine import OPT, RES, CASE, crf

ONSITE = [k for k in RES if OPT.loc[k, "location"] == "onsite"]
CONTRACTS = ["utility_solar", "wind", "nuclear"]


@dataclass
class DealInputs:
    max_upfront_musd: float | None = None   # capital constraint
    prefer_off_balance_sheet: bool = False
    provider_wacc: float = 0.10             # tolling / energy-as-a-service provider
    provider_margin: float = 0.08
    tariff_demand_usd_kw_month: float = 12.0
    tariff_min_take: float = 0.85           # minimum-demand commitment (large-load tariffs)
    obs_tolerance: float = 0.05             # accept up to 5% higher cost for off-balance-sheet


def build(result, delay: int, inp: DealInputs):
    m = result.metrics
    led = {x["option_id"]: x for x in m["capacity_cost_ledger"]}
    years = (CASE["horizon_months"] - result.scenario.initial_service_month) / 12
    onsite_mw = {k: result.caps.get(k, 0) for k in ONSITE if result.caps.get(k, 0) > 0}
    capex = sum(OPT.loc[k, "capex_usd_per_kw"] * 1000 * mw for k, mw in onsite_mw.items())
    onsite_fixed = sum(led[k]["capacity_charges_usd"] for k in onsite_mw)
    ppa_pay = sum(led[k]["energy_payment_or_variable_om_usd"] for k in CONTRACTS if k in led)
    base = m["total_decision_cost_usd"]
    req = m["requested_mwh"]
    out = []

    def add(name, total, upfront, committed, tenor, bs, risks, notes):
        out.append(dict(structure=name, total_usd=total, usd_per_mwh=total / req, upfront_usd=upfront,
                        committed_usd=committed, tenor=tenor, balance_sheet=bs, risks=risks, notes=notes))

    # 1) Own and operate onsite plant, sign PPAs
    add("Own onsite plant + PPAs", base, capex, ppa_pay + 0.0, f"Asset life {int(max([OPT.loc[k, 'life_years'] for k in onsite_mw] or [0]))} y",
        "On balance sheet",
        {"Fuel price": "Developer", "Construction / delivery": "Developer", "Unit outage": "Developer",
         "Curtailment (PPA)": "Developer", "Stranded asset": "Developer"},
        "Common benchmark cost: annualized capex at 8% + O&M + fuel + contracts + merchant.")
    # 2) Tolling / energy-as-a-service: provider owns onsite assets
    toll = 0.0
    for k, mw in onsite_mw.items():
        o = OPT.loc[k]
        ann = mw * 1000 * (o.capex_usd_per_kw * crf(o.life_years, inp.provider_wacc) + o.fom_usd_per_kw_year)
        hours = (CASE["horizon_months"] - led[k]["commitment_start_month"]) * CASE["hours_per_model_month"]
        toll += ann * (1 + inp.provider_margin) * hours / 8760
    total_toll = base - onsite_fixed + toll
    add("Tolling / energy-as-a-service + PPAs", total_toll, 0.0, ppa_pay + toll, "10 y toll",
        "Off balance sheet (subject to lease accounting review)",
        {"Fuel price": "Developer (pass-through)", "Construction / delivery": "Provider", "Unit outage": "Provider (availability guarantee)",
         "Curtailment (PPA)": "Developer", "Stranded asset": "Provider"},
        f"Provider return {inp.provider_wacc:.0%} WACC + {inp.provider_margin:.0%} margin on onsite capacity.")
    # 3) Utility large-load tariff after the grid is full, toll bridge power before
    grid_full = 30 + delay
    s = result.scenario.initial_service_month
    bridge_years = max(0, grid_full - s) / 12
    after_years = max(0.0, (CASE["horizon_months"] - max(s, grid_full)) / 12)
    avg_mwh_yr = CASE["full_load_year_mwh"]
    energy_rate = (m["local_energy_cost_usd"] / max(m["local_served_mwh"], 1)) * 0.9   # utility energy charge proxy
    demand = inp.tariff_demand_usd_kw_month * 75_000 * 12 * inp.tariff_min_take
    tariff_cost = after_years * (avg_mwh_yr * energy_rate + demand)
    bridge_cost = (base / max(years, 1e-9)) * bridge_years * 1.1 if bridge_years > 0 else 0.0
    total_tariff = tariff_cost + bridge_cost + m["relocation_cost_usd"] + m["interruption_consequence_usd"]
    add("Utility large-load tariff (+ bridge power until grid is full)", total_tariff, 0.0,
        after_years * demand + bridge_cost, f"Tariff min-take {inp.tariff_min_take:.0%}, ~{after_years:.0f} y",
        "Off balance sheet; tariff commitment disclosed",
        {"Fuel price": "Utility (in rates)", "Construction / delivery": "Utility (grid date risk on developer)",
         "Unit outage": "Utility", "Curtailment (PPA)": "n/a", "Stranded asset": "Developer via min-take"},
        f"Demand charge ${inp.tariff_demand_usd_kw_month:.0f}/kW-month on {inp.tariff_min_take:.0%} of 75 MW; "
        f"bridge power tolled until month {grid_full}. Clean share depends on the utility mix.")
    # choose
    feas = [d for d in out if inp.max_upfront_musd is None or d["upfront_usd"] <= inp.max_upfront_musd * 1e6]
    pick, why = None, ""
    if feas:
        cheapest = min(feas, key=lambda d: d["total_usd"])
        pick = cheapest
        why = "Lowest total cost" + (" within your upfront-capital limit" if inp.max_upfront_musd is not None else "")
        if inp.prefer_off_balance_sheet and cheapest["balance_sheet"].startswith("On"):
            obs = [d for d in feas if not d["balance_sheet"].startswith("On")]
            if obs:
                b = min(obs, key=lambda d: d["total_usd"])
                if b["total_usd"] <= cheapest["total_usd"] * (1 + inp.obs_tolerance):
                    pick, why = b, f"Off balance sheet within {inp.obs_tolerance:.0%} of the cheapest structure"
    else:
        why = "No structure fits the upfront-capital limit; raise the limit or use a third-party structure."
    for d in out:
        d["recommended"] = pick is not None and d["structure"] == pick["structure"]
    return out, pick, why, capex
