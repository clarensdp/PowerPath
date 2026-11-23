"""v31.5 underwriting layer: evidence, ledger, deliverability, bridge, change pipeline, forecasts, brief."""
import os, tempfile
os.environ['POWERPATH_DATA_DIR'] = tempfile.mkdtemp(prefix='pp-underwriting-')
os.environ['POWERPATH_V27_AUTH_MODE'] = 'local_only'
os.environ.pop('POWERPATH_DATABASE_URL', None)
import pytest
from fastapi.testclient import TestClient
from server.app import app, db, calculate
from server.underwriting import bridge as B, drivers as D


@pytest.fixture
def proj():
    c = TestClient(app, base_url='http://127.0.0.1')
    pid = c.post('/api/projects?starter_scenario=true', json={'name': 'Underwriting test', 'target_mw': 150}).json()['id']
    sc = c.get(f'/api/projects/{pid}/scenarios').json()[0]
    return c, pid, sc, f'/api/projects/{pid}/underwriting'


def evidence(c, pid):
    r = c.post(f'/api/projects/{pid}/evidence', json={'title': 'Utility study', 'category': 'utility'})
    assert r.status_code == 201, r.text
    eid = r.json()['id']
    f = c.post(f'/api/projects/{pid}/evidence/{eid}/file', files={'attachment': ('study.pdf', b'%PDF-1.4 test', 'application/pdf')})
    assert f.status_code in (200, 201), f.text
    return eid


# ------------------------------------------------------------------ 1. evidence

def test_proposed_values_do_not_enter_case_until_accepted(proj):
    c, pid, sc, u = proj
    base = c.get(u + '/priorities').json()['base_result']
    r = c.post(u + '/assumptions', json={'key': 'construction_cost_mw', 'value': 9, 'downside_value': 10.5,
               'source_kind': 'quote', 'source_name': 'EPC budget quote', 'source_date': '2026-10-01',
               'verification': 'estimated', 'rationale': 'Budgetary EPC quote for shell and core'})
    assert r.status_code == 201, r.text
    change = r.json()['change']
    assert change['body']['requires'] == 'approval' and change['body']['impact']['change']['npvM'] < 0
    assert c.get(u + '/priorities').json()['base_result']['npvM'] == pytest.approx(base['npvM'])
    a = c.post(u + f'/approvals/{change["id"]}/accept', json={'note': 'Accepted per IC'})
    assert a.status_code == 200, a.text
    after = c.get(u + '/priorities').json()
    assert after['approved_case']['assignments'] == {'construction_cost_mw': 9}
    assert after['base_result']['npvM'] == pytest.approx(change['body']['impact']['if_accepted']['npvM'])
    assert c.post(u + f'/approvals/{change["id"]}/accept', json={'note': 'again'}).status_code == 422


def test_new_accepted_version_supersedes_and_history_is_immutable(proj):
    c, pid, sc, u = proj
    for value in (8, 9.5):
        ch = c.post(u + '/assumptions', json={'key': 'construction_cost_mw', 'value': value, 'rationale': 'Updated cost estimate'}).json()['change']
        assert c.post(u + f'/approvals/{ch["id"]}/accept', json={}).status_code == 200
    reg = c.get(u + '/assumptions').json()
    assert [r['state'] for r in reg] == ['superseded', 'accepted']
    assert c.get(u + '/priorities').json()['approved_case']['assignments']['construction_cost_mw'] == 9.5
    with db() as con:
        with pytest.raises(Exception):
            con.execute('DELETE FROM uw_assumptions WHERE id=?', (reg[0]['id'],))
        with pytest.raises(Exception):
            con.execute("UPDATE uw_reviews SET decision='accepted'")


