"""Offline parcel → providers → saved inputs → existing financial engine integration.

Run independently from required-auth modules, whose globals intentionally differ.
"""
import json
import os
import tempfile

os.environ['POWERPATH_DATA_DIR'] = tempfile.mkdtemp(prefix='pp-energy-test-')
os.environ['POWERPATH_V27_AUTH_MODE'] = 'local_only'
os.environ.pop('POWERPATH_DATABASE_URL', None)
os.environ.pop('POWERPATH_IDENTITY_PROVIDER', None)

import pytest
from fastapi.testclient import TestClient
from server.app import app, db, calculate
from tests.site_energy_samples import MockTransport


@pytest.fixture
def flow(monkeypatch):
    for name in ('EIA','NREL'):
        monkeypatch.setenv(f'POWERPATH_{name}_API_KEY', 'SYNTHETIC_TEST_KEY')
    for name in ('POWERPATH_TERRITORY_LAYER_URL','POWERPATH_SUBSTATION_LAYER_URL'):
        monkeypatch.delenv(name, raising=False)
    transport = MockTransport()
    monkeypatch.setattr(app.state.site_energy.http, 'transport', transport)
    c = TestClient(app,base_url='http://127.0.0.1')
    pid = c.post('/api/projects?starter_scenario=true',json={'name':'Energy test only','target_mw':50}).json()['id']
    parcel = str(c.get('/api/parcels28/catalog').json()['features'][0]['properties']['PA_MCPI'])
    base = f'/api/projects/{pid}/parcels28/{parcel}/energy'
    scenario = c.get(f'/api/projects/{pid}/scenarios').json()[0]
    return c,pid,parcel,base,scenario,transport


def selection(scenario, **kwargs):
    return {'scenario_id':scenario['id'], 'expected_version':scenario['version'],
            'price_mode':'assumed','price_mwh':85,'rationale':'Synthetic test scenario assumption', **kwargs}


def selected_reference(point):
    return {'reference_period':point['effective_date'],'reference_coverage':point['coverage'],
            'reference_value':point['value']}


def test_parcel_context_persistence_cache_and_financial_run(flow):
    c,pid,parcel,base,scenario,transport = flow
    assert c.post(f'/api/projects/{pid}/parcels28',json={'parcel_id':parcel}).status_code == 201
    response = c.get(base+'-context')
    assert response.status_code == 200, response.text
    context = response.json()
    assert context['parcel']['state'] == 'VA'
    assert context['delivered_price']['value'] is None
    line = context['grid_infrastructure']['transmission_line']['features'][0]
    assert line['properties']['available_capacity_mw'] is None
    assert context['renewable_resources']['solar']['points'][0]['status'] == 'estimated'
    calls = len(transport.calls)
    assert c.get(base+'-context').json()['electricity']['eia']['cached']
    assert len(transport.calls) == calls
    ref = context['electricity']['eia']['points'][0]
    applied = c.post(base+'/scenario-inputs',json=selection(scenario,price_mode='eia_reference',**selected_reference(ref)))
    assert applied.status_code == 200, applied.text
    config = applied.json()['config']
    assert config['powerCostMWh'] == 82.5
    assert config['siteEnergyInputs']['electricity']['status'] == 'assumed'
    assert config['siteEnergyInputs']['reference']['status'] == 'observed'
    expected = calculate('underwrite',{**scenario['config'],'powerCostMWh':82.5})
    run = c.post(f'/api/projects/{pid}/scenarios/{scenario["id"]}/runs')
    assert run.status_code == 201,run.text
    assert run.json()['summary'] == expected['summary']
    with db() as con:
        stored = json.loads(con.execute('SELECT input_json FROM runs WHERE id=?',(run.json()['id'],)).fetchone()[0])
        assert stored['siteEnergyInputs']['parcel_source_version'] == context['parcel']['source_version']
        snapshot = json.loads(con.execute('SELECT body FROM site_energy_contexts WHERE project_id=?',(pid,)).fetchone()[0])
        assert snapshot['grid_infrastructure']['transmission_line']['features'][0]['geometry'] == line['geometry']


