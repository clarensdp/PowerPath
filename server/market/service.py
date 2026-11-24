"""Market metric catalog, cache and project snapshot.

Public observations are cached once per database under scope 'public'. Licensed imports
are stored under scope 'project:<id>' so one firm's licensed data never reaches another
tenant. Every value returned carries source, as-of date, retrieval time and a staleness
flag, so a number in a memo or a spreadsheet can always be traced.
"""
import json
import statistics
from datetime import date, datetime, timedelta, timezone

from server.market import providers as P

SCHEMA = '''
CREATE TABLE IF NOT EXISTS mk_obs (
 scope TEXT NOT NULL, metric TEXT NOT NULL, location TEXT NOT NULL, period TEXT NOT NULL,
 body TEXT NOT NULL, source TEXT NOT NULL, retrieved_at TEXT NOT NULL,
 PRIMARY KEY(scope, metric, location, period));
CREATE TABLE IF NOT EXISTS mk_profiles (
 project_id TEXT PRIMARY KEY REFERENCES projects(id), body TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mk_imports (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS mk_imports_no_update BEFORE UPDATE ON mk_imports BEGIN SELECT RAISE(ABORT,'Append-only import log'); END;
CREATE TRIGGER IF NOT EXISTS mk_imports_no_delete BEFORE DELETE ON mk_imports BEGIN SELECT RAISE(ABORT,'Append-only import log'); END;
'''

CATALOG = {
    'lmp_da': {'label': 'Day-ahead LMP (zonal)', 'unit': 'USD/MWh', 'frequency': 'daily', 'location': 'NYISO zone',
               'stats': ['avg', 'on_peak', 'off_peak', 'max', 'min', 'stdev', 'congestion_avg'], 'source': 'NYISO day-ahead LBMP (public CSV)',
               'url': P.NYISO_DAM.replace('{day}', 'YYYYMMDD'), 'profile': 'nyiso_zone', 'lag_days': 3},
    'henry_hub': {'label': 'Henry Hub natural gas spot', 'unit': 'USD/MMBtu', 'frequency': 'daily', 'location': 'HENRY', 'stats': ['value'],
                  'source': 'EIA natural gas spot prices (RNGWHHD)', 'url': P.EIA + 'natural-gas/pri/fut/data/', 'profile': None, 'lag_days': 10},
    'spark_spread': {'label': 'Spark spread (derived)', 'unit': 'USD/MWh', 'frequency': 'daily', 'location': 'NYISO zone', 'stats': ['avg', 'on_peak'],
                     'source': 'Derived: NYISO LMP − heat rate × Henry Hub', 'url': None, 'profile': 'nyiso_zone', 'lag_days': 10},
    'ba_demand': {'label': 'Balancing-authority demand', 'unit': 'MWh/day', 'frequency': 'daily', 'location': 'EIA BA code', 'stats': ['value', 'avg_mw'],
                  'source': 'EIA hourly electric grid monitor (daily-region-data, type D)', 'url': P.EIA + 'electricity/rto/daily-region-data/data/', 'profile': 'ba', 'lag_days': 4},
    'fuel_mix': {'label': 'Generation mix and estimated carbon intensity', 'unit': 'share / t CO2 per MWh', 'frequency': 'daily', 'location': 'EIA BA code',
                 'stats': ['gas', 'coal', 'nuclear', 'hydro', 'wind', 'solar', 'storage', 'oil', 'other', 'renewables', 'carbon_t_per_mwh'],
                 'source': 'EIA hourly electric grid monitor (daily-fuel-type-data); carbon from screening factors', 'url': P.EIA + 'electricity/rto/daily-fuel-type-data/data/', 'profile': 'ba', 'lag_days': 4},
    'retail_industrial': {'label': 'Average industrial retail price', 'unit': 'USD/MWh', 'frequency': 'monthly', 'location': 'State', 'stats': ['value'],
                          'source': 'EIA electricity retail sales (IND)', 'url': P.EIA + 'electricity/retail-sales/data/', 'profile': 'state', 'lag_days': 120},
    'retail_commercial': {'label': 'Average commercial retail price', 'unit': 'USD/MWh', 'frequency': 'monthly', 'location': 'State', 'stats': ['value'],
                          'source': 'EIA electricity retail sales (COM)', 'url': P.EIA + 'electricity/retail-sales/data/', 'profile': 'state', 'lag_days': 120},
}
DEFAULT_PROFILE = {'state': None, 'ba': None, 'nyiso_zone': None, 'heat_rate': 7.0}
NYISO_MAX_DAYS = 62
MISS_SECONDS = 600
_MISSES = {}  # (zone, day) -> time of last failed fetch; avoids re-requesting unpublished files
EIA_REFRESH_HOURS = 6


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def initialize(db):
    with db() as con:
        con.executescript(SCHEMA)