def test_priorities_rank_by_exposure_weighted_by_confidence(proj):
    c, pid, sc, u = proj
    eid = evidence(c, pid)
    c.post(u + '/assumptions', json={'key': 'rent_per_kw_month', 'value': 170, 'downside_value': 150, 'source_kind': 'contract',
           'source_name': 'Executed lease', 'source_date': '2026-09-01', 'evidence_id': eid, 'verification': 'contracted',
           'rationale': 'Signed hyperscaler lease rate'})
    p = c.get(u + '/priorities').json()
    items = {i['key']: i for i in p['priorities']}
    rent = items['rent_per_kw_month']
    assert rent['documented'] and rent['confidence']['label'] == 'high' and rent['downside_basis'] == 'documented downside'
    assert rent['priority_score'] == pytest.approx(abs(rent['exposure']['npv_delta_m']) * (1 - rent['confidence']['score']), rel=1e-6)
    delay = items['energization_delay_months']
    assert not delay['documented'] and delay['downside_basis'] == 'default stress convention'
    scores = [i['priority_score'] for i in p['priorities'] if i['priority_score'] is not None]
    assert scores == sorted(scores, reverse=True)


def test_confidence_rubric_penalises_missing_document_and_age():
    from datetime import date
    from server.underwriting.evidence import confidence
    fresh = confidence({'verification': 'studied', 'evidence_id': 'x', 'source_date': '2026-10-01'}, None, date(2026, 11, 1))
    nodoc = confidence({'verification': 'studied', 'source_date': '2026-10-01'}, None, date(2026, 11, 1))
    stale = confidence({'verification': 'studied', 'evidence_id': 'x', 'source_date': '2024-01-01'}, None, date(2026, 11, 1))
    assert fresh['score'] > nodoc['score'] and fresh['score'] > stale['score']


def test_unknown_key_and_bad_values_rejected(proj):
    c, pid, sc, u = proj
    assert c.post(u + '/assumptions', json={'key': 'magic', 'value': 1, 'rationale': 'not a real input'}).status_code == 422
    assert c.post(u + '/assumptions', json={'key': 'pue', 'value': 9, 'rationale': 'impossible PUE value'}).status_code == 422


# -------------------------------------------------------------------- ledger

def test_ledger_outcomes_append_only_and_backtest(proj):
    c, pid, sc, u = proj
    d = c.post(u + '/deliverability', json={'target_month': 30, 'sources': [
        {'id': 'g', 'name': 'Utility', 'label': 'studied', 'mw': 150, 'earliest_month': 24, 'likely_month': 30, 'latest_month': 40}]})
    assert d.status_code == 201, d.text
    ledger = c.get(u + '/ledger').json()
    ttp = next(e for e in ledger if e['kind'] == 'time_to_power_month')
    assert ttp['body']['base'] == 30 and ttp['outcome'] is None
    r = c.post(u + f'/ledger/{ttp["id"]}/outcome', json={'observed': 36, 'observed_at': '2029-06-01'})
    assert r.status_code == 201, r.text
    assert c.post(u + f'/ledger/{ttp["id"]}/outcome', json={'observed': 30, 'observed_at': '2029-06-01'}).status_code == 422
    board = {s['kind']: s for s in c.get(u + '/backtest').json()['scores']}
    assert board['time_to_power_month']['mean_abs_error'] == 6 and board['time_to_power_month']['bias'] == 6
    # downside (studied not counted) never reaches target -> range high is None; hit rate computed only where bounded
    assert board['time_to_power_month']['status'] == 'insufficient_history'


# ------------------------------------------------------------ 2. deliverability

SOURCES = [
    {'id': 'grid1', 'name': 'Utility phase 1', 'label': 'contracted', 'mw': 100, 'earliest_month': 24, 'likely_month': 28, 'latest_month': 34, 'depends_on': ['sub']},
    {'id': 'grid2', 'name': 'Utility phase 2', 'label': 'studied', 'mw': 100, 'earliest_month': 30, 'likely_month': 36, 'latest_month': 48},
    {'id': 'head', 'name': 'Feeder headroom', 'label': 'headroom', 'mw': 40, 'earliest_month': 12, 'likely_month': 12, 'latest_month': 12},
    {'id': 'plate', 'name': 'Transformer nameplate', 'label': 'nameplate', 'mw': 300, 'earliest_month': 1, 'likely_month': 1, 'latest_month': 1},
    {'id': 'gas', 'name': 'Bridge gas', 'kind': 'bridge_generation', 'label': 'contracted', 'mw': 60, 'earliest_month': 18, 'likely_month': 20, 'latest_month': 26, 'capex_m': 90},
    {'id': 'pv', 'name': 'Onsite solar', 'kind': 'onsite_solar', 'label': 'contracted', 'mw': 50, 'earliest_month': 12, 'likely_month': 12, 'latest_month': 12},
]
DEPS = [{'id': 'sub', 'name': 'New 230 kV substation', 'kind': 'substation', 'status': 'in_progress', 'start_month': 6,
         'earliest_months': 20, 'likely_months': 26, 'latest_months': 36}]


