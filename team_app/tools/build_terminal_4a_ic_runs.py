import sys, json, time
sys.path.insert(0, '/home/claude/v7/team_app')
from dataclasses import replace
from gridpilot.advisor import *
from gridpilot.interconnect import profile_for
from gridpilot.engine import OPT, THERMAL, BATT
states = sys.argv[1].split(','); out = sys.argv[2]
prefs = Preferences(); v, lam = prefs.implied(); req = Requirements()
DELAYS = [0, 6, 12, 18, 24, 36]
def pack(r):
    if r is None: return None
    mm = r.metrics or {}
    firm = {k: [float(r.caps.get(k, 0)), int(OPT.loc[k, 'available_month'])] for k in THERMAL + [BATT] if r.caps.get(k, 0) > 0}
    return dict(open=r.scenario.initial_service_month, ok=r.status == 'ok',
                cost=mm.get('decision_cost_usd_per_requested_mwh'), kg=mm.get('combined_electricity_co2_kg_per_mwh'),
                mix={k: float(x) for k, x in r.caps.items() if x > 0}, firm=firm)
res = {}
for ab in states:
    key = '' if ab == 'TX' else 'US-' + ab
    base = Options(workers=1, region=key); rd = region_delay(base)
    curves = {}
    for d in DELAYS:
        t = time.time()
        opt = replace(base, grid_delay=d - rd)
        w = cached_run(make_scenario(max(14, 18 + d), req, opt, lam))
        b = cached_run(make_scenario(20, req, opt, lam)) if 20 < 18 + d else None
        curves[d] = dict(wait=pack(w), bridge=pack(b))
        print(ab, d, round(time.time() - t, 1), flush=True)
    res[ab] = curves
    json.dump(res, open(out, 'w'), default=float)
print('DONE', flush=True)
