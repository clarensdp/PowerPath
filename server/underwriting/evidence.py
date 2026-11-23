"""Evidence & confidence register.

Every material underwriting input is an assumption record with a source, date,
verification status, confidence, financial exposure and next action. Records are
proposed first and only enter the approved case after review (accept/reject).
Diligence work is ranked by financial exposure weighted by how unverified the
input is, not by how much information is missing.
"""
import json
from datetime import date

from server.underwriting import drivers
from server.underwriting.store import encode, fingerprint, now, one, rows, uid

VERIFICATION = {
    # Generic ladder
    'assumed': 0.20, 'estimated': 0.35, 'user_supplied': 0.45, 'studied': 0.60,
    'contracted': 0.85, 'observed': 0.90, 'verified': 1.00,
    # Capacity labels (deliverability engine)
    'nameplate': 0.10, 'headroom': 0.30, 'energized': 1.00,
}
SOURCE_KINDS = ('utility_study', 'utility_confirmation', 'contract', 'quote', 'public_data',
                'third_party_forecast', 'analyst_estimate', 'assumption', 'other')
STALE_MONTHS = 18

# Illustrative stress conventions used only for inputs that have no documented downside.
DEFAULT_STRESS = {
    'power_cost_mwh': lambda v: round((v or 85) * 1.25, 4),
    'construction_cost_mw': lambda v: round((v or 7) * 1.15, 4),
    'rent_per_kw_month': lambda v: round((v or 170) * 0.90, 4),
    'pue': lambda v: round((v or 1.3) + 0.1, 4),
    'interest_rate_pct': lambda v: round((v or 8) + 2, 4),
    'energization_delay_months': lambda v: 12,
    'lease_start_delay_months': lambda v: 6,
}
STRESS_NOTE = ('Default stress (screening convention, not a forecast): power cost +25%, construction +15%, '
               'rent −10%, PUE +0.1, rate +2 pts, energization +12 months, lease start +6 months.')


def confidence(body, evidence_row=None, today=None):
    today = today or date.today()
    score = VERIFICATION.get(body.get('verification'), 0.2)
    reasons = [f"{body.get('verification', 'assumed')} source"]
    if not body.get('evidence_id'):
        score *= 0.75
        reasons.append('no supporting document attached')
    elif evidence_row is not None and evidence_row.get('evidence_status') in ('executed_document', 'third_party_review'):
        score = min(1.0, score * 1.1)
        reasons.append(f"evidence is {evidence_row['evidence_status'].replace('_', ' ')}")
    src = body.get('source_date')
    if not src:
        score *= 0.85
        reasons.append('source undated')
    else:
        d = date.fromisoformat(src)
        age = (today.year - d.year) * 12 + today.month - d.month
        if age > STALE_MONTHS:
            score *= 0.8
            reasons.append(f'source {age} months old')
    score = round(min(1.0, score), 3)
    label = 'high' if score >= 0.75 else 'medium' if score >= 0.45 else 'low'
    return {'score': score, 'label': label, 'basis': '; '.join(reasons),
            'method': 'Screening rubric (verification tier × documentation × age). Not calibrated; see the forecast ledger.'}


def next_action(body, conf):
    v, label = body.get('verification'), drivers.CATALOG[body['key']]['label']
    grid = body['key'] in ('grid_capacity', 'energization_delay_months')
    if conf['basis'].find('months old') >= 0:
        return f'Refresh the {label.lower()} source; it is older than {STALE_MONTHS} months'
    if not body.get('evidence_id') and v not in ('assumed',):
        return f'Attach the document supporting the {label.lower()} figure'
    if v in ('assumed', 'estimated', 'nameplate', 'headroom', 'user_supplied'):
        return ('Request a utility feasibility / system impact study' if grid
                else f'Obtain a primary source (quote, study or contract) for {label.lower()}')
    if v == 'studied':
        return 'Convert the study into an executed facilities / electric service agreement' if grid \
            else f'Convert the {label.lower()} estimate into a contract or firm quote'
    if v == 'contracted':
        return 'Track contract milestones and conditions precedent'
    return 'No action; keep monitoring'


def evidence_row(con, pid, eid):
    if not eid:
        return None
    r = con.execute('SELECT * FROM evidence WHERE project_id=? AND id=?', (pid, eid)).fetchone()
    return dict(r) if r else None


