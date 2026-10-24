"""
PowerPath location screener: any US ZIP / state or major country -> feasibility score.

For each location the SAME 87,600-hour engine sizes and dispatches a portfolio for the default
customer (opening month 20, the customer's carbon price), on the benchmark's hourly shapes scaled
by regional price, grid-CO2 and renewable indices and shifted by the regional grid-connection
delay. The score is a transparent weighted sum of six components, each shown with its inputs.

Parcels are ILLUSTRATIVE (seeded, plausible attributes) unless the user uploads a parcel CSV
(e.g. a county or Regrid export mapped to PARCEL_COLUMNS). No live GIS lookup is performed.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from .engine import Scenario, context, CASE
from .regions import resolve

PARCEL_COLUMNS = ["parcel_id", "lat", "lon", "acres", "dist_substation_km", "substation_spare_mw",
                  "dist_gas_km", "flood_zone", "zoning", "land_usd_per_acre"]
MIN_ACRES = 50          # campus buildings + 8 acres of onsite energy + setbacks (screening assumption)
FIRST_PHASE_MW = 25     # first 1/3 of load
WATER_SCORE = {1: 100, 2: 80, 3: 60, 4: 35, 5: 15}


def scenario_for(loc: dict, carbon_price: float, opening: int = 20, n_minus_1: bool = False) -> Scenario:
    return Scenario(initial_service_month=opening, grid_delay_months=0 if loc["benchmark"] else int(loc["delay"]),
                    carbon_price=carbon_price, region="" if loc["benchmark"] else loc["key"],
                    n_minus_1=n_minus_1)


def illustrative_parcels(loc: dict, n: int = 60) -> pd.DataFrame:
    seed = int(hashlib.sha1((loc["key"] + loc.get("zip", "")).encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    spread = 0.35 if loc.get("zip") else (3.0 if loc["kind"] == "country" else 1.0)
    cap_factor = {0: 1.3, 6: 1.1, 12: 0.9, 18: 0.75, 24: 0.6, 36: 0.45}.get(int(loc["delay"]), 0.8)
    df = pd.DataFrame({
        "parcel_id": [f"{loc['abbr']}-{i:03d}" for i in range(n)],
        "lat": loc["lat"] + rng.normal(0, spread, n) * 0.6,
        "lon": loc["lon"] + rng.normal(0, spread, n),
        "acres": np.round(rng.lognormal(np.log(120), 0.8, n), 1),
        "dist_substation_km": np.round(rng.gamma(2.0, 4.0, n), 1),
        "substation_spare_mw": np.round(np.clip(rng.gamma(2.0, 30.0, n) * cap_factor, 0, 400), 0),
        "dist_gas_km": np.round(rng.gamma(1.6, 6.0, n), 1),
        "flood_zone": (rng.random(n) < 0.15).astype(int),
        "zoning": rng.choice(["Industrial", "Agricultural", "Mixed / PUD"], n, p=[0.3, 0.55, 0.15]),
    })
    mult = np.where(df.zoning == "Industrial", 2.5, np.where(df.zoning == "Mixed / PUD", 1.8, 1.0))
    df["land_usd_per_acre"] = np.round(loc["land_usd"] * mult * rng.lognormal(0, 0.3, n), -1)
    df["source"] = "ILLUSTRATIVE"
    return df


def score_parcels(df: pd.DataFrame, needs_gas: bool) -> pd.DataFrame:
    d = df.copy()
    d["gate_acres"] = d.acres >= MIN_ACRES
    d["gate_flood"] = d.flood_zone.astype(int) == 0
    d["gate_power"] = (d.substation_spare_mw >= FIRST_PHASE_MW) | (d.dist_gas_km <= 15)
    d["gate_gas"] = (d.dist_gas_km <= 25) if needs_gas else True
    d["passes"] = d.gate_acres & d.gate_flood & d.gate_power & d.gate_gas
    s_power = np.clip(d.substation_spare_mw / 75, 0, 1) * 35 + np.clip(1 - d.dist_substation_km / 30, 0, 1) * 10
    s_gas = np.clip(1 - d.dist_gas_km / 30, 0, 1) * (20 if needs_gas else 8)
    s_land = np.clip(1 - np.log10(np.clip(d.land_usd_per_acre, 500, 1e6) / 500) / 2.0, 0, 1) * 15
    s_size = np.clip(d.acres / 150, 0, 1) * 10
    s_zone = np.where(d.zoning == "Industrial", 10, np.where(d.zoning == "Mixed / PUD", 6, 3))
    d["parcel_score"] = np.round((s_power + s_gas + s_land + s_size + s_zone) / (100 if needs_gas else 88) * 100, 0)
    d.loc[~d.passes, "parcel_score"] = np.minimum(d.loc[~d.passes, "parcel_score"], 35)
    return d.sort_values("parcel_score", ascending=False)


def location_score(loc: dict, result, parcels: pd.DataFrame, weights: tuple) -> dict:
    """weights = (speed, cost, clean) preference sliders."""
    ws, wc, we = [max(x, 0) for x in weights]
    tot = ws + wc + we or 1.0
    m = result.metrics if result is not None and result.metrics else None
    feasible = result is not None and result.status == "ok"
    comp = {}
    if m:
        cost = m["decision_cost_usd_per_requested_mwh"]
        kg = m["combined_electricity_co2_kg_per_mwh"]
        comp["Cost"] = (float(np.clip(100 * (110 - cost) / 70, 0, 100)), f"{cost:.2f} $/MWh modeled")
        comp["Carbon"] = (float(np.clip(100 * (500 - kg) / 500, 0, 100)), f"{kg:.0f} kg CO₂/MWh modeled")
    else:
        comp["Cost"] = (0.0, "no feasible portfolio")
        comp["Carbon"] = (0.0, "no feasible portfolio")
    comp["Speed to power"] = (float(np.clip(100 * (1 - loc["delay"] / 36), 0, 100)) if feasible else 0.0,
                              f"+{loc['delay']} months grid wait vs benchmark")
    share = float(parcels.passes.mean()) if len(parcels) else 0.0
    top = float(parcels.parcel_score.head(5).mean()) if len(parcels) else 0.0
    comp["Land & parcels"] = (0.5 * share * 100 + 0.5 * top, f"{share:.0%} of parcels pass gates; top-5 avg {top:.0f}")
    comp["Water"] = (float(WATER_SCORE[int(loc["water"])]), f"stress tier {loc['water']}/5")
    pol = loc.get("policy", "")
    restrictive = any(w in pol.lower() for w in ("restriction", "moratorium", "allocated", "queue"))
    comp["Policy & permitting"] = (40.0 if restrictive else (75.0 if pol else 90.0), pol or "no flagged large-load rule")
    wmap = {"Cost": 60 * wc / tot, "Speed to power": 60 * ws / tot, "Carbon": 60 * we / tot,
            "Land & parcels": 15, "Water": 10, "Policy & permitting": 15}
    total = sum(comp[k][0] * wmap[k] for k in comp) / 100
    if not feasible:
        verdict = "Blocked within catalog"
    elif total >= 70:
        verdict = "Strong"
    elif total >= 50:
        verdict = "Conditional"
    else:
        verdict = "Weak"
    conf = "High (benchmark data)" if loc["benchmark"] else ("Low (country defaults)" if loc["coarse"] else "Medium (state indices)")
    return dict(score=round(total, 1), verdict=verdict, confidence=conf, components=comp, weights=wmap)


def price_forecast(loc: dict) -> pd.DataFrame:
    ctx = context(20, 0, (), "" if loc["benchmark"] else loc["key"])
    p = ctx["grid_price"]
    mh = np.arange(len(p))
    df = pd.DataFrame({"month": mh // CASE["hours_per_model_month"], "year": mh // 8760 + 1, "price": p})
    monthly = df.groupby("month").price.agg(["mean", lambda s: s.quantile(0.95), "max"]).reset_index()
    monthly.columns = ["month", "avg", "p95", "max"]
    return monthly


def parse_locations(text: str) -> list:
    out = []
    for part in [x.strip() for x in text.replace(";", ",").replace("\n", ",").split(",")]:
        if part:
            loc = resolve(part)
            out.append((part, loc))
    return out
