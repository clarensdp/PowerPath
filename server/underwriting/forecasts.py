"""Provider-neutral price forecast interface and multi-year underwriting scenarios.

PowerPath does not build a short-term price model. It imports quantile forecasts from
any licensed or free provider (hub-level forecasts, consultant curves, internal desks)
in one schema, keeps each import as issued, and extends them into multi-year
low/base/high price paths using the project's own long-term planning assumptions.
Each path flows through the same frozen financial engine.

Provider adapters convert a provider's native response into FORECAST_SCHEMA. Only
the generic JSON/CSV adapters ship here; a provider-specific adapter is added once
that provider's API terms and documentation are confirmed.
"""
import csv
import io
import math
import re

from server.underwriting import drivers
from server.underwriting.store import encode, now, one, rows, uid

PERIOD = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
CASE_QUANTILE = {'low': 'p10', 'base': 'p50', 'high': 'p90'}


def _finite(v, label):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f'{label} must be a finite number')
    return float(v)


def normalize(data):
    periods, seen = [], set()
    for p in data['periods']:
        if not PERIOD.match(str(p.get('period', ''))):
            raise ValueError('Periods must be monthly YYYY-MM (aggregate hourly/daily forecasts before import)')
        if p['period'] in seen:
            raise ValueError(f'Duplicate period {p["period"]}')
        seen.add(p['period'])
        q = {k: _finite(p[k], f'{p["period"]} {k}') for k in ('p10', 'p50', 'p90')}
        if not q['p10'] <= q['p50'] <= q['p90']:
            raise ValueError(f'{p["period"]}: quantiles must satisfy p10 ≤ p50 ≤ p90')
        periods.append({'period': p['period'], **q})
    if not periods:
        raise ValueError('Forecast has no periods')
    periods.sort(key=lambda p: p['period'])
    if data.get('unit', 'USD/MWh') != 'USD/MWh':
        raise ValueError('Only USD/MWh forecasts are supported')
    return {k: data.get(k) for k in ('provider', 'product', 'market', 'location', 'issued_at', 'license', 'source_url')} | {
        'unit': 'USD/MWh', 'periods': periods,
        'coverage': f'{periods[0]["period"]} to {periods[-1]["period"]} ({len(periods)} months)'}


def from_csv(meta, text):
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿')))
    need = {'period', 'p10', 'p50', 'p90'}
    if not reader.fieldnames or not need <= {f.strip().lower() for f in reader.fieldnames}:
        raise ValueError('CSV needs columns period,p10,p50,p90')
    out = []
    for r in reader:
        r = {k.strip().lower(): (v or '').strip() for k, v in r.items()}
        try:
            out.append({'period': r['period'], **{k: float(r[k]) for k in ('p10', 'p50', 'p90')}})
        except ValueError:
            raise ValueError(f'Row {r.get("period")}: quantiles must be numbers') from None
    return normalize({**meta, 'periods': out})


ADAPTERS = {'json': lambda meta, payload: normalize({**meta, 'periods': payload}),
            'csv': from_csv}


def save(con, pid, body):
    fid, ts = uid(), now()
    con.execute('INSERT INTO uw_price_forecasts VALUES(?,?,?,?,?)', (fid, pid, body.get('provider') or 'unspecified', encode(body), ts))
    return {'id': fid, 'created_at': ts, 'body': body}


def get(con, pid, fid):
    f = one(con, 'SELECT * FROM uw_price_forecasts WHERE project_id=? AND id=?', (pid, fid))
    if not f:
        raise LookupError('Forecast not found')
    return f


def listing(con, pid):
    return [{'id': r['id'], 'provider': r['provider'], 'created_at': r['created_at'],
             **{k: r['body'].get(k) for k in ('product', 'market', 'location', 'issued_at', 'coverage', 'license')}}
            for r in rows(con, 'SELECT * FROM uw_price_forecasts WHERE project_id=? ORDER BY created_at DESC', (pid,))]


def _calendar(cfg, m):
    offset = int(cfg.get('calendarStartMonth', 1)) + m - 2
    return f'{int(cfg.get("calendarStartYear", 2026)) + offset // 12:04d}-{offset % 12 + 1:02d}'


def price_paths(cfg, cases, forecast=None, blend_months=12):
    months = int(cfg.get('months', 120))
    by_period = {p['period']: p for p in (forecast or {}).get('periods', [])}
    last = (forecast or {}).get('periods', [None])[-1] if forecast else None
    paths = {}
    for case, spec in cases.items():
        q = CASE_QUANTILE[case]
        start = spec.get('start_price')
        if start is None:
            start = last[q] if last else float(cfg.get('powerCostMWh', 85))
        esc = float(spec.get('escalation_pct', 0)) / 100
        path, last_fc, gap = [], None, 0
        for m in range(1, months + 1):
            period = _calendar(cfg, m)
            long_term = start * (1 + esc) ** ((m - 1) / 12)
            if period in by_period:
                price, last_fc, gap, basis = by_period[period][q], by_period[period][q], 0, 'forecast'
            elif last_fc is not None and gap < blend_months:
                gap += 1
                w = gap / (blend_months + 1)
                price, basis = (1 - w) * last_fc + w * long_term, 'blend'
            else:
                price, basis = long_term, 'planning assumption'
            path.append({'month': m, 'period': period, 'price_mwh': round(price, 6), 'basis': basis})
        paths[case] = path
    return paths


def run_scenarios(calculate, cfg, cases, forecast=None, blend_months=12):
    for c in cases:
        if c not in CASE_QUANTILE:
            raise ValueError('Cases are low, base and high')
    base_rows = calculate('underwrite', cfg)['rows']
    weights = {r['month']: max(0.0, float(r.get('grossEnergy') or 0)) for r in base_rows}
    paths = price_paths(cfg, cases, forecast, blend_months)
    out = {}
    for case, path in paths.items():
        w = sum(weights.get(p['month'], 0) for p in path)
        weighted = (sum(p['price_mwh'] * weights.get(p['month'], 0) for p in path) / w) if w else sum(p['price_mwh'] for p in path) / len(path)
        result = drivers.summarize(calculate('underwrite', drivers.apply(cfg, {'power_cost_mwh': weighted})))
        counts = {}
        for p in path:
            counts[p['basis']] = counts.get(p['basis'], 0) + 1
        out[case] = {'energy_weighted_price_mwh': round(weighted, 4), 'result': result, 'months_by_basis': counts,
                     'path_sample': path[::12]}
    return {'cases': out, 'power_responsibility': cfg.get('powerResponsibility'), 'power_pass_through_pct': cfg.get('powerPassThroughPct'),
            'forecast': {k: forecast.get(k) for k in ('provider', 'product', 'market', 'location', 'issued_at', 'coverage')} if forecast else None,
            'limitations': ['The engine takes one power price; each path enters as its energy-weighted average over base-case operating months.',
                            'low/base/high map to the forecast p10/p50/p90 while the forecast lasts, then glide to the long-term planning path.',
                            'Returns sensitivity to price depends on the scenario\'s power pass-through terms.',
                            'Scenario bounds are illustrative underwriting assumptions, not calibrated probabilities.']}
