"""permitting-1.0 tests: rules integrity, triggers, overlays, critical path, export consistency, v8.2 hand-off, backtest."""
import copy
import json
import math
import os
import tempfile
from pathlib import Path

import pytest

os.environ.setdefault('POWERPATH_DATA_DIR', tempfile.mkdtemp(prefix='pp_permit_'))
from permitting import assess, apply_to_v82_inputs, export_schedule27, public
from permitting.engine import load_jurisdiction, PermittingError, INF
from permitting.backtest import main as backtest

ROOT = Path(__file__).resolve().parent.parent
F = json.loads((ROOT / 'feasibility' / 'v82' / 'fixtures_v8_2.json').read_text())


def project(**over):
    p = {'name': 't', 'anchor_date': '2026-11-01', 'jurisdiction': {'state': 'VA', 'county': 'Loudoun'},
         'parcel': {'policy_area': 'Suburban', 'acres_disturbed': 60, 'residential_within_ft': 1200},
         'design': {'it_mw': 200, 'construction_months': 18},
         'paths': {'grid': {'first_power_month': 42, 'full_load_month': 42}}}
    for k, v in over.items():
        if isinstance(v, dict) and k in p and isinstance(p[k], dict):
            p[k] = {**p[k], **v}
        else:
            p[k] = v
    return p


def ids(a, include_p90=False):
    return {p['id'] for p in a['permits'] if include_p90 or not p['only_in_p90']}


def test_rules_load_and_every_citation_resolves():
    J = load_jurisdiction('VA', 'Loudoun')
    assert len(J['rules']) >= 15
    for r in J['rules'].values():
        bases = [r.get('duration', {}).get('basis')] + [s['duration'].get('basis') for s in r.get('steps', [])]
        if any(b in ('statute', 'observed', 'industry') for b in bases):
            assert r.get('sources'), f"{r['id']} claims a sourced basis without a citation"
    for o in J['overlays'].values():
        assert all(s in J['sources'] for s in o['sources'])


def test_unmapped_jurisdiction_is_an_error_not_a_clear_result():
    with pytest.raises(PermittingError, match='No permitting rules'):
        assess(project(jurisdiction={'state': 'VA', 'county': 'Fairfax'}))


@pytest.mark.parametrize('over,present,absent', [
    ({}, {'LU_LEGISLATIVE', 'SITE_PLAN', 'BUILDING_PERMIT', 'AIR_BACKUP', 'UTILITY_LARGE_LOAD', 'LAND_DISTURBANCE', 'STATE_HEUF_ASSESSMENT'},
     {'FAA_7460', 'WETLANDS_404', 'AIR_ONSITE', 'SCC_TRANSMISSION', 'LU_SUBSTATION'}),
    ({'parcel': {'airport_distance_ft': 9000, 'airport_longest_runway_ft': 5500}}, {'FAA_7460'}, set()),
    ({'parcel': {'airport_distance_ft': 25000, 'airport_longest_runway_ft': 5500}}, set(), {'FAA_7460'}),
    ({'parcel': {'wetlands_or_streams': True}}, {'WETLANDS_404'}, set()),
    ({'design': {'onsite_generation_mw': 50}}, {'AIR_ONSITE'}, set()),
    ({'design': {'new_transmission_kv': 230}}, {'SCC_TRANSMISSION', 'TX_LINE_BUILD'}, set()),
    ({'design': {'new_transmission_kv': 115}}, set(), {'SCC_TRANSMISSION'}),
    ({'design': {'new_substations': 1}}, {'LU_SUBSTATION', 'LU_2232'}, set()),
    ({'design': {'new_substations': 1}, 'parcel': {'substation_on_comprehensive_plan': True}}, {'LU_SUBSTATION'}, {'LU_2232'}),
    ({'design': {'it_mw': 60}}, set(), {'STATE_HEUF_ASSESSMENT'}),
])
def test_triggers(over, present, absent):
    a = assess(project(**over))
    assert present <= ids(a), present - ids(a)
    assert not (absent & ids(a)), absent & ids(a)


def test_heuf_law_only_for_decisions_after_effective_date():
    early = assess(project(anchor_date='2023-01-01'))
    assert 'STATE_HEUF_ASSESSMENT' in early['excluded_by_effective_date']['p50']
    assert 'STATE_HEUF_ASSESSMENT' not in ids(early)
    assert 'STATE_HEUF_ASSESSMENT' in ids(assess(project()))


