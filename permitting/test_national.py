"""Release tests for deliberately incomplete nationwide screening, not legal accuracy."""
import json

import pytest
from fastapi.testclient import TestClient

from permitting.national import (NationalScreenError, STATES_51, counties, resolve_state, screen,
                                 sha, state_geojson, tri_evaluate)


@pytest.mark.parametrize('feature', state_geojson()['features'], ids=lambda f: f['properties']['STUSAB'])
def test_50_states_and_dc_have_navigable_geometry(feature):
    p = feature['properties']
    actual = resolve_state(float(p['INTPTLAT']),float(p['INTPTLON']))
    assert actual['abbr']==p['STUSAB'] and actual['fips']==p['STATE']
    assert actual['verified_local_boundary'] is False


def test_national_scope_exact_and_no_state_overclaim():
    assert len(STATES_51) == len(state_geojson()['features']) == 51
    for f in state_geojson()['features']:
        assert f['properties']['STUSAB'] in STATES_51
    ny=screen(40.72,-74,as_of='2026-10-29')
    assert ny['coverage']['geography']=='STATE_NAVIGATION_ONLY'
    assert ny['coverage']['local_rules']=='UNMAPPED' and ny['coverage']['state_rules']=='UNMAPPED'
    assert ny['coverage']['parcel']=='NOT_ASSESSED' and ny['coverage']['no_all_clear']
    assert len(ny['rules']) == 2 and all(x['layer']=='federal' for x in ny['rules'])


def test_facts_not_falsely_inferred():
    for op in ('true','false','ge','lt','eq'):
        assert tri_evaluate({'field':'parcel.missing','op':op,'value':10},{'parcel':{}}) == ('UNKNOWN',['parcel.missing'])
    assert tri_evaluate({'all':[{'field':'a','op':'false'}, {'field':'b','op':'true'}]}, {'b':True})[0] == 'UNKNOWN'
    assert tri_evaluate({'any':[{'field':'a','op':'false'}, {'field':'b','op':'true'}]}, {'b':True})[0] == 'TRUE'
    assert tri_evaluate({'all':[{'field':'a','op':'false'}, {'field':'b','op':'false'}]}, {'a':True})[0] == 'FALSE'
    assert tri_evaluate({'field':'flag','op':'false'}, {'flag':False})[0] == 'TRUE'
    assert tri_evaluate({'field':'flag','op':'false'}, {'flag':None})[0] == 'UNKNOWN'


def test_wetlands_and_faa_missing_trigger_verify_not_not_required():
    a=screen(34.05,-118.24,as_of='2026-10-29')
    assert all(r['finding']=='POSSIBLE_VERIFY' for r in a['rules'])
    w=next(x for x in a['rules'] if x['id']=='WETLANDS_404')
    assert w['missing_facts']==['parcel.wetlands_or_streams']
    assert 'Virginia' not in w['authority'] and 'Norfolk' not in w['authority']
    b=screen(34.05,-118.24,as_of='2026-10-29',facts={'parcel':{'wetlands_or_streams':False}})
    assert next(x for x in b['rules'] if x['id']=='WETLANDS_404')['finding']=='NOT_TRIGGERED'
    assert b['coverage']['no_all_clear']


def test_loudoun_requires_explicit_geoid_and_flags_design_unknowns():
    a=screen(39.08,-77.55,as_of='2026-10-29')
    assert a['coverage']['local_rules']=='UNMAPPED'
    b=screen(39.08,-77.55,county_geoid='51107',facts={'design':{'it_mw':200}},as_of='2026-10-29')
    assert b['coverage']['local_rules']=='LOUDOUN_ALPHA_PREVIEW'
    assert b['site']['county']['basis']=='user_selected_unverified'
    assert next(r for r in b['rules'] if r['id']=='STATE_HEUF_ASSESSMENT')['finding']=='POSSIBLE_VERIFY'
    assert next(r for r in b['rules'] if r['id']=='LU_LEGISLATIVE')['finding']=='POSSIBLE_VERIFY'
    assert b['coverage']['schedule']=='NOT_CALIBRATED'


def test_no_utility_mw_or_backup_default():
    b=screen(39.08,-77.55,county_geoid='51107',facts={'design':{'it_mw':200}},as_of='2026-10-29')
    for r in ('UTILITY_LARGE_LOAD','AIR_BACKUP'):
        assert next(x for x in b['rules'] if x['id']==r)['finding']=='POSSIBLE_VERIFY'


