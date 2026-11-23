"""Change pipeline: detect a change → rerun the model → send it for review.

One pipeline serves the living project record (new assumption versions, revised
utility studies) and interconnection queue monitoring. A change never edits the
approved case by itself. Assumption changes carry their computed returns impact and
wait for an approver to accept or reject them. Queue events are flagged for
analysis only: a withdrawal is never treated as newly available capacity.
"""
import json
import math
from datetime import date

from server.underwriting import bridge, drivers, evidence
from server.underwriting.store import encode, fingerprint, now, one, rows, uid

QUEUE_STATUSES = ('active', 'suspended', 'withdrawn', 'in_service')
WITHDRAWAL_NOTE = ('A nearby queue project has withdrawn. Review whether the withdrawal changes assumptions about '
                   'local network upgrades or available capacity. No capacity is credited automatically.')


def record(con, pid, source, body):
    cid, ts = uid(), now()
    con.execute('INSERT INTO uw_changes VALUES(?,?,?,?,?)', (cid, pid, source, encode(body), ts))
    return {'id': cid, 'source': source, 'body': body, 'created_at': ts, 'status': 'pending_review'}


def status(con, pid, change_id):
    d = one(con, 'SELECT * FROM uw_change_decisions WHERE project_id=? AND change_id=?', (pid, change_id))
    return (d['decision'], d) if d else ('pending_review', None)


def listing(con, pid, pending_only=False):
    out = []
    for c in rows(con, 'SELECT * FROM uw_changes WHERE project_id=? ORDER BY created_at DESC, rowid DESC', (pid,)):
        st, d = status(con, pid, c['id'])
        if pending_only and st != 'pending_review':
            continue
        out.append({**c, 'status': st, 'decision': d})
    return out


def _impact(con, pid, calculate, key, value, scope):
    case = evidence.approved_case(con, pid, scope=scope)
    result = bridge.run(calculate, case['config'], {key: value})
    return {'approved_case_fingerprint': case['fingerprint'], 'base': result['base'], 'if_accepted': result['final'],
            'change': result['total_change'], 'explanation': result['explanation']}


def on_assumption(con, pid, calculate, proposal):
    body = proposal['body']
    prior = next((r for r in evidence.accepted(con, pid, body['scope']) if r['key'] == body['key']), None)
    try:
        impact = _impact(con, pid, calculate, body['key'], body['value'], body['scope'])
    except Exception as exc:
        impact = {'error': str(getattr(exc, 'detail', exc))}
    conf = evidence.confidence(body, evidence.evidence_row(con, pid, body.get('evidence_id')))
    ready = conf['score'] >= 0.45 and body.get('evidence_id')
    title = (f'{body["label"]} changed' if prior else f'{body["label"]} documented') + f' ({body["scope"]})'
    return record(con, pid, 'assumption', {
        'title': title, 'assumption_id': proposal['id'], 'key': body['key'], 'scope': body['scope'],
        'previous': {'assumption_id': prior['id'], 'value': prior['body']['value'], 'source_name': prior['body'].get('source_name'),
                     'source_date': prior['body'].get('source_date')} if prior else None,
        'proposed': {'value': body['value'], 'source_name': body.get('source_name'), 'source_date': body.get('source_date'),
                     'verification': body.get('verification'), 'evidence_id': body.get('evidence_id')},
        'confidence': conf, 'impact': impact, 'requires': 'approval',
        'recommendation': ('Ready for approver review: source documented.' if ready else
                           'Request supporting evidence before accepting; confidence is low or no document is attached.')})


def decide(con, pid, calculate, change_id, decision, note, reviewer=None):
    c = one(con, 'SELECT * FROM uw_changes WHERE project_id=? AND id=?', (pid, change_id))
    if not c:
        raise LookupError('Change not found')
    st, _ = status(con, pid, change_id)
    if st != 'pending_review':
        raise ValueError(f'Change already {st}')
    body = c['body']
    if body['requires'] == 'analysis' and decision != 'acknowledged':
        raise ValueError('Queue and monitoring events are acknowledged with an analysis note; they never change the approved case')
    if body['requires'] == 'approval' and decision not in ('accepted', 'rejected'):
        raise ValueError('Assumption changes are accepted or rejected')
    if decision == 'acknowledged' and len((note or '').strip()) < 10:
        raise ValueError('Record the analysis conclusion (at least 10 characters)')
    snapshot = None
    if body['requires'] == 'approval':
        before = evidence.approved_case(con, pid, scope=body['scope'])
        evidence.review(con, pid, body['assumption_id'], decision, note, reviewer)
        after = evidence.approved_case(con, pid, scope=body['scope'])
        snapshot = {'approved_case_before': before['fingerprint'], 'approved_case_after': after['fingerprint'],
                    'assignments_after': after['assignments'], 'scenario_id': after['scenario_id'],
                    'scenario_version': after['scenario_version']}
        if decision == 'accepted':
            snapshot['result_after'] = drivers.summarize(calculate('underwrite', after['config']))
    ts = now()
    con.execute('INSERT INTO uw_change_decisions VALUES(?,?,?,?,?,?)',
                (uid(), pid, change_id, decision, encode({'note': note, 'reviewer': reviewer, 'decision_record': snapshot}), ts))
    return {'id': change_id, 'status': decision, 'decided_at': ts, 'decision_record': snapshot}