def propose(con, pid, data):
    drivers.validate(data['key'], data['value'])
    if data.get('downside_value') is not None:
        drivers.validate(data['key'], data['downside_value'])
    ev = evidence_row(con, pid, data.get('evidence_id'))
    if data.get('evidence_id') and not ev:
        raise ValueError('Evidence record does not belong to this project')
    scope = data.get('scope') or 'project'
    latest = one(con, 'SELECT * FROM uw_assumptions WHERE project_id=? AND scope=? AND key=? ORDER BY version DESC LIMIT 1',
                 (pid, scope, data['key']))
    version = latest['version'] + 1 if latest else 1
    body = {**data, 'scope': scope, 'label': drivers.CATALOG[data['key']]['label'], 'unit': drivers.CATALOG[data['key']]['unit'],
            'evidence_sha256': ev['content_hash'] if ev else None}
    rid, ts = uid(), now()
    con.execute('INSERT INTO uw_assumptions VALUES(?,?,?,?,?,?,?)', (rid, pid, scope, data['key'], version, encode(body), ts))
    return {'id': rid, 'version': version, 'state': 'proposed', 'body': body, 'created_at': ts}


def state_of(con, pid, assumption_id):
    r = one(con, 'SELECT * FROM uw_reviews WHERE project_id=? AND assumption_id=? ORDER BY rowid DESC LIMIT 1', (pid, assumption_id))
    return (r['decision'], r) if r else ('proposed', None)


def review(con, pid, assumption_id, decision, note, reviewer=None):
    a = one(con, 'SELECT * FROM uw_assumptions WHERE project_id=? AND id=?', (pid, assumption_id))
    if not a:
        raise LookupError('Assumption not found')
    state, _ = state_of(con, pid, assumption_id)
    if state != 'proposed':
        raise ValueError(f'Assumption is already {state}')
    ts = now()
    if decision == 'accepted':
        for prior in accepted(con, pid, a['scope']):
            if prior['key'] == a['key']:
                con.execute('INSERT INTO uw_reviews VALUES(?,?,?,?,?,?)', (uid(), pid, prior['id'], 'superseded',
                            encode({'by': assumption_id, 'note': 'Superseded by accepted version'}), ts))
    con.execute('INSERT INTO uw_reviews VALUES(?,?,?,?,?,?)',
                (uid(), pid, assumption_id, decision, encode({'note': note, 'reviewer': reviewer}), ts))
    return {'id': assumption_id, 'state': decision, 'reviewed_at': ts}


def register(con, pid, today=None):
    out = []
    for a in rows(con, 'SELECT * FROM uw_assumptions WHERE project_id=? ORDER BY scope,key,version', (pid,)):
        state, rv = state_of(con, pid, a['id'])
        conf = confidence(a['body'], evidence_row(con, pid, a['body'].get('evidence_id')), today)
        out.append({'id': a['id'], 'scope': a['scope'], 'key': a['key'], 'version': a['version'], 'state': state,
                    'reviewed_at': rv['created_at'] if rv else None, 'created_at': a['created_at'], 'body': a['body'],
                    'confidence': conf, 'next_action': next_action(a['body'], conf)})
    return out


def accepted(con, pid, scope='project'):
    return [r for r in register(con, pid) if r['state'] == 'accepted' and r['scope'] == scope]


def assignments(con, pid, scope='project'):
    """Accepted values that form the approved case. Parcel/path scopes override project scope."""
    values = {r['key']: r['body']['value'] for r in accepted(con, pid, 'project')}
    if scope != 'project':
        values.update({r['key']: r['body']['value'] for r in accepted(con, pid, scope)})
    return values


def base_config(con, pid, scenario_id=None):
    if not scenario_id:
        s = con.execute('SELECT base_scenario_id FROM uw_settings WHERE project_id=?', (pid,)).fetchone()
        scenario_id = s['base_scenario_id'] if s else None
    if not scenario_id:
        r = con.execute("SELECT * FROM scenarios WHERE project_id=? AND mode='underwrite' ORDER BY created_at,id LIMIT 1", (pid,)).fetchone()
    else:
        r = con.execute('SELECT * FROM scenarios WHERE project_id=? AND id=?', (pid, scenario_id)).fetchone()
    if not r or r['mode'] != 'underwrite':
        raise LookupError('No underwriting scenario. Create one or set the underwriting base case.')
    return r['id'], r['version'], json.loads(r['config_json'])