def test_deliverability_rules_and_ranges():
    from server.underwriting.deliverability import assess
    r = assess({'target_mw': 200, 'target_month': 36, 'sources': SOURCES, 'dependencies': DEPS,
                'configurations': [{'name': 'Grid only', 'source_ids': ['grid1', 'grid2', 'head', 'plate']},
                                   {'name': 'Hybrid', 'source_ids': ['grid1', 'grid2', 'gas', 'pv', 'plate']}]})
    grid, hybrid = r['configurations']
    base = grid['cases']['base']
    # substation finishes month 6+26=32 -> phase 1 from month 33; phase 2 at 36 -> 200 MW at 36
    assert base['target_reached_month'] == 36
    assert next(s for s in base['counted_sources'] if s['id'] == 'grid1')['month'] == 33
    assert all(s['id'] != 'plate' for s in base['counted_sources'])
    down = grid['cases']['downside']
    assert down['mw_at_target_month'] == 0 and down['target_reached_month'] is None  # substation late, studied excluded
    assert grid['deliverable_mw_at_target'] == {'low': 0, 'base': 200, 'high': 240}
    # solar adds zero firm MW; bridge gas counts
    hb = hybrid['cases']['base']
    assert hb['mw_at_target_month'] == 260 and hb['power_capex_m'] == 90
    assert any('substation' in x.lower() for x in grid['what_must_be_true'])


def test_deliverability_study_cap_and_cycle():
    from server.underwriting.deliverability import assess
    src = [{**SOURCES[1], 'study': {'type': 'system_impact', 'issuer': 'Utility', 'max_mw': 60}}]
    r = assess({'target_mw': 100, 'target_month': 40, 'sources': src})['configurations'][0]
    assert r['cases']['base']['mw_at_target_month'] == 60 and r['cases']['upside']['mw_at_target_month'] == 100
    with pytest.raises(ValueError):
        assess({'target_mw': 10, 'target_month': 10, 'sources': [{**SOURCES[0], 'depends_on': ['a']}],
                'dependencies': [{'id': 'a', 'name': 'A', 'depends_on': ['b'], 'earliest_months': 1, 'likely_months': 1, 'latest_months': 1},
                                 {'id': 'b', 'name': 'B', 'depends_on': ['a'], 'earliest_months': 1, 'likely_months': 1, 'latest_months': 1}]})


# ------------------------------------------------------------------- 3. bridge

def test_shapley_attribution_reconciles_and_is_order_independent():
    cfg = calculate('defaults27', {})['project']
    changes = {'energization_delay_months': 9, 'power_capex_m': 120, 'interest_rate_pct': 10}
    a = B.run(calculate, cfg, changes, order=['power_capex_m', 'interest_rate_pct', 'energization_delay_months'])
    b = B.run(calculate, cfg, changes, order=['energization_delay_months', 'power_capex_m', 'interest_rate_pct'])
    for m in ('npvM', 'leveredIRR', 'minDSCR'):
        assert a['reconciliation_residual'][m] == pytest.approx(0, abs=1e-9)
        assert a['attribution'][m] == pytest.approx(b['attribution'][m])
        assert sum(x[m] for x in a['sequential_waterfall']) == pytest.approx(a['total_change'][m])
    assert a['engine_runs'] == 8 and a['total_change']['npvM'] < 0
    assert a['explanation'][0].startswith('Levered IRR fell')