def _month(day, cfg):
    d = date.fromisoformat(day)
    return max(1, (d.year - cfg.get('calendarStartYear', 2026)) * 12 + d.month - cfg.get('calendarStartMonth', 1) + 1 + (d.day > 1))


def scan_utility_studies(con, pid, calculate):
    """Turn new or revised parcel utility studies into proposed grid-capacity assumptions."""
    created = []
    try:
        studies = con.execute('SELECT parcel_id, body FROM site_energy_studies WHERE project_id=?', (pid,)).fetchall()
    except Exception:
        return created
    _, _, cfg = evidence.base_config(con, pid)
    for row in studies:
        s = json.loads(row['body'])
        if s.get('capacity_mw') is None or not s.get('energization_date'):
            continue
        scope = f'parcel:{row["parcel_id"]}'
        value = {'basis': 'gross', 'phases': [{'month': _month(s['energization_date'], cfg), 'mw': float(s['capacity_mw'])}]}
        latest = one(con, 'SELECT * FROM uw_assumptions WHERE project_id=? AND scope=? AND key=? ORDER BY version DESC LIMIT 1',
                     (pid, scope, 'grid_capacity'))
        if latest and latest['body']['value'] == value and latest['body'].get('source_date') == s.get('source_date'):
            continue
        proposal = evidence.propose(con, pid, {
            'key': 'grid_capacity', 'scope': scope, 'value': value, 'downside_value': None,
            'source_kind': 'utility_study' if s.get('source_kind') == 'study' else 'utility_confirmation',
            'source_name': s.get('issuer') or 'Utility study', 'source_date': s.get('source_date'), 'source_url': s.get('source_url'),
            'evidence_id': s.get('evidence_id'), 'verification': 'studied' if s.get('source_kind') == 'study' else 'user_supplied',
            'rationale': 'Detected from the parcel utility study record: ' + (s.get('notes') or '')[:500]})
        created.append(on_assumption(con, pid, calculate, proposal))
    return created


# ---------------------------------------------------------------- queue monitoring

def _km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


def _months_between(a, b):
    da, db = date.fromisoformat(a), date.fromisoformat(b)
    return (db.year - da.year) * 12 + db.month - da.month


def _near(entry, sites, radius):
    if not sites:
        return True, None
    if entry.get('latitude') is None or entry.get('longitude') is None:
        return False, None
    d = min(_km((entry['latitude'], entry['longitude']), (s['latitude'], s['longitude'])) for s in sites)
    return d <= radius, round(d, 3)


