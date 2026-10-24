import sys, json, numpy as np
from pathlib import Path
TEAM_APP = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TEAM_APP)
from gridpilot.advisor import *
from gridpilot.analytics import curtailment, clean_coverage, spikes, n1_check
from gridpilot.regions import resolve
from gridpilot.screener import scenario_for, illustrative_parcels, score_parcels, location_score, price_forecast
from gridpilot.engine import context, LABELS
W=2
prefs=Preferences(); v, lam = prefs.implied()
rec = recommend(prefs, Requirements(), Options(workers=W))
best = rec.best; m = best.metrics
recn1 = recommend(prefs, Requirements(n_minus_1=True), Options(workers=W)).best
out = {}
def portrec(r):
    mm=r.metrics
    return dict(open=r.scenario.initial_service_month, caps={k:v for k,v in r.caps.items() if v>0},
                cost=mm['decision_cost_usd_per_requested_mwh'], total=mm['total_decision_cost_usd'],
                kg=mm['combined_electricity_co2_kg_per_mwh'], clean=mm['clean_energy_share'],
                merch=mm['merchant_mwh']/mm['local_served_mwh'], t1=mm['relocated_local_equivalent_mwh'],
                t2=mm['interrupted_mwh'], reloc_cost=mm['relocation_cost_usd'], int_cost=mm['interruption_consequence_usd'])
out['best']=portrec(best); out['n1best']=portrec(recn1)
out['value_per_month']=v; out['carbon_price']=lam
out['candidates']=[dict(open=r.scenario.initial_service_month, ok=r.status=='ok', cost=r.metrics.get('decision_cost_usd_per_requested_mwh'),
                        kg=r.metrics.get('combined_electricity_co2_kg_per_mwh'),
                        mix={k:v for k,v in r.caps.items() if v>0}) for r in rec.candidates]
out['scores']={str(k):v for k,v in rec.scores.items()}
out['alternatives']=[dict(name=a['name'], tagline=a.get('tagline',''), gains=a['gains'], gives=a['gives'], when=a['when'],
                          cost=a['result'].metrics['decision_cost_usd_per_requested_mwh'], kg=a['result'].metrics['combined_electricity_co2_kg_per_mwh'],
                          mix={k:v for k,v in a['result'].caps.items() if v>0}) for a in rec.alternatives]
out['explanation']=rec.explanation
out['annual']=[{k:y[k] for k in ('model_year','requested_mwh','total_decision_cost_usd','local_energy_cost_usd','combined_electricity_co2_kg_per_mwh','clean_energy_share')} for y in m['annual_results']]
cdf,_=curtailment(best); cov=clean_coverage(best); sp,pp,pb,pmax=spikes(best); n1=n1_check(best)
out['curt']=dict(mwh=float(cdf.curtailed_mwh.sum()), usd=float(cdf.paid_for_curtailed_usd.sum()))
out['cov']=dict(matched=cov['hourly_matched_share'], full=cov['hours_fully_clean'])
out['spikes']=dict(years=sp.year.tolist(), port=sp.portfolio_premium_usd.tolist(), base=sp.merchant_only_premium_usd.tolist(), port_total=pp, base_total=pb, pmax=pmax)
out['n1']={k:(float(v) if isinstance(v,(int,float,np.floating,np.integer)) else v) for k,v in n1.items() if k!='options'}
out['n1']['options']=[{k:(float(v) if isinstance(v,(np.floating,np.integer,np.bool_)) else v) for k,v in o.items()} for o in n1['options']]
# stress day: first event day in model year 5
ctx = context(best.scenario.initial_service_month, 0, (), "")
d = best.dispatch; act = ctx['active']
ev = np.nonzero(act & (np.arange(len(act))//8760 == 4))[0]
day = ev[0]//24; h0, h1 = day*24-6, day*24+30
cols = {'Wind':'wind_mw','Solar':'utility_solar_mw','Merchant':'grid_mw','Turbine':'gas_turbine_mw','Engines':'gas_engine_mw','Fuel cells':'fuel_cell_mw','Battery':'battery_4h_discharge_mw','Tier 1 moved':'tier1_relocated_mw','Tier 2 cut':'tier2_curtailed_mw'}
out['stress']=dict(hours=list(range(h0,h1)), series={k:[round(float(x),2) for x in d[c].values[h0:h1]] for k,c in cols.items() if d[c].values[h0:h1].sum()>1e-6},
                   load=[round(float(x),2) for x in ctx['load'][h0:h1]], limit=[round(float(x),2) for x in ctx['grid_limit'][h0:h1]],
                   tier0=[round(float(x),2) for x in ctx['tier0'][h0:h1]], stress=[int(x) for x in act[h0:h1]])
# screener
queries=['78626','20147','Iowa','Ohio','Oklahoma','Arizona','Ireland','Japan']
locs=[(q,resolve(q)) for q in queries]
res=run_many([scenario_for(l, lam, 20) for _,l in locs], W)
sites=[]
for (q,l),r in zip(locs,res):
    needs_gas=any(r.caps.get(k,0)>0 for k in ('gas_turbine','gas_engine','fuel_cell'))
    par=score_parcels(illustrative_parcels(l), needs_gas)
    sc=location_score(l, r, par, (prefs.speed,prefs.cost,prefs.env))
    pf=price_forecast(l)
    mm=r.metrics or {}
    sites.append(dict(q=q, label=l['label']+(f" ({l['zip']})" if l.get('zip') else ''), grid=l['grid'], kind=l['kind'],
        lat=l['lat'], lon=l['lon'], delay=l['delay'], water=l['water'], policy=l.get('policy',''), provenance=l['provenance'],
        score=sc['score'], verdict=sc['verdict'], confidence=sc['confidence'],
        components={k:dict(score=round(v[0],1), basis=v[1], weight=round(sc['weights'][k],1)) for k,v in sc['components'].items()},
        cost=mm.get('decision_cost_usd_per_requested_mwh'), kg=mm.get('combined_electricity_co2_kg_per_mwh'),
        clean=mm.get('clean_energy_share'), mix={k:v for k,v in r.caps.items() if v>0}, ok=r.status=='ok',
        price_avg=[round(x,1) for x in pf['avg']], price_p95=[round(x,1) for x in pf['p95']],
        parcels=[dict(id=p.parcel_id, lat=round(p.lat,4), lon=round(p.lon,4), acres=p.acres, mw=p.substation_spare_mw, gas=p.dist_gas_km,
                      flood=int(p.flood_zone), zoning=p.zoning, usd=p.land_usd_per_acre, ok=bool(p.passes), score=p.parcel_score) for p in par.head(25).itertuples()]))
out['sites']=sites
out['labels']=LABELS
json.dump(out, open(str(Path(__file__).resolve().parents[1] / 'terminal') + '/data.json','w'), default=float)
print('ok', len(json.dumps(out, default=float))//1024, 'KB', [ (s['label'],s['score']) for s in sites])