def test_removed_provider_is_not_requested_or_exposed(flow, monkeypatch):
    c,pid,parcel,base,sc,transport = flow
    # Even a leftover shell setting cannot activate the removed integration.
    monkeypatch.setenv('POWERPATH_PJM_API_KEY', 'UNUSED_TEST_KEY')
    context = c.get(base+'-context?pjm_node=123').json()
    assert set(context['electricity']) == {'eia'}
    assert 'pjm' not in context['data_quality']
    assert set(c.get(base+'/electricity-prices').json()['electricity']) == {'eia'}
    assert all('pjm.com' not in url for url in transport.calls)
    schema = app.openapi()
    assert 'pjm_node' not in json.dumps(schema)
    assert 'pjm_plus_delivery' not in json.dumps(schema)


@pytest.mark.parametrize('removed', [
    {'price_mode':'pjm_plus_delivery'}, {'pjm_node':123}, {'delivery_adjustment_mwh':100}
])
def test_removed_selection_rejected_without_mutating_scenario(flow, removed):
    c,pid,parcel,base,sc,_ = flow
    assert c.post(base+'/scenario-inputs',json=selection(sc,**removed)).status_code == 422
    current = c.get(f'/api/projects/{pid}/scenarios').json()[0]
    assert current['version'] == sc['version']
    assert current['config'] == sc['config']


@pytest.mark.parametrize('mode', ['assumed', 'user_supplied'])
def test_explicit_price_requires_value_and_preserves_financial_outputs(flow, mode):
    c,pid,parcel,base,sc,transport = flow
    assert c.post(base+'/scenario-inputs',json=selection(sc,price_mode=mode,price_mwh=None)).status_code == 422
    response = c.post(base+'/scenario-inputs',json=selection(sc,price_mode=mode,price_mwh=97))
    assert response.status_code == 200, response.text
    assert response.json()['config']['powerCostMWh'] == 97
    expected = calculate('underwrite',{**sc['config'],'powerCostMWh':97})
    run = c.post(f'/api/projects/{pid}/scenarios/{sc["id"]}/runs')
    assert run.json()['summary'] == expected['summary']
    assert not transport.calls


def test_historical_price_selection_remains_readable_and_runnable(flow):
    c,pid,parcel,base,sc,transport = flow
    legacy = {**sc['config'], 'powerCostMWh':94.5,
              'siteEnergyInputs':{'price_mode':'pjm_plus_delivery', 'delivery_adjustment_mwh':100,
                                  'reference':{'value':-5.5,'source_name':'Historical PJM reference'}}}
    with db() as con:
        con.execute('UPDATE scenarios SET config_json=? WHERE id=?',(json.dumps(legacy),sc['id']))
    current = c.get(f'/api/projects/{pid}/scenarios').json()[0]
    assert current['config'] == legacy
    run = c.post(f'/api/projects/{pid}/scenarios/{sc["id"]}/runs')
    assert run.status_code == 201, run.text
    assert run.json()['summary'] == calculate('underwrite',legacy)['summary']
    assert not transport.calls


def test_reference_drift_and_version_conflict(flow):
    c,pid,parcel,base,sc,_ = flow
    context = c.get(base+'-context').json()
    ref = context['electricity']['eia']['points'][0]
    wrong = selection(sc,price_mode='eia_reference',**selected_reference(ref))
    wrong['reference_value'] = 1
    assert c.post(base+'/scenario-inputs',json=wrong).status_code == 409
    assert c.post(base+'/scenario-inputs',json=selection(sc)).status_code == 200
    assert c.post(base+'/scenario-inputs',json=selection(sc)).status_code == 409