def _scope(metric, pid):
    return f'project:{pid}' if metric.startswith('imported:') else 'public'


def cached(con, metric, location, start, end, pid=None):
    rows = con.execute('SELECT period, body, source, retrieved_at FROM mk_obs WHERE scope=? AND metric=? AND location=? AND period BETWEEN ? AND ? ORDER BY period',
                       (_scope(metric, pid), metric, location, start, end)).fetchall()
    return [{'period': r['period'], **json.loads(r['body']), 'source': r['source'], 'retrieved_at': r['retrieved_at']} for r in rows]


def _store(con, metric, location, obs, source, scope='public'):
    ts = now()
    for o in obs:
        body = {k: v for k, v in o.items() if k != 'period'}
        con.execute('INSERT INTO mk_obs VALUES(?,?,?,?,?,?,?) ON CONFLICT(scope,metric,location,period) DO UPDATE SET body=excluded.body, source=excluded.source, retrieved_at=excluded.retrieved_at',
                    (scope, metric, location, o['period'], json.dumps(body, allow_nan=False), source, ts))


def _days(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def refresh(con, metric, location, start, end, fetch=None):
    """Fill gaps from the public source. Returns (fetched_count, warnings)."""
    fetch = fetch or P.http_fetch
    spec = CATALOG.get(metric)
    if not spec:
        raise P.MarketError(f'Unknown metric "{metric}"')
    warnings, fetched = [], 0
    today = date.today()
    end = min(end, today)
    if metric == 'lmp_da':
        start = max(start, end - timedelta(days=NYISO_MAX_DAYS - 1))
        have = {o['period'] for o in cached(con, metric, location, start.isoformat(), end.isoformat()) if o.get('hours', 0) >= 23}
        tomorrow_published = end >= today
        for d in _days(start, end + (timedelta(days=1) if tomorrow_published else timedelta(0))):
            if d.isoformat() in have:
                continue
            miss = _MISSES.get((location, d))
            if miss and (datetime.now(timezone.utc) - miss).total_seconds() < MISS_SECONDS:
                continue
            try:
                obs = P.nyiso_day(fetch, d, location)
                _store(con, metric, location, [obs], spec['source'])
                _MISSES.pop((location, d), None)
                fetched += 1
            except P.MarketError as exc:
                _MISSES[(location, d)] = datetime.now(timezone.utc)
                if d < today - timedelta(days=1):
                    warnings.append(str(exc))
        return fetched, warnings[:5]
    if metric == 'spark_spread':
        return 0, []
    last = con.execute('SELECT MAX(retrieved_at) m, MAX(period) p FROM mk_obs WHERE scope=? AND metric=? AND location=?', ('public', metric, location)).fetchone()
    fresh = last['m'] and datetime.fromisoformat(last['m']) > datetime.now(timezone.utc) - timedelta(hours=EIA_REFRESH_HOURS) and last['p'] and last['p'] >= start.isoformat()[:len(last['p'])]
    if fresh:
        return 0, []
    if metric == 'henry_hub':
        obs = P.eia_henry_hub(fetch, start, end)
    elif metric == 'ba_demand':
        obs = [{**o, 'avg_mw': round(o['value'] / 24, 3)} for o in P.eia_ba_demand(fetch, location, start, end)]
    elif metric == 'fuel_mix':
        obs = []
        for o in P.eia_fuel_mix(fetch, location, start, end):
            s = o['shares']
            obs.append({'period': o['period'], **{k: s.get(k, 0.0) for k in ('gas', 'coal', 'nuclear', 'hydro', 'wind', 'solar', 'storage', 'oil', 'other')},
                        'renewables': round(s.get('wind', 0) + s.get('solar', 0) + s.get('hydro', 0), 6),
                        'carbon_t_per_mwh': o['carbon_t_per_mwh'], 'total_mwh': o['total_mwh']})
    else:
        obs = P.eia_retail(fetch, location, 'IND' if metric == 'retail_industrial' else 'COM')
    _store(con, metric, location, obs, spec['source'])
    return len(obs), warnings


def series(con, metric, location, start, end, pid=None, heat_rate=7.0, fetch=None, live=True):
    if metric.startswith('imported:'):
        return {'metric': metric, 'location': location, 'observations': cached(con, metric, location, start.isoformat(), end.isoformat(), pid), 'warnings': []}
    warnings = []
    if metric == 'spark_spread':
        lmp = series(con, 'lmp_da', location, start, end, pid, fetch=fetch, live=live)
        gas = series(con, 'henry_hub', 'HENRY', start - timedelta(days=7), end, pid, fetch=fetch, live=live)
        gas_by = sorted((o['period'], o['value']) for o in gas['observations'])
        out = []
        for o in lmp['observations']:
            prior = [v for p, v in gas_by if p <= o['period']]
            if not prior:
                continue
            g = prior[-1]
            out.append({'period': o['period'], 'avg': round(o['avg'] - heat_rate * g, 4),
                        'on_peak': None if o.get('on_peak') is None else round(o['on_peak'] - heat_rate * g, 4),
                        'gas_used': g, 'heat_rate': heat_rate, 'source': CATALOG['spark_spread']['source'], 'retrieved_at': o['retrieved_at']})
        return {'metric': metric, 'location': location, 'observations': out, 'warnings': lmp['warnings'] + gas['warnings']}
    if live:
        try:
            _, warnings = refresh(con, metric, location, start, end, fetch)
        except P.MarketError as exc:
            warnings = [str(exc)]
    span_start = start.isoformat()[:7] if CATALOG[metric]['frequency'] == 'monthly' else start.isoformat()
    span_end = end.isoformat()[:7] if CATALOG[metric]['frequency'] == 'monthly' else end.isoformat()
    return {'metric': metric, 'location': location, 'observations': cached(con, metric, location, span_start, span_end), 'warnings': warnings}


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.fmean(xs), 4) if xs else None