def ingest_queue(con, pid, snapshot):
    entries = snapshot['entries']
    ids = [e['queue_id'] for e in entries]
    if len(set(ids)) != len(ids):
        raise ValueError('Queue ids must be unique within a snapshot')
    previous = one(con, 'SELECT * FROM uw_queue_snapshots WHERE project_id=? AND source=? ORDER BY created_at DESC, rowid DESC LIMIT 1',
                   (pid, snapshot['source']))
    sid, ts = uid(), now()
    con.execute('INSERT INTO uw_queue_snapshots VALUES(?,?,?,?,?)', (sid, pid, snapshot['source'], encode(snapshot), ts))
    events = []
    if previous:
        before = {e['queue_id']: e for e in previous['body']['entries']}
        after = {e['queue_id']: e for e in entries}
        sites, radius = snapshot.get('sites') or [], snapshot.get('radius_km', 50)
        for qid, e in after.items():
            near, dist = _near(e, sites, radius)
            if not near:
                continue
            p = before.get(qid)
            base = {'queue_id': qid, 'name': e.get('name'), 'fuel': e.get('fuel'), 'mw': e.get('mw'), 'distance_km': dist,
                    'source': snapshot['source'], 'as_of': snapshot['as_of']}
            if p is None:
                events.append({**base, 'event': 'new_entry', 'title': f'New nearby queue request: {e.get("name") or qid} ({e.get("mw")} MW)',
                               'detail': 'Adds to local queue concentration and may compete for the same network upgrades.'})
                continue
            if p['status'] != 'withdrawn' and e['status'] == 'withdrawn':
                events.append({**base, 'event': 'withdrawal', 'title': f'Queue withdrawal: {e.get("name") or qid} ({e.get("mw")} MW)',
                               'detail': WITHDRAWAL_NOTE, 'capacity_effect': 'none assumed'})
            elif p['status'] != e['status']:
                events.append({**base, 'event': 'status_change', 'title': f'{e.get("name") or qid}: {p["status"]} → {e["status"]}',
                               'detail': 'Review the status change against network upgrade and timing assumptions.'})
            if p.get('requested_cod') and e.get('requested_cod') and p['requested_cod'] != e['requested_cod']:
                slip = _months_between(p['requested_cod'], e['requested_cod'])
                if slip:
                    events.append({**base, 'event': 'cod_change', 'slip_months': slip,
                                   'title': f'{e.get("name") or qid}: requested in-service date {"slipped" if slip > 0 else "advanced"} {abs(slip)} months',
                                   'detail': 'Shared upgrades tied to this project may move with it.'})
            if p.get('mw') != e.get('mw'):
                events.append({**base, 'event': 'mw_change', 'title': f'{e.get("name") or qid}: {p.get("mw")} → {e.get("mw")} MW',
                               'detail': 'Review whether the change affects allocated network upgrades.'})
        for qid in set(before) - set(after):
            near, dist = _near(before[qid], sites, radius)
            if near:
                events.append({'queue_id': qid, 'name': before[qid].get('name'), 'event': 'missing_from_source', 'distance_km': dist,
                               'source': snapshot['source'], 'as_of': snapshot['as_of'],
                               'title': f'{before[qid].get("name") or qid} no longer appears in the source',
                               'detail': 'Absence from a feed is not a confirmed withdrawal. Verify with the ISO/utility.'})
    changes = [record(con, pid, 'queue', {**e, 'requires': 'analysis', 'snapshot_id': sid}) for e in events]
    return {'snapshot_id': sid, 'entries': len(entries), 'compared_to': previous['id'] if previous else None, 'changes': changes}


def queue_summary(con, pid, source, sites, radius_km=50):
    snaps = rows(con, 'SELECT * FROM uw_queue_snapshots WHERE project_id=? AND source=? ORDER BY created_at, rowid', (pid, source))
    if not snaps:
        raise LookupError('No queue snapshots for this source')
    latest = snaps[-1]['body']
    nearby, unknown = [], 0
    for e in latest['entries']:
        if sites and (e.get('latitude') is None or e.get('longitude') is None):
            unknown += 1
            continue
        near, dist = _near(e, sites, radius_km)
        if near:
            nearby.append({**e, 'distance_km': dist})
    by = {}
    for e in nearby:
        k = (e.get('fuel') or 'unknown', e['status'])
        by.setdefault(k, {'fuel': k[0], 'status': k[1], 'count': 0, 'mw': 0.0})
        by[k]['count'] += 1
        by[k]['mw'] += float(e.get('mw') or 0)
    history, cods = {}, {}
    for s in snaps:
        for e in s['body']['entries']:
            history.setdefault(e['queue_id'], []).append(e['status'])
            if e.get('requested_cod'):
                cods.setdefault(e['queue_id'], []).append(e['requested_cod'])
    terminal = [v[-1] for v in history.values() if v[-1] in ('withdrawn', 'in_service')]
    slips = sorted(_months_between(v[0], v[-1]) for v in cods.values() if len(v) > 1)
    durations = sorted(_months_between(e['queue_date'], e['in_service_date']) for e in latest['entries']
                       if e['status'] == 'in_service' and e.get('queue_date') and e.get('in_service_date'))
    med = lambda xs: (xs[len(xs) // 2] if len(xs) % 2 else (xs[len(xs) // 2 - 1] + xs[len(xs) // 2]) / 2) if xs else None
    return {'source': source, 'as_of': latest['as_of'], 'snapshots': len(snaps), 'radius_km': radius_km,
            'nearby': {'count': len(nearby), 'active_mw': round(sum(float(e.get('mw') or 0) for e in nearby if e['status'] == 'active'), 3),
                       'by_fuel_status': sorted(by.values(), key=lambda x: -x['mw']), 'location_unknown': unknown},
            'historical_withdrawal_rate': round(terminal.count('withdrawn') / len(terminal), 4) if terminal else None,
            'withdrawal_rate_basis': f'{len(terminal)} requests that reached a final status across {len(snaps)} snapshots',
            'median_cod_slip_months': med(slips), 'median_queue_to_service_months': med(durations),
            'limitations': ['Computed only from snapshots loaded into this project.',
                            'Withdrawals are flagged for analysis and never counted as freed capacity.']}
