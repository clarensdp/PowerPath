import json
from pathlib import Path
import pytest
from permitting.footprint import assess, FootprintError
from permitting.footprint_sources import _get_layer,official_overlays


def rect(x0,y0,x1,y1):
    return {'type':'Polygon','coordinates':[[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]]}

P=rect(-77,38,-76.99,38.01)

def layer(kind,polygons,coverage=None):
    return {'kind':kind,'source':{'title':'Synthetic fixture; no real-world legal assertions','url':'https://example.org/testing'},
            'features':{'type':'FeatureCollection','features':[{'type':'Feature','geometry':p,'properties':{'class':kind}} for p in polygons]},
            'coverage_geometry':coverage}


def test_geometry_intersection_area_and_nontrivial_extent():
    f=assess(P,[layer('wetlands',[rect(-77,38,-76.995,38.01)])])
    assert 0.49<f['layers'][0]['intersection_pct']/100<0.51
    assert f['layers'][0]['intersection_acres']>0
    assert f['summary']['certified_buildable_acres'] is None
    assert f['coverage']['overall']=='SCREENING_NOT_CLEARED'
    assert f['layers'][0]['intersection_geometry'] is not None


def test_union_prevents_double_counting():
    half=rect(-77,38,-76.995,38.01)
    f=assess(P,[layer('wetlands',[half,half]),layer('flood',[half])])
    assert f['layers'][0]['intersection_pct']<51
    assert f['summary']['intersecting_supplied_constraints_acres']==pytest.approx(f['layers'][0]['intersection_acres'],abs=.0001)


def test_hole_subtracts_area():
    shell=P['coordinates'][0]
    hole=rect(-76.998,38.002,-76.992,38.008)['coordinates'][0][::-1]
    with_hole={'type':'Polygon','coordinates':[shell,hole]}
    a=assess(P,[layer('wetlands',[with_hole])])
    assert 0<a['layers'][0]['intersection_pct']<100


def test_multigeometry_union():
    mp={'type':'MultiPolygon','coordinates':[rect(-77,38,-76.997,38.005)['coordinates'],rect(-76.995,38.006,-76.99,38.01)['coordinates']]}
    result=assess(P,[layer('flood',[mp])])
    assert result['layers'][0]['intersection_pct']>0


def test_bbox_overlaps_without_polygon_overlap():
    # Outer bbox of the first section can overlap parcel; actual shapes need to intersect.
    other=rect(-76.98,38.01,-76.97,38.02)
    r=assess(P,[layer('wetlands',[other])])
    assert r['layers'][0]['intersection_acres']==0
    assert r['layers'][0]['coverage_status']=='EXTENT_UNKNOWN'
    assert 'NOT CLEARANCE' in r['layers'][0]['no_intersection_meaning']


def test_declared_coverage_is_still_not_regulatory_clearance():
    r=assess(P,[layer('wetlands',[],P),layer('flood',[],P),layer('zoning',[P],P)])
    assert r['coverage']['wetlands']=='DECLARED_COMPLETE'
    assert r['coverage']['zoning']=='DECLARED_COMPLETE_UNVERIFIED'
    assert r['summary']['certified_buildable_acres'] is None
    assert r['summary']['complete_flood_wetlands_extent_declared']


def test_partial_extent_not_complete():
    r=assess(P,[layer('wetlands',[],rect(-77,38,-76.995,38.01))])
    assert r['layers'][0]['coverage_status']=='PARTIAL_EXTENT_DECLARED'
    assert r['coverage']['wetlands']=='UNKNOWN'


def test_multiple_distinct_categories_not_double_counted_in_total():
    r=assess(P,[layer('other',[P]),layer('setback',[P]),layer('zoning',[P])])
    assert r['summary']['intersecting_supplied_constraints_acres']==pytest.approx(r['parcel']['area_acres'],abs=.0001)

@pytest.mark.parametrize('bad',[
    {'type':'Point','coordinates':[-77,38]},
    rect(0,0,10,10),
    {'type':'Polygon','coordinates':[[[-77,38],[-76.99,38.01],[-77,38.01],[-76.99,38],[-77,38]]]},
    {'type':'Polygon','coordinates':[[[-77,38],[-76.99,38],[-76.99,38.01],[-77,38.01]]]},
    {'type':'Polygon','coordinates':[[[-77,38],[-76.99,38],[-76.99,float('nan')],[-77,38]]]},
])
def test_invalid_parcels_rejected(bad):
    with pytest.raises(FootprintError):assess(bad,[])


