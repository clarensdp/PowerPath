"""Build regions.json: real hourly grid shapes for 31 U.S. balancing authorities.

Inputs
- EIA-930 hourly carbon intensity and average-day generation shares by BA, Oct 2025 - Sep 2026,
  from the MIT-licensed Cleanest Hour build (github.com/Bowen1314/cleanest-hour, data/*.json),
  which processes EIA930_BALANCE files with EPA eGRID2023 emission factors.
- Solar: pvlib solar geometry + Ineichen clear sky (Linke turbidity climatology) for a
  single-axis tracker at each BA's load-weighted location, modulated by observed daily
  cloudiness from the ERCOT 2023 reference year.
- Wind: each BA's own season-by-hour wind profile (EIA-930), modulated by ERCOT 2023
  day-to-day variability; BAs with <1% wind share fall back to the ERCOT shape.
- Price shape: modeled in the browser from hourly carbon intensity (marginal fossil proxy);
  elasticity fit here on ERCOT month-hour cells.
Outputs base64-packed arrays (uint16 co2 kg/MWh, uint8 solar/wind CF x 250).
"""
import json, base64, sys, math
import numpy as np, pandas as pd, pvlib

SRC = sys.argv[1] if len(sys.argv) > 1 else '/home/claude/ext/cleanest-hour/data'
H = json.load(open('hourly.json'))
TXs, TXw, TXp = np.array(H['solar']), np.array(H['wind']), np.array(H['whole'])

LOC = {'PJM': (39.0, -77.5), 'ERCO': (31.0, -97.5), 'MISO': (41.5, -90.5), 'SWPP': (37.0, -98.0), 'SOCO': (33.0, -85.0),
       'DUK': (35.5, -80.8), 'CPLE': (35.5, -78.5), 'TVA': (35.8, -86.5), 'AZPS': (33.4, -112.0), 'SRP': (33.4, -111.9),
       'TEPC': (32.2, -110.9), 'NEVP': (36.2, -115.1), 'PACE': (40.7, -111.9), 'PSCO': (39.7, -105.0), 'CISO': (36.5, -119.5),
       'NYIS': (42.0, -75.0), 'ISNE': (42.4, -71.5), 'BPAT': (46.0, -120.5), 'PGE': (45.5, -122.7), 'PSEI': (47.6, -122.2),
       'PACW': (44.0, -123.0), 'FPL': (26.5, -80.5), 'FPC': (28.5, -82.0), 'LGEE': (38.0, -85.5), 'PNM': (35.1, -106.6),
       'IPCO': (43.6, -116.2), 'NWMT': (46.5, -110.5), 'SCEG': (34.0, -81.0), 'SC': (33.5, -80.0), 'LDWP': (34.0, -118.3),
       'BANC': (38.6, -121.4)}
TZ = {'PJM': 'America/New_York', 'ERCO': 'America/Chicago'}
STATE_BA = {'AL': 'SOCO', 'AZ': 'SRP', 'AR': 'MISO', 'CA': 'CISO', 'CO': 'PSCO', 'CT': 'ISNE', 'DE': 'PJM', 'DC': 'PJM', 'FL': 'FPL',
            'GA': 'SOCO', 'ID': 'IPCO', 'IL': 'PJM', 'IN': 'MISO', 'IA': 'MISO', 'KS': 'SWPP', 'KY': 'LGEE', 'LA': 'MISO', 'ME': 'ISNE',
            'MD': 'PJM', 'MA': 'ISNE', 'MI': 'MISO', 'MN': 'MISO', 'MS': 'MISO', 'MO': 'MISO', 'MT': 'NWMT', 'NE': 'SWPP', 'NV': 'NEVP',
            'NH': 'ISNE', 'NJ': 'PJM', 'NM': 'PNM', 'NY': 'NYIS', 'NC': 'DUK', 'ND': 'MISO', 'OH': 'PJM', 'OK': 'SWPP', 'OR': 'PGE',
            'PA': 'PJM', 'RI': 'ISNE', 'SC': 'SCEG', 'SD': 'SWPP', 'TN': 'TVA', 'TX': 'ERCO', 'UT': 'PACE', 'VT': 'ISNE', 'VA': 'PJM',
            'WA': 'BPAT', 'WV': 'PJM', 'WI': 'MISO', 'WY': 'PACE'}

def season(d):  # d = day of year 0..364 in a Jan-1 year
    m = (pd.Timestamp('2026-01-01') + pd.Timedelta(days=int(d))).month
    return 'winter' if m in (12, 1, 2) else 'spring' if m in (3, 4, 5) else 'summer' if m in (6, 7, 8) else 'fall'
SEAS = [season(d) for d in range(365)]

def tracker_clearsky(lat, lon, tz):
    t = pd.date_range('2023-01-01', periods=8760, freq='h', tz=tz) + pd.Timedelta(minutes=30)
    loc = pvlib.location.Location(lat, lon, tz=tz)
    sp = loc.get_solarposition(t)
    cs = loc.get_clearsky(t, model='ineichen')
    tr = pvlib.tracking.singleaxis(sp['apparent_zenith'], sp['azimuth'], axis_azimuth=180, max_angle=60, backtrack=True, gcr=0.35)
    poa = pvlib.irradiance.get_total_irradiance(tr['surface_tilt'].fillna(0), tr['surface_azimuth'].fillna(180),
                                                 sp['apparent_zenith'], sp['azimuth'], cs['dni'], cs['ghi'], cs['dhi'])
    p = (poa['poa_global'].fillna(0).clip(lower=0) / 1000 * 0.86).clip(upper=1).values  # 14% system losses
    return p

