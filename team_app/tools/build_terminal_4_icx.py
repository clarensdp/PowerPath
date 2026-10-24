"""Interconnect explorer data: per-state engine curves (wait vs bridge at grid waits 0-36 mo) + grid mix.
Usage: python tools/build_terminal_4_icx.py curves1.json [curves2.json ...]  -> terminal/terminal_data.json gets D['icx']"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from gridpilot.interconnect import profile_for
from gridpilot.advisor import ref_mwh, Preferences
from gridpilot.regions import resolve
# Approx. share of in-state net generation (%), EIA State Electricity Profiles 2024, rounded.
GENMIX = {
 'TX': ({'gas': 50, 'wind': 23, 'coal': 13, 'nuclear': 8, 'solar': 6}, 'Largest US producer: gas-led, the most wind of any state and fast-growing solar. Own grid (ERCOT), the fastest large-load path.'),
 'SD': ({'wind': 56, 'hydro': 25, 'coal': 10, 'gas': 8, 'solar': 1}, 'Wind and Missouri River hydro supply roughly 80% of generation.'),
 'NE': ({'coal': 50, 'wind': 31, 'nuclear': 15, 'gas': 2, 'hydro': 2}, 'All public power. Coal-heavy, wind now about a third, one nuclear plant (Cooper).'),
 'OK': ({'gas': 48, 'wind': 42, 'coal': 8, 'hydro': 1, 'solar': 1}, 'Gas and wind split the grid; a top-three US wind state.'),
 'KS': ({'wind': 48, 'coal': 28, 'nuclear': 17, 'gas': 6, 'solar': 1}, 'Wind is the largest source (about half), plus Wolf Creek nuclear; coal declining.'),
 'IA': ({'wind': 62, 'coal': 22, 'gas': 11, 'solar': 3, 'hydro': 2}, 'Highest wind share of any state; no nuclear since Duane Arnold closed in 2020.'),
 'LA': ({'gas': 72, 'nuclear': 15, 'other': 7, 'coal': 5, 'solar': 1}, 'Gas-dominated industrial grid; two nuclear plants (Waterford 3, River Bend).'),
 'WI': ({'gas': 40, 'coal': 31, 'nuclear': 17, 'wind': 4, 'solar': 4, 'hydro': 2, 'other': 2}, 'Gas and coal lead, Point Beach nuclear; wind and solar small but growing.'),
 'MN': ({'wind': 27, 'nuclear': 24, 'coal': 22, 'gas': 18, 'solar': 5, 'other': 4}, 'Diversified: wind, nuclear (Prairie Island, Monticello), coal and gas each about a fifth or more.'),
 'KY': ({'coal': 68, 'gas': 25, 'hydro': 6, 'other': 1}, 'One of the most coal-dependent grids; gas growing; some hydro.'),
 'OH': ({'gas': 52, 'coal': 29, 'nuclear': 14, 'wind': 2, 'solar': 2, 'other': 1}, 'Gas is now the largest source, then coal and nuclear (Davis-Besse, Perry).'),
}
f = ROOT / 'terminal' / 'terminal_data.json'; D = json.load(open(f))
curves = {}
for p in sys.argv[1:]: curves.update(json.load(open(p)))
sites = {s['abbr']: s for s in D['sites'] if s.get('kind') == 'state'}
v, lam = Preferences().implied()
icx = {}
for ab, (gm, known) in GENMIX.items():
    if ab not in curves: print('missing', ab); continue
    s = sites[ab]; spread, upg, path = profile_for(s['grid'])
    icx[ab] = dict(name=s['label'].split(',')[0], grid=s['grid'], delay=int(s['delay']), spread=spread, upg_kw=upg, path=path,
                   genmix=gm, known=known, score=s['score'], curves=curves[ab])
D['icx'] = icx; D['icx_meta'] = dict(ref_mwh=ref_mwh(), value_per_month=v, order=[k for k in GENMIX if k in icx],
    genmix_src='Approximate share of in-state net generation, EIA State Electricity Profiles (2024), rounded to whole percent.')
json.dump(D, open(f, 'w'), default=float); print('icx', list(icx))
