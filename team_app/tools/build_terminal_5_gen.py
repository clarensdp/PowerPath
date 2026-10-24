"""Portfolio builder data: 2023 reference-year hourly shapes + catalog + engine plans for calibration."""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
import pandas as pd
DATA = ROOT.parent / 'data'
h = pd.read_csv(DATA / 'reference_hourly.csv')
o = pd.read_csv(DATA / 'resource_options.csv').set_index('option_id')
case = json.load(open(DATA / 'case.json')); pt = json.load(open(DATA / 'price_trajectory.json'))
rp = json.load(open(DATA / 'response_parameters.json'))
r = lambda c, n=3: [round(float(x), n) for x in h[c]]
G = dict(
  solar=r('solar_proxy_cf', 4), wind=r('wind_proxy_cf', 4), whole=r('wholesale_price_usd_per_mwh', 2), load=r('load_mw', 2),
  t1=r('tier1_relocatable_mw', 2), t2=r('tier2_interruptible_mw', 2), hh=r('henry_hub_usd_per_mmbtu', 3), gadd=r('delivered_gas_adder_usd_per_mmbtu', 3),
  co2=r('grid_co2_t_per_mwh', 4), firm=r('firm_clean_available_fraction', 3), stress=[int(x) for x in h['stress_active']], sfrac=r('stress_import_fraction', 2),
  adder=float(h['grid_adder_usd_per_mwh'].iloc[0]),
  rates=pt['annual_real_rates'], grid=case['grid_access'], disc=case['discount_rate_real'], land=case['onsite_energy_land_acres'],
  remote=dict(cap=rp['remote_capacity_mw'] / rp['remote_energy_multiplier'], usd=rp['remote_electricity_usd_per_mwh'] * rp['remote_energy_multiplier'] + rp['relocation_service_usd_per_local_mwh'],
              mult=rp['remote_energy_multiplier'], int_usd=rp['interruption_consequence_usd_per_mwh']),
  opts={k: dict(kind=v.kind, loc=v.location, block=float(v.block_mw), max=float(v.max_mw), avail=int(v.available_month), capex=float(v.capex_usd_per_kw),
                fom=float(v.fom_usd_per_kw_year), life=int(v.life_years), pay=float(v.payment_usd_per_mwh), basis=v.payment_basis, hr=float(v.heat_rate_mmbtu_per_mwh_hhv),
                co2=float(v.co2_t_per_mwh), dur=float(v.duration_hours), rte=float(v.round_trip_efficiency), cyc=float(v.max_cycles_per_year), land=float(v.land_acres_per_mw))
        for k, v in o.iterrows()})
f = ROOT / 'terminal' / 'terminal_data.json'; D = json.load(open(f)); D['gen'] = G
json.dump(D, open(f, 'w'), default=float); print('gen ok', len(G['load']))
# Customer requests: checker-validated priority-change runs from outputs/
OUT = ROOT.parent / 'outputs'
REQ = [('', 'Balanced priorities, no must-haves (submission)', 'Speed / cost / clean weighted 34 / 33 / 33'),
       ('priority_change_speed_full_demand_by_24', 'Must reach full demand by month 24', 'Brief example 1 · speed deadline'),
       ('priority_change_clean_under_100kg', 'Cost first, with a hard cap of 100 kg CO₂/MWh', 'Brief examples 2–3 · cost priority + environmental limit'),
       ('priority_change_zero_tier2', 'No Tier 2 interruption during grid stress', 'Brief example 4 · continuity'),
       ('priority_change_n1_reliability', 'Must survive loss of the largest onsite unit (N-1)', 'Reliability must-have'),
       ('extension_execution_aware_today_m0', 'Start today with real permit and equipment lead times', 'Execution-aware extension')]
reqs = []
for d, name, sub in REQ:
    pth = OUT / d if d else OUT
    pf = json.load(open(pth / 'portfolio.json')); ck = json.load(open(pth / 'check_results.json'))
    reqs.append(dict(name=name, sub=sub, folder='outputs/' + d if d else 'outputs/', open=ck['initial_service_month'], full=ck['full_demand_month'],
                     caps={k: v for k, v in pf['capacities_mw'].items() if v > 0}, cost=ck['decision_cost_usd_per_requested_mwh'],
                     kg=ck['combined_electricity_co2_kg_per_mwh'], clean=ck['clean_energy_share'], intr=ck['interrupted_mwh'],
                     merch=ck['merchant_mwh'] / max(ck['local_served_mwh'], 1), ok=bool(ck['physical_checks_passed'])))
D = json.load(open(f)); D['requests'] = reqs; json.dump(D, open(f, 'w'), default=float); print('requests', len(reqs))