def test_path_bridge_matches_schedule_engine(proj):
    c, pid, sc, u = proj
    path = c.post(f'/api/projects/{pid}/paths', json={'name': 'Phased grid', 'strategy': 'grid', 'delay_months': 4,
                  'capex_uplift_pct': 10, 'energy_uplift_pct': 5, 'power_phases': [{'month': 24, 'mw': 75}, {'month': 36, 'mw': 150}]}).json()
    c.put(u + '/base-case', json={'scenario_id': sc['id']})
    r = c.get(u + f'/paths/{path["id"]}/bridge')
    assert r.status_code == 200, r.text
    impact = c.get(f'/api/projects/{pid}/paths/{path["id"]}/schedule-impact', params={'source_scenario_id': sc['id']}).json()
    assert r.json()['final']['npvM'] == pytest.approx(impact['revised']['npvM'], rel=1e-9)
    # The bridge explains the whole path against the unadjusted scenario (schedule-impact's baseline already includes uplifts).
    assert r.json()['base']['npvM'] == pytest.approx(calculate('underwrite', sc['config'])['summary']['npvM'], rel=1e-9)
    assert {d['key'] for d in r.json()['drivers']} == {'grid_capacity', 'energization_delay_months', 'construction_cost_mw', 'power_cost_mwh'}


def test_bridge_from_deliverability_case(proj):
    c, pid, sc, u = proj
    d = c.post(u + '/deliverability', json={'target_month': 36, 'sources': SOURCES, 'dependencies': DEPS,
               'configurations': [{'name': 'Hybrid', 'source_ids': ['grid1', 'grid2', 'gas']}]}).json()
    r = c.post(u + '/bridge', json={'from_deliverability': {'assessment_id': d['id'], 'configuration': 'Hybrid', 'case': 'downside'}})
    assert r.status_code == 200, r.text
    keys = {x['key'] for x in r.json()['drivers']}
    assert keys == {'grid_capacity', 'power_capex_m'}
    assert abs(sum(r.json()['attribution']['npvM'].values()) - r.json()['total_change']['npvM']) < 1e-6


# ------------------------------------------------------- 4. change pipeline

QUEUE = [{'queue_id': 'Q1', 'name': 'Solar A', 'status': 'active', 'fuel': 'solar', 'mw': 200, 'latitude': 39.0, 'longitude': -77.5, 'requested_cod': '2028-06-01'},
         {'queue_id': 'Q2', 'name': 'Gas B', 'status': 'active', 'fuel': 'gas', 'mw': 500, 'latitude': 39.1, 'longitude': -77.4, 'requested_cod': '2029-01-01'},
         {'queue_id': 'Q3', 'name': 'Far wind', 'status': 'active', 'fuel': 'wind', 'mw': 300, 'latitude': 45.0, 'longitude': -100.0}]
SITE = {'sites': [{'name': 'Site', 'latitude': 39.05, 'longitude': -77.45}], 'radius_km': 40}


def test_queue_withdrawal_flagged_for_analysis_never_credited(proj):
    c, pid, sc, u = proj
    first = c.post(u + '/queue/snapshots', json={'source': 'PJM queue', 'as_of': '2026-10-01', 'entries': QUEUE, **SITE}).json()
    assert first['changes'] == []
    nxt = [dict(QUEUE[0], status='withdrawn'), dict(QUEUE[1], requested_cod='2030-01-01'), dict(QUEUE[2], status='withdrawn')]
    second = c.post(u + '/queue/snapshots', json={'source': 'PJM queue', 'as_of': '2026-11-01', 'entries': nxt, **SITE}).json()
    events = {ch['body']['event']: ch for ch in second['changes']}
    assert set(events) == {'withdrawal', 'cod_change'}  # far wind ignored
    w = events['withdrawal']
    assert w['body']['requires'] == 'analysis' and w['body']['capacity_effect'] == 'none assumed'
    assert events['cod_change']['body']['slip_months'] == 12
    assert c.post(u + f'/approvals/{w["id"]}/accept', json={'note': 'x' * 20}).status_code == 422
    assert c.post(u + f'/approvals/{w["id"]}/acknowledge', json={'note': 'short'}).status_code == 422
    assert c.post(u + f'/approvals/{w["id"]}/acknowledge', json={'note': 'Reviewed: no shared upgrade with our POI'}).status_code == 200
    s = c.get(u + '/queue/summary', params={'source': 'PJM queue', 'latitude': 39.05, 'longitude': -77.45, 'radius_km': 40}).json()
    assert s['nearby']['count'] == 2 and s['historical_withdrawal_rate'] == 1.0 and s['median_cod_slip_months'] == 6  # Q1 0, Q2 12