def test_rural_policy_area_blocks_and_gates_no_go():
    a = public(assess(project(parcel={'policy_area': 'Rural'})))
    assert a['v82_gates']['gates']['Zoning'] == 'N'
    assert a['tranches']['ENERGIZATION_GRID']['p50']['date'] == 'blocked'


def test_transition_area_is_major():
    a = assess(project(parcel={'policy_area': 'Transition'}))
    assert a['v82_gates']['gates']['Zoning'] == 'C' and a['v82_gates']['severity']['Zoning'] == 'Major'


def test_grandfathered_by_right_converts_to_legislative_in_p90():
    a = assess(project(parcel={'grandfathered_by_right': True, 'residential_within_ft': 800}))
    assert 'LU_BY_RIGHT' in ids(a) and 'LU_LEGISLATIVE' not in ids(a)
    assert 'LU_LEGISLATIVE' in ids(a, include_p90=True)
    assert a['grandfather_converted_in_p90'] is True
    assert a['v82_gates']['gates']['Zoning'] == 'C' and a['v82_gates']['severity']['Zoning'] == 'Minor'
    near = assess(project(parcel={'grandfathered_by_right': True, 'residential_within_ft': 400}))
    assert 'LU_LEGISLATIVE' in ids(near)   # within 500 ft: grandfathering does not apply


def test_pause_holds_decisions_to_referral_plus_12_or_phase2():
    p = project(anchor_date='2025-06-01', as_of_date='2026-10-29',
                status={'LU_LEGISLATIVE': {'state': 'pending', 'pre_hearing_date': '2026-03-01'}})
    a = public(assess(p))
    lu = next(x for x in a['permits'] if x['id'] == 'LU_LEGISLATIVE')
    assert lu['p50']['holds'] and lu['p50']['finish_date'] == '2027-03-01'     # referral + 12 binds
    assert a['v82_gates']['gates']['Moratorium'] == 'C'
    late = public(assess({**p, 'status': {'LU_LEGISLATIVE': {'state': 'pending', 'pre_hearing_date': '2026-10-01'}}}))
    lu2 = next(x for x in late['permits'] if x['id'] == 'LU_LEGISLATIVE')
    assert lu2['p50']['finish_date'] == '2027-07-31' and lu2['p50']['holds'][0]['binding'] == 'Phase 2 adoption target'


def test_pause_does_not_touch_decisions_before_it_or_new_filings_after_release():
    assert assess(project())['v82_gates']['gates']['Moratorium'] == 'Y'   # new filing decides after the pause window
    old = assess(project(anchor_date='2023-03-01'))
    assert old['v82_gates']['gates']['Moratorium'] == 'Y'


def test_grid_reliability_substation_exempt_from_pause():
    p = project(anchor_date='2025-06-01', as_of_date='2026-10-29', parcel={'grandfathered_by_right': True, 'residential_within_ft': 900},
                design={'new_substations': 1, 'grid_reliability_substation': True},
                status={'LU_SUBSTATION': {'state': 'pending', 'pre_hearing_date': '2026-03-01'}})
    a = public(assess(p))
    sub = next(x for x in a['permits'] if x['id'] == 'LU_SUBSTATION')
    assert not sub['p50']['holds']


def test_approved_permits_are_fixed_and_denied_block():
    ok = public(assess(project(status={'LU_LEGISLATIVE': {'state': 'approved', 'decision_date': '2027-01-01'}})))
    lu = next(x for x in ok['permits'] if x['id'] == 'LU_LEGISLATIVE')
    assert lu['p50']['finish_date'] == lu['p90']['finish_date'] == '2027-01-01'
    assert ok['v82_gates']['gates']['Zoning'] == 'Y'
    no = public(assess(project(status={'LU_LEGISLATIVE': {'state': 'denied'}})))
    assert no['v82_gates']['gates']['Zoning'] == 'N' and no['tranches']['ENERGIZATION_GRID']['p50']['date'] == 'blocked'


def test_p90_never_earlier_than_p50():
    for over in ({}, {'design': {'onsite_generation_mw': 100, 'new_substations': 2, 'new_transmission_kv': 230}},
                 {'parcel': {'wetlands_or_streams': True, 'wetland_impact_acres': 2}}):
        a = assess(project(**over))
        for t, v in a['tranches'].items():
            assert v['p90']['month'] >= v['p50']['month'] - 1e-9, t


