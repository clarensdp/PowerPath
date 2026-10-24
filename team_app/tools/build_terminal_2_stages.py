import sys, json, numpy as np
from pathlib import Path
TEAM_APP = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, TEAM_APP)
from dataclasses import replace
from gridpilot.advisor import *
from gridpilot.interconnect import profile_for, energization, deliverable_power, decide
from gridpilot.deals import build, DealInputs
from gridpilot.monitor import triggers
from gridpilot.regions import resolve
D = json.load(open(str(Path(__file__).resolve().parents[1] / 'terminal') + '/data.json'))
prefs = Preferences(); v, lam = prefs.implied()
def stage(region_key, grid_name):
    opt = Options(workers=2, region=region_key); req = Requirements()
    rec = recommend(prefs, req, opt); best = rec.best
    spread, upg, path = profile_for(grid_name); delay = region_delay(opt); en = energization(delay, spread)
    s_wait = int(min(109, max(14, 18 + delay))); s_b = 20
    wait = cached_run(make_scenario(s_wait, req, opt, lam))
    bridge = cached_run(make_scenario(s_b, req, opt, lam)) if s_b < s_wait else None
    p90 = cached_run(make_scenario(best.scenario.initial_service_month, req, replace(opt, grid_delay=en['P90'] - en['P50']), lam))
    dec = decide(best, wait, bridge or wait, v, ref_mwh())
    dp = deliverable_power(best, delay); dp90 = deliverable_power(best, en['P90'])
    opts = []
    for name, r in [('Wait for grid', wait), ('Bridge to target', bridge), ('Plan at P90 grid slip', p90)]:
        if r is None: continue
        mm = r.metrics or {}
        opts.append(dict(name=name, open=r.scenario.initial_service_month, ok=r.status == 'ok',
                         cost=mm.get('decision_cost_usd_per_requested_mwh'), kg=mm.get('combined_electricity_co2_kg_per_mwh'),
                         mix={k: x for k, x in r.caps.items() if x > 0}))
    deals, pick, why, capex = build(best, delay, DealInputs())
    deals_obs, pick_obs, why_obs, _ = build(best, delay, DealInputs(prefer_off_balance_sheet=True))
    trig = triggers(best, p90, en)
    mm = best.metrics
    return dict(grid=grid_name, delay=delay, en=en, upgrade=upg * 75000, upg_kw=upg, path=path,
                decision=dict(verdict=dec['verdict'], text=dec['text'], breakeven=dec.get('breakeven')),
                dp=dict(months=list(range(61)), demand=[round(x, 1) for x in dp['demand'][:61]], grid=list(dp['grid'][:61]),
                        firm=[round(a + b, 1) for a, b in zip(dp['grid'][:61], dp['onsite'][:61])], gap=[round(x, 1) for x in dp['gap'][:61]],
                        grid90=list(dp90['grid'][:61]), bridge_mw=dp['bridge_mw'], gap_mwm=dp['bridge_mw_months']),
                options=opts, best=dict(open=best.scenario.initial_service_month, cost=mm['decision_cost_usd_per_requested_mwh'],
                                        kg=mm['combined_electricity_co2_kg_per_mwh'], mix={k: x for k, x in best.caps.items() if x > 0}),
                deals=[{k: d[k] for k in ('structure', 'total_usd', 'usd_per_mwh', 'upfront_usd', 'committed_usd', 'tenor', 'balance_sheet', 'risks', 'notes', 'recommended')} for d in deals],
                pick=pick['structure'] if pick else None, why=why, pick_obs=pick_obs['structure'] if pick_obs else None, why_obs=why_obs,
                triggers=trig)
D['stage'] = {'TX': stage('', 'ERCOT'), 'OH': stage('US-OH', resolve('Ohio')['grid'])}
for sdat in D['sites']:
    sdat['grid_full'] = 30 + int(sdat['delay'])
    rs = sdat  # bridge MW from demand ramp opening 20 vs grid
    months = np.arange(121); frac = np.where(months < 20, 0, np.minimum(1, 1/3 + (months - 20) / 15)); dem = 75 * frac
    g = np.zeros(121)
    for m0, cap in [(18, 25), (24, 50), (30, 75)]: g = np.where(months >= m0 + sdat['delay'], cap, g)
    sdat['bridge_mw'] = float(np.clip(dem - g, 0, None).max())
json.dump(D, open(str(Path(__file__).resolve().parents[1] / 'terminal') + '/data2.json', 'w'), default=float)
print('ok', D['stage']['TX']['decision'], D['stage']['OH']['decision']['verdict'])
