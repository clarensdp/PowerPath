"""Score ledger and backtest board.

Every forecast PowerPath issues (time to power, deliverable MW, a yes/no on hitting
a target) is saved as issued and never edited. When the real outcome is known it is
recorded once against the forecast. The backtest board scores the record: error of
the base case, bias, how often outcomes landed inside the low–high range, and a
Brier score where a probability was issued. This is the path from illustrative
ranges to calibrated probabilities.
"""
import math

from server.underwriting.store import encode, fingerprint, now, one, rows, uid

KINDS = {
    'time_to_power_month': {'type': 'numeric', 'unit': 'project month'},
    'deliverable_mw_at_target': {'type': 'numeric', 'unit': 'MW'},
    'energization_month': {'type': 'numeric', 'unit': 'project month'},
    'target_met': {'type': 'binary', 'unit': 'probability'},
}
MIN_RESOLVED = 10


def issue(con, pid, kind, subject, forecast, source):
    if kind not in KINDS:
        raise ValueError(f'Unknown forecast kind {kind}')
    if KINDS[kind]['type'] == 'numeric':
        values = [forecast.get(k) for k in ('low', 'base', 'high')]
        if any(v is not None and (not isinstance(v, (int, float)) or not math.isfinite(v)) for v in values):
            raise ValueError('Forecast values must be finite numbers or null')
    else:
        p = forecast.get('probability')
        if p is not None and not 0 <= p <= 1:
            raise ValueError('Probability must be between 0 and 1')
    body = {'kind': kind, 'subject': subject, 'unit': KINDS[kind]['unit'], **forecast, 'source': source}
    fid, ts = uid(), now()
    con.execute('INSERT INTO uw_forecasts VALUES(?,?,?,?,?,?,?)', (fid, pid, kind, subject, fingerprint(body), encode(body), ts))
    return {'id': fid, 'issued_at': ts, 'body': body}


def resolve(con, pid, forecast_id, observed, observed_at, evidence_id=None, notes=''):
    f = one(con, 'SELECT * FROM uw_forecasts WHERE project_id=? AND id=?', (pid, forecast_id))
    if not f:
        raise LookupError('Forecast not found')
    if one(con, 'SELECT id FROM uw_outcomes WHERE forecast_id=?', (forecast_id,)):
        raise ValueError('Outcome already recorded; outcomes are append-only')
    if KINDS[f['kind']]['type'] == 'binary' and observed not in (0, 1, True, False):
        raise ValueError('Binary outcomes must be true/false')
    if evidence_id and not con.execute('SELECT 1 FROM evidence WHERE project_id=? AND id=?', (pid, evidence_id)).fetchone():
        raise ValueError('Evidence record does not belong to this project')
    body = {'observed': float(observed), 'observed_at': observed_at, 'evidence_id': evidence_id, 'notes': notes}
    oid, ts = uid(), now()
    con.execute('INSERT INTO uw_outcomes VALUES(?,?,?,?,?)', (oid, pid, forecast_id, encode(body), ts))
    return {'id': oid, 'forecast_id': forecast_id, 'body': body, 'recorded_at': ts}


def entries(con, pid, kind=None):
    sql = 'SELECT f.*, o.body AS outcome, o.created_at AS resolved_at FROM uw_forecasts f LEFT JOIN uw_outcomes o ON o.forecast_id=f.id WHERE f.project_id=?'
    args = [pid]
    if kind:
        sql += ' AND f.kind=?'
        args.append(kind)
    import json
    out = []
    for r in con.execute(sql + ' ORDER BY f.issued_at, f.id', args):
        d = dict(r)
        d['body'] = json.loads(d['body'])
        d['outcome'] = json.loads(d['outcome']) if d['outcome'] else None
        out.append(d)
    return out


def board(con, pid=None):
    """pid=None scores every project the caller can reach (used by the portfolio board)."""
    import json
    sql = 'SELECT f.kind, f.body, o.body AS outcome FROM uw_forecasts f JOIN uw_outcomes o ON o.forecast_id=f.id'
    args = ()
    if pid:
        sql += ' WHERE f.project_id=?'
        args = (pid,)
    issued_sql = 'SELECT kind, COUNT(*) n FROM uw_forecasts' + (' WHERE project_id=?' if pid else '') + ' GROUP BY kind'
    issued = {r['kind']: r['n'] for r in con.execute(issued_sql, args)}
    resolved = {}
    for r in con.execute(sql, args):
        resolved.setdefault(r['kind'], []).append((json.loads(r['body']), json.loads(r['outcome'])))
    scores = []
    for kind, spec in KINDS.items():
        pairs = resolved.get(kind, [])
        item = {'kind': kind, 'unit': spec['unit'], 'issued': issued.get(kind, 0), 'resolved': len(pairs)}
        if spec['type'] == 'numeric':
            errs = [o['observed'] - f['base'] for f, o in pairs if f.get('base') is not None]
            ranged = [(f, o) for f, o in pairs if f.get('low') is not None and f.get('high') is not None]
            item.update(mean_abs_error=round(sum(map(abs, errs)) / len(errs), 4) if errs else None,
                        bias=round(sum(errs) / len(errs), 4) if errs else None,
                        range_hit_rate=round(sum(min(f['low'], f['high']) <= o['observed'] <= max(f['low'], f['high']) for f, o in ranged) / len(ranged), 4) if ranged else None)
        else:
            probs = [(f['probability'], o['observed']) for f, o in pairs if f.get('probability') is not None]
            item.update(brier=round(sum((p - y) ** 2 for p, y in probs) / len(probs), 4) if probs else None,
                        hit_rate=round(sum(o['observed'] for _, o in pairs) / len(pairs), 4) if pairs else None)
        item['status'] = 'reportable' if len(pairs) >= MIN_RESOLVED else 'insufficient_history'
        scores.append(item)
    return {'scores': scores, 'min_resolved_for_reporting': MIN_RESOLVED,
            'note': 'Scores use only forecasts as originally issued. Ranges are scenario bounds, not probability intervals, until enough outcomes calibrate them.'}