def _stale(spec, as_of):
    if not as_of:
        return True
    d = date.fromisoformat(as_of + ('-01' if len(as_of) == 7 else ''))
    return (date.today() - d).days > spec['lag_days']


def _item(metric, location, label, value, unit, as_of, obs, method):
    spec = CATALOG.get(metric, {})
    return {'metric': metric, 'location': location, 'label': label, 'value': value, 'unit': unit, 'as_of': as_of,
            'source': spec.get('source'), 'source_url': spec.get('url'), 'retrieved_at': obs[-1]['retrieved_at'] if obs else None,
            'stale': _stale(spec, as_of) if spec else False, 'method': method}


def snapshot(con, profile, days=30, fetch=None, live=True):
    profile = {**DEFAULT_PROFILE, **(profile or {})}
    end = date.today()
    start = end - timedelta(days=days)
    items, gaps = [], []

    def add(metric, location, builders):
        if not location:
            gaps.append({'metric': metric, 'reason': f'Set the project market profile ({CATALOG[metric]["profile"]})'})
            return
        s = series(con, metric, location, start if CATALOG[metric]['frequency'] == 'daily' else end - timedelta(days=430), end,
                   heat_rate=profile['heat_rate'], fetch=fetch, live=live)
        obs = s['observations']
        if not obs:
            gaps.append({'metric': metric, 'reason': '; '.join(s['warnings']) or 'No observations in window'})
            return
        for b in builders:
            items.append(b(obs, location))
        if s['warnings']:
            gaps.append({'metric': metric, 'reason': '; '.join(s['warnings'])})

    z, ba, st = profile['nyiso_zone'], profile['ba'], profile['state']
    last = lambda o: o[-1]['period']
    add('lmp_da', z, [
        lambda o, l: _item('lmp_da', l, 'Day-ahead LMP, latest day (avg)', o[-1]['avg'], 'USD/MWh', last(o), o, '24-hour average of hourly day-ahead LBMP'),
        lambda o, l: _item('lmp_da', l, f'Day-ahead LMP, {days}-day avg', _mean([x['avg'] for x in o]), 'USD/MWh', last(o), o, f'Mean of daily averages over {len(o)} days'),
        lambda o, l: _item('lmp_da', l, f'Day-ahead LMP, {days}-day on-peak', _mean([x.get('on_peak') for x in o]), 'USD/MWh', last(o), o, 'Hours beginning 07:00–22:00 Mon–Fri'),
        lambda o, l: _item('lmp_da', l, f'Day-ahead LMP, {days}-day off-peak', _mean([x.get('off_peak') for x in o]), 'USD/MWh', last(o), o, 'All other hours'),
        lambda o, l: _item('lmp_da', l, f'Price volatility ({days}-day)', _mean([x.get('stdev') for x in o]), 'USD/MWh', last(o), o, 'Mean intraday standard deviation of hourly prices'),
        lambda o, l: _item('lmp_da', l, f'Congestion component, {days}-day avg', _mean([x.get('congestion_avg') for x in o]), 'USD/MWh', last(o), o, 'Mean congestion component of LBMP'),
    ])
    add('henry_hub', 'HENRY', [
        lambda o, l: _item('henry_hub', l, 'Henry Hub spot, latest', o[-1]['value'], 'USD/MMBtu', last(o), o, 'Daily spot price'),
        lambda o, l: _item('henry_hub', l, f'Henry Hub spot, {days}-day avg', _mean([x['value'] for x in o]), 'USD/MMBtu', last(o), o, 'Mean of daily spot prices'),
    ])
    add('spark_spread', z, [
        lambda o, l: _item('spark_spread', l, f'Spark spread, {days}-day on-peak', _mean([x.get('on_peak') for x in o]), 'USD/MWh', last(o), o,
                           f'On-peak LMP − {profile["heat_rate"]} MMBtu/MWh × Henry Hub (latest prior gas print)'),
    ])
    add('retail_industrial', st, [
        lambda o, l: _item('retail_industrial', l, 'Industrial retail price, latest month', o[-1]['value'], 'USD/MWh', last(o), o, 'Statewide revenue ÷ sales; not a site tariff'),
        lambda o, l: _item('retail_industrial', l, 'Industrial retail price, 12-month avg', _mean([x['value'] for x in o[-12:]]), 'USD/MWh', last(o), o, f'Mean of last {min(12, len(o))} months'),
    ])
    add('ba_demand', ba, [
        lambda o, l: _item('ba_demand', l, 'Grid demand, latest day (avg MW)', o[-1]['avg_mw'], 'MW', last(o), o, 'Daily demand ÷ 24'),
        lambda o, l: _item('ba_demand', l, f'Grid demand, {days}-day peak day (avg MW)', max(x['avg_mw'] for x in o), 'MW', last(o), o, 'Highest daily average in window'),
    ])
    add('fuel_mix', ba, [
        lambda o, l: _item('fuel_mix', l, 'Gas share of generation (latest day)', o[-1]['gas'], 'share', last(o), o, 'EIA daily generation by fuel'),
        lambda o, l: _item('fuel_mix', l, 'Wind + solar + hydro share (latest day)', o[-1]['renewables'], 'share', last(o), o, 'EIA daily generation by fuel'),
        lambda o, l: _item('fuel_mix', l, f'Estimated carbon intensity, {days}-day avg', _mean([x['carbon_t_per_mwh'] for x in o]), 't CO2/MWh', last(o), o,
                           'Generation-weighted screening factors (coal 1.0, oil 0.8, gas 0.41, other 0.4, zero-carbon 0). Estimate, not an inventory.'),
    ])
    return {'profile': profile, 'window_days': days, 'calculated_at': now(), 'items': items, 'gaps': gaps,
            'notes': ['Wholesale LMP is an energy price only; delivered cost adds transmission, capacity and utility charges.',
                      'Public sources revise recent data; values are re-pulled after 6 hours (NYISO day-ahead prices are final when published).']}