# ERCOT daily cloudiness index: observed daily solar energy / clear-sky tracker energy in Texas
tx_cs = tracker_clearsky(*LOC['ERCO'], 'America/Chicago')
dobs = TXs.reshape(365, 24).sum(1); dcs = tx_cs.reshape(365, 24).sum(1)
kidx = dobs / np.maximum(dcs, 1e-6); kidx = kidx / np.percentile(kidx, 95); kidx = np.clip(kidx, 0.05, 1.0)

# ERCOT wind variability relative to its season-hour mean
TXw2 = TXw.reshape(365, 24)
txmean = {s: TXw2[[d for d in range(365) if SEAS[d] == s]].mean(0) for s in ('winter', 'spring', 'summer', 'fall')}
wvar = np.array([TXw2[d] / np.maximum(txmean[SEAS[d]], 1e-3) for d in range(365)])

def reorder(rows):  # source starts 2025-10-01; rotate to Jan 1
    return rows[92:] + rows[:92]

FU = None; out = {}
idx = json.load(open(f'{SRC}/index.json'))
meta = {r['ba']: r for r in idx['regions']}
ci_tx = None
for ba, (lat, lon) in LOC.items():
    d = json.load(open(f'{SRC}/{ba}.json')); FU = d['fuels']
    ci = np.array([[np.nan if v is None else v for v in row] for row in reorder(d['ci'])], dtype=float)  # 365x24 g/kWh
    hm = np.nanmean(ci, 0); ci = np.where(np.isnan(ci), hm[None, :], ci)
    if ba == 'ERCO': ci_tx = ci.copy()
    # solar
    cs = tracker_clearsky(lat, lon, d['tz'])
    sol = (cs.reshape(365, 24) * kidx[:, None]).ravel()
    # wind
    wi = FU.index('wind'); share = meta[ba]['genShare'].get('wind', 0)
    if share >= 0.01:
        prof = {s: np.array([r[wi] for r in d['mix'][s]], float) for s in ('winter', 'spring', 'summer', 'fall')}
        allm = np.mean([prof[s].mean() for s in prof])
        w = np.array([prof[SEAS[dd]] / allm * wvar[dd] for dd in range(365)]).ravel()
        wsrc = 'own'
    else:
        w = TXw / TXw.mean(); wsrc = 'ercot'
    w = w / w.mean() * 0.35; w = np.clip(w, 0, 1)
    sol_n = np.clip(sol / sol.mean() * 0.22, 0, 1) if sol.mean() > 0 else sol
    enc = lambda a, dt: base64.b64encode(np.asarray(a).astype(dt).tobytes()).decode()
    out[ba] = {'name': d['name'], 'tz': d['tz'], 'lat': lat, 'lon': lon, 'windSource': wsrc,
               'co2Avg': round(float(ci.mean()), 1), 'egrid': meta[ba].get('egrid2023Avg_g_per_kwh'),
               'share': {k: round(v, 3) for k, v in meta[ba]['genShare'].items() if v >= 0.005},
               'co2': enc(np.round(ci.ravel()), '<u2'), 'solar': enc(np.round(sol_n * 250), 'u1'), 'wind': enc(np.round(w * 250), 'u1')}

# price elasticity on carbon: fit log(price) ~ e*log(ci) over ERCOT month x hour cells
mon = np.array([(pd.Timestamp('2023-01-01') + pd.Timedelta(hours=h)).month for h in range(8760)])
P = TXp.reshape(-1); C = ci_tx.ravel()
cells = [(m, h) for m in range(1, 13) for h in range(24)]
hr = np.arange(8760) % 24
lp = np.array([np.log(max(5, np.median(P[(mon == m) & (hr == h)]))) for m, h in cells])
lc = np.array([np.log(C[(mon == m) & (hr == h)].mean()) for m, h in cells])
e = float(np.polyfit(lc, lp, 1)[0]); r = float(np.corrcoef(lc, lp)[0, 1])
print('elasticity', round(e, 2), 'r', round(r, 2))
res = {'meta': {'period': 'Oct 2025 - Sep 2026 (EIA-930), rotated to a Jan-Dec year', 'priceElasticity': round(max(0.5, min(3.0, e)), 2),
                'priceFitR': round(r, 2), 'source': 'EIA-930 via Cleanest Hour (MIT) + EPA eGRID2023 factors; solar: pvlib clear-sky tracker x ERCOT 2023 cloudiness; wind: BA season-hour profile x ERCOT 2023 variability'},
       'stateBA': STATE_BA, 'ba': out}
json.dump(res, open('regions.json', 'w'), separators=(',', ':'))
print('wrote regions.json', round(len(json.dumps(res)) / 1e6, 2), 'MB')
for ba in ('PJM', 'ERCO', 'MISO', 'SOCO', 'CISO', 'SRP', 'BPAT'):
    o = out[ba]; print(ba, o['co2Avg'], o['egrid'], o['windSource'])
