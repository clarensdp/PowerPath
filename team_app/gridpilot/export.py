"""Submission exports in the packet's exact format + a readable summary."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .engine import RES, LABELS, Result


def portfolio_dict(r: Result) -> dict:
    return r.portfolio()


def write_submission(r: Result, folder, rec=None, prefs=None, req=None, opt=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "portfolio.json").write_text(json.dumps(portfolio_dict(r), indent=2))
    r.dispatch.to_csv(folder / "dispatch.csv", index=False, float_format="%.6f")
    (folder / "check_results.json").write_text(json.dumps(r.metrics, indent=2))
    (folder / "summary.md").write_text(summary_md(r, rec, prefs, req, opt))


def money(x, d=1):
    return f"${x / 1e6:,.{d}f}M"


def summary_md(r: Result, rec=None, prefs=None, req=None, opt=None) -> str:
    m = r.metrics
    s = r.scenario.initial_service_month
    L = ["# PowerPath results summary", ""]
    if prefs is not None and rec is not None:
        L += ["## Customer inputs",
              f"- Preferences (speed / cost / clean): {prefs.speed:.0f} / {prefs.cost:.0f} / {prefs.env:.0f} "
              f"→ value of opening a month earlier {money(rec.value_per_month)}, internal carbon price "
              f"${rec.carbon_price:,.0f}/t (customer valuations, not common costs)"]
        if req is not None:
            must = {k: v for k, v in asdict(req).items() if v not in (None, False, (), True) and k != "premium_ref_open"}
            L.append(f"- Must-haves: {must if must else 'none'}")
        L.append(f"- Opening months tested: {', '.join(map(str, rec.tested))}; grid delay "
                 f"{r.scenario.grid_delay_months} months")
        L.append("")
    L += ["## Recommendation",
          f"- Initial service: month {s}; full demand: month {s + 10}",
          "- Portfolio: " + ", ".join(f"{LABELS[k]} {c:.0f} MW" for k, c in r.caps.items() if c > 0),
          "", "## Cost (common benchmark accounting, packet checker)",
          f"- Local energy cost: {money(m['local_energy_cost_usd'])} "
          f"({m['local_energy_cost_usd_per_mwh']:.2f} $/MWh local served)",
          f"- Relocation cost: {money(m['relocation_cost_usd'], 2)}; interruption consequence: "
          f"{money(m['interruption_consequence_usd'], 2)}",
          f"- Total decision cost: {money(m['total_decision_cost_usd'])} "
          f"({m['decision_cost_usd_per_requested_mwh']:.2f} $/MWh requested)",
          "", "## Environment",
          f"- CO₂: local {m['local_operational_co2_t']:,.0f} t, remote {m['remote_operational_co2_t']:,.0f} t, "
          f"combined {m['combined_operational_co2_t']:,.0f} t",
          f"- Combined electricity intensity: {m['combined_electricity_co2_kg_per_mwh']:.1f} kg CO₂/MWh",
          f"- Clean share (annual accounting): {m['clean_energy_share'] * 100:.1f}%",
          "", "## Service",
          f"- Requested {m['requested_mwh']:,.0f} MWh; served locally {m['local_served_mwh']:,.0f}; "
          f"relocated {m['relocated_local_equivalent_mwh']:,.0f} (remote electricity "
          f"{m['remote_electricity_mwh']:,.0f}); interrupted {m['interrupted_mwh']:,.0f}",
          f"- Merchant electricity: {m['merchant_mwh']:,.0f} MWh "
          f"({m['merchant_mwh'] / m['local_served_mwh'] * 100:.1f}% of local served)",
          f"- Physical checks passed: {m['physical_checks_passed']}; max grid import {m['max_grid_import_mw']:.2f} MW",
          ]
    try:
        from .analytics import curtailment, clean_coverage, spikes, n1_check
        cdf, _ = curtailment(r); cov = clean_coverage(r); _, sp_port, sp_base, _ = spikes(r); n1 = n1_check(r)
        L += ["", "## v4 diagnostics",
              f"- Clean energy curtailed (paid for, unused): {cdf.curtailed_mwh.sum() if len(cdf) else 0:,.0f} MWh, "
              f"{money(cdf.paid_for_curtailed_usd.sum() if len(cdf) else 0)}",
              f"- Hourly clean matching: {cov['hourly_matched_share'] * 100:.1f}% of local load; "
              f"{cov['hours_fully_clean'] * 100:.1f}% of operating hours fully clean (annual share above is a different metric)",
              f"- Merchant price-spike premium (> $200/MWh): {money(sp_port, 2)} vs {money(sp_base)} if all-merchant"]
        if n1 is not None:
            L.append(f"- Largest-unit outage ({n1['lost_mw']:.0f} MW {n1['lost'].lower()}): {n1['hours_short']:,} hours "
                     f"unservable, worst {n1['worst_mw']:.1f} MW; expected consequence {money(n1['expected_consequence_usd'], 2)} "
                     "at a 3% forced-outage planning assumption")
        if r.scenario.avail_shift:
            L.append("- Availability shifts applied (execution-aware / slip): " +
                     ", ".join(f"{LABELS[k]} +{m_} months" for k, m_ in r.scenario.avail_shift))
    except Exception as e:  # diagnostics must never block an export
        L += ["", f"_(v4 diagnostics unavailable: {e})_"]
    if rec is not None and rec.explanation:
        L += ["", "## Why this portfolio"] + [f"- {e}" for e in rec.explanation]
    if rec is not None and rec.alternatives:
        L += ["", "## Alternatives (each passes the packet checker)"]
        for a in rec.alternatives:
            L.append(f"- **{a['name']}** ({a.get('tagline', '')}): gains {', '.join(a['gains']) or '—'}; "
                     f"gives up {', '.join(a['gives']) or '—'}. {a['when']}.")
    from .execution import plan, sb6_check
    tbl, site, flags = plan(r.caps, s, r.scenario.grid_delay_months, 0, shift=r.scenario.avail_shift)
    L += ["", "## Execution: what's next (planning assumptions, not benchmark inputs)"]
    for _, x in tbl.sort_values("order_by").iterrows():
        pb = f"file permit by M{int(x.permit_by)}, " if x.permit_by == x.permit_by and x.permit else ""
        L.append(f"- {x.resource}: needed M{x.need}; {pb}order/sign by M{int(x.order_by)}. {x.pathway}.")
    for _, x in site.iterrows():
        L.append(f"- {x['item']}: start by M{int(x.start_by)} ({x.agency}).")
    sb = sb6_check(r.caps)
    L.append(f"- Texas SB 6 backup disclosure: {sb['firm_onsite_mw']:.0f} MW firm onsite vs "
             f"{sb['half_load_mw']:.0f} MW (50% of load).")
    for f_ in flags:
        L.append(f"- ⚠ {f_['text']}")
    L += ["", "## Annual results", "",
          "| Year | Requested MWh | Total decision $ | $/MWh req. | kg CO₂/MWh | Clean share |",
          "|---|---|---|---|---|---|"]
    for y in m["annual_results"]:
        if y["requested_mwh"] > 0:
            L.append(f"| {y['model_year']} | {y['requested_mwh']:,.0f} | {y['total_decision_cost_usd']:,.0f} | "
                     f"{y['decision_cost_usd_per_requested_mwh']:.2f} | "
                     f"{y['combined_electricity_co2_kg_per_mwh']:.0f} | {y['clean_energy_share'] * 100:.1f}% |")
    return "\n".join(L)
