"""Public power-market feeds, normalised to daily observations.

Every observation carries its source, URL template, unit and retrieval time. Errors
never include credential-bearing URLs. Providers take an injected `fetch(url, params)`
so tests run on recorded payloads and production uses bounded urllib requests.

Coverage (no licence needed):
  NYISO   day-ahead zonal LBMP, public CSV, no key
  EIA     Henry Hub spot (natural-gas/pri/fut), BA daily demand (electricity/rto/daily-region-data),
          BA daily generation by fuel (electricity/rto/daily-fuel-type-data),
          state retail price by sector (electricity/retail-sales); free API key
Other ISOs (PJM, ERCOT, MISO, CAISO, SPP, ISO-NE) and forward curves come in through the
licensed import route until their access terms are confirmed.
"""
import csv
import io
import json
import math
import os
import statistics
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

UA = 'PowerPath/31.5 market data (+https://github.com/clarensdp/powerpath)'
NYISO_DAM = 'http://mis.nyiso.com/public/csv/damlbmp/{day}damlbmp_zone.csv'
NYISO_ZONES = ('CAPITL', 'CENTRL', 'DUNWOD', 'GENESE', 'H Q', 'HUD VL', 'LONGIL', 'MHK VL', 'MILLWD', 'N.Y.C.', 'NORTH', 'NPX', 'O H', 'PJM', 'WEST')
EIA = 'https://api.eia.gov/v2/'
EIA_KEY_ENV = 'POWERPATH_EIA_API_KEY'


class MarketError(Exception):
    """Client-safe message."""