def test_precise_explicit_facts_change_classification_without_clearance():
    facts={'design':{'it_mw':200,'anticipated_utility_mw':200,'backup_generators':False},
           'parcel':{'grandfathered_by_right':False,'wetlands_or_streams':False}}
    a=screen(39.08,-77.55,county_geoid='51107',facts=facts,as_of='2026-10-29')
    f={r['id']:r['finding'] for r in a['rules']}
    assert f['AIR_BACKUP']=='NOT_TRIGGERED'
    assert f['UTILITY_LARGE_LOAD']=='POTENTIALLY_REQUIRED'
    assert f['LU_LEGISLATIVE']=='POTENTIALLY_REQUIRED'
    assert f['LU_BY_RIGHT']=='NOT_TRIGGERED'
    assert a['coverage']['no_all_clear']


def test_proposed_scenario_does_not_auto_adopt():
    a=screen(39.08,-77.55,county_geoid='51107',proposed=True,as_of='2026-10-29')
    assert a['policy_scenario']=={'proposed_enabled':True,'applied_to_baseline':False}


def test_county_is_reference_only_and_geoid_must_match_state():
    v=counties('51', 'Loudoun')
    assert v['counties'][0]['geoid']=='51107'
    assert len(counties('48')['counties'])>200
    with pytest.raises(NationalScreenError):screen(40.72,-74,county_geoid='51107')
    with pytest.raises(NationalScreenError):screen(39.08,-77.55,county_geoid='51999')


def test_outside_nation_explicit_error():
    with pytest.raises(NationalScreenError,match='outside'):
        screen(51.51,-0.12)
    with pytest.raises(NationalScreenError,match='finite'):
        resolve_state(float('nan'),-78)


def test_snapshot_reproducible_input_sensitive():
    a=screen(40.72,-74,as_of='2026-10-29');b=screen(40.72,-74,as_of='2026-10-29');c=screen(40.72,-74,as_of='2026-10-30')
    assert a['snapshot_sha256']==b['snapshot_sha256'] and a['snapshot_sha256']!=c['snapshot_sha256']
    assert len(a['snapshot_sha256'])==64


def test_read_only_api_and_auth_gate(monkeypatch):
    from server.app import app
    client=TestClient(app,base_url='http://localhost')
    geo=client.get('/api/permitting/map/states');assert geo.status_code==200 and len(geo.json()['features'])==51
    r=client.get('/api/permitting/coverage',params={'latitude':40.72,'longitude':-74});assert r.status_code==200
    r=client.get('/api/permitting/counties',params={'state_fips':'51','q':'Loudoun'});assert r.status_code==200
    r=client.post('/api/permitting/screen',json={'latitude':40.72,'longitude':-74});assert r.status_code==200
    assert client.get('/permitiq-national').status_code==200
    assert 'sandbox' not in r.json()['assessment_type']
    assert client.post('/api/permitting/screen',json={'latitude':40.72,'longitude':-74,'extraneous':1}).status_code==422
    monkeypatch.setenv('POWERPATH_V27_AUTH_MODE','required')
    for path in ('/api/permitting/coverage?latitude=40.72&longitude=-74','/api/permitting/map/states','/permitiq-national'):
        assert client.get(path).status_code==503
    assert client.post('/api/permitting/screen',json={'latitude':40.72,'longitude':-74}).status_code==503


def test_optional_county_polygons_and_mismatch(monkeypatch,tmp_path):
    import permitting.national as national
    # Tiny geometries are test fixtures, not real Loudoun zoning boundaries.
    polygon={'type':'Polygon','coordinates':[[[-77.7,38.9],[-77.4,38.9],[-77.4,39.3],[-77.7,39.3],[-77.7,38.9]]]}
    payload={'type':'FeatureCollection','powerpath_source':{'provider':'test only'},
             'features':[{'type':'Feature','properties':{'STATE':'51','GEOID':'51107','NAME':'Loudoun County'},'geometry':polygon}]}
    path=tmp_path/'counties.geojson';path.write_text(json.dumps(payload))
    monkeypatch.setattr(national,'COUNTY_GEOMETRIES_FILE',path)
    national.county_geometries.cache_clear()
    try:
        a=national.screen(39.08,-77.55,as_of='2026-10-29')
        assert a['site']['county']['geoid']=='51107'
        assert a['site']['county']['basis']=='generalized_census_county_polygon'
        assert a['coverage']['county_boundary']=='GENERALIZED_CENSUS_POLYGON'
        assert a['coverage']['local_rules']=='LOUDOUN_ALPHA_PREVIEW'
        with pytest.raises(NationalScreenError,match='conflicts'):
            national.screen(39.08,-77.55,county_geoid='51059',as_of='2026-10-29')
    finally:
        national.county_geometries.cache_clear()