def import_series(con, pid, data, uid):
    slug = data['metric']
    metric = 'imported:' + slug
    for o in data['observations']:
        if not (len(o['period']) in (7, 10)):
            raise ValueError('Periods must be YYYY-MM or YYYY-MM-DD')
    obs = [{'period': o['period'], 'value': o['value']} for o in data['observations']]
    _store(con, metric, data['location'], obs, f'{data["source"]} (licensed: {data["license"]})', scope=f'project:{pid}')
    rid = uid()
    con.execute('INSERT INTO mk_imports VALUES(?,?,?,?)', (rid, pid, json.dumps({k: v for k, v in data.items() if k != 'observations'} | {'count': len(obs)}), now()))
    return {'id': rid, 'metric': metric, 'location': data['location'], 'count': len(obs)}


def trailing_value(con, metric, location, stat, window, pid=None, fetch=None, live=True, heat_rate=7.0):
    """Mean of `stat` over the last `window` days (daily metrics), months (monthly) or observations (imports)."""
    end = date.today()
    if metric.startswith('imported:'):
        obs = series(con, metric, location, date(1900, 1, 1), end, pid)['observations'][-window:]
        warnings = []
    else:
        monthly = CATALOG[metric]['frequency'] == 'monthly'
        start = end - timedelta(days=window * 31 + 62 if monthly else window)
        s = series(con, metric, location, start, end, pid, heat_rate=heat_rate, fetch=fetch, live=live)
        obs, warnings = (s['observations'][-window:] if monthly else s['observations']), s['warnings']
    vals = [o.get(stat, o.get('value')) for o in obs]
    v = _mean(vals)
    if v is None:
        raise ValueError('; '.join(warnings) or 'No observations to average')
    return v, obs[0]['period'], obs[-1]['period'], len([x for x in vals if x is not None])
