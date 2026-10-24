"""
Execution layer: turn a recommended portfolio into "what to file, order and build, and by when".

The benchmark catalog's available_month is treated as the vendor/contract OFFER date (a
reserved delivery slot). From each resource's need date (when the portfolio first uses it)
we back-plan the latest permit filing, order and contract dates. Durations below are
labelled planning assumptions, editable in the product, NOT benchmark inputs. If an item
cannot be done in time, the slip lever re-runs the optimizer with that resource arriving
late, so the developer sees the portfolio and cost consequence before it happens.
"""
from __future__ import annotations

import pandas as pd

from .engine import OPT, LABELS, avail_month, CASE

# months; sources/notes are shown in the product
DEFAULT_STEPS = {
    "gas_engine": dict(
        pathway="TCEQ air-authorization screening for engines; confirm whether standard permit, "
                "permit by rule or case-specific authorization applies + local reviews",
        agency="TCEQ (air); county/city (site plan, building, fire)",
        permit=6, procure=14, build=6,
        note="Confirm technology, engine model, heat input and emissions against current TCEQ rules "
             "before selecting an authorization pathway."),
    "gas_turbine": dict(
        pathway="TCEQ air-authorization screening for gas turbines + local permitting",
        agency="TCEQ (air NSR, public notice); county/city",
        permit=14, procure=36, build=10,
        note="Long procurement lead time is an editable scenario assumption, not a verified offer; "
             "confirm actual turbine quote and authorization type."),
    "fuel_cell": dict(
        pathway="TCEQ authorization review (permit-by-rule / standard permit screening) + local "
                "building and fire permits",
        agency="TCEQ; county/city fire marshal",
        permit=4, procure=9, build=4,
        note="Confirm fuel type, emissions, configuration and applicable TCEQ authorization."),
    "battery_4h": dict(
        pathway="Local fire-code review (NFPA 855 / IFC energy-storage provisions), building and "
                "electrical permits, utility interconnection of onsite equipment",
        agency="Fire marshal; county/city building official",
        permit=4, procure=10, build=5,
        note="Hazard mitigation analysis and emergency response plan typically required."),
    "utility_solar": dict(
        pathway="Physical PPA execution (seller holds project permits and its own interconnection)",
        agency="Counterparty; ERCOT/utility for delivery",
        permit=0, procure=6, build=0,
        note="'Procure' = contract negotiation and credit support before the offer date."),
    "wind": dict(
        pathway="Physical PPA execution (seller holds project permits and its own interconnection)",
        agency="Counterparty; ERCOT/utility for delivery",
        permit=0, procure=6, build=0,
        note="'Procure' = contract negotiation and credit support before the offer date."),
    "nuclear": dict(
        pathway="Physical PPA with a new offsite plant (NRC licensing is the seller's risk)",
        agency="Counterparty; NRC (seller)",
        permit=0, procure=12, build=0,
        note="Delivery depends on the seller's licensing and construction schedule; keep a fallback."),
}

SITE_STEPS = [
    dict(item="Large-load service / interconnection screening (Texas; applicability unverified)",
         agency="Transmission provider / ERCOT / PUCT", lead=24,
         note="Determine applicable large-load requirements with the utility, ERCOT and PUCT. "
              "The benchmark peak is 75 MW; threshold inclusivity, application type, "
              "requirements, fees and effective implementation require verification. "
              "This is a diligence task, not a compliance conclusion."),
    dict(item="Site plan, zoning and building permits for the campus",
         agency="Williamson County / city (ETJ dependent)", lead=9, note="Exact authority depends on parcel."),
    dict(item="Natural gas supply agreement and lateral to site",
         agency="Gas utility / pipeline", lead=12,
         note="Benchmark assumes fuel ready at each gas unit's date; this is the real-world dependency."),
]


def plan(caps: dict, start: int, grid_delay: int = 0, today: int = 0, overrides: dict | None = None,
         shift=()):
    """Back-planned schedule. Returns (DataFrame rows per resource activity, flags)."""
    overrides = overrides or {}
    rows, flags = [], []
    for k, mw in caps.items():
        if mw <= 0:
            continue
        st = {**DEFAULT_STEPS[k], **overrides.get(k, {})}
        need = max(start, avail_month(k, shift))
        build_start = need - st["build"]
        permit_by = build_start - st["permit"]
        order_by = need - st["build"] - st["procure"] if OPT.loc[k, "location"] == "onsite" else need - st["procure"]
        first_action = min(permit_by, order_by)
        late = first_action < today
        rows.append(dict(key=k, resource=f"{LABELS[k]} ({mw:.0f} MW)", need=need,
                         permit_by=permit_by if st["permit"] else None, order_by=order_by,
                         build_start=build_start if st["build"] else None,
                         permit=st["permit"], procure=st["procure"], build=st["build"],
                         slack=first_action - today, late=late, pathway=st["pathway"],
                         agency=st["agency"], note=st["note"]))
        if late:
            flags.append(dict(key=k, months_late=today - first_action,
                              text=f"{LABELS[k]}: the first action was due in month {first_action}, "
                                   f"{today - first_action} months before today (month {today}). "
                                   f"Unless the offer's delivery slot is secured, expect a slip."))
    grid_months = [m + (grid_delay if m > 0 else 0) for m, _ in
                   [(18, 25), (24, 50), (30, 75)]]
    site = []
    for s in SITE_STEPS:
        need = start if "Site plan" in s["item"] else (grid_months[0] if "interconnection" in s["item"]
               else min((max(start, avail_month(k, shift)) for k in ("gas_engine", "gas_turbine", "fuel_cell")
                         if caps.get(k, 0) > 0), default=None))
        if need is None:
            continue
        due = need - s["lead"]
        site.append(dict(item=s["item"], agency=s["agency"], need=need, start_by=due,
                         slack=due - today, late=due < today, note=s["note"]))
    return pd.DataFrame(rows), pd.DataFrame(site), flags


def sb6_check(caps: dict, peak_mw: float = 75.0):
    """Descriptive capacity screen only; NOT a statutory compliance test."""
    firm_onsite = sum(caps.get(k, 0) for k in ("gas_turbine", "gas_engine", "fuel_cell")) + caps.get("battery_4h", 0)
    half = 0.5 * peak_mw
    return dict(firm_onsite_mw=firm_onsite, half_load_mw=half, meets_half=firm_onsite >= half,
                applicability="Unverified; consult utility/PUCT/ERCOT",
                caveat="A 50% capacity comparison is not evidence of legal compliance; battery MW is not firm generation without duration and availability checks.")
