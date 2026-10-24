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