def test_missing_from_feed_is_not_a_withdrawal(proj):
    c, pid, sc, u = proj
    c.post(u + '/queue/snapshots', json={'source': 'MISO', 'as_of': '2026-10-01', 'entries': QUEUE[:2], **SITE})
    r = c.post(u + '/queue/snapshots', json={'source': 'MISO', 'as_of': '2026-11-01', 'entries': QUEUE[:1], **SITE}).json()
    assert [ch['body']['event'] for ch in r['changes']] == ['missing_from_source']


def test_utility_study_scan_proposes_parcel_capacity(proj, monkeypatch):
    c, pid, sc, u = proj
    import json as _json
    eid = evidence(c, pid)
    with db() as con:
        con.execute('INSERT INTO site_energy_studies VALUES(?,?,?,?)', (pid, 'P1', _json.dumps({
            'evidence_id': eid, 'source_kind': 'study', 'issuer': 'Dominion', 'source_date': '2026-10-15',
            'notes': 'Facilities study result', 'capacity_mw': 120, 'energization_date': '2029-04-01', 'connection_cost_usd': 4e7}), 'now'))
    r = c.post(u + '/changes/scan-utility-studies').json()
    assert len(r['changes']) == 1 and r['changes'][0]['body']['scope'] == 'parcel:P1'
    assert c.post(u + '/changes/scan-utility-studies').json()['changes'] == []  # idempotent
    reg = c.get(u + '/assumptions').json()[0]
    assert reg['body']['value']['phases'] == [{'month': 40, 'mw': 120.0}] and reg['state'] == 'proposed'


# ----------------------------------------------------------- 5. forecasts

def test_forecast_import_and_price_scenarios(proj):
    c, pid, sc, u = proj
    bad = c.post(u + '/forecasts', json={'provider': 'Hub provider', 'issued_at': '2026-11-01', 'license': 'Free hub tier',
                 'periods': [{'period': '2026-01', 'p10': 60, 'p50': 50, 'p90': 70}]})
    assert bad.status_code == 422
    csv = 'period,p10,p50,p90\n' + '\n'.join(f'2026-{m:02d},{40+m},{50+m},{65+m}' for m in range(1, 13))
    f = c.post(u + '/forecasts', json={'adapter': 'csv', 'provider': 'Hub provider', 'market': 'PJM', 'location': 'WEST HUB',
               'issued_at': '2026-11-01', 'license': 'Free hub tier', 'csv': csv})
    assert f.status_code == 201, f.text
    r = c.post(u + '/price-scenarios', json={'forecast_id': f.json()['id'], 'blend_months': 6,
               'cases': {'low': {'start_price': 55, 'escalation_pct': 1}, 'base': {'start_price': 70, 'escalation_pct': 2.5},
                         'high': {'start_price': 95, 'escalation_pct': 4}}})
    assert r.status_code == 200, r.text
    cases = r.json()['cases']
    assert cases['low']['energy_weighted_price_mwh'] < cases['base']['energy_weighted_price_mwh'] < cases['high']['energy_weighted_price_mwh']
    assert cases['base']['months_by_basis'] == {'forecast': 12, 'blend': 6, 'planning assumption': 102}


# ------------------------------------------------------- 6. brief + auth

def test_brief_carries_references(proj):
    c, pid, sc, u = proj
    c.post(u + '/deliverability', json={'target_month': 36, 'sources': SOURCES[:2], 'dependencies': DEPS})
    b = c.get(u + '/brief')
    assert b.status_code == 200, b.text
    b = b.json()
    assert b['top_diligence_priorities'] and all('reference' in p for p in b['top_diligence_priorities'])
    assert b['deliverability']['answers'] and b['pending_changes'] == []
    assert any('withdrawal' in g for g in b['guidance'])