def test_unknown_kind_rejected():
    with pytest.raises(FootprintError):assess(P,[layer('UNSUPPORTED',[])])


def test_fingerprint_deterministic():
    a=assess(P,[layer('zoning',[P])]);b=assess(P,[layer('zoning',[P])]);assert a['snapshot_sha256']==b['snapshot_sha256']


def test_empty_source_not_silent_all_clear():
    f=assess(P,[])
    assert f['layers']==[] and f['summary']['certified_buildable_acres'] is None
    assert f['coverage']['zoning']=='UNKNOWN'
    assert f['coverage']['wetlands']=='UNKNOWN'


def test_remote_requires_consent_and_enabled(monkeypatch):
    monkeypatch.delenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS',raising=False)
    with pytest.raises(FootprintError):official_overlays(P,consent=True)


def test_remote_polygon_fetch_mock_and_sfha_filter():
    hits=[]
    def fake(url,params):
        hits.append(params)
        if params.get('returnIdsOnly')=='true':return {'objectIds':[101,102]}
        if params.get('f')=='geojson':
            return {'type':'FeatureCollection','features':[
                {'type':'Feature','geometry':P,'properties':{'SFHA_TF':'T','FLD_ZONE':'AE'}},
                {'type':'Feature','geometry':P,'properties':{'SFHA_TF':'F','FLD_ZONE':'X'}}]}
        raise AssertionError(params)
    layerdoc,n=_get_layer('fema',P,fake)
    assert n==2
    assert len(layerdoc['features']['features'])==1
    assert hits[0]['geometryType']=='esriGeometryEnvelope'
    assert layerdoc['coverage_geometry'] is None


def test_remote_excessive_results_fail_closed():
    def fake(url,params):return {'objectIds':list(range(250))}
    with pytest.raises(ValueError,match='bounded'): _get_layer('nwi',P,fake)


def test_remote_partial_service_fails_closed(monkeypatch):
    monkeypatch.setenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS','1')
    def fake(url,params):raise ValueError('network down')
    layers,stats,warns=official_overlays(P,consent=True,fetch=fake)
    assert layers==[]
    assert stats['fema']['status']=='UNAVAILABLE'
    assert stats['nwi']['status']=='UNAVAILABLE'
    assert len(warns)==2


def test_live_api_readonly_and_rejects_missing_consent(monkeypatch):
    from fastapi.testclient import TestClient
    from server.app import app
    c=TestClient(app,base_url='http://localhost')
    monkeypatch.delenv('POWERPATH_V27_AUTH_MODE',raising=False)
    response=c.post('/api/permitting/footprint',json={'geometry':P,'layers':[layer('wetlands',[P])]})
    assert response.status_code==200, response.text
    data=response.json()
    assert data['layers'][0]['intersection_pct']==100
    assert data['persisted'] is False
    status=c.get('/api/permitting/footprint/status')
    assert status.status_code==200
    response=c.post('/api/permitting/footprint',json={'geometry':P,'official':True,'layers':[]})
    assert response.status_code==422


def test_required_auth_blocks_alpha(monkeypatch):
    from fastapi.testclient import TestClient
    from server.app import app
    monkeypatch.setenv('POWERPATH_V27_AUTH_MODE','required')
    r=TestClient(app,base_url='http://localhost').get('/api/permitting/footprint/status')
    assert r.status_code in (401,403,503)


def test_remote_3d_polygons_are_normalized_to_2d():
    p3={'type':'Polygon','coordinates':[[[x,y,15] for x,y in P['coordinates'][0]]]}
    def fake(url,params):
        if params.get('returnIdsOnly')=='true':return {'objectIds':[5]}
        return {'type':'FeatureCollection','features':[{'type':'Feature','geometry':p3,'properties':{'WETLAND_TYPE':'Riverine'}}]}
    result,count=_get_layer('nwi',P,fake)
    assert count==1
    assert len(result['features']['features'][0]['geometry']['coordinates'][0][0])==2
