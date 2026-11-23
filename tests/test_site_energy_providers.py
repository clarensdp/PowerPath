import copy
import json
import sqlite3
from contextlib import contextmanager
from io import BytesIO
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError
from shapely.geometry import mapping, Point
from server.providers.base import PublicHTTP, ProviderError, DataPoint
from server.providers.electricity import eia
from server.providers.infrastructure import public_grid
from server.providers.renewables import nrel
from server.services.data_provenance import initialize
from tests.site_energy_samples import EIA, SOLAR, PV

TS = '2026-11-11T12:00:00+00:00'


@pytest.fixture
def db(tmp_path):
    @contextmanager
    def connection():
        con = sqlite3.connect(tmp_path / 'cache.sqlite3', isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()
    with connection() as con:
        con.execute('CREATE TABLE projects(id TEXT PRIMARY KEY)')
        con.executemany('INSERT INTO projects VALUES(?)', [('one',), ('two',)])
    initialize(connection)
    return connection


def test_eia_units_scope_zero_missing_and_provenance():
    result = eia.normalize(EIA, 'VA', TS)
    assert result['points'][0]['value'] == 82.5
    assert result['points'][0]['category'] == 'retail_statistic'
    assert result['points'][0]['retrieved_at'] == TS
    assert result['points'][0]['effective_date'] == '2026-08'
    assert result['points'][1]['value'] is None
    assert result['points'][1]['status'] == 'unavailable'
    assert eia.normalize(EIA, 'NC', TS)['status'] == 'unavailable'
    other = copy.deepcopy(EIA)
    other['response']['data'][0]['price'] = '0'
    assert eia.normalize(other, 'VA', TS)['points'][0]['value'] == 0
    other['response']['data'][0]['price-units'] = 'USD/kWh'
    with pytest.raises(ProviderError):
        eia.normalize(other, 'VA', TS)


def test_solar_resource_monthly_missing_and_generation():
    result = nrel.normalize_resource(SOLAR, 39, -77.5, TS)
    assert len(result['points']) == 4
    assert result['points'][0]['status'] == 'estimated'
    assert result['points'][1]['value'] == 2.1
    assert result['points'][2]['value'] is None
    estimate = nrel.normalize_generation(PV, nrel.SolarSystem(capacity_kw=1000), TS)
    assert estimate['points'][0]['value'] == 1500
    assert estimate['system_assumptions']['status'] == 'assumed'
    assert 'No storage' in estimate['points'][0]['methodology']
    with pytest.raises(ProviderError):
        nrel.normalize_generation({**PV,'station_info':'bad'},nrel.SolarSystem(capacity_kw=1000),TS)
    for bad in (0, -1, float('nan'), float('inf')):
        with pytest.raises(ValidationError):
            nrel.SolarSystem(capacity_kw=bad)


def test_distance_projection_footprint_intersection_and_unknown_capacity():
    parcel = mapping(Point(-77.5, 39).buffer(.001))
    # Latitude degrees must not accidentally be interpreted as meters.
    near = mapping(Point(-77.5, 39.01))
    assert 0.99 < public_grid.distance_km(parcel, near) < 1.02
    crossing = {'type': 'LineString', 'coordinates': [[-77.51,39],[-77.49,39]]}
    assert public_grid.distance_km(parcel, crossing) == 0
    feature = {'type':'Feature','geometry':crossing,'properties':{'ID':'1','VOLTAGE':-999999}}
    data = public_grid.normalize({'type':'FeatureCollection','features':[feature]}, parcel, TS)
    props = data['features'][0]['properties']
    assert props['available_capacity_mw'] is None and props['voltage_kv'] is None
    assert props['energization_date'] is None and props['connection_cost_usd'] is None
    assert props['source_id'] == '1' and props['retrieved_at'] == TS
    with pytest.raises(ValueError):
        public_grid.valid_geometry({'type':'Point','coordinates':[500000,4300000]})


def test_gis_truncation_invalid_geometry_and_territory_intersection():
    parcel = mapping(Point(-77.5,39).buffer(.001))
    far = {'type':'Feature', 'geometry':mapping(Point(-80,35).buffer(.01)), 'properties':{'ID':'x'}}
    payload = {'type':'FeatureCollection','features':[far], 'exceededTransferLimit':True}
    result = public_grid.normalize(payload, parcel, TS, kind='service_territory')
    assert result['features'] == [] and result['status'] == 'partial'
    payload['features'].append({'type':'Feature','geometry':None,'properties':{}})
    assert 'invalid' in ' '.join(public_grid.normalize(payload,parcel,TS)['warnings'])


def test_cache_project_isolation_original_timestamp_and_secret_redaction(db):
    calls = []
    def transport(req, timeout):
        calls.append(req)
        assert timeout == 8
        return BytesIO(b'{"inputs":{"api_key":"SECRET","lat":39},"outputs":{"value":1}}')
    http = PublicHTTP(db, transport)
    first = http.get('one', 'https://example.gov/api', {'api_key':'SECRET'})
    second = http.get('one', 'https://example.gov/api', {'api_key':'SECRET'})
    third = http.get('two', 'https://example.gov/api', {'api_key':'SECRET'})
    assert len(calls) == 2 and first[1] == second[1]
    assert not first[2] and second[2] and not third[2]
    with db() as con:
        assert 'SECRET' not in json.dumps([dict(r) for r in con.execute('SELECT * FROM site_energy_cache')])
        con.execute('UPDATE site_energy_cache SET expires_at=0')
    assert not http.get('one', 'https://example.gov/api', {'api_key':'SECRET'})[2]


def test_timeout_retry_and_negative_cache(db):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise TimeoutError('url-with-secret')
    http = PublicHTTP(db, fail, sleep=lambda _: None)
    for _ in range(2):
        with pytest.raises(ProviderError, match='timed out'):
            http.get('one', 'https://example.gov')
    assert len(calls) == 2


@pytest.mark.parametrize('payload', [b'not-json', b'{"error":{"message":"SECRET"}}', b'[]'])
def test_bad_response_never_returns_observation(db, payload):
    http = PublicHTTP(db, lambda *a, **kw: BytesIO(payload))
    with pytest.raises(ProviderError):
        http.get('one', 'https://example.gov')


def test_401_not_retried_and_key_not_exposed(db):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise HTTPError('https://example.gov?api_key=SECRET',401,'SECRET',{},None)
    with pytest.raises(ProviderError, match='HTTP 401'):
        PublicHTTP(db, fail).get('one','https://example.gov')
    assert len(calls) == 1


def test_missing_credentials_are_explicit(monkeypatch, db):
    for key in ('POWERPATH_EIA_API_KEY','POWERPATH_NREL_API_KEY'):
        monkeypatch.delenv(key, raising=False)
    def no_network(*args, **kwargs):
        raise AssertionError('No requests expected')
    http = PublicHTTP(db,no_network)
    for result in (eia.fetch(http,'one','VA'), nrel.fetch(http,'one',39,-77)):
        assert result['status'] == 'unavailable' and result['points'] == [] and result['error']


def test_datapoint_rejects_nonfinite():
    with pytest.raises(ValidationError):
        DataPoint(value=float('nan'),unit='MW',source_name='test',retrieved_at=TS,status='observed',methodology='test')


def test_configured_infrastructure_with_provenance_and_county_scope(monkeypatch):
    parcel = mapping(Point(-79.25, 35.75).buffer(.005))
    calls = []

    class HTTP:
        def get(self, project, url, params, ttl):
            calls.append(url)
            territory = 'Chatham_ElectricDistricts' in url
            feature = {'type':'Feature', 'properties':{'OBJECTID':1, 'SERVICE':'Synthetic utility',
                'NAME':None if territory else 'Synthetic station','VOLTAGE':230,'last_edited_date':1666638166000},
                'geometry':parcel if territory else mapping(Point(-79.26,35.75))}
            return {'type':'FeatureCollection','features':[feature]},TS,False

    monkeypatch.setenv('POWERPATH_SUBSTATION_LAYER_URL','https://example.gov/stations/FeatureServer/0')
    monkeypatch.setenv('POWERPATH_SUBSTATION_LAYER_NAME','Synthetic station layer · test vintage')
    monkeypatch.delenv('POWERPATH_TERRITORY_LAYER_URL',raising=False)
    monkeypatch.setenv('POWERPATH_CHATHAM_TERRITORY_OPT_IN','1')
    station=public_grid.fetch(HTTP(),'one',parcel,'substation')
    territory=public_grid.fetch(HTTP(),'one',parcel,'service_territory','37125')
    assert station['features'][0]['properties']['distance_km']>0
    assert station['features'][0]['properties']['available_capacity_mw'] is None
    props=territory['features'][0]['properties']
    assert props['name']=='Synthetic utility' and props['distance_km']==0
    assert props['effective_date'] is None and props['record_edited_at'].startswith('2022-')
    assert public_grid.fetch(HTTP(),'one',parcel,'service_territory','51107')['status']=='unavailable'
    assert len(calls)==2