def test_later_pc_hearing_never_earlier_power():
    prev = None
    for d in ('2027-06-01', '2027-09-01', '2028-01-01', '2028-06-01'):
        a = assess(project(status={'LU_LEGISLATIVE': {'state': 'pending', 'pre_hearing_date': d}}))
        m = a['tranches']['ENERGIZATION_GRID']['p50']['month']
        if prev is not None:
            assert m >= prev - 1e-9
        prev = m


@pytest.mark.parametrize('over', [{}, {'design': {'onsite_generation_mw': 100, 'new_substations': 1},
                                       'paths': {'grid': {'first_power_month': 42, 'full_load_month': 42}, 'hyb': {'first_power_month': 15, 'full_load_month': 42}}},
                                  {'design': {'new_transmission_kv': 230}, 'parcel': {'wetlands_or_streams': True}},
                                  {'anchor_date': '2025-06-01', 'as_of_date': '2026-10-29', 'status': {'LU_LEGISLATIVE': {'state': 'pending', 'pre_hearing_date': '2026-03-01'}}}])
def test_schedule27_export_max_equals_engine_delay(over):
    a = assess(project(**over))
    ex = export_schedule27(None, a)
    assert ex
    for pk, v in ex.items():
        eng = a['paths'][pk]['p50']['first_power_delay_months']
        assert max(m['delay_months'] for m in v['milestones']) == math.ceil(eng - 1e-9), pk


def test_v82_handoff_runs_and_shifts_by_permitting_delay():
    from feasibility.v82.integration import score_one
    p = project(design={'onsite_generation_mw': 100, 'new_substations': 1},
                paths={'grid': {'first_power_month': 42, 'full_load_month': 42}, 'hyb': {'first_power_month': 15, 'full_load_month': 42}})
    a = assess(p)
    inp, ms = apply_to_v82_inputs(F['inputs']['Site G'], a)
    r = score_one('Loudoun hand-off', inp, 'default', milestone_schedules=ms)
    hyb_delay = math.ceil(a['paths']['hyb']['p50']['first_power_delay_months'] - 1e-9)
    assert r['selected'] == 'Hybrid' and r['first_power'] == 15 + hyb_delay
    # Known v8.2 limitation: one shift for both tranches. The permitting engine keeps per-tranche dates.
    assert a['paths']['hyb']['p50']['full_load_month'] < 42 + hyb_delay


def test_backtest_consistency():
    res = {r['id']: r for r in backtest()['results']}
    cm, sv = res['cross-mill'], res['spring-valley']
    assert cm['pc_hearing_band'] == 'between P50 and P90' and cm['decision_band'] == 'between P50 and P90'
    assert {'FAA_7460', 'LU_LEGISLATIVE'} <= set(cm['predicted_permits']) and 'LU_SUBSTATION' not in cm['predicted_permits']
    assert sv['zoning_gate'] == ['C', 'Major'] or sv['zoning_gate'] == ('C', 'Major')
    assert sv['pc_hearing_band'] == 'between P50 and P90'
    assert {'LU_SUBSTATION', 'AIR_ONSITE', 'STATE_HEUF_ASSESSMENT', 'WETLANDS_404'} <= set(sv['predicted_permits'])
    assert sv['live_prediction']['earliest_board_decision_p50'] == '2027-07-23'


def test_api_route_read_only():
    from fastapi.testclient import TestClient
    os.environ.pop('POWERPATH_V27_AUTH_MODE', None)
    from server.app import app
    c = TestClient(app, base_url='http://127.0.0.1')
    r = c.post('/api/permitting/assess', json=project())
    assert r.status_code == 200, r.text
    assert r.json()['engine_version'] == 'permitting-1.0'
    bad = c.post('/api/permitting/assess', json=project(jurisdiction={'state': 'TX', 'county': 'Hood'}))
    assert bad.status_code == 422


def test_pause_assumption_switch_for_nov_17_vote():
    p = project(anchor_date='2025-06-01', as_of_date='2026-10-29',
                status={'LU_LEGISLATIVE': {'state': 'pending', 'pre_hearing_date': '2026-03-01'}})
    held = public(assess(p))
    free = public(assess({**p, 'overlay_assumptions': {'LC_PAUSE_2026': 'not_adopted'}}))
    h = next(x for x in held['permits'] if x['id'] == 'LU_LEGISLATIVE')['p50']
    f = next(x for x in free['permits'] if x['id'] == 'LU_LEGISLATIVE')['p50']
    assert h['holds'] and not f['holds'] and f['finish_month'] < h['finish_month']
    assert free['v82_gates']['gates']['Moratorium'] == 'Y'
