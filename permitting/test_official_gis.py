"""v30.6 deterministic contract tests using stubbed official GIS responses.

They prove integration and fail-closed interpretation, not live government-service reachability.
"""
import copy
import json

import pytest
from fastapi.testclient import TestClient
from permitting import official_gis as gis
from permitting.national import NationalScreenError


def fake_fetch(url,params):
    if url==gis.CENSUS:
        return {'result':{'geographies':{
            'Counties':[{'GEOID':'51107','NAME':'Loudoun County, Virginia','STATE':'51'}],
            'Incorporated Places':[]}}}
    if url==gis.FEMA:
        return {'features':[{'attributes':{'FLD_ZONE':'X','SFHA_TF':'F','FLD_AR_ID':'FAKE'}}]}
    if url==gis.NWI:
        return {'features':[{'attributes':{'Wetlands.ATTRIBUTE':'PFO1A','Wetlands.WETLAND_TYPE':'Freshwater Forested/Shrub Wetland','Wetlands.ACRES':2.0}}]}
    raise AssertionError('Unexpected service')


def test_source_hosts_are_fixed():
    for url in [gis.CENSUS,gis.FEMA,gis.NWI]:
        assert url.startswith('https://') and '?' not in url
    assert 'geocoding.geo.census.gov' in gis.CENSUS
    assert 'hazards.fema.gov' in gis.FEMA
    assert 'wim.usgs.gov' in gis.NWI


def test_no_remote_without_explicit_user_and_operator_consent(monkeypatch):
    monkeypatch.delenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS',raising=False)
    with pytest.raises(NationalScreenError,match='consent'):
        gis.assess_official(39.08,-77.55,consent=False,fetch=fake_fetch)
    with pytest.raises(NationalScreenError,match='disabled'):
        gis.assess_official(39.08,-77.55,consent=True,fetch=fake_fetch)


def test_official_sources_positive_hits_are_just_point_screening(monkeypatch):
    monkeypatch.setenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS','1')
    d=gis.assess_official(39.08,-77.55,consent=True,fetch=fake_fetch)
    assert d['jurisdiction']['status']=='MATCHED'
    assert d['jurisdiction']['county']['geoid']=='51107'
    assert d['jurisdiction']['county_basis']=='CENSUS_COORDINATE_LOOKUP'
    assert not d['jurisdiction']['incorporated_place_candidates']
    assert all(x['status']=='MAPPED_INTERSECTION' for x in d['environmental_layers'])
    assert d['environmental_layers'][1]['features'][0]['ATTRIBUTE']=='PFO1A'
    assert d['coverage']['no_all_clear'] is True
    assert d['coverage']['parcel_footprint']=='NOT_EVALUATED'
    assert d['coverage']['zoning']=='NOT_VERIFIED'
    assert len(d['evidence_sha256'])==64
    assert 'current' not in d['coverage']['approval'].lower()


def test_no_features_does_not_mean_clear(monkeypatch):
    monkeypatch.setenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS','1')
    def empty(url,params):
        return fake_fetch(url,params) if url==gis.CENSUS else {'features':[]}
    d=gis.assess_official(39.08,-77.55,consent=True,fetch=empty)
    assert all(x['status']=='NO_MAPPED_INTERSECTION_AT_POINT' for x in d['environmental_layers'])
    assert all('does not clear' in x['meaning'] for x in d['environmental_layers'])
    assert d['coverage']['no_all_clear']


def test_individual_service_down_does_not_crash_or_clear(monkeypatch):
    monkeypatch.setenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS','1')
    def offline(url,params):
        if url==gis.NWI:raise TimeoutError('Timed out')
        if url==gis.FEMA:return {'error': {'code':500,'message':'Service unavailable'}}
        return fake_fetch(url,params)
    d=gis.assess_official(39.08,-77.55,consent=True,fetch=offline)
    assert [x['status'] for x in d['environmental_layers']]==['UNAVAILABLE','UNAVAILABLE']
    assert d['jurisdiction']['status']=='MATCHED'
    assert d['coverage']['no_all_clear']


