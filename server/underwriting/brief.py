"""Sourced project brief: the structured context a copilot (in-app or via MCP) answers from.

Every figure carries where it came from: the assumption record, its source and date,
the evidence document, or the engine run that produced it. A copilot should quote
these references rather than restate numbers without them.
"""
from server.underwriting import changes, evidence, ledger
from server.underwriting.store import one


def build(con, pid, calculate, project, scenario_id=None, top=5):
    pr = evidence.priorities(con, pid, calculate, scenario_id)
    deliver = one(con, 'SELECT * FROM uw_deliverability WHERE project_id=? ORDER BY version DESC LIMIT 1', (pid,))
    pending = changes.listing(con, pid, pending_only=True)
    out = {
        'project': {k: project[k] for k in ('id', 'name', 'location', 'target_mw', 'status')},
        'approved_case': {**pr['approved_case'], 'result': pr['base_result'],
                          'reference': f'engine run on scenario {pr["approved_case"]["scenario_id"]} v{pr["approved_case"]["scenario_version"]} '
                                       f'with {len(pr["approved_case"]["assignments"])} accepted assumptions'},
        'top_diligence_priorities': [{
            'rank': p['rank'], 'item': p['label'], 'materiality': p['materiality'], 'confidence': p['confidence']['label'],
            'npv_at_risk_m': (p['exposure'] or {}).get('npv_delta_m'), 'downside': p['downside_value'], 'downside_basis': p['downside_basis'],
            'next_action': p['next_action'], 'reference': {'assumption_id': p['assumption_id'], 'source': p['source']}}
            for p in pr['priorities'][:top]],
        'deliverability': None, 'pending_changes': [{
            'id': c['id'], 'source': c['source'], 'title': c['body']['title'], 'requires': c['body']['requires'],
            'impact': (c['body'].get('impact') or {}).get('explanation'), 'created_at': c['created_at']} for c in pending],
        'forecast_track_record': ledger.board(con, pid)['scores'],
        'guidance': ['Cite the reference for every number.', 'Treat proposed changes as unapproved until an approver accepts them.',
                     'Deliverability ranges and stress cases are scenario bounds, not probabilities.',
                     'Never describe a queue withdrawal as freed capacity.'],
    }
    if deliver:
        out['deliverability'] = {'assessment_id': deliver['id'], 'version': deliver['version'], 'assessed_at': deliver['created_at'],
                                 'answers': [c['answer'] for c in deliver['body']['configurations']],
                                 'what_must_be_true': deliver['body']['configurations'][0]['what_must_be_true']}
    return out
