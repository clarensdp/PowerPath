"""
PowerPath - energy portfolio decision terminal (GRIDTECH packet v5.5.1)
Run from the packet folder:  streamlit run team_app/app.py
"""
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gridpilot.engine import RES, LABELS, OPT, CASE, context, ETA, cs  # noqa: E402
from gridpilot.advisor import decision_flips, execution_shifts, MAX_VALUE_PER_MONTH, MAX_CARBON_PRICE, CODE_VERSION  # noqa: E402
from gridpilot.analytics import curtailment, clean_coverage, spikes, n1_check, FORCED_OUTAGE_RATE, SPIKE_USD  # noqa: E402
from gridpilot.advisor import (Preferences, Requirements, Options, recommend, money,  # noqa: E402
                               ANCHOR_VALUE_PER_MONTH, ANCHOR_CARBON_PRICE, STRESS_HOURS)
from gridpilot.export import summary_md, portfolio_dict  # noqa: E402
from gridpilot.execution import plan as exec_plan, sb6_check, DEFAULT_STEPS, SITE_STEPS  # noqa: E402

st.set_page_config(page_title="PowerPath", layout="wide", page_icon="⚡")
import plotly.io as pio  # noqa: E402
from gridpilot.regions import resolve, STATES as _ST  # noqa: E402
from gridpilot.interconnect import profile_for, energization, deliverable_power, decide  # noqa: E402
from gridpilot.deals import DealInputs, build as build_deals  # noqa: E402
from gridpilot.monitor import triggers as build_triggers  # noqa: E402
from gridpilot.advisor import cached_run, make_scenario, region_delay, ref_mwh  # noqa: E402
from gridpilot.screener import (scenario_for, illustrative_parcels, score_parcels, location_score,  # noqa: E402
                                price_forecast, parse_locations, PARCEL_COLUMNS, MIN_ACRES)

# ---------------- terminal look ----------------
AMBER, CYAN, BG, PANEL, GRID = "#FFB000", "#4FC3F7", "#0A0E14", "#111821", "#1E2A36"
pio.templates["powerpath"] = go.layout.Template(layout=dict(
    paper_bgcolor=BG, plot_bgcolor=BG, font=dict(family="IBM Plex Mono, Menlo, monospace", color="#D7DCE2", size=12),
    xaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
    yaxis=dict(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID),
    colorway=[AMBER, CYAN, "#66BB6A", "#EF5350", "#AB47BC", "#FFA726", "#26C6DA"],
    legend=dict(bgcolor="rgba(0,0,0,0)")))
pio.templates.default = "plotly_dark+powerpath"
# plotly >= 5.24 ships MapLibre "Scattermap"; older versions only have "Scattermapbox"
MapTrace = getattr(go, "Scattermap", None) or getattr(go, "Scattermapbox")
MAP_KEY = "map" if getattr(go, "Scattermap", None) else "mapbox"
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stDataFrame, input, textarea, button, select {{
  font-family: 'IBM Plex Mono', Menlo, Consolas, monospace !important; }}