def test_solar_generation_and_explicit_blend_use_existing_engine(flow):
    c,pid,parcel,base,sc,_ = flow
    solar = {'capacity_kw':1000,'tilt':20,'azimuth':180,'losses_pct':14}
    r = c.post(base+'/solar-estimate',json=solar)
    assert r.json()['points'][0]['value'] == 1500
    body = selection(sc,solar=solar,blend_solar=True,annual_load_mwh=10000,solar_cost_mwh=50,solar_self_use_pct=100)
    r = c.post(base+'/scenario-inputs',json=body)
    assert r.status_code == 200,r.text
    assert r.json()['config']['powerCostMWh'] == pytest.approx(.85*85+.15*50)
    assert r.json()['config']['powerTranches'] == sc['config']['powerTranches']
    assert r.json()['config']['buildings'] == sc['config']['buildings']


def test_foreign_scenario_and_evidence_rejected(flow):
    c,pid,parcel,base,sc,_ = flow
    other = c.post('/api/projects?starter_scenario=true',json={'name':'Other project','target_mw':20}).json()['id']
    other_sc = c.get(f'/api/projects/{other}/scenarios').json()[0]
    assert c.post(base+'/scenario-inputs',json=selection(other_sc)).status_code == 404
    body = {'evidence_id':'not-in-project','source_date':'2026-01-01','source_url':'https://example.gov/study',
            'notes':'Synthetic test utility study','capacity_mw':10}
    assert c.put(base+'/utility-study',json=body).status_code == 422
    eid = c.post(f'/api/projects/{pid}/evidence',json={'title':'Synthetic test study','category':'utility'}).json()['id']
    body['evidence_id'] = eid
    assert c.put(base+'/utility-study',json=body).status_code == 422
    c.post(f'/api/projects/{pid}/evidence/{eid}/file',files={'attachment':('study.txt',b'Synthetic test only','text/plain')})
    response = c.put(base+'/utility-study',json=body)
    assert response.status_code == 200,response.text
    context = c.get(base+'-context').json()
    assert context['utility_study']['capacity_mw'] == 10
    assert context['utility_study']['status'] == 'user_supplied'
    assert context['grid_capacity']['value'] is None


def test_provider_failure_and_missing_keys_do_not_break_modeling(flow, monkeypatch):
    c,pid,parcel,base,sc,_ = flow
    def fail(*args,**kwargs):
        raise TimeoutError()
    monkeypatch.setattr(app.state.site_energy.http,'transport',fail)
    monkeypatch.setattr(app.state.site_energy.http,'sleep',lambda _:None)
    r = c.get(base+'-context')
    assert r.status_code == 200
    assert r.json()['electricity']['eia']['status'] == 'unavailable'
    assert r.json()['grid_infrastructure']['transmission_line']['status'] == 'unavailable'
    assert c.get(f'/api/projects/{pid}/parcels28/{parcel}').status_code == 200
    assert c.post(base+'/scenario-inputs',json=selection(sc,price_mode='eia_reference')).status_code == 422
    applied = c.post(base+'/scenario-inputs',json=selection(sc))
    assert applied.status_code == 200,applied.text
    expected = calculate('underwrite',sc['config'])
    run = c.post(f'/api/projects/{pid}/scenarios/{sc["id"]}/runs').json()
    assert run['summary'] == expected['summary']


def test_unknown_project_parcel_and_invalid_solar(flow):
    c,pid,parcel,base,sc,_ = flow
    assert c.get(base.replace(pid,'missing')+'-context').status_code == 404
    assert c.get(base.replace(parcel,'missing')+'-context').status_code == 404
    assert c.post(base+'/solar-estimate',json={'capacity_kw':-10}).status_code == 422


def test_metadata_does_not_change_financial_math(flow):
    _,_,_,_,sc,_ = flow
    expected = calculate('underwrite',sc['config'])
    actual = calculate('underwrite',{**sc['config'],'siteEnergyInputs':{'test':'synthetic provenance'}})
    # The engine echoes input metadata in assumptions; all financial outputs are unchanged.
    actual['assumptions'].pop('siteEnergyInputs')
    assert expected == actual
