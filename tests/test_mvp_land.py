import pytest
import json
from shapely.geometry import box, mapping as _mapping, shape

def mapping(g): return json.loads(json.dumps(_mapping(g)))
from permitting.footprint import assess


def layer(kind, geometry, parcel):
    return {'kind':kind,'source':{'title':'Synthetic unit test'},'coverage_geometry':mapping(parcel),
            'features':{'type':'FeatureCollection','features':[{'type':'Feature','properties':{},'geometry':mapping(geometry)}]}}


def test_lake_splits_residual_and_overlap_is_not_double_counted():
    parcel=box(-77,38,-76.99,38.01); water=box(-76.998,37.99,-76.993,38.02)
    r=assess(mapping(parcel),[layer('water',water,parcel),layer('wetlands',water,parcel)])
    s=r['summary'];total=r['parcel']['area_acres']
    assert s['potentially_usable_acres']==pytest.approx(total*.5,rel=.001)
    assert s['largest_contiguous_acres']==pytest.approx(total*.3,rel=.001)
    assert shape(s['residual_geometry']).geom_type=='MultiPolygon'
    assert s['assessment_complete'] is False
    assert 'slope' in s['missing_constraint_kinds']
    assert s['intersecting_supplied_constraints_acres']==pytest.approx(total*.5,rel=.001)


def test_no_layers_is_incomplete_not_clear():
    r=assess(mapping(box(-77,38,-76.99,38.01)),[])
    assert r['summary']['assessment_status']=='INCOMPLETE_UPPER_BOUND'
    assert len(r['summary']['missing_constraint_kinds'])==5


def test_terrain_has_mapped_exclusions_and_no_declared_extent():
    from permitting.land_sources import terrain
    def samples(url,params):
        points=json.loads(params['geometry'])['points']
        return {'samples':[{'location':{'x':x,'y':y},'value':(x+77)*100000} for x,y in points]}
    r=terrain(mapping(box(-77,38,-76.99,38.01)),15,samples)
    assert len(r['features']['features'])==100
    assert r['coverage_geometry'] is None