.stApp {{ background: {BG}; }}
section[data-testid="stSidebar"] {{ background: #070A0F; border-right: 1px solid {GRID}; }}
h1, h2, h3 {{ color: {AMBER} !important; letter-spacing: .04em; text-transform: uppercase; }}
h1 {{ font-size: 1.35rem !important; }} h2, h3 {{ font-size: 1.0rem !important; }}
div[data-testid="stMetric"] {{ background: {PANEL}; border: 1px solid {GRID}; border-left: 3px solid {AMBER};
  padding: 8px 10px; border-radius: 2px; }}
div[data-testid="stMetricValue"] {{ color: {AMBER}; font-size: 1.25rem; }}
div[data-testid="stMetricLabel"] p {{ color: #8FA3B8; text-transform: uppercase; font-size: .68rem; letter-spacing: .06em; }}
button[data-baseweb="tab"] p {{ font-size: .74rem; letter-spacing: .05em; text-transform: uppercase; }}
button[data-baseweb="tab"][aria-selected="true"] p {{ color: {AMBER}; }}
div[data-baseweb="tab-highlight"] {{ background-color: {AMBER} !important; }}
.pp-ticker {{ overflow: hidden; white-space: nowrap; border-top: 1px solid {GRID}; border-bottom: 1px solid {GRID};
  background: #05080C; padding: 4px 0; margin: -8px 0 10px 0; }}
.pp-ticker span.inner {{ display: inline-block; padding-left: 100%; animation: pp-scroll 45s linear infinite; }}
.pp-ticker b {{ color: {AMBER}; font-weight: 600; }} .pp-ticker i {{ color: {CYAN}; font-style: normal; }}
@keyframes pp-scroll {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-100%); }} }}
.pp-brand {{ color: {AMBER}; font-weight: 600; letter-spacing: .18em; font-size: 1.05rem; }}
.pp-sub {{ color: #8FA3B8; font-size: .7rem; letter-spacing: .08em; }}
</style>""", unsafe_allow_html=True)

COL = {"gas_turbine": "#8c6d4f", "gas_engine": "#b5835a", "fuel_cell": "#d9a66b",
       "utility_solar": "#f2c14e", "wind": "#5fa8d3", "nuclear": "#7b5ea7",
       "battery_4h": "#2a9d8f", "grid": "#9aa5b1", "r1": "#e76f51", "i2": "#c0392b"}
FLOW = {"nuclear": "nuclear_mw", "wind": "wind_mw", "utility_solar": "utility_solar_mw",
        "grid": "grid_mw", "gas_turbine": "gas_turbine_mw", "gas_engine": "gas_engine_mw",
        "fuel_cell": "fuel_cell_mw", "battery_4h": "battery_4h_discharge_mw"}
SHORT = {"utility_solar": "Solar", "wind": "Wind", "battery_4h": "Battery", "gas_turbine": "Turbine",
         "nuclear": "Nuclear", "gas_engine": "Engines", "fuel_cell": "Fuel cells"}
FLAB = {**LABELS, "grid": "Merchant grid", "battery_4h": "Battery discharge",
        "r1": "Tier 1 relocated", "i2": "Tier 2 interrupted"}


@st.cache_resource(max_entries=60, show_spinner=False)
def compute(prefs_t, req_t, opt_t):
    return recommend(Preferences(**dict(prefs_t)), Requirements(**dict(req_t)), Options(**dict(opt_t)))


# ------------------------------------------------------------------------------------
PRESETS = {
    "— custom —": {},
    "Default priorities: balanced (opening optimized)": dict(speed=34, cost=33, env=33),
    "1 · Speed: full demand by month 24": dict(use_full=True, full=24, speed=60, cost=30, env=10),
    "2 · Cost: lowest cost, full demand as late as 36": dict(use_full=True, full=36, speed=0, cost=100, env=0, lo=14, hi=26),
    "3 · Clean: under 100 kg/MWh, earliest date": dict(use_int=True, intensity=100, speed=80, cost=20, env=0),
    "4 · Continuity: zero Tier 2 interruption": dict(no_t2=True, speed=34, cost=33, env=33),
    "5 · Grid slips 6 months: keep full demand by 24?": dict(delay=6, use_full=True, full=24, speed=60, cost=30, env=10),
    "6 · Pay ≤10% more for full demand at 24 vs 30": dict(use_full=True, full=24, use_prem=True, prem=10, speed=50, cost=40, env=10),
    "7 · Reliability: survive loss of the largest onsite unit": dict(use_n1=True, speed=34, cost=33, env=33),
    "8 · Execution-aware: order from today (month 0)": dict(exec_aware=True, today=0, speed=34, cost=33, env=33),
}
DEFAULTS = dict(use_full=False, full=30, use_open=False, open=20, use_int=False, intensity=150,
                use_clean=False, clean=60, use_merch=False, merch=30, use_budget=False, budget=400,
                no_t2=False, allow_t1=True, excluded=[], use_prem=False, prem=10,
                speed=34, cost=33, env=33, delay=0, lo=14, hi=26, step=2,
                slip_res="none", slip_m=0, today=0, exec_aware=False, use_n1=False,
                deal_cap_on=False, deal_cap=150, deal_obs=False,
                ov=False, ov_v=5.0, ov_c=100)
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)
S = st.session_state


def apply_preset():
    cfg = PRESETS[S.preset]
    if not cfg:
        return
    for k, v in DEFAULTS.items():
        S[k] = v
    for k, v in cfg.items():
        S[k] = v
    S.force_run = True


def set_site(key, label):
    S.site_key, S.site_label, S.force_run = key, label, True


def make_exec_aware():
    S.exec_aware, S.force_run = True, True


def add_n1():
    S.use_n1, S.force_run = True, True


def apply_grid_delay(months):
    # runs as a callback, before the sidebar slider is drawn on the next rerun
    S.delay, S.force_run = int(months), True


def set_slip(res, months):
    S.slip_res, S.slip_m, S.force_run = res, months, True


def req_row(label, flag, key, lo, hi, step=1, help=None):
    c1, c2 = st.columns([1.25, 1])
    c1.checkbox(label, key=flag, help=help)
    c2.number_input(label, lo, hi, step=step, key=key, label_visibility="collapsed",
                    disabled=not S[flag])


with st.sidebar:
    st.markdown('<div class="pp-brand">⚡ POWERPATH</div><div class="pp-sub">SITE · POWER · EXECUTION TERMINAL</div>', unsafe_allow_html=True)
    act = S.get("site_label", "Williamson County, TX (benchmark)")
    st.markdown(f"**ACTIVE SITE** `{act}`")
    if S.get("site_key"):
        st.button("↺ Back to benchmark site", on_click=set_site, args=("", "Williamson County, TX (benchmark)"))
    st.selectbox("Start from a customer question", list(PRESETS), key="preset", on_change=apply_preset)
    st.markdown("### 1 · Must-haves")
    st.caption("Hard requirements. Never traded away. If nothing meets them, the tool says what to relax.")
    req_row("Full demand by month", "use_full", "full", 24, 60)
    req_row("Open by month", "use_open", "open", 14, 50)
    req_row("Max kg CO₂/MWh", "use_int", "intensity", 0, 400, 10,
            help="Combined electricity intensity, including the remote site's emissions for relocated load.")
    req_row("Min clean share %", "use_clean", "clean", 0, 100, 5)
    req_row("Max merchant share %", "use_merch", "merch", 0, 100, 5)
    req_row("Max total cost $M", "use_budget", "budget", 0, 2000, 10)
    req_row("Max premium %", "use_prem", "prem", 0, 100, 1,
            help="Versus the cheapest portfolio that opens at month 20 (full demand month 30).")
    st.checkbox("Survive loss of the largest onsite unit (N-1)", key="use_n1",
                help="Every hour stays servable with one block of the biggest onsite unit out, using only "
                     "permitted Tier 1/Tier 2 flexibility, the import limit and the other onsite units.")
    st.checkbox("No Tier 2 interruption", key="no_t2")
    st.checkbox("Allow Tier 1 relocation", key="allow_t1")
    st.multiselect("Exclude resources", RES, key="excluded", format_func=lambda k: LABELS[k])

    st.markdown("### 2 · Nice-to-haves")
    st.caption("Preferences. Traded against each other and translated into dollars you can check.")
    st.slider("Speed to power", 0, 100, key="speed", help="Preference, not a deadline. Increases the value assigned to earlier initial service. Expand How it works for the scoring method.")
    st.slider("Low cost", 0, 100, key="cost", help="Relative preference for lower normalized decision cost. Hard budgets belong in Must-haves.")
    st.slider("Clean energy", 0, 100, key="env", help="Preference for avoiding CO₂. A maximum emissions intensity is a separate hard requirement.")
    prefs = Preferences(S.speed, S.cost, S.env,
                        override_value=S.ov_v * 1e6 if S.ov else None,
                        override_carbon=float(S.ov_c) if S.ov else None)
    v_imp, lam_imp = prefs.implied()
    st.info(f"These weights mean opening **one month earlier is worth {money(v_imp)}** and "
            f"**avoiding a tonne of CO₂ is worth ${lam_imp:,.0f}**.")
    if not S.ov and (v_imp >= MAX_VALUE_PER_MONTH - 1 or lam_imp >= MAX_CARBON_PRICE - 1):
        st.caption(f"Capped at {money(MAX_VALUE_PER_MONTH)}/month and ${MAX_CARBON_PRICE:,.0f}/t; type exact values below to go higher.")
    with st.expander("Set the dollar values directly"):
        st.checkbox("Override", key="ov")
        st.number_input("$M per month earlier", 0.0, 50.0, step=0.5, key="ov_v")
        st.number_input("$ per tonne CO₂", 0, 1000, step=10, key="ov_c")

    st.markdown("### 3 · Scenario")
    st.slider("Grid connection delay (months)", 0, 12, key="delay", help="Optional sensitivity: moves grid connection milestones, not the benchmark baseline.")
    st.selectbox("Equipment / permit slip", ["none"] + RES, key="slip_res",
                 format_func=lambda k: "none" if k == "none" else LABELS[k],
                 help="Execution risk: this resource arrives late (procurement or permit delay). "
                      "The no-slip benchmark stays the comparison anchor.")
    st.slider("Slip (months late)", 0, 36, key="slip_m", disabled=S.slip_res == "none")
    st.checkbox("Execution-aware: respect lead times from today", key="exec_aware",
                help="Each resource can run no earlier than today + its permit/procurement/build lead time "
                     "(editable planning assumptions in the Execution plan tab). Off = catalog offer dates, "
                     "i.e. delivery slots assumed secured.")
    st.slider("Today is development month", 0, 24, key="today", disabled=not S.exec_aware)
    c1, c2, c3 = st.columns(3)
    c1.number_input("Open from", 14, 60, key="lo")
    c2.number_input("to", 14, 60, key="hi")
    c3.number_input("step", 1, 6, key="step")
    go_btn = st.button("Recommend a portfolio", type="primary", width="stretch")

req = Requirements(full_demand_by=S.full if S.use_full else None,
                   open_by=S.open if S.use_open else None,
                   max_intensity_kg=float(S.intensity) if S.use_int else None,
                   min_clean_share=S.clean / 100 if S.use_clean else None,
                   max_merchant_share=S.merch / 100 if S.use_merch else None,
                   budget_musd=float(S.budget) if S.use_budget else None,
                   no_tier2=S.no_t2, allow_tier1=S.allow_t1, excluded=tuple(S.excluded),
                   max_premium_pct=float(S.prem) if S.use_prem else None, n_minus_1=S.use_n1)
opt = Options(earliest_open=int(S.lo), latest_open=int(S.hi), step=int(S.step),
              grid_delay=int(S.delay), workers=min(4, os.cpu_count() or 1),
              slips=((S.slip_res, int(S.slip_m)),) if S.slip_res != "none" and S.slip_m > 0 else (),
              region=S.get("site_key", ""), execution_aware=bool(S.exec_aware), today=int(S.today) if S.exec_aware else 0,
              lead_overrides=tuple(sorted((k, v["permit"], v["procure"], v["build"])
                                          for k, v in S.get("lead_overrides", {}).items())) if S.exec_aware else ())
key = tuple(tuple(sorted(asdict(x).items())) for x in (prefs, req, opt))
if go_btn or S.pop("force_run", False) or "rec_key" not in S:
    S.rec_key = key
if S.rec_key != key:
    st.warning("Inputs changed. Press **Recommend a portfolio** to update.")
# ---- loading screen: draw the shell immediately so the page never looks blank ----
import time as _time  # noqa: E402
_boot = st.empty()
with _boot.container():
    st.markdown(f"# PowerPath ⟩ {S.get('site_label', 'Williamson County, TX (benchmark)')}")
    st.markdown('<div style="display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border-bottom:1px solid #1C2633;margin-bottom:10px">'
                + "".join(f'<div style="padding:6px 10px;color:#8FA3B8;font-size:.72rem;letter-spacing:.12em">{n}<div style="color:#3b4a5c;font-size:.9rem;letter-spacing:0">computing…</div></div>'
                          for n in ["1 · SCREEN", "2 · INTERCONNECT", "3 · GENERATE", "4 · STRUCTURE", "5 · MONITOR"]) + "</div>",
                unsafe_allow_html=True)
    _msg = st.empty()
    _msg.info("**Sizing portfolios and checking all 87,600 hours.** The first run for a new set of inputs takes about "
              "1–3 minutes; repeat views are instant. Tip: run `python team_app/run.py warm` before a demo.")
    _bar = st.progress(5, text="Optimizing each opening month…")
_t0 = _time.time()
rec = compute(*S.rec_key)
best = rec.best
_boot.empty()


@st.cache_resource(max_entries=40, show_spinner=False)
def analyze(_r, key_):
    return dict(curt=curtailment(_r), cov=clean_coverage(_r), spk=spikes(_r), n1=n1_check(_r))


AN = analyze(best, (S.rec_key, best.scenario.initial_service_month, tuple(sorted(best.caps.items())))) if best is not None else None

site_label = S.get("site_label", "Williamson County, TX (benchmark)")
st.markdown(f"# PowerPath ⟩ {site_label}")
_tk = []
if best is not None:
    _m = best.metrics
    _tk = [f"<b>PORT</b> open M{best.scenario.initial_service_month} / full M{best.scenario.initial_service_month + 10}",
           f"<b>COST</b> <i>{_m['decision_cost_usd_per_requested_mwh']:.2f}</i> $/MWh",
           f"<b>CO2</b> <i>{_m['combined_electricity_co2_kg_per_mwh']:.0f}</i> kg/MWh",
           f"<b>CLEAN</b> <i>{_m['clean_energy_share'] * 100:.0f}%</i>",
           f"<b>TOTAL</b> <i>{money(_m['total_decision_cost_usd'])}</i>",
           f"<b>MIX</b> " + " ".join(f"{SHORT[k].upper()} <i>{c:.0f}MW</i>" for k, c in best.caps.items() if c > 0)]
_pf = context(20, 0, (), S.get("site_key", ""))["grid_price"]
_tk += [f"<b>MERCHANT Y1</b> <i>{_pf[:8760].mean():.1f}</i> $/MWh", f"<b>MERCHANT Y10</b> <i>{_pf[-8760:].mean():.1f}</i> $/MWh",
        f"<b>PEAK</b> <i>{_pf.max():,.0f}</i> $/MWh", f"<b>ENGINE</b> <i>{CODE_VERSION}</i>"]
st.markdown('<div class="pp-ticker"><span class="inner">' + " &nbsp;│&nbsp; ".join(_tk * 2) + "</span></div>",
            unsafe_allow_html=True)
if S.get("site_key"):
    st.warning("Screening site active: results use regionally scaled benchmark inputs and PowerPath's mirror of the "
               "checker formulas. The official submission remains the Williamson County benchmark.")
# ---------------- stage computations (one decision layer) ----------------
@st.cache_resource(max_entries=30, show_spinner=False)
def interconnect_stage(rec_key):
    prefs_, req_, opt_ = (Preferences(**dict(rec_key[0])), Requirements(**dict(rec_key[1])), Options(**dict(rec_key[2])))
    v_, lam_ = prefs_.implied()
    site = resolve(opt_.region[3:]) if opt_.region.startswith("US-") else (resolve(opt_.region[2:]) if opt_.region.startswith("C-") else resolve("TX"))
    grid_name = site["grid"] if site else "ERCOT"
    spread, upg, path = profile_for(grid_name)
    delay = opt_.grid_delay + region_delay(opt_)
    en = energization(delay, spread)
    s_wait = int(min(109, max(14, 18 + delay)))
    target = (req_.full_demand_by - 10) if req_.full_demand_by else (req_.open_by if req_.open_by else 20)
    s_bridge = int(min(109, max(14, target)))
    from dataclasses import replace as _r
    req_free = _r(req_, full_demand_by=None, open_by=None)
    wait = cached_run(make_scenario(s_wait, req_free, opt_, lam_))
    bridge = cached_run(make_scenario(s_bridge, req_free, opt_, lam_)) if s_bridge < s_wait else None
    best_ = compute(*rec_key).best
    p90 = None
    if best_ is not None:
        p90 = cached_run(make_scenario(best_.scenario.initial_service_month, req_free,
                                       _r(opt_, grid_delay=opt_.grid_delay + (en["P90"] - en["P50"])), lam_))
    dec = decide(best_, wait, bridge if bridge is not None else wait, v_, ref_mwh())
    return dict(grid=grid_name, spread=spread, upgrade_usd_kw=upg, path=path, delay=delay, en=en,
                wait=wait, bridge=bridge, p90=p90, decision=dec, s_wait=s_wait, s_bridge=s_bridge)


with st.spinner("Checking interconnection options and the P90 grid slip…"):
    IC = interconnect_stage(S.rec_key) if best is not None else None
DEAL_IN = DealInputs(max_upfront_musd=float(S.get("deal_cap", 150)) if S.get("deal_cap_on", False) else None,
                     prefer_off_balance_sheet=bool(S.get("deal_obs", False)))
DEALS = build_deals(best, IC["delay"], DEAL_IN) if best is not None else None
TRIG = build_triggers(best, IC["p90"], IC["en"]) if best is not None else []
site_rec = None
if S.get("site_key"):
    k_ = S["site_key"]
    site_rec = resolve(k_[3:]) if k_.startswith("US-") else resolve(k_[2:])
else:
    site_rec = resolve("78626")

# ---------------- stage bar ----------------
def _card(n, name, verdict, sub, tone):
    col = {"good": "#5BD17A", "warn": "#F2A93B", "bad": "#F05454", "info": "#4FC3F7"}[tone]
    return (f'<div style="flex:1 1 170px;min-width:0;background:#0D1218;border:1px solid #1C2633;border-top:3px solid {col};padding:7px 10px">'
            f'<div style="font-size:.66rem;letter-spacing:.12em;color:#8FA3B8">{n} · {name}</div>'
            f'<div style="color:{col};font-weight:600;font-size:.95rem">{verdict}</div>'
            f'<div style="font-size:.7rem;color:#8FA3B8">{sub}</div></div>')


if best is not None:
    _sc_label = S.get("site_label", "Williamson County, TX (benchmark)")
    _dl = IC["decision"]
    _pick = DEALS[1]
    _high = sum(1 for t in TRIG if t["severity"] == "high")
    cards = [
        _card("1", "SCREEN", "Benchmark site" if not S.get("site_key") else "Screened site", _sc_label[:38], "info"),
        _card("2", "INTERCONNECT", _dl["verdict"], f"grid P50 +{IC['en']['P50']}m · P90 +{IC['en']['P90']}m · {IC['grid']}",
              "good" if _dl["verdict"] in ("WAIT", "BRIDGE") else "bad"),
        _card("3", "GENERATE", f"Open M{best.scenario.initial_service_month} · {best.metrics['decision_cost_usd_per_requested_mwh']:.2f} $/MWh",
              ", ".join(f"{c:.0f} {SHORT[k].lower()}" for k, c in best.caps.items() if c > 0), "good"),
        _card("4", "STRUCTURE", (_pick["structure"].split(" (")[0] if _pick else "No fit"), DEALS[2][:60], "good" if _pick else "bad"),
        _card("5", "MONITOR", f"{len(TRIG)} triggers armed", f"{_high} high-severity", "warn" if _high else "good"),
    ]
    st.markdown('<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:6px">' + "".join(cards) + "</div>",
                unsafe_allow_html=True)

if best is not None:
    with st.sidebar:
        st.markdown("### DECISION LEDGER")
        _dl = IC["decision"]
        _pk = DEALS[1]
        led = [("Site", S.get("site_label", "Williamson County, TX (benchmark)")),
               ("Grid region", f"{IC['grid']} · P50 +{IC['en']['P50']}m"),
               ("Interconnect", _dl["verdict"]),
               ("Opening", f"M{best.scenario.initial_service_month} → full M{best.scenario.initial_service_month + 10}"),
               ("Portfolio", ", ".join(f"{c:.0f} {SHORT[k].lower()}" for k, c in best.caps.items() if c > 0)),
               ("Cost / carbon", f"{best.metrics['decision_cost_usd_per_requested_mwh']:.2f} $/MWh · {best.metrics['combined_electricity_co2_kg_per_mwh']:.0f} kg"),
               ("Structure", _pk["structure"] if _pk else "none fits"),
               ("Valuations", f"{money(rec.value_per_month)}/mo · ${rec.carbon_price:,.0f}/t"),
               ("Triggers", f"{len(TRIG)} armed")]
        st.markdown("\n".join(f"- **{a}**: {b}" for a, b in led))

T_SCREEN, T_IC, T_GEN, T_STRUCT, T_EXMON, TAB_HOW, TAB_EXP = st.tabs(
    ["1 ⟩ SCREEN", "2 ⟩ INTERCONNECT", "3 ⟩ GENERATE", "4 ⟩ STRUCTURE", "5 ⟩ EXECUTE & MONITOR", "METHOD", "EXPORT"])
TAB_SITE = T_SCREEN
with T_GEN:
    TAB_REC, TAB_EXPLAIN, TAB_TRADE, TAB_STRESS = st.tabs(["Recommendation", "Explain", "Speed · cost · CO₂", "Stress & N-1"])
with T_STRUCT:
    TAB_DEAL, TAB_YEAR = st.tabs(["Deal structures", "Cost & carbon by year"])
with T_EXMON:
    TAB_EXEC, TAB_MON, TAB_FEAS, TAB_CMP = st.tabs(["Execution plan", "Watchlist & triggers", "Diligence", "Compare scenarios"])
anchor = None
if opt.slips or opt.grid_delay:
    from dataclasses import replace as _rp
    akey = (S.rec_key[0], S.rec_key[1], tuple(sorted(asdict(_rp(opt, slips=(), grid_delay=0)).items())))
    with st.spinner("Computing the no-slip benchmark anchor…"):
        anchor = compute(*akey).best

# ====================================================================================
@st.cache_resource(max_entries=30, show_spinner=False)
def screen(queries: tuple, lam: float, n1: bool, workers: int):
    from gridpilot.advisor import run_many
    locs = [(q, resolve(q)) for q in queries]
    good = [(q, l) for q, l in locs if l is not None]
    res = run_many([scenario_for(l, lam, 20, n1) for _, l in good], workers)
    return locs, dict(zip([l["key"] + l.get("zip", "") for _, l in good], res))


with TAB_SITE:
    st.subheader("Location screener · any US ZIP, state, or major country")
    st.caption("The 87,600-hour benchmark is ground truth. Each location re-runs the same engine for the default "
               "customer (opening month 20, your carbon price) on benchmark hourly shapes scaled by regional "
               "price, grid CO₂ and renewable indices, with the regional grid-connection wait applied.")
    c1, c2, c3 = st.columns([3, 1, 1])
    qtext = c1.text_input("Locations (comma-separated)", value=S.get("site_query", "78626, 20147, Iowa, Ohio, Ireland"),
                          key="site_query", help="Examples: 78626 (Georgetown TX), 20147 (Ashburn VA), Iowa, OK, Ireland, Japan")
    n1_scr = c2.checkbox("Screen with N-1", key="scr_n1", help="Require surviving the largest-unit outage at every site.")
    c3.write("")
    run_scr = c3.button("SCREEN ⟩ GO", type="primary", width="stretch")
    if run_scr or "scr_key" not in S:
        S.scr_key = (tuple(q for q, _ in parse_locations(qtext))[:6], float(rec.carbon_price), bool(n1_scr))
    with st.spinner("Running the 87,600-hour engine for each location…"):
        locs, results = screen(*S.scr_key, min(4, os.cpu_count() or 1))
    bad = [q for q, l in locs if l is None]
    if bad:
        st.warning("Not recognised: " + ", ".join(bad) + ". Use a US ZIP, a state name/code, or one of: "
                   "Canada, UK, Ireland, Germany, Netherlands, France, Spain, Sweden, Norway, Finland, Japan, "
                   "Singapore, India, Australia, Brazil, Mexico, UAE.")
    up = st.file_uploader("Optional: real parcel CSV for the selected location (columns: " + ", ".join(PARCEL_COLUMNS) + ")",
                          type=["csv"], key="parcel_csv")
    rank_by = st.radio("Rank by", ["Deliverable power", "Feasibility score"], horizontal=True, key="rank_by",
                       help="Deliverable power: earliest month the grid can carry the full 75 MW, then least bridge "
                            "power needed. Feasibility: the weighted score.")
    rows, details = [], {}
    wts = (S.speed, S.cost, S.env)
    for q, l in locs:
        if l is None:
            continue
        r = results[l["key"] + l.get("zip", "")]
        needs_gas = bool(r.caps and any(r.caps.get(k, 0) > 0 for k in ("gas_turbine", "gas_engine", "fuel_cell")))
        par = score_parcels(illustrative_parcels(l), needs_gas)
        sc_ = location_score(l, r, par, wts)
        details[q] = (l, r, par, sc_)
        mm = r.metrics or {}
        rows.append({"Location": f"{l['label']}" + (f" ({l['zip']})" if l.get("zip") else ""), "Grid": l["grid"],
                     "Score": sc_["score"], "Verdict": sc_["verdict"], "Confidence": sc_["confidence"],
                     "$/MWh": round(mm.get("decision_cost_usd_per_requested_mwh") or 0, 2),
                     "kg/MWh": round(mm.get("combined_electricity_co2_kg_per_mwh") or 0),
                     "Grid wait": f"+{l['delay']}m",
                     "Grid full": f"M{30 + int(l['delay'])}",
                     "Bridge MW": round(deliverable_power(r, int(l["delay"]))["bridge_mw"]) if r.caps else None,
                     "Portfolio": ", ".join(f"{c:.0f} {SHORT[k].lower()}" for k, c in (r.caps or {}).items() if c > 0) or "–"})
    if rows:
        tbl = pd.DataFrame(rows)
        if rank_by == "Deliverable power":
            tbl["_g"] = tbl["Grid full"].str[1:].astype(int)
            tbl = tbl.sort_values(["_g", "Bridge MW", "Score"], ascending=[True, True, False]).drop(columns="_g")
        else:
            tbl = tbl.sort_values("Score", ascending=False)
        st.dataframe(tbl, hide_index=True, width="stretch",
                     column_config={"Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%.0f")})
        # stacked contribution chart
        f = go.Figure()
        comps = ["Cost", "Speed to power", "Carbon", "Land & parcels", "Water", "Policy & permitting"]
        palette = [AMBER, CYAN, "#66BB6A", "#AB47BC", "#26C6DA", "#EF5350"]
        names = [details[q][0]["label"] for q in details]
        for cmp_, colr in zip(comps, palette):
            f.add_bar(y=names, x=[details[q][3]["components"][cmp_][0] * details[q][3]["weights"][cmp_] / 100 for q in details],
                      name=cmp_, orientation="h", marker_color=colr)
        f.update_layout(barmode="stack", height=90 + 46 * len(names), xaxis_title="Feasibility score (0–100), contribution by component",
                        legend=dict(orientation="h", y=1.25), margin=dict(t=50, l=10))
        st.plotly_chart(f, width="stretch")
        sel = st.selectbox("Inspect location", list(details), format_func=lambda q: details[q][0]["label"] +
                           (f" ({details[q][0]['zip']})" if details[q][0].get("zip") else ""))
        l, r, par, sc_ = details[sel]
        if up is not None:
            try:
                upl = pd.read_csv(up)
                miss = [c for c in PARCEL_COLUMNS if c not in upl.columns]
                if miss:
                    st.error("Parcel CSV missing columns: " + ", ".join(miss))
                else:
                    upl["source"] = "UPLOADED"
                    par = score_parcels(upl, bool(any(r.caps.get(k, 0) > 0 for k in ("gas_turbine", "gas_engine", "fuel_cell"))))
                    sc_ = location_score(l, r, par, wts)
                    st.success(f"Scored {len(par)} uploaded parcels for {l['label']}.")
            except Exception as e:
                st.error(f"Could not read parcel CSV: {e}")
        k = st.columns(5)
        k[0].metric("Feasibility score", f"{sc_['score']:.0f}/100", sc_["verdict"], delta_color="off")
        k[1].metric("Confidence", sc_["confidence"].split(" (")[0], sc_["confidence"].split("(")[-1].rstrip(")"), delta_color="off")
        mm = r.metrics or {}
        k[2].metric("Modeled cost", f"{mm.get('decision_cost_usd_per_requested_mwh', 0):.2f} $/MWh")
        k[3].metric("Modeled intensity", f"{mm.get('combined_electricity_co2_kg_per_mwh', 0):.0f} kg/MWh")
        k[4].metric("Parcels passing gates", f"{int(par.passes.sum())}/{len(par)}", par.source.iloc[0] if len(par) else "", delta_color="off")
        left, right = st.columns([1.15, 1])
        with left:
            fm = go.Figure()
            fm.add_trace(MapTrace(lat=par.lat, lon=par.lon, mode="markers",
                                          marker=dict(size=np.clip(par.acres / 25, 5, 18), color=par.parcel_score,
                                                      colorscale=[[0, "#3A1C1C"], [0.5, "#7A5B00"], [1, AMBER]], cmin=0, cmax=100,
                                                      colorbar=dict(title="parcel")),
                                          text=[f"{a.parcel_id} · {a.acres:.0f} ac · {a.substation_spare_mw:.0f} MW spare · "
                                                f"gas {a.dist_gas_km:.0f} km · {a.zoning}{' · FLOOD' if a.flood_zone else ''}"
                                                for a in par.itertuples()], hoverinfo="text", name="parcels"))
            fm.add_trace(MapTrace(lat=[l["lat"]], lon=[l["lon"]], mode="markers+text", text=[l["label"]],
                                          marker=dict(size=14, color=CYAN), textposition="top right", name="location"))
            fm.update_layout(**{MAP_KEY: dict(style="carto-darkmatter", center=dict(lat=l["lat"], lon=l["lon"]),
                                              zoom=8.5 if l.get("zip") else (3.5 if l["kind"] == "country" else 5.5))},
                             height=420, margin=dict(l=0, r=0, t=0, b=0), showlegend=False)
            st.plotly_chart(fm, width="stretch")
            st.caption("Parcels are ILLUSTRATIVE unless you upload a CSV. Gates: ≥%d acres, outside flood zone, "
                       "≥25 MW substation headroom or gas within 15 km, gas within 25 km if the portfolio burns gas." % MIN_ACRES)
        with right:
            comp = pd.DataFrame([{"Component": c, "Score": round(v[0]), "Weight %": round(sc_["weights"][c]), "Basis": v[1]}
                                 for c, v in sc_["components"].items()])
            st.dataframe(comp, hide_index=True, width="stretch")
            st.caption(l["provenance"])
            if l.get("policy"):
                st.info("Policy to verify: " + l["policy"])
            st.button(f"Make {l['label']} the active site ⟩ re-run every tab", on_click=set_site,
                      args=("" if l["benchmark"] else l["key"], l["label"] + (" (benchmark)" if l["benchmark"] else "")),
                      type="primary")
        pf = price_forecast(l)
        fp = go.Figure()
        fp.add_trace(go.Scatter(x=pf.month, y=pf.p95, name="P95 hourly", line=dict(color="#EF5350", width=1)))
        fp.add_trace(go.Scatter(x=pf.month, y=pf["avg"], name="Average", line=dict(color=AMBER, width=2)))
        fp.update_layout(height=280, yaxis_title="Merchant $/MWh", xaxis_title="Development month (120-month horizon)",
                         legend=dict(orientation="h", y=1.2), margin=dict(t=40))
        st.markdown("**Merchant price forecast** (benchmark ERCOT hourly shape × regional price index × packet real-terms trajectory)")
        st.plotly_chart(fp, width="stretch")
        with st.expander(f"Top parcels ({par.source.iloc[0].lower()})"):
            st.dataframe(par.head(15)[["parcel_id", "acres", "substation_spare_mw", "dist_substation_km", "dist_gas_km",
                                       "flood_zone", "zoning", "land_usd_per_acre", "passes", "parcel_score"]],
                         hide_index=True, width="stretch")

# ====================================================================================
with T_IC:
    if best is None or IC is None:
        st.info("No feasible plan yet; relax a must-have first.")
    else:
        st.subheader("Interconnect · wait for the grid, bridge with onsite power, or walk away")
        dl = IC["decision"]
        tone = st.success if dl["verdict"] in ("WAIT", "BRIDGE") else st.error
        tone(f"**Decision: {dl['verdict']}.** {dl['text']}")
        k = st.columns(5)
        k[0].metric("Grid region", IC["grid"])
        k[1].metric("Energization P10 / P50 / P90", f"+{IC['en']['P10']} / +{IC['en']['P50']} / +{IC['en']['P90']} mo",
                    "vs benchmark grid schedule", delta_color="off")
        k[2].metric("Grid full (75 MW)", f"M{30 + IC['delay']}", f"P90 M{30 + IC['en']['P90']}", delta_color="off")
        k[3].metric("Indicative upgrade cost", money(IC["upgrade_usd_kw"] * 75_000), f"${IC['upgrade_usd_kw']}/kW screening", delta_color="off")
        dp = deliverable_power(best, IC["delay"])
        k[4].metric("Bridge power needed", f"{dp['bridge_mw']:.0f} MW", f"{dp['bridge_mw_months']:,.0f} MW-months of gap", delta_color="off")
        f = go.Figure()
        f.add_trace(go.Scatter(x=dp["months"], y=dp["grid"], name="Grid import cap (P50)", line=dict(color=CYAN, width=2, shape="hv")))
        f.add_trace(go.Scatter(x=dp["months"], y=dp["grid"] + dp["onsite"], name="Grid + onsite firm", line=dict(color=AMBER, width=2, shape="hv")))
        f.add_trace(go.Scatter(x=dp["months"], y=dp["demand"], name="Demand peak (ramp)", line=dict(color="#FFFFFF", width=2, dash="dot", shape="hv")))
        f.add_trace(go.Scatter(x=dp["months"], y=dp["gap"], name="Power gap the grid cannot carry", fill="tozeroy",
                               line=dict(color="#EF5350", width=0), fillcolor="rgba(239,83,80,0.25)"))
        p90grid = deliverable_power(best, IC["en"]["P90"])["grid"]
        f.add_trace(go.Scatter(x=dp["months"], y=p90grid, name="Grid cap if P90 slip", line=dict(color=CYAN, width=1, dash="dash", shape="hv")))
        f.update_layout(height=360, xaxis_title="Development month", yaxis_title="MW", xaxis=dict(range=[0, 60]),
                        legend=dict(orientation="h", y=1.18), margin=dict(t=50))
        st.plotly_chart(f, width="stretch")
        st.caption("Deliverable power: projects get built where MW can actually be delivered by month, not where demand "
                   "assumes power will follow. Onsite firm = selected gas units + battery power from their start month.")
        c1, c2 = st.columns(2)
        rows = []
        for name, r in [("Wait for grid", IC["wait"]), ("Bridge to target", IC["bridge"]), ("Plan at P90 grid slip", IC["p90"])]:
            if r is None:
                continue
            mm = r.metrics or {}
            rows.append({"Option": name, "Opens": f"M{r.scenario.initial_service_month}", "Status": "feasible" if r.status == "ok" else r.status,
                         "$/MWh": f"{mm.get('decision_cost_usd_per_requested_mwh', float('nan')):.2f}" if mm else "–",
                         "kg/MWh": f"{mm.get('combined_electricity_co2_kg_per_mwh', float('nan')):.0f}" if mm else "–",
                         "Portfolio": ", ".join(f"{c:.0f} {SHORT[k].lower()}" for k, c in r.caps.items() if c > 0)})
        c1.markdown("**Options sized on all 87,600 hours**")
        c1.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        if dl.get("breakeven"):
            c1.caption(f"Break-even value of time: {money(dl['breakeven'])}/month. Above it, bridge; below it, wait.")
        c2.markdown("**Study path and exposure (screening)**")
        c2.write(IC["path"])
        if site_rec and site_rec.get("policy"):
            c2.info("Verify: " + site_rec["policy"])
        c2.caption("Energization spread, upgrade $/kW and study paths are labelled screening assumptions by region, "
                   "not utility study results. Upgrade cost is reported here and is not part of common benchmark cost.")

# ====================================================================================
with TAB_DEAL:
    if best is None or DEALS is None:
        st.info("No feasible plan to structure.")
    else:
        st.subheader("Structure · how to own and pay for the plan")
        c1, c2, c3 = st.columns([1, 1, 2])
        c1.checkbox("Limit upfront capital", key="deal_cap_on")
        c2.number_input("Max upfront $M", 0, 2000, step=10, key="deal_cap", disabled=not S.get("deal_cap_on", False))
        c3.checkbox("Prefer off-balance-sheet (accept up to 5% higher cost)", key="deal_obs")
        deals, pick, why, capex = DEALS
        if pick:
            st.success(f"**Recommended structure: {pick['structure']}.** {why}.")
        else:
            st.error(why)
        tbl = pd.DataFrame([{"Structure": ("★ " if d["recommended"] else "") + d["structure"],
                             "Total cost": money(d["total_usd"]), "$/MWh": f"{d['usd_per_mwh']:.2f}",
                             "Upfront capital": money(d["upfront_usd"]), "Committed obligations": money(d["committed_usd"]),
                             "Tenor": d["tenor"], "Balance sheet": d["balance_sheet"]} for d in deals])
        st.dataframe(tbl, hide_index=True, width="stretch")
        risk = pd.DataFrame({d["structure"].split(" (")[0].split(" +")[0]: d["risks"] for d in deals})
        st.markdown("**Who carries which risk**")
        st.dataframe(risk, width="stretch")
        for d in deals:
            st.caption(f"{d['structure']}: {d['notes']}")
        st.caption("'Own' equals the common benchmark cost. Other structures add a counterparty return or tariff terms "
                   "(labelled screening assumptions) so the physical result is never hidden by the structure.")

# ====================================================================================
with TAB_MON:
    if best is None:
        st.info("No plan to monitor yet.")
    else:
        st.subheader("Monitor · what would change this decision")
        sev = {"high": "🔴", "medium": "🟠", "low": "🟢"}
        tdf = pd.DataFrame([{"": sev[t["severity"]], "Trigger": t["trigger"], "Watch": t["watch"], "Impact if it fires": t["impact"],
                             "Action": t["action"]} for t in TRIG])
        st.dataframe(tdf, hide_index=True, width="stretch")
        st.caption("Price and fuel impacts are exact for the fixed portfolio (re-priced dispatch). The grid-slip trigger "
                   "re-sizes the plan on all 87,600 hours at the P90 energization date.")
        st.markdown("**Site pipeline**")
        S.setdefault("pipeline", {})
        lab = S.get("site_label", "Williamson County, TX (benchmark)")
        if lab not in S.pipeline:
            S.pipeline[lab] = "Shortlist"
        pdf = pd.DataFrame([{"Site": k, "Stage": v} for k, v in S.pipeline.items()])
        new = st.data_editor(pdf, hide_index=True, disabled=["Site"], key="pipe_editor",
                             column_config={"Stage": st.column_config.SelectboxColumn(
                                 options=["Shortlist", "Interconnect study", "Diligence", "Term sheet", "Hold", "Dropped"])})
        S.pipeline = {r["Site"]: r["Stage"] for _, r in new.iterrows()}
        st.caption("Sites enter the pipeline when you make them active in Screen. Stages are session-only in this prototype.")

# ====================================================================================
with TAB_REC:
    if best is None:
        st.error(f"No portfolio opening in months {rec.tested[0] if rec.tested else '–'}–"
                 f"{rec.tested[-1] if rec.tested else '–'} meets every must-have. Nearest fixes:")
        for rx in rec.relaxations:
            with st.container(border=True):
                st.markdown(f"**{rx['change']}**")
                if rx["note"]:
                    st.caption(rx["note"])
                r = rx.get("result")
                if r is not None and r.metrics:
                    mm = r.metrics
                    st.write(f"Opens month {r.scenario.initial_service_month} · "
                             f"{mm['decision_cost_usd_per_requested_mwh']:.2f} $/MWh · "
                             f"{mm['combined_electricity_co2_kg_per_mwh']:.0f} kg/MWh · "
                             f"{mm['interrupted_mwh']:,.0f} MWh Tier 2 interrupted")
    else:
        m = best.metrics
        s = best.scenario.initial_service_month
        st.success(f"**Recommended:** open at **month {s}**, full demand at **month {s + 10}**, "
                   f"with {', '.join(f'{c:.0f} MW {LABELS[k].lower()}' for k, c in best.caps.items() if c > 0)}.")
        if anchor is not None:
            am_ = anchor.metrics
            what = ", ".join([f"{LABELS[r_]} {mm_} months late" for r_, mm_ in opt.slips] +
                             ([f"grid {opt.grid_delay} months late"] if opt.grid_delay else []))
            st.warning(f"**Execution scenario ({what}) vs. the on-schedule benchmark:** opening "
                       f"M{anchor.scenario.initial_service_month} → M{s}; "
                       f"{am_['decision_cost_usd_per_requested_mwh']:.2f} → {m['decision_cost_usd_per_requested_mwh']:.2f} $/MWh; "
                       f"{am_['combined_electricity_co2_kg_per_mwh']:.0f} → {m['combined_electricity_co2_kg_per_mwh']:.0f} kg/MWh. "
                       "Capacity charges follow the common rule from the catalog date (conservative).")
        k = st.columns(4)
        k[0].metric("Opens / full demand", f"M{s} / M{s + 10}", help="Initial service month and full demand month. The official commissioning ramp reaches full demand 10 months after opening.")
        k[1].metric("Total decision cost", money(m["total_decision_cost_usd"]),
                    f"{m['decision_cost_usd_per_requested_mwh']:.2f} $/MWh requested", delta_color="off", help="Official checker total decision cost: local energy (fixed/variable/fuel/contracts/merchant) + remote relocation + Tier 2 interruption consequence. Per requested MWh uses all requested energy, including service that was relocated or interrupted.")
        k[2].metric("Emissions intensity", f"{m['combined_electricity_co2_kg_per_mwh']:.0f} kg/MWh",
                    f"{m['combined_operational_co2_t'] / 1e3:,.0f} kt CO₂ over horizon", delta_color="off", help="Checker combined operational emissions include campus supply and relocated remote electricity; intensity divides by the packet-defined energy accounting denominator.")
        k[3].metric("Clean share", f"{m['clean_energy_share'] * 100:.0f}%", help="Official checker clean share of locally supplied electricity. Storage shifts clean energy but creates no new clean MWh; it must not double count renewable credit.")
        k = st.columns(4)
        k[0].metric("Merchant dependence", f"{m['merchant_mwh'] / m['local_served_mwh'] * 100:.0f}%", help="Merchant energy purchased divided by locally served energy; all grid-supplied contracts and merchant purchases share the import cap.")
        k[1].metric("Tier 1 relocated", f"{m['relocated_local_equivalent_mwh']:,.0f} MWh",
                    money(m["relocation_cost_usd"], 2), delta_color="off", help="Tier 1 workload shifted to the remote site in designated stress hours; remote energy, cost, and emissions remain accounted for.")
        k[2].metric("Tier 2 interrupted", f"{m['interrupted_mwh']:,.0f} MWh",
                    money(m["interruption_consequence_usd"], 2), delta_color="off", help="Tier 2 demand curtailed only where permitted during stress events; associated service consequence is part of decision cost.")
        k[3].metric("Checker", "✅ passed", f"max import {m['max_grid_import_mw']:.1f} MW", delta_color="off")
        cdf, _ = AN["curt"]
        cov = AN["cov"]
        n1 = AN["n1"]
        k = st.columns(4)
        k[0].metric("Clean energy curtailed", f"{cdf.curtailed_mwh.sum() / 1e3:,.0f} GWh" if len(cdf) else "0",
                    (money(cdf.paid_for_curtailed_usd.sum()) + " paid, unused") if len(cdf) else None, delta_color="off",
                    help="Solar/wind/nuclear energy that was available (and paid for under the available-generation "
                         "contracts) but not used, because of the import limit or no load. This is generation "
                         "curtailment, not customer interruption.")
        k[1].metric("Hourly clean matching", f"{cov['hourly_matched_share'] * 100:.0f}%",
                    f"{cov['hours_fully_clean'] * 100:.0f}% of hours fully clean", delta_color="off",
                    help="Share of local load matched by clean energy in the same hour (24/7 view). The annual "
                         "clean share can be higher because surplus hours offset deficit hours.")
        if n1 is None:
            k[2].metric("Largest-unit outage (N-1)", "no onsite units")
        else:
            k[2].metric("Largest-unit outage (N-1)", "✅ covered" if n1["hours_short"] == 0 else f"⚠ {n1['hours_short']:,} h short",
                        f"{n1['lost_mw']:.0f} MW {n1['lost'].lower()} out" + ("" if n1["hours_short"] == 0 else f", up to {n1['worst_mw']:.0f} MW"),
                        delta_color="off", help="If one block of the biggest onsite unit is unavailable, can every hour still be "
                                                "served with permitted flexibility and the import limit? See Grid stress & reliability.")
        sh = getattr(rec, "shifts", ())
        k[3].metric("Execution mode", "lead-time aware" if opt.execution_aware else "catalog dates",
                    (", ".join(f"{SHORT[r_]} +{m_}m" for r_, m_ in sh) or "no shifts") if sh or opt.execution_aware else "slots assumed secured",
                    delta_color="off")
        fl = decision_flips(rec)
        if fl["value"] or fl["carbon"]:
            st.info("**Where the answer flips** (holding each tested portfolio fixed): "
                    + "; ".join(x["text"] for x in fl["value"] + fl["carbon"]) + ".")

        left, right = st.columns([1, 1.1])
        with left:
            st.subheader("What to build and contract")
            rows = []
            for kk in RES:
                c = best.caps.get(kk, 0)
                if c <= 0:
                    continue
                led = next(x for x in m["capacity_cost_ledger"] if x["option_id"] == kk)
                rows.append({"Resource": LABELS[kk], "MW": f"{c:.0f}",
                             "Where": OPT.loc[kk, "location"], "Starts": f"M{led['commitment_start_month']}",
                             "Horizon cost": money(led["total_cost_usd"])})
            st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
            land = sum(best.caps.get(kk, 0) * OPT.loc[kk, "land_acres_per_mw"] for kk in RES)
            st.caption(f"Onsite land used: {land:.2f} of 8 acres. Merchant grid fills the rest within the import limit.")
            st.subheader("Must-have check")
            chk = []
            fdb = req.full_demand_by
            if fdb: chk.append(("Full demand by", f"M{fdb}", f"M{s + 10}", s + 10 <= fdb))
            if req.open_by: chk.append(("Open by", f"M{req.open_by}", f"M{s}", s <= req.open_by))
            if req.max_intensity_kg is not None: chk.append(("Max kg/MWh", f"{req.max_intensity_kg:.0f}", f"{m['combined_electricity_co2_kg_per_mwh']:.1f}", True))
            if req.min_clean_share is not None: chk.append(("Min clean share", f"{req.min_clean_share:.0%}", f"{m['clean_energy_share']:.1%}", True))
            if req.max_merchant_share is not None: chk.append(("Max merchant share", f"{req.max_merchant_share:.0%}", f"{m['merchant_mwh'] / m['local_served_mwh']:.1%}", True))
            if req.budget_musd is not None: chk.append(("Max total cost", money(req.budget_musd * 1e6), money(m["total_decision_cost_usd"]), True))
            if req.max_premium_pct is not None and rec.premium_ref: chk.append(("Premium vs cheapest month-20 opening", f"≤{req.max_premium_pct:.0f}%", f"{(m['decision_cost_usd_per_requested_mwh'] / rec.premium_ref - 1) * 100:+.1f}%", True))
            if req.no_tier2: chk.append(("No Tier 2 interruption", "0 MWh", f"{m['interrupted_mwh']:.0f}", True))
            if req.n_minus_1 and n1 is not None: chk.append(("Survive largest-unit outage", "0 hours short", f"{n1['hours_short']}", n1["hours_short"] == 0))
            chk += [("Tier 0 served locally", "every hour", "yes", True),
                    ("Grid/stress import limit", "every hour", "yes", True),
                    ("Battery SOC, cycles, clean-only charging", "packet rules", "yes", True)]
            st.dataframe(pd.DataFrame(chk, columns=["Requirement", "Target", "Result", "Met"]),
                         hide_index=True, width="stretch")
        with right:
            st.subheader("Why this portfolio")
            for e in rec.explanation:
                st.markdown("- " + e)

        st.subheader("Fast Track · Lower Cost · Cleaner: when each would win")
        alts = rec.alternatives[:6]
        if alts:
            cols = st.columns(min(3, len(alts)))
            for i, a in enumerate(alts):
                am = a["result"].metrics
                with cols[i % len(cols)].container(border=True):
                    st.markdown(f"**{a['name']}**" + ("  ·  *same as recommendation*" if a.get("same") else ""))
                    st.caption(a.get("tagline", ""))
                    st.caption(f"{am['decision_cost_usd_per_requested_mwh']:.2f} $/MWh · "
                               f"{am['combined_electricity_co2_kg_per_mwh']:.0f} kg/MWh · "
                               + ", ".join(f"{c:.0f} {LABELS[k].split()[0].lower()}"
                                           for k, c in a["result"].caps.items() if c > 0))
                    if a["gains"]:
                        st.markdown("➕ " + "; ".join(a["gains"]))
                    if a["gives"]:
                        st.markdown("➖ " + "; ".join(a["gives"]))
                    st.markdown(f"*{a['when']}*")

# ====================================================================================
with TAB_EXPLAIN:
    st.subheader("Why PowerPath chose this portfolio")
    st.caption("Hover chart segments for numerical evidence. Each panel gives the calculation, the source, and what would change the result.")
    if best is None:
        st.info("No feasible result under the current hard requirements. See Recommendation for tested relaxations.")
    else:
        m = best.metrics
        d = best.dispatch
        st.markdown("### 1 · How the power mix actually supplies the campus")
        st.write("**Selected capacity is not the same as electricity delivered.** Installed/contracted MW represents the resource size; actual MWh depends on sunlight, wind, grid access, fuel dispatch and availability dates. Battery discharge is shown separately as shifted energy, not newly produced generation.")
        cap_rows = []
        for resource in RES:
            cap = float(best.caps.get(resource, 0))
            if cap > 0:
                col = FLOW.get(resource)
                delivered = float(d[col].sum()) if col in d.columns else 0.0
                cap_rows.append({"Technology": LABELS[resource], "Selected MW": cap,
                                 "Dispatched GWh": delivered / 1000,
                                 "What limits output": "Grid import cap / hourly availability" if resource in ("utility_solar", "wind", "nuclear") else
                                 "Clean charging and storage state" if resource == "battery_4h" else "Available hours, fuel economics and load"})
        cap_rows.append({"Technology": "Merchant grid (no installed MW)", "Selected MW": 0.0,
                         "Dispatched GWh": float(d.grid_mw.sum()) / 1000,
                         "What limits output": "Hourly merchant price and shared grid-import limit"})
        mix_df = pd.DataFrame(cap_rows)
        fig = go.Figure()
        for r in cap_rows:
            name = r["Technology"]
            ckey = next((k for k, v in LABELS.items() if v == name), "grid")
            fig.add_trace(go.Bar(x=[name], y=[r["Dispatched GWh"]], name=name,
                                 marker_color=COL.get(ckey, "#9aa5b1"),
                                 customdata=[[r["Selected MW"], r["What limits output"]]],
                                 hovertemplate="<b>%{x}</b><br>Dispatched: %{y:,.1f} GWh<br>Selected: %{customdata[0]:,.0f} MW<br>Driver: %{customdata[1]}<extra></extra>"))
        fig.update_layout(height=370, showlegend=False, yaxis_title="Dispatched energy across 120 months (GWh)",
                          xaxis_tickangle=-24, margin=dict(t=20, b=20))
        st.plotly_chart(fig, width="stretch")
        with st.expander("See exact capacity, energy and dispatch caveats"):
            st.dataframe(mix_df, hide_index=True, width="stretch")
            st.caption("The full-horizon dispatch CSV is the underlying source. Over the ten-year horizon, generation varies with resource availability and the commissioning ramp. Dispatched battery energy is not counted as new generation.")
        st.markdown("### 2 · Reconcile the customer outcome")
        info = [
            ("Initial / full service", f"M{best.scenario.initial_service_month} / M{best.scenario.initial_service_month + 10}", "The official 10-month commissioning ramp maps initial service to full demand. Opening months are enumerated within the selected search range."),
            ("Total decision cost", money(m["total_decision_cost_usd"]), "Official packet accounting: local energy cost plus relocation cost plus interruption consequence; not a discounted NPV."),
            ("Cost per requested MWh", f"${m['decision_cost_usd_per_requested_mwh']:,.2f}", "Total decision cost / all requested MWh across the evaluation horizon; shown alongside service amount to avoid rewarding dropped load."),
            ("Combined emissions intensity", f"{m['combined_electricity_co2_kg_per_mwh']:,.1f} kg/MWh", "Official checker includes onsite and imported electricity plus remote emissions from moved workloads; does not treat relocation as eliminating energy use."),
            ("Annual clean-energy share (checker aggregate)", f"{100*m['clean_energy_share']:,.1f}%", "Checker-computed clean portfolio energy share. This is not 24/7 clean coverage; storage does not create an additional clean attribute."),
            ("Relocated / interrupted", f"{m['relocated_local_equivalent_mwh']:,.0f} / {m['interrupted_mwh']:,.0f} MWh", "Tier 1 moved remotely and Tier 2 curtailed only during designated events, each with separate penalties/accounting.")
        ]
        for title, val, explanation in info:
            with st.expander(f"{title}: {val}"):
                st.write(explanation)
        st.markdown("### 3 · Where the money goes")
        cost_parts = {"Local energy": float(m["local_energy_cost_usd"]),
                      "Remote relocation": float(m["relocation_cost_usd"]),
                      "Tier 2 interruption": float(m["interruption_consequence_usd"])}
        fcost = go.Figure(go.Bar(x=list(cost_parts), y=[v / 1e6 for v in cost_parts.values()],
                                marker_color=["#264653", "#e76f51", "#c0392b"],
                                hovertemplate="%{x}: $%{y:,.2f}M<extra></extra>"))
        fcost.update_layout(height=290, yaxis_title="$ million, full evaluation horizon", margin=dict(t=12, b=20))
        st.plotly_chart(fcost, width="stretch")
        st.caption(f"Sum = {money(sum(cost_parts.values()))}; official total = {money(m['total_decision_cost_usd'])}. Source: bundled competition checker and the selected hourly dispatch.")
        st.markdown("### 4 · Why it won: transparent preference and requirement logic")
        st.write("**Hard requirements are never traded off.** The engine rejects candidates that violate physical rules or the customer ceilings/deadlines. It then ranks feasible candidates using normalized common decision cost plus optional speed and carbon valuations.")
        p1, p2 = st.columns(2)
        p1.metric("Customer value of 1 month earlier", money(rec.value_per_month),
                  help="Illustrative willingness-to-pay derived from speed and cost preferences, or explicit dollar override. Not a benchmark cash flow.")
        p2.metric("Internal value of avoided CO₂", f"${rec.carbon_price:,.0f}/t",
                  help="Illustrative internal shadow price from preference slider or explicit override, not a carbon tax or actual spend.")
        with st.expander("Decision logic, model limits and reproducibility"):
            st.markdown("1. Convert must-haves into candidate filtering and solver constraints.\n2. Search selected opening months; size resources using mixed-integer optimization on representative and stress days.\n3. Dispatch all 87,600 hours chronologically, enforce SOC/import/flex limits and rescreen constraints.\n4. Use the official checker for cost and environmental results.\n5. Compare candidates with the separately labeled customer valuation. The sampled sizing relaxation gap is **not** a proven full-horizon optimality gap.")
            st.write("Search window:", opt.earliest_open, "to", opt.latest_open, "months in steps of", opt.step)
            st.write("Selected capacities:", {LABELS[k]: v for k,v in best.caps.items() if v > 0})
        st.markdown("### 5 · What to inspect next")
        st.info("Open **Grid stress** to see how protected demand stays served under reduced imports, **Year by year** to see trends and cost ledgers, and **Compare** to pin a different preference scenario. Charts disclose sources and limitations rather than treating modeled forecasts as firm vendor quotes.")

# ====================================================================================
with TAB_EXEC:
    if best is None:
        st.info("No feasible recommendation yet; relax a must-have first.")
    else:
        s = best.scenario.initial_service_month
        st.subheader("From decision to execution: what to file, order and build, and by when")
        c1, c2 = st.columns([1, 2])
        with c1:
            st.metric("Today (development month)", f"M{S.today}",
                      "execution-aware" if S.exec_aware else "catalog offer dates", delta_color="off")
            if not S.exec_aware:
                st.button("Re-optimize respecting these lead times", on_click=make_exec_aware,
                          help="Turns on execution-aware mode: resources become usable no earlier than "
                               "today + permit/procure/build, and the optimizer re-plans around that.")
        ov = S.get("lead_overrides", {})
        tbl, site, flags = exec_plan(best.caps, s, best.scenario.grid_delay_months, S.today, ov,
                                     best.scenario.avail_shift)
        sb6 = sb6_check(best.caps)
        with c2:
            k = st.columns(3)
            k[0].metric("Items at risk", f"{len(flags) + int(site.late.sum()) if len(site) else len(flags)}")
            k[1].metric("Earliest action due", f"M{int(min(tbl[['permit_by', 'order_by']].min().min(), site.start_by.min() if len(site) else 999))}")
            k[2].metric("Illustrative onsite capacity screen", f"{sb6['firm_onsite_mw']:.0f} / {sb6['half_load_mw']:.0f} MW",
                        "Not a legal compliance determination", delta_color="off")
            st.caption(sb6["caveat"])
        for f in flags:
            c_a, c_b = st.columns([4, 1])
            c_a.error(f["text"])
            c_b.button(f"Model a {min(36, max(6, f['months_late']))}-month slip", key=f"slip_{f['key']}",
                       on_click=set_slip, args=(f["key"], int(min(36, max(6, f["months_late"])))))

        # Gantt
        fig = go.Figure()
        ylab = []
        def bar(y, a, b, color, name, show):
            if b is None or a is None or b <= a:
                return
            fig.add_trace(go.Bar(y=[y], x=[b - a], base=[a], orientation="h", marker_color=color,
                                 name=name, legendgroup=name, showlegend=show,
                                 hovertemplate=f"{name}: M%{{base}}–M{b}<extra>{y}</extra>"))
        shown = set()
        for _, r in site.iterrows():
            y = r["item"][:48]
            bar(y, r.start_by, r.need, "#6c757d", "Site / grid approvals", "Site / grid approvals" not in shown)
            shown.add("Site / grid approvals")
        for _, r in tbl.iterrows():
            y = r["resource"]
            onsite = OPT.loc[r.key, "location"] == "onsite"
            if r.permit:
                bar(y, r.permit_by, r.build_start, "#e76f51", "Permit", "Permit" not in shown); shown.add("Permit")
            if onsite:
                bar(y, r.order_by, r.need - r.build, "#f4a261", "Procure / deliver", "Procure / deliver" not in shown); shown.add("Procure / deliver")
                bar(y, r.build_start, r.need, "#2a9d8f", "Build / commission", "Build / commission" not in shown); shown.add("Build / commission")
            else:
                bar(y, r.order_by, r.need, "#5fa8d3", "Contract (PPA)", "Contract (PPA)" not in shown); shown.add("Contract (PPA)")
        for xv, lab, col in [(S.today, "today", "#c0392b"), (s, "opening", "#264653"), (s + 10, "full demand", "#264653")]:
            fig.add_vline(x=xv, line_dash="dash", line_color=col, annotation_text=lab)
        fig.update_layout(barmode="overlay", height=120 + 42 * (len(tbl) + len(site)), xaxis_title="Development month",
                          legend=dict(orientation="h", y=1.12), margin=dict(t=40, l=10))
        st.plotly_chart(fig, width="stretch")
        st.caption("Back-planned from each resource's need date (the later of opening and its catalog offer date). "
                   "Durations are labelled planning assumptions you can edit below; they never change the benchmark inputs.")

        st.markdown("**Preliminary permitting pathways and possible agencies (verification required)**")
        st.warning("Execution timing is illustrative. No parcel-specific permit search, enacted-moratorium check, or statutory compliance determination is performed. Confirm requirements with the authority having jurisdiction.")
        show = tbl[["resource", "pathway", "agency", "need", "permit_by", "order_by", "slack", "note"]].copy()
        show.columns = ["Resource", "Pathway", "Agency", "Needed by", "File permit by", "Order / sign by", "Slack (months)", "Notes"]
        st.dataframe(show, hide_index=True, width="stretch")
        st.dataframe(site[["item", "agency", "need", "start_by", "slack", "note"]].rename(columns={
            "item": "Site-level step", "agency": "Agency", "need": "Needed by", "start_by": "Start by",
            "slack": "Slack (months)", "note": "Notes"}), hide_index=True, width="stretch")

        with st.expander("Edit lead-time assumptions (months)"):
            ed = pd.DataFrame([{"resource": k, "permit": {**DEFAULT_STEPS[k], **ov.get(k, {})}["permit"],
                                "procure": {**DEFAULT_STEPS[k], **ov.get(k, {})}["procure"],
                                "build": {**DEFAULT_STEPS[k], **ov.get(k, {})}["build"]}
                               for k in best.caps if best.caps[k] > 0])
            new = st.data_editor(ed, hide_index=True, disabled=["resource"], key="lead_editor")
            if st.button("Apply lead times"):
                S.lead_overrides = {r.resource: dict(permit=int(r.permit), procure=int(r.procure), build=int(r.build))
                                    for r in new.itertuples()}
                st.rerun()

        st.markdown("**Approvals tracker**")
        items = [f"{LABELS[k]}: {DEFAULT_STEPS[k]['pathway'].split('+')[0].strip()}" for k in best.caps if best.caps[k] > 0] + \
                [x["item"] for x in SITE_STEPS]
        prev = S.get("tracker", {})
        trk = pd.DataFrame({"Approval / contract": items,
                            "Owner": [prev.get(i, {}).get("Owner", "") for i in items],
                            "Status": [prev.get(i, {}).get("Status", "Not started") for i in items]})
        trk = st.data_editor(trk, hide_index=True, disabled=["Approval / contract"], key="tracker_editor",
                             column_config={"Status": st.column_config.SelectboxColumn(
                                 options=["Not started", "In progress", "Filed", "Approved", "Blocked"])})
        S.tracker = {r["Approval / contract"]: {"Owner": r["Owner"], "Status": r["Status"]} for _, r in trk.iterrows()}
        st.caption("Planning assumptions only. Confirm each permit, legal effective date, submittal, and responsible authority from primary sources before relying on the workflow.")

# ====================================================================================
with TAB_EXEC, st.expander("PermitIQ · preliminary permitting checklist and review packet", expanded=False):
    from gridpilot.permitiq import preliminary_screen, task_template
    st.subheader("PermitIQ · Evidence-first compliance workflow")
    st.info("This is a configurable screening and workflow aid, not a legal determination. The official fictional Texas benchmark is unchanged by this tab.")
    jurisdiction = st.selectbox("Jurisdiction", ["Williamson County, Texas (unincorporated - assumption)",
        "Texas municipality (identify actual city)", "PJM region (select parcel and utility before conclusions)"], key="permit_jurisdiction")
    project_name = st.text_input("Project reference", "PowerPath 75 MW campus")
    entries = preliminary_screen(best.caps if best else {}, jurisdiction)
    dfperm = pd.DataFrame(entries)
    st.dataframe(dfperm, width="stretch", hide_index=True)
    st.caption("Verified status means source review has occurred; this prototype flags unverified requirements instead of claiming approvals or active moratoria.")
    if len(dfperm):
        st.download_button("Download diligence checklist (CSV)", data=dfperm.to_csv(index=False).encode(),
                           file_name="permitiq_checklist.csv", mime="text/csv")
    st.markdown("**Draft review packet — human approval required**")
    st.code(task_template(project_name, jurisdiction, entries), language="markdown")
    st.download_button("Download review packet", task_template(project_name, jurisdiction, entries),
                       file_name="permitiq_review_packet.md", mime="text/markdown")
    st.markdown("**Regulatory change-control**")
    st.write("Track rule source, official URL, jurisdiction, effective date, access date, reviewer, and disposition. Pending proposals must never be modeled as enacted requirements.")
    st.markdown("**Portfolio linkage**")
    st.write("When a verified requirement changes project timing, use the Execution plan and Scenario controls to model a resource delivery or grid delay. Preserve the baseline benchmark results.")

# ====================================================================================
with TAB_FEAS:
    from gridpilot.feasibility import CRITERIA, DOMAINS, STATES, blank_records, evaluate, export_report, drafting_checklist
    st.subheader("PowerPath Feasibility · Is this site development-ready?")
    st.info("Evidence-first desktop screening. No live GIS, utility service study, municipal-code search or permit approval is implied. The official fictional Williamson County model is unchanged unless you explicitly apply an optional grid-delay scenario.")
    with st.container(border=True):
        fc1, fc2, fc3 = st.columns([1.8, 1.8, 1])
        f_name = fc1.text_input("Project name", "PowerPath 75 MW campus", key="f_name")
        f_loc = fc2.text_input("Location / jurisdiction", "Williamson County, TX (hypothetical)", key="f_loc")
        f_mw = fc3.number_input("Peak demand (MW)", min_value=1.0, value=75.0, step=5.0, key="f_mw")
        f_parcel = st.text_input("Parcel ID / site identifier", "Not specified — exact jurisdiction unverified", key="f_parcel")
        f_stage = st.selectbox("Diligence stage", ["Desktop screening", "Development diligence", "Investment readiness"], key="f_stage")
    if 'feas_records' not in S:
        S.feas_records = blank_records()
    current = S.feas_records
    assessment = evaluate(current)
    st.markdown('### Readiness snapshot')
    a,b,c,d=st.columns(4)
    a.metric('Evidence-backed checks',f"{assessment['verified_with_support']}/{assessment['criteria_count']}",help='Number of criteria with a verified met/not-applicable status, a named reviewer, and evidence reference. NOT a probability of project success.')
    b.metric('Open critical gates',assessment['critical_unresolved'],help='Critical project questions that still require documentary diligence.')
    c.metric('Supported blockers',assessment['supported_critical_blockers'],help='Critical blockers marked as verified and supported with an evidence reference and reviewer.')
    d.metric('Incomplete evidence claims',assessment['evidence_deficiencies'],help='Any verified/blocked/not-applicable claim missing an evidence reference or reviewer.')
    if assessment['supported_critical_blockers']:
        st.error(assessment['determination'])
    else:
        st.warning(assessment['determination'])
    st.caption('These are evidence counts, not a weighted suitability score. Unknown is not equivalent to feasible, and recorded evidence does not replace legal or engineering review.')
    domain_rows=[{'Area':k,'Checks':v['total'],'Evidence-backed':v['verified_evidenced'],'Critical open':v['critical_open'],'Blocked':v['blocked']} for k,v in assessment['domains'].items()]
    st.dataframe(pd.DataFrame(domain_rows),hide_index=True,width='stretch')
    st.markdown('### Review site criteria and supporting evidence')
    st.caption('Edit statuses directly. A verified status counts only with a document/source reference and identified reviewer. Never use "Verified — blocked" for an unconfirmed proposal.')
    for domain in DOMAINS:
        with st.expander(domain, expanded=domain in ['Power','Permitting & Compliance']):
            changed=[]
            for r in [x for x in current if x['domain']==domain]:
                with st.container(border=True):
                    st.markdown(('**Required gate · **' if r['critical'] else '**Advisory · **')+r['title'])
                    cols=st.columns([1.25,1.1,1.1])
                    status=cols[0].selectbox('Assessment',STATES,index=STATES.index(r['status']),key='f_status_'+r['id'])
                    evidence=cols[1].text_input('Evidence / official source ref',value=r['evidence_reference'],key='f_evi_'+r['id'])
                    reviewer=cols[2].text_input('Reviewed by',value=r['verified_by'],key='f_review_'+r['id'])
                    st.caption('Suggested evidence: '+r['evidence_hint']+' · Responsible source: '+r['source_owner'])
                    r.update(status=status,evidence_reference=evidence,verified_by=reviewer)
    # Evaluate after editing; display updated report and next actions without changing official model.
    assessment=evaluate(current)
    unresolved=assessment['next_actions']
    st.markdown('### Action plan')
    if unresolved:
        st.dataframe(pd.DataFrame([{'Priority':'Critical' if r['critical'] else 'Advisory','Area':r['domain'],
                'Requirement':r['title'],'Current status':r['status'],'Next evidence':r['evidence_hint']} for r in unresolved]),
                hide_index=True,width='stretch')
    else:
        st.success('No outstanding screening-gate evidence gaps recorded. This is not a permit or engineering approval.')
    project=dict(name=f_name,location=f_loc,parcel=f_parcel,peak_mw=f_mw,stage=f_stage)
    b1,b2=st.columns(2)
    b1.download_button('Download full feasibility JSON',export_report(project,current),
                       file_name='gridpilot_site_feasibility.json',mime='application/json',width='stretch')
    b2.download_button('Download diligence memo',drafting_checklist(project,current),
                       file_name='gridpilot_site_diligence.md',mime='text/markdown',width='stretch')
    st.markdown('### Link site constraints to the energy scenario')
    st.write('If the serving utility estimates a grid energization slip, model the impact in the existing validated energy engine. This is an optional scenario, not a change to the official base assumptions.')
    grid_slip=st.slider('Hypothetical grid delay (months)',0,12,value=int(S.delay),key='feas_grid_delay')
    st.button('Apply grid delay to energy optimization', key='apply_feas', type='secondary',
              on_click=apply_grid_delay, args=(int(grid_slip),))
    st.caption('Site-specific land, water, connectivity, permitting and vendor-gating inputs are diligence flags here, not yet solved as coupled hard constraints. Do not interpret this screen as proof of buildability.')

# ====================================================================================
with TAB_TRADE:
    st.subheader("Every opening month tested")
    rows = []
    for r in rec.candidates:
        s_ = r.scenario.initial_service_month
        mm = r.metrics or {}
        sc_ = rec.scores.get(s_)
        rows.append(dict(open=s_, full=s_ + 10, ok=r.status == "ok",
                         status="meets must-haves" if r.status == "ok" else (r.message or r.status)[:90],
                         cost=mm.get("decision_cost_usd_per_requested_mwh"),
                         kg=mm.get("combined_electricity_co2_kg_per_mwh"),
                         clean=mm.get("clean_energy_share"), t2=mm.get("interrupted_mwh"),
                         total=mm.get("total_decision_cost_usd"),
                         common=sc_["common"] if sc_ else None, carbon=sc_["carbon"] if sc_ else None,
                         delay=sc_["delay"] if sc_ else None,
                         mix=", ".join(f"{c:.0f} {LABELS[k].split()[0].lower()}" for k, c in r.caps.items() if c > 0)))
    tdf = pd.DataFrame(rows)
    if len(tdf):
        okd = tdf[tdf.ok]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=okd.open, y=okd.cost, mode="lines+markers", name="$/MWh requested",
                                 line=dict(color="#264653", width=3)))
        fig.add_trace(go.Scatter(x=okd.open, y=okd.kg, mode="lines+markers", name="kg CO₂/MWh",
                                 yaxis="y2", line=dict(color="#2a9d8f", width=3, dash="dot")))
        bad = tdf[~tdf.ok]
        if len(bad):
            fig.add_trace(go.Scatter(x=bad.open, y=[okd.cost.min() if len(okd) else 0] * len(bad), mode="markers",
                                     name="fails a must-have", marker=dict(symbol="x", size=13, color="#c0392b")))
        if best is not None:
            fig.add_vline(x=best.scenario.initial_service_month, line_dash="dash", line_color="#e9c46a",
                          annotation_text="recommended")
        fig.update_layout(height=380, xaxis_title="Opening month (full demand = +10)",
                          yaxis=dict(title="Decision cost, $/MWh requested"),
                          yaxis2=dict(title="kg CO₂/MWh", overlaying="y", side="right"),
                          legend=dict(orientation="h", y=1.12), margin=dict(t=40, b=40))
        st.plotly_chart(fig, width="stretch")
        st.caption("Compared per requested MWh: a later opening serves fewer MWh inside the fixed "
                   "120-month horizon, so its lower total would otherwise look like a saving.")
        sdf = tdf.dropna(subset=["common"])
        if len(sdf):
            st.subheader("How your preferences pick the winner")
            base = sdf.common.min()
            f2 = go.Figure()
            f2.add_bar(x=sdf.open, y=(sdf.common - base) / 1e6, name="Common cost above cheapest", marker_color="#264653")
            f2.add_bar(x=sdf.open, y=sdf.carbon / 1e6, name=f"Carbon valuation (${rec.carbon_price:,.0f}/t)", marker_color="#2a9d8f")
            f2.add_bar(x=sdf.open, y=sdf.delay / 1e6, name=f"Delay valuation ({money(rec.value_per_month)}/month)", marker_color="#e76f51")
            f2.update_layout(barmode="stack", height=330, xaxis_title="Opening month",
                             yaxis_title="$M on a common 90-month basis (lower wins)",
                             legend=dict(orientation="h", y=1.15), margin=dict(t=40, b=40))
            st.plotly_chart(f2, width="stretch")
        okr = sorted([r for r in rec.candidates if r.status == "ok"], key=lambda r: r.scenario.initial_service_month)
        if len(okr) >= 2:
            a, b = okr[0], okr[-1]
            R = CASE["full_load_year_mwh"] * 90 / 12
            d = (a.metrics["decision_cost_usd_per_requested_mwh"] - b.metrics["decision_cost_usd_per_requested_mwh"]) * R
            dm = b.scenario.initial_service_month - a.scenario.initial_service_month
            st.info(f"**Price of speed:** opening at month {a.scenario.initial_service_month} instead of "
                    f"{b.scenario.initial_service_month} changes common cost by {money(d)} "
                    f"({money(d / dm)} per month gained) and intensity by "
                    f"{a.metrics['combined_electricity_co2_kg_per_mwh'] - b.metrics['combined_electricity_co2_kg_per_mwh']:+.0f} kg/MWh.")
        show = tdf[["open", "full", "status", "cost", "kg", "clean", "t2", "total", "mix"]].copy()
        show.columns = ["Open", "Full demand", "Status", "$/MWh", "kg/MWh", "Clean", "Tier 2 MWh", "Total $", "Portfolio MW"]
        show["$/MWh"] = show["$/MWh"].map(lambda x: f"{x:.2f}" if pd.notna(x) else "–")
        show["kg/MWh"] = show["kg/MWh"].map(lambda x: f"{x:.0f}" if pd.notna(x) else "–")
        show["Clean"] = show["Clean"].map(lambda x: f"{x:.0%}" if pd.notna(x) else "–")
        show["Tier 2 MWh"] = show["Tier 2 MWh"].map(lambda x: f"{x:,.0f}" if pd.notna(x) else "–")
        show["Total $"] = show["Total $"].map(lambda x: money(x) if pd.notna(x) else "–")
        st.dataframe(show, hide_index=True, width="stretch")
        st.caption(f"Opening months tested: {', '.join(map(str, rec.tested))}. A failed date means no "
                   "portfolio was found within this catalog and data, not proof of impossibility.")

# ====================================================================================
with TAB_STRESS:
    if best is None:
        st.info("No feasible recommendation to show.")
    else:
        d = best.dispatch
        ctx = context(best.scenario.initial_service_month, best.scenario.grid_delay_months, best.scenario.avail_shift, best.scenario.region)
        act = ctx["active"]
        st.subheader("When the grid asks the campus to cut imports to 60%")
        imp = d.grid_mw + d.utility_solar_mw + d.wind_mw + d.nuclear_mw
        served = act & (ctx["load"] > 0)
        k = st.columns(4)
        k[0].metric("Stress hours while operating", f"{int(served.sum())}", f"{STRESS_HOURS} per year", delta_color="off")
        k[1].metric("Tier 1 relocated in events", f"{d.tier1_relocated_mw[act].sum():,.0f} MWh",
                    f"+{(d.tier1_relocated_mw * 1.05 * ctx['remote_co2'])[act].sum():,.0f} t CO₂ remote", delta_color="off")
        k[2].metric("Tier 2 interrupted", f"{d.tier2_curtailed_mw[act].sum():,.0f} MWh")
        k[3].metric("Worst-hour import headroom", f"{(ctx['grid_limit'] - imp)[served].min():.2f} MW", "≥ 0 means limit met", delta_color="off")
        ev_hours = np.nonzero(served)[0]
        years = sorted(set(ev_hours // 8760 + 1))
        yr = st.select_slider("Model year", years, value=years[min(len(years) - 1, 4)])
        ev_y = ev_hours[(ev_hours // 8760 + 1) == yr]
        days = sorted(set(ev_y // 24))
        day = st.selectbox("Event day", days, format_func=lambda x: f"Model hour {x * 24:,} (event day {days.index(x) + 1} of {len(days)})")
        h0, h1 = day * 24 - 12, day * 24 + 36
        w = d.iloc[h0:h1]
        x = np.arange(h0, h1)
        f3 = go.Figure()
        for kk, col in FLOW.items():
            if w[col].sum() > 1e-6:
                f3.add_trace(go.Scatter(x=x, y=w[col], stackgroup="s", name=FLAB[kk], line=dict(width=0), fillcolor=COL[kk]))
        for kk, col in [("r1", "tier1_relocated_mw"), ("i2", "tier2_curtailed_mw")]:
            if w[col].sum() > 1e-6:
                f3.add_trace(go.Scatter(x=x, y=w[col], stackgroup="s", name=FLAB[kk], line=dict(width=0), fillcolor=COL[kk]))
        f3.add_trace(go.Scatter(x=x, y=ctx["load"][h0:h1] + w.battery_4h_charge_mw, name="Demand (+ battery charging)", line=dict(color="black", width=2)))
        f3.add_trace(go.Scatter(x=x, y=ctx["grid_limit"][h0:h1], name="Import limit", line=dict(color="#c0392b", width=2, dash="dash")))
        f3.add_trace(go.Scatter(x=x, y=ctx["tier0"][h0:h1], name="Tier 0 protected", line=dict(color="#6a4c93", dash="dot")))
        for t in x[act[h0:h1]]:
            f3.add_vrect(x0=t - 0.5, x1=t + 0.5, fillcolor="#f4a261", opacity=0.18, line_width=0)
        f3.update_layout(height=430, xaxis_title="Model hour (shaded = stress event)", yaxis_title="MW",
                         legend=dict(orientation="h", y=1.15), margin=dict(t=40))
        st.plotly_chart(f3, width="stretch")
        st.caption("Offsite contracts and merchant purchases share the import limit. Onsite units and "
                   "the battery carry what imports cannot; relocation and interruption are shown as "
                   "their own bands, never as supply.")
        ev = pd.DataFrame({"hour": ev_y, "limit": ctx["grid_limit"][ev_y], "imports": imp.values[ev_y],
                           "onsite": (d.gas_turbine_mw + d.gas_engine_mw + d.fuel_cell_mw + d.battery_4h_discharge_mw).values[ev_y],
                           "T1": d.tier1_relocated_mw.values[ev_y], "T2": d.tier2_curtailed_mw.values[ev_y],
                           "Tier0": ctx["tier0"][ev_y]}).round(2)
        with st.expander(f"All {len(ev)} stress hours in year {yr}"):
            st.dataframe(ev, hide_index=True, width="stretch")

        st.subheader("Reliability: what if the largest onsite unit is out?")
        n1 = AN["n1"]
        if n1 is None:
            st.caption("No onsite generating units in this portfolio; supply depends entirely on the import limit, "
                       "the battery and permitted flexibility.")
        else:
            k = st.columns(4)
            k[0].metric("Unit removed", f"{n1['lost_mw']:.0f} MW", n1["lost"], delta_color="off")
            k[1].metric("Hours that could not be served", f"{n1['hours_short']:,}",
                        f"{n1['hours_short_stress']} in stress events", delta_color="off")
            k[2].metric("Worst-hour shortfall", f"{n1['worst_mw']:.1f} MW",
                        f"{n1['short_mwh']:,.0f} MWh if out all horizon", delta_color="off")
            k[3].metric(f"Expected consequence ({FORCED_OUTAGE_RATE:.0%} outage rate)", money(n1["expected_consequence_usd"], 2),
                        f"{n1['expected_unserved_mwh']:,.0f} MWh unserved", delta_color="off")
            if n1["hours_short"] > 0:
                st.error(f"With one {n1['lost_mw']:.0f} MW {n1['lost'].lower()} block down, {n1['hours_short']:,} hours "
                         "cannot be served even after all permitted Tier 1/Tier 2 actions. Most fall in the commissioning "
                         "months, when grid capacity is below load. That includes protected Tier 0 demand.")
                if n1["options"]:
                    o = pd.DataFrame(n1["options"])
                    o["annual_cost_usd"] = o.annual_cost_usd.map(lambda x: money(x, 2) + "/yr")
                    o.columns = ["Add one block of", "MW", "Capacity charge", "Covers worst hour", "Available from"]
                    st.dataframe(o, hide_index=True, width="stretch")
                st.button("Make 'survive the largest-unit outage' a must-have and re-optimize", on_click=add_n1,
                          type="primary")
                st.caption(f"Financial framing: the expected consequence uses a {FORCED_OUTAGE_RATE:.0%} forced-outage "
                           "planning assumption and the packet's $1,000/MWh interruption value. A data-center customer "
                           "usually treats Tier 0 loss as unacceptable rather than priced, hence the must-have.")
            else:
                st.success("Every hour stays servable with the largest onsite unit out (permitted flexibility, the import "
                           "limit and the remaining units). Battery support was not needed for this check.")

# ====================================================================================
with TAB_YEAR:
    if best is None:
        st.info("No feasible recommendation to show.")
    else:
        m = best.metrics
        ann = pd.DataFrame(m["annual_results"])
        d = best.dispatch
        yr_idx = d.model_hour // 8760 + 1
        mix = pd.DataFrame({FLAB[k]: d[c].groupby(yr_idx).sum() / 1e3 for k, c in FLOW.items() if d[c].sum() > 0})
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Cost by model year")
            f = go.Figure()
            f.add_bar(x=ann.model_year, y=ann.local_energy_cost_usd / 1e6, name="Local energy", marker_color="#264653")
            f.add_bar(x=ann.model_year, y=ann.relocation_cost_usd / 1e6, name="Relocation", marker_color="#e76f51")
            f.add_bar(x=ann.model_year, y=ann.interruption_consequence_usd / 1e6, name="Interruption", marker_color="#c0392b")
            f.update_layout(barmode="stack", height=340, yaxis_title="$M", xaxis_title="Model year",
                            legend=dict(orientation="h", y=1.15), margin=dict(t=40))
            st.plotly_chart(f, width="stretch")
        with c2:
            st.subheader("Supply mix and intensity")
            f = go.Figure()
            for name in mix.columns:
                kk = next(k for k in FLOW if FLAB[k] == name)
                f.add_bar(x=mix.index, y=mix[name], name=name, marker_color=COL[kk])
            f.add_trace(go.Scatter(x=ann.model_year, y=ann.combined_electricity_co2_kg_per_mwh, yaxis="y2",
                                   name="kg/MWh", line=dict(color="black")))
            f.update_layout(barmode="stack", height=340, yaxis_title="GWh",
                            yaxis2=dict(overlaying="y", side="right", title="kg/MWh"),
                            legend=dict(orientation="h", y=1.25), margin=dict(t=50))
            st.plotly_chart(f, width="stretch")
        show = ann[["model_year", "requested_mwh", "local_served_mwh", "relocated_local_equivalent_mwh",
                    "interrupted_mwh", "local_energy_cost_usd", "total_decision_cost_usd",
                    "decision_cost_usd_per_requested_mwh", "combined_operational_co2_t",
                    "combined_electricity_co2_kg_per_mwh", "clean_energy_share"]].copy()
        show.columns = ["Year", "Requested MWh", "Local served MWh", "Relocated MWh", "Interrupted MWh",
                        "Local energy $", "Total decision $", "$/MWh req.", "CO₂ t", "kg/MWh", "Clean share"]
        st.dataframe(show.style.format({"Requested MWh": "{:,.0f}", "Local served MWh": "{:,.0f}",
                                        "Relocated MWh": "{:,.0f}", "Interrupted MWh": "{:,.0f}",
                                        "Local energy $": "{:,.0f}", "Total decision $": "{:,.0f}",
                                        "$/MWh req.": "{:.2f}", "CO₂ t": "{:,.0f}", "kg/MWh": "{:.0f}",
                                        "Clean share": "{:.1%}"}, na_rep="–"), hide_index=True, width="stretch")
        led = pd.DataFrame(m["capacity_cost_ledger"])
        led = led[led.selected_mw > 0]
        led["option_id"] = led.option_id.map(LABELS)
        st.subheader("Cost ledger by resource (common accounting)")
        st.dataframe(led.style.format({c: "{:,.0f}" for c in led.columns if c.endswith("usd")}), hide_index=True, width="stretch")
        ctx_price = context(best.scenario.initial_service_month, best.scenario.grid_delay_months, best.scenario.avail_shift, best.scenario.region)["grid_price"]
        grid_cost = float((d.grid_mw * ctx_price).sum())
        spike = float((d.grid_mw * np.clip(ctx_price - 200, 0, None)).sum())
        st.caption(f"Merchant electricity: {money(grid_cost)} over the horizon, of which {money(spike, 2)} is "
                   f"the premium paid in hours above $200/MWh (price-spike exposure). "
                   f"Customer carbon valuation, not a cash cost: {money(rec.carbon_price * m['combined_operational_co2_t'])}.")

        st.subheader("Merchant price spikes: exposure and hedge value")
        sp, port_p, base_p, pmax = AN["spk"]
        f = go.Figure()
        f.add_bar(x=sp.year, y=sp.merchant_only_premium_usd / 1e6, name="If every MWh were bought at merchant", marker_color="#e9c46a")
        f.add_bar(x=sp.year, y=sp.portfolio_premium_usd / 1e6, name="This portfolio", marker_color="#c0392b")
        f.update_layout(barmode="group", height=320, yaxis_title=f"$M paid above ${SPIKE_USD:.0f}/MWh", xaxis_title="Model year",
                        legend=dict(orientation="h", y=1.15), margin=dict(t=40))
        st.plotly_chart(f, width="stretch")
        st.caption(f"Premium paid in hours when merchant power costs more than ${SPIKE_USD:.0f}/MWh (peak {pmax:,.0f} $/MWh). "
                   f"This portfolio pays {money(port_p, 2)} over the horizon versus {money(base_p)} for an all-merchant "
                   "campus, because contracts and onsite units cover most spike hours. The all-merchant line ignores "
                   "the import limit; it is an exposure yardstick, not a feasible plan.")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Clean energy curtailed")
            cdf, cby = AN["curt"]
            if len(cdf):
                show_c = cdf.copy()
                show_c.columns = ["Resource", "Available MWh", "Used MWh", "Curtailed MWh", "Curtailed share", "Paid for, unused $"]
                st.dataframe(show_c.style.format({"Available MWh": "{:,.0f}", "Used MWh": "{:,.0f}", "Curtailed MWh": "{:,.0f}",
                                                  "Curtailed share": "{:.0%}", "Paid for, unused $": "{:,.0f}"}),
                             hide_index=True, width="stretch")
                st.caption("Available-generation contracts pay for every available MWh. Oversizing wind/solar is still "
                           "chosen when the extra clean MWh in low-output hours are worth more than the curtailed surplus.")
            else:
                st.caption("No offsite clean contracts selected.")
        with c2:
            st.subheader("Annual vs hourly clean")
            cov = AN["cov"]
            ann_c = pd.DataFrame(m["annual_results"])[["model_year", "clean_energy_share"]].merge(
                cov["annual"].rename(columns={"year": "model_year"}), on="model_year")
            f = go.Figure()
            f.add_trace(go.Scatter(x=ann_c.model_year, y=ann_c.clean_energy_share * 100, name="Annual clean share (checker)", mode="lines+markers", line=dict(color="#2a9d8f")))
            f.add_trace(go.Scatter(x=ann_c.model_year, y=ann_c.hourly_matched_share * 100, name="Hourly matched share", mode="lines+markers", line=dict(color="#264653", dash="dot")))
            f.add_trace(go.Scatter(x=ann_c.model_year, y=ann_c.full * 100, name="Hours fully clean", mode="lines+markers", line=dict(color="#e76f51", dash="dash")))
            f.update_layout(height=300, yaxis_title="%", xaxis_title="Model year", legend=dict(orientation="h", y=1.25), margin=dict(t=50))
            st.plotly_chart(f, width="stretch")

# ====================================================================================
with TAB_CMP:
    S.setdefault("pins", [])
    name = st.text_input("Label for this result", value=f"Scenario {len(S.pins) + 1}")
    if st.button("📌 Pin the current recommendation", disabled=best is None):
        mm = best.metrics
        S.pins.append({"Scenario": name,
                       "Must-haves": "; ".join(f"{k}={v}" for k, v in asdict(req).items()
                                               if v not in (None, False, (), True) and k != "premium_ref_open") or "none",
                       "Speed/Cost/Clean": f"{S.speed}/{S.cost}/{S.env}", "Grid delay": opt.grid_delay,
                       "Opens": f"M{best.scenario.initial_service_month}",
                       **{LABELS[k]: f"{best.caps.get(k, 0):.0f}" for k in RES},
                       "Total $M": f"{mm['total_decision_cost_usd'] / 1e6:,.1f}",
                       "$/MWh req.": f"{mm['decision_cost_usd_per_requested_mwh']:.2f}",
                       "kg/MWh": f"{mm['combined_electricity_co2_kg_per_mwh']:.0f}",
                       "Clean %": f"{mm['clean_energy_share'] * 100:.0f}",
                       "Tier 1 MWh": f"{mm['relocated_local_equivalent_mwh']:,.0f}",
                       "Tier 2 MWh": f"{mm['interrupted_mwh']:,.0f}"})
    if S.pins:
        st.dataframe(pd.DataFrame(S.pins).set_index("Scenario").T.astype(str), width="stretch")
        if st.button("Clear"):
            S.pins = []
    else:
        st.caption("Pin a result, change one priority, recommend again and pin it, to show exactly what moved.")

# ====================================================================================
with TAB_HOW:
    st.markdown(f"""
**From customer answers to a portfolio**

1. **Must-haves are constraints.** Deadlines limit which opening months are searched (full demand
   is always opening + 10 months). Emissions cap, clean share, merchant share, cost cap and zero
   Tier 2 are constraints inside the optimizer and are re-checked on the full chronological run.
2. **Nice-to-haves are prices.** The sliders set the value of opening a month earlier
   (anchor {money(ANCHOR_VALUE_PER_MONTH)}/month at equal weight) and an internal carbon price
   (anchor ${ANCHOR_CARBON_PRICE:.0f}/t). Both are shown to the customer, can be typed in directly,
   and are reported apart from common cost.
3. **For each opening month a mixed-integer program sizes the portfolio**: catalog blocks and
   maxima, 8-acre land limit, availability dates, exact horizon capacity and contract charges,
   and hourly dispatch on representative days (low/median/high renewable days across the horizon
   plus every stress day), objective = common cost + carbon valuation.
4. **Every one of the 87,600 hours is then dispatched** month by month with the battery state of
   charge carried across months and years. Any unserved hour adds those days to the sizing
   problem and it is re-solved; a missed portfolio-level must-have is tightened and re-solved.
5. **The packet's own checker scores the dispatch.** Every cost and emissions number in this
   product is the common benchmark figure.
6. **The winner** has the lowest common cost + carbon valuation + delay valuation, compared per
   requested MWh. Alternatives show what they gain, give up, and the break-even value at which
   they would win. If nothing passes, the tool relaxes one must-have at a time and reports the
   nearest fix.
""")
    st.subheader("Resource catalog (packet)")
    st.dataframe(cs.options[["option_id", "label", "block_mw", "max_mw", "available_month", "capex_usd_per_kw",
                             "fom_usd_per_kw_year", "payment_usd_per_mwh", "heat_rate_mmbtu_per_mwh_hhv",
                             "co2_t_per_mwh", "land_acres_per_mw"]], hide_index=True, width="stretch")

# ====================================================================================
with TAB_EXP:
    if S.get("site_key"):
        st.error("Exports below are for a SCREENING site (regionally scaled inputs). They will not pass the packet "
                 "checker. Switch back to the benchmark site for the official submission files.")
    if best is None:
        st.info("No feasible recommendation to export.")
    else:
        port = portfolio_dict(best)
        st.download_button("portfolio.json", json.dumps(port, indent=2), "portfolio.json", "application/json")
        st.download_button("dispatch.csv (87,600 rows)", best.dispatch.to_csv(index=False, float_format="%.6f"),
                           "dispatch.csv", "text/csv")
        st.download_button("check_results.json", json.dumps(best.metrics, indent=2), "check_results.json",
                           "application/json")
        smd = summary_md(best, rec, prefs, req, opt)
        st.download_button("summary.md", smd, "summary.md", "text/markdown")
        st.markdown(smd)