def http_fetch(url, params=None, timeout=20):
    full = url + ('?' + urllib.parse.urlencode(params, doseq=True) if params else '')
    req = urllib.request.Request(full, headers={'User-Agent': UA, 'Accept': 'application/json, text/csv'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed public hosts)
            if r.status != 200:
                raise MarketError(f'{urllib.parse.urlparse(url).netloc} returned HTTP {r.status}')
            return r.read(8_000_000).decode('utf-8-sig')
    except urllib.error.HTTPError as exc:
        raise MarketError(f'{urllib.parse.urlparse(url).netloc} returned HTTP {exc.code}') from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise MarketError(f'{urllib.parse.urlparse(url).netloc} is unreachable') from None


def _finite(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ------------------------------------------------------------------ NYISO

def nyiso_day(fetch, day, zone):
    """Hourly day-ahead LBMP for one zone and day -> daily stats observation."""
    if zone not in NYISO_ZONES:
        raise MarketError(f'Unknown NYISO zone "{zone}". Zones: {", ".join(NYISO_ZONES)}')
    text = fetch(NYISO_DAM.format(day=day.strftime('%Y%m%d')), None)
    reader = csv.DictReader(io.StringIO(text))
    need = {'Time Stamp', 'Name', 'LBMP ($/MWHr)'}
    if not reader.fieldnames or not need <= set(reader.fieldnames):
        raise MarketError('NYISO file layout not recognised')
    hours = []
    for row in reader:
        if row['Name'].strip() != zone:
            continue
        ts = datetime.strptime(row['Time Stamp'].strip(), '%m/%d/%Y %H:%M')
        price = _finite(row['LBMP ($/MWHr)'])
        if price is not None:
            hours.append((ts, price, _finite(row.get('Marginal Cost Congestion ($/MWHr)'))))
    if len(hours) < 20:
        raise MarketError(f'NYISO {zone} {day}: only {len(hours)} hourly prices published')
    return daily_stats(day, hours)


def daily_stats(day, hours):
    prices = [p for _, p, _ in hours]
    weekday = day.weekday() < 5
    # Eastern on-peak convention: hours beginning 07:00–22:00, Monday–Friday (NERC holidays not excluded).
    peak = [p for ts, p, _ in hours if weekday and 7 <= ts.hour <= 22]
    off = [p for ts, p, _ in hours if not (weekday and 7 <= ts.hour <= 22)]
    cong = [c for _, _, c in hours if c is not None]
    return {'period': day.isoformat(), 'avg': round(statistics.fmean(prices), 4),
            'on_peak': round(statistics.fmean(peak), 4) if peak else None,
            'off_peak': round(statistics.fmean(off), 4) if off else None,
            'max': max(prices), 'min': min(prices), 'stdev': round(statistics.pstdev(prices), 4),
            'congestion_avg': round(statistics.fmean(cong), 4) if cong else None, 'hours': len(prices)}


# ------------------------------------------------------------------ EIA

def _eia_key():
    key = os.environ.get(EIA_KEY_ENV, '').strip()
    if not key:
        raise MarketError(f'Configure {EIA_KEY_ENV} (free at eia.gov/opendata) for EIA data')
    return key


def _eia_rows(fetch, route, params):
    text = fetch(EIA + route, {'api_key': _eia_key(), **params})
    try:
        payload = json.loads(text)
    except ValueError:
        raise MarketError('EIA response was not JSON') from None
    rows = (payload.get('response') or {}).get('data')
    if not isinstance(rows, list):
        raise MarketError(str((payload.get('error') or 'EIA response is missing its data array'))[:200])
    return rows


def eia_henry_hub(fetch, start, end):
    rows = _eia_rows(fetch, 'natural-gas/pri/fut/data/', {
        'frequency': 'daily', 'data[0]': 'value', 'facets[series][]': 'RNGWHHD',
        'start': start.isoformat(), 'end': end.isoformat(), 'sort[0][column]': 'period', 'sort[0][direction]': 'asc', 'length': 5000})
    out = []
    for r in rows:
        v = _finite(r.get('value'))
        if v is not None and str(r.get('units', '$/MMBTU')).upper().replace(' ', '') in ('$/MMBTU', 'DOLLARSPERMILLIONBTU'):
            out.append({'period': str(r['period'])[:10], 'value': v})
    return out


def eia_ba_demand(fetch, ba, start, end):
    rows = _eia_rows(fetch, 'electricity/rto/daily-region-data/data/', {
        'frequency': 'daily', 'data[0]': 'value', 'facets[respondent][]': ba, 'facets[type][]': 'D',
        'facets[timezone][]': 'Eastern', 'start': start.isoformat(), 'end': end.isoformat(),
        'sort[0][column]': 'period', 'sort[0][direction]': 'asc', 'length': 5000})
    return [{'period': str(r['period'])[:10], 'value': _finite(r.get('value'))} for r in rows
            if r.get('respondent') == ba and _finite(r.get('value')) is not None]


FUEL_GROUPS = {'NG': 'gas', 'COL': 'coal', 'OIL': 'oil', 'NUC': 'nuclear', 'WAT': 'hydro', 'SUN': 'solar', 'WND': 'wind', 'OTH': 'other', 'BAT': 'storage', 'GEO': 'other', 'PS': 'storage'}
# Screening combustion factors (t CO2 per MWh generated). Configurable estimate, not a reported inventory.
EMISSION_FACTORS = {'coal': 1.0, 'gas': 0.41, 'oil': 0.8, 'nuclear': 0.0, 'hydro': 0.0, 'solar': 0.0, 'wind': 0.0, 'storage': 0.0, 'other': 0.4}


def eia_fuel_mix(fetch, ba, start, end):
    rows = _eia_rows(fetch, 'electricity/rto/daily-fuel-type-data/data/', {
        'frequency': 'daily', 'data[0]': 'value', 'facets[respondent][]': ba, 'facets[timezone][]': 'Eastern',
        'start': start.isoformat(), 'end': end.isoformat(), 'sort[0][column]': 'period', 'sort[0][direction]': 'asc', 'length': 5000})
    days = {}
    for r in rows:
        v = _finite(r.get('value'))
        if r.get('respondent') != ba or v is None:
            continue
        g = FUEL_GROUPS.get(str(r.get('fueltype')), 'other')
        d = days.setdefault(str(r['period'])[:10], {})
        d[g] = d.get(g, 0.0) + max(0.0, v)
    out = []
    for period, mix in sorted(days.items()):
        total = sum(mix.values())
        if total <= 0:
            continue
        out.append({'period': period, 'total_mwh': round(total, 3),
                    'shares': {k: round(v / total, 6) for k, v in sorted(mix.items())},
                    'carbon_t_per_mwh': round(sum(EMISSION_FACTORS.get(k, 0.4) * v for k, v in mix.items()) / total, 6)})
    return out


def eia_retail(fetch, state, sector='IND', months=24):
    rows = _eia_rows(fetch, 'electricity/retail-sales/data/', {
        'frequency': 'monthly', 'data[0]': 'price', 'facets[stateid][]': state, 'facets[sectorid][]': sector,
        'sort[0][column]': 'period', 'sort[0][direction]': 'desc', 'length': months})
    out = []
    for r in rows:
        v = _finite(r.get('price'))
        if r.get('stateid') == state and r.get('sectorid') == sector and v is not None:
            out.append({'period': str(r['period'])[:7], 'value': round(v * 10, 4)})  # cents/kWh -> USD/MWh
    return sorted(out, key=lambda x: x['period'])
