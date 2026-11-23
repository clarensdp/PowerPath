"""Bounded public land screening; missing layers remain unknown, never clear."""
import json
import math
from datetime import datetime, timezone
from pyproj import Geod
from shapely.errors import GEOSException
from shapely.geometry import shape, box, mapping
from permitting.footprint_sources import SOURCES, _get_layer, _http_json, official_overlays

WATER='https://hydro.nationalmap.gov/arcgis/rest/services/3DHP_all/FeatureServer/60'
ELEVATION='https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer'
# Fixed USGS-hosted hydrography endpoint; no arbitrary user URLs.
PAD='https://services.arcgis.com/v01gqwM5QqNysAAi/arcgis/rest/services/PADUS_Protection_Status_by_GAP_Status_Code/FeatureServer/0'
SOURCES['protected_land']={'url':PAD+'/query','kind':'protected_land','name':'USGS PAD-US 4.1 · GAP status 1 and 2',
    'fields':'OBJECTID,Unit_Nm,GAP_Sts,Category,MngNm_Desc','where':"GAP_Sts IN ('1','2')"}
SOURCES['water']={'url':WATER+'/query','kind':'water','name':'USGS 3DHP waterbody polygons','fields':'id3dhp,featuretype,featuredate'}


def terrain(geometry, threshold=15, fetch=_http_json):
    """10x10 grid, finite-difference percent slope. Coarse estimate, not grading design."""
    g=shape(geometry);w,s,e,n=g.bounds
    size=10
    points=[[w+(e-w)*i/size,s+(n-s)*j/size] for j in range(size+1) for i in range(size+1)]
    samples=[]
    for start in range(0,len(points),25):
        batch=points[start:start+25]
        data=fetch(ELEVATION+'/getSamples',{'f':'json','geometryType':'esriGeometryMultipoint',
            'geometry':json.dumps({'points':batch,'spatialReference':{'wkid':4326}}),
            'returnFirstValueOnly':'true','interpolation':'RSP_BilinearInterpolation','outFields':'Name'})
        samples.extend(data.get('samples',[]))
    if len(samples)!=len(points):raise ValueError('Incomplete elevation sample grid')
    # Match returned coordinates; never assume sample ordering across raster items.
    values={}
    for sample in samples:
        loc=sample.get('location',{})
        key=(round(float(loc['x']),8),round(float(loc['y']),8))
        if key in values:raise ValueError('Ambiguous elevation samples')
        v=float(sample['value'])
        if not math.isfinite(v) or v < -500 or v > 9000:raise ValueError('Missing elevation')
        values[key]=v
    z=[values[(round(x,8),round(y,8))] for x,y in points]
    geod=Geod(ellps='WGS84');features=[];widths=[]
    for j in range(size):
        for i in range(size):
            x,y=points[j*(size+1)+i];xe,yn=points[(j+1)*(size+1)+i+1]
            dx=abs(geod.inv(x,y,xe,y)[2]);dy=abs(geod.inv(x,y,x,yn)[2]);widths.append(max(dx,dy))
            a=z[j*(size+1)+i];b=z[j*(size+1)+i+1];c=z[(j+1)*(size+1)+i];d=z[(j+1)*(size+1)+i+1]
            slope=100*math.hypot(((b-a)+(d-c))/(2*dx),((c-a)+(d-b))/(2*dy))
            if slope>threshold:
                features.append({'type':'Feature','geometry':mapping(box(x,y,xe,yn)), 'properties':{'slope_pct':round(slope,3),'threshold_pct':threshold}})
    return json.loads(json.dumps({'kind':'slope','source':{'title':f'USGS 3DEP sampled slope > {threshold}% (10×10 screening grid)',
        'url':ELEVATION,'retrieved_at':datetime.now(timezone.utc).isoformat(),
        'license':'USGS public data; coarse derived model, not a survey'},
        'features':{'type':'FeatureCollection','features':features},
        # Do not represent sparse samples as continuous verified coverage.
        'coverage_geometry':None,
        'sampling':{'source_tiles':sorted({str(sample.get('attributes',{}).get('Name','unknown')) for sample in samples}), 'grid_cells':100,'max_cell_width_m':max(widths),'threshold_pct':threshold,'status':'estimated'}}))


def fetch_layers(geometry, threshold=15, fetch=_http_json):
    layers,stats,warnings=official_overlays(geometry,consent=True,fetch=fetch)
    for key in ('water','slope','protected_land'):
        try:
            layer=terrain(geometry,threshold,fetch) if key=='slope' else _get_layer(key,geometry,fetch)[0]
            layers.append(layer);stats[key]={'status':'available','coverage':'UNCONFIRMED','sampling':layer.get('sampling')}
        except (ValueError,KeyError,TypeError,OSError,TimeoutError,GEOSException) as exc:
            stats[key]={'status':'unavailable','error_type':type(exc).__name__};warnings.append(f'{key} source unavailable; no clearance inferred')
    return layers,stats,warnings
