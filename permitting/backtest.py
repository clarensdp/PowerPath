"""Loudoun backtest: blind predictions at filing vs documented actuals, plus a live prediction for open cases.
Run: python -m permitting.backtest  (prints JSON)"""
import copy
import json
from datetime import date
from pathlib import Path
from .engine import assess, public, date_to_month

CASES = Path(__file__).resolve().parent / 'cases' / 'loudoun_backtest.json'
LIVE_AS_OF = '2026-10-29'


def _band(actual, p50, p90):
    if actual is None:
        return 'pending'
    if actual <= p50 + 1e-9:
        return 'at or before P50'
    if actual <= p90 + 1e-9:
        return 'between P50 and P90'
    return 'later than P90'


def run_case(case):
    proj = copy.deepcopy(case['project'])
    proj['as_of_date'] = proj['anchor_date']
    a = public(assess(proj))
    anchor = date.fromisoformat(proj['anchor_date'])
    lu = next(p for p in a['permits'] if p['id'] == 'LU_LEGISLATIVE')
    pred = {s: {'pc_hearing_month': lu[s]['steps'][0]['finish'], 'decision_month': lu[s]['finish_month'],
                'pc_hearing_date': lu[s]['steps'][0]['finish_date'], 'decision_date': lu[s]['finish_date']} for s in ('p50', 'p90')}
    act = case['actual']
    pc = date_to_month(anchor, act['pc_hearing_date']) if act.get('pc_hearing_date') else None
    dec = date_to_month(anchor, act['decision_date']) if act.get('decision_date') else None
    out = {'id': case['id'], 'name': proj['name'], 'anchor_date': proj['anchor_date'], 'anchor_basis': proj.get('anchor_basis'),
           'predicted_permits': sorted(p['id'] for p in a['permits'] if not p['only_in_p90']),
           'zoning_gate': (a['v82_gates']['gates']['Zoning'], a['v82_gates']['severity'].get('Zoning')),
           'prediction': pred,
           'actual': {'pc_hearing_month': pc, 'decision_month': dec, 'outcome': act['outcome'], 'pc_recommendation': act.get('pc_recommendation')},
           'pc_hearing_band': _band(pc, pred['p50']['pc_hearing_month'], pred['p90']['pc_hearing_month']),
           'decision_band': _band(dec, pred['p50']['decision_month'], pred['p90']['decision_month']),
           'excluded_by_effective_date': a['excluded_by_effective_date']}
    if act.get('decision_date') is None and dec is None:
        months_so_far = date_to_month(anchor, LIVE_AS_OF)
        out['decision_band'] = ('pending; already past P50' if months_so_far > pred['p50']['decision_month'] else 'pending') + \
                               ('; already past P90' if months_so_far > pred['p90']['decision_month'] else '')
    if case.get('live_status'):
        live = copy.deepcopy(case['project'])
        live['as_of_date'] = LIVE_AS_OF
        live['status'] = case['live_status']
        b = public(assess(live))
        lu2 = next(p for p in b['permits'] if p['id'] == 'LU_LEGISLATIVE')
        out['live_prediction'] = {'as_of': LIVE_AS_OF, 'earliest_board_decision_p50': lu2['p50']['finish_date'],
                                  'earliest_board_decision_p90': lu2['p90']['finish_date'], 'holds': lu2['p50']['holds'],
                                  'gates': b['v82_gates']['gates'], 'severity': b['v82_gates']['severity'],
                                  'permits_required': sorted(p['id'] for p in b['permits'] if not p['only_in_p90'])}
    return out


def main():
    cases = json.loads(CASES.read_text())
    res = {'note': cases['note'], 'results': [run_case(c) for c in cases['cases']]}
    print(json.dumps(res, indent=1, default=str))
    return res


if __name__ == '__main__':
    main()
