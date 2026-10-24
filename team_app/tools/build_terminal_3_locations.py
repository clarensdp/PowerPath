import sys, json, numpy as np, time
from pathlib import Path
TEAM_APP = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TEAM_APP)
from gridpilot.advisor import *
from gridpilot.regions import resolve, STATES, COUNTRIES
from gridpilot.screener import scenario_for, illustrative_parcels, score_parcels, location_score
from gridpilot.interconnect import deliverable_power
from gridpilot.engine import context, cs, OPT
P = str(Path(__file__).resolve().parents[1] / 'terminal') + '/'
D = json.load(open(P + 'data2.json'))
prefs = Preferences(); v, lam = prefs.implied()
queries = ['78626'] + [s for s in STATES if s != 'TX'] + [COUNTRIES[c][0] for c in COUNTRIES]
locs = [(q, resolve(q)) for q in queries]
t = time.time()
res = run_many([scenario_for(l, lam, 20) for _, l in locs], 2)
print('runs', round(time.time() - t), flush=True)
ref = np.arange(87600) % 8760
hour = ref % 24
onpk = (hour >= 6) & (hour <= 21)
yr = np.arange(87600) // 8760
HR_T, VOM_T = OPT.loc['gas_turbine', 'heat_rate_mmbtu_per_mwh_hhv'], OPT.loc['gas_turbine', 'payment_usd_per_mwh']
HR_E, VOM_E = OPT.loc['gas_engine', 'heat_rate_mmbtu_per_mwh_hhv'], OPT.loc['gas_engine', 'payment_usd_per_mwh']
sites = []
for (q, l), r in zip(locs, res):
    needs_gas = any(r.caps.get(k, 0) > 0 for k in ('gas_turbine', 'gas_engine', 'fuel_cell'))
    par = score_parcels(illustrative_parcels(l), needs_gas)
    sc = location_score(l, r, par, (prefs.speed, prefs.cost, prefs.env))
    ctx = context(20, 0, (), '' if l['benchmark'] else l['key'])
    p, g = ctx['grid_price'], ctx['gas_price']
    sol = np.clip(cs.hourly['solar_proxy_cf'].to_numpy()[ref] * l['solar_ratio'], 0, 1)
    wnd = np.clip(cs.hourly['wind_proxy_cf'].to_numpy()[ref] * l['wind_ratio'], 0, 1)
    strip = []
    for y in range(10):
        m = yr == y
        pa = p[m]
        strip.append(dict(year=y + 1, atc=float(pa.mean()), onpk=float(pa[onpk[m]].mean()), offpk=float(pa[~onpk[m]].mean()),
                          p95=float(np.quantile(pa, 0.95)), spike_h=int((pa > 200).sum()), neg_h=int((pa < 0).sum()),
                          gas=float(g[m].mean()), ccgt=float((HR_T * g[m] + VOM_T).mean()), recip=float((HR_E * g[m] + VOM_E).mean()),
                          solar_cap=float((pa * sol[m]).sum() / max(sol[m].sum(), 1e-9)),
                          wind_cap=float((pa * wnd[m]).sum() / max(wnd[m].sum(), 1e-9))))
    mm = r.metrics or {}
    dp = deliverable_power(r, int(l['delay'])) if r.caps else None
    sites.append(dict(q=q, key=l['key'], abbr=l['abbr'], label=l['label'] + (f" ({l['zip']})" if l.get('zip') else ''), grid=l['grid'], kind=l['kind'],
        delay=l['delay'], water=l['water'], policy=l.get('policy', ''), provenance=l['provenance'], coarse=l['coarse'], benchmark=l['benchmark'],
        price_c=l['price_c'], co2_kg_grid=l['co2_kg'], land=l['land_usd'], solar_cf=l['solar_cf'], wind_cf=l['wind_cf'],
        score=sc['score'], verdict=sc['verdict'], confidence=sc['confidence'],
        components={k: dict(score=round(x[0], 1), basis=x[1]) for k, x in sc['components'].items()},
        cost=mm.get('decision_cost_usd_per_requested_mwh'), kg=mm.get('combined_electricity_co2_kg_per_mwh'),
        clean=mm.get('clean_energy_share'), mix={k: x for k, x in r.caps.items() if x > 0}, ok=r.status == 'ok',
        grid_full=30 + int(l['delay']), bridge_mw=float(dp['bridge_mw']) if dp else None,
        parcels_pass=int(par.passes.sum()), parcels_n=len(par),
        strip=strip,
        parcels=[dict(id=x.parcel_id, acres=x.acres, mw=x.substation_spare_mw, gas=x.dist_gas_km, flood=int(x.flood_zone), zoning=x.zoning,
                      usd=x.land_usd_per_acre, ok=bool(x.passes), score=x.parcel_score) for x in par.head(25).itertuples()]))
D['sites'] = sites
D['contracts'] = {'solar': float(OPT.loc['utility_solar', 'payment_usd_per_mwh']), 'wind': float(OPT.loc['wind', 'payment_usd_per_mwh']),
                  'nuclear': float(OPT.loc['nuclear', 'payment_usd_per_mwh'])}
json.dump(D, open(P + 'terminal_data.json', 'w'), default=float)
print('ok', len(sites), round(len(json.dumps(D, default=float)) / 1024), 'KB', round(time.time() - t))