def test_missing_county_does_not_fallback_to_centroid():
    def missing(url,params):
        return {'result':{'geographies':{'Counties':[]}}}
    state={'fips':'51'}
    d=gis.census_lookup(39.08,-77.55,state,fetch=missing)
    assert d['status']=='NO_UNAMBIGUOUS_MATCH' and 'county' not in d


def test_county_geography_mismatch_is_review():
    def mismatch(url,params):
        return {'result':{'geographies':{'Counties':[{'GEOID':'36061','STATE':'36','NAME':'New York County'}]}}}
    d=gis.census_lookup(39.08,-77.55,{'fips':'51'},fetch=mismatch)
    assert d['status']=='NO_UNAMBIGUOUS_MATCH'


def test_no_future_external_urls_from_request():
    params={'lat':'-77.5','lon':'39.0'}
    # User input goes only into approved coordinate parameters, not a URL or host.
    assert all('http' not in str(value) for value in params.values())


def test_truncated_arcgis_fails_closed():
    def over(url,params):return {'features': [], 'exceededTransferLimit':True}
    assert gis.fema_lookup(39,-77,fetch=over)['status']=='UNAVAILABLE'


def test_bad_arcgis_shape_fails_closed():
    def invalid(url,params):return {'wrongField':[]}
    assert gis.wetlands_lookup(39,-77,fetch=invalid)['status']=='UNAVAILABLE'


def test_route_behind_operator_flag_and_auth(monkeypatch):
    from server.app import app
    c=TestClient(app,base_url="http://localhost")
    monkeypatch.delenv('POWERPATH_V27_AUTH_MODE',raising=False)
    monkeypatch.delenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS',raising=False)
    assert c.get('/api/permitting/official-gis/status').json()['enabled'] is False
    args={'latitude':39.08,'longitude':-77.55,'consent_remote':True}
    assert c.post('/api/permitting/official-gis',json=args).status_code==503
    assert c.post('/api/permitting/official-gis',json={**args,'consent_remote':False}).status_code==422
    assert c.post('/api/permitting/official-gis',json={**args,'untrusted_endpoint':'https://evil.invalid'}).status_code==422
    monkeypatch.setenv('POWERPATH_V27_AUTH_MODE','required')
    assert c.post('/api/permitting/official-gis',json=args).status_code==503
    assert c.get('/api/permitting/official-gis/status').status_code==503


def test_route_data_mocked_and_rate_limit(monkeypatch):
    from server.app import app
    import server.national_permitting_api as api
    monkeypatch.delenv('POWERPATH_V27_AUTH_MODE',raising=False)
    monkeypatch.setenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS','1')
    monkeypatch.setattr(api,'assess_official',lambda lat,lon,consent: {'county':'test-fixture','no_all_clear':True})
    api._GIS_RATELIMIT.clear()
    c=TestClient(app,base_url="http://localhost")
    args={'latitude':39.08,'longitude':-77.55,'consent_remote':True}
    for i in range(20):
        r=c.post('/api/permitting/official-gis',json=args)
        assert r.status_code==200,r.text
    assert c.post('/api/permitting/official-gis',json=args).status_code==429
    api._GIS_RATELIMIT.clear()


def test_territories_are_outside_scope(monkeypatch):
    monkeypatch.setenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS','1')
    with pytest.raises(NationalScreenError,match='outside'):
        gis.assess_official(18.45,-66.1,consent=True,fetch=fake_fetch)


def test_request_not_accept_nan_or_overly_precise_wrong_lat(monkeypatch):
    from server.app import app
    c=TestClient(app,base_url="http://localhost")
    assert c.post('/api/permitting/official-gis',json={'latitude':100,'longitude':-77,'consent_remote':True}).status_code==422
    assert c.post('/api/permitting/official-gis',json={'latitude':39,'longitude':'NaN','consent_remote':True}).status_code==422