def approved_case(con, pid, scenario_id=None, scope='project'):
    sid, version, cfg = base_config(con, pid, scenario_id)
    values = assignments(con, pid, scope)
    return {'scenario_id': sid, 'scenario_version': version, 'assignments': values,
            'config': drivers.apply(cfg, values), 'fingerprint': fingerprint({'s': sid, 'v': version, 'a': values})}


def priorities(con, pid, calculate, scenario_id=None, scope='project', today=None):
    """Rank diligence work: |ΔNPV at downside| × (1 − confidence)."""
    case = approved_case(con, pid, scenario_id, scope)
    base = drivers.summarize(calculate('underwrite', case['config']))
    reg = [r for r in register(con, pid, today) if r['scope'] in ('project', scope) and r['state'] in ('accepted', 'proposed')]
    # The current record per key is the accepted one, or the newest proposal if none is accepted.
    current = {}
    for r in reg:
        k = r['key']
        if k not in current or (r['state'] == 'accepted') or (current[k]['state'] != 'accepted' and r['version'] > current[k]['version']):
            current[k] = r
    items = []
    for key in drivers.ORDER:
        rec = current.get(key)
        if rec:
            downside = rec['body'].get('downside_value')
            conf, action, documented = rec['confidence'], rec['next_action'], True
            label = rec['body']['label']
        else:
            documented, label = False, drivers.CATALOG[key]['label']
            conf = {'score': 0.2, 'label': 'low', 'basis': 'Undocumented: saved scenario value in use', 'method': 'Screening rubric'}
            action = f'Document a source for {label.lower()}'
            downside = None
        stress_kind = 'documented downside'
        if downside is None and key in DEFAULT_STRESS:
            downside = DEFAULT_STRESS[key](case['assignments'].get(key, drivers.current_value(case['config'], key)))
            stress_kind = 'default stress convention'
        item = {'key': key, 'label': label, 'documented': documented, 'assumption_id': rec['id'] if rec else None,
                'state': rec['state'] if rec else 'undocumented',
                'value': rec['body']['value'] if rec else drivers.current_value(case['config'], key),
                'unit': drivers.CATALOG[key]['unit'],
                'source': {k: rec['body'].get(k) for k in ('source_kind', 'source_name', 'source_date', 'evidence_id', 'source_url')} if rec else None,
                'verification': rec['body'].get('verification') if rec else None,
                'confidence': conf, 'next_action': action, 'downside_value': downside, 'downside_basis': stress_kind if downside is not None else None,
                'exposure': None, 'priority_score': None}
        if downside is not None:
            try:
                stressed = drivers.summarize(calculate('underwrite', drivers.apply(case['config'], {key: downside})))
                d_npv = None if stressed['npvM'] is None or base['npvM'] is None else stressed['npvM'] - base['npvM']
                d_irr = None if stressed['leveredIRR'] is None or base['leveredIRR'] is None else stressed['leveredIRR'] - base['leveredIRR']
                item['exposure'] = {'npv_delta_m': d_npv, 'irr_delta': d_irr, 'downside_npv_m': stressed['npvM'],
                                    'downside_min_dscr': stressed['minDSCR'], 'covenant_breach_months': stressed['breachMonths']}
                if d_npv is not None:
                    item['priority_score'] = round(abs(d_npv) * (1 - conf['score']), 4)
            except Exception as exc:  # engine rejection is reported, never hidden
                item['exposure'] = {'error': str(getattr(exc, 'detail', exc))}
        items.append(item)
    base_npv = abs(base['npvM'] or 0) or 1
    for item in items:
        e, p = item['exposure'] or {}, item['priority_score']
        share = abs(e.get('npv_delta_m') or 0) / base_npv
        item['materiality'] = ('critical' if share >= 0.10 and item['confidence']['score'] < 0.6 else
                               'high' if share >= 0.05 else 'moderate' if share >= 0.01 else 'low') if p is not None else 'not_quantified'
    items.sort(key=lambda i: (i['priority_score'] is None, -(i['priority_score'] or 0)))
    for rank, item in enumerate(items, 1):
        item['rank'] = rank
    return {'approved_case': {k: case[k] for k in ('scenario_id', 'scenario_version', 'assignments', 'fingerprint')},
            'base_result': base, 'priorities': items,
            'method': 'Priority = |NPV change at downside| × (1 − confidence). Proposed (unreviewed) values are ranked but excluded from the approved case.',
            'stress_note': STRESS_NOTE}
