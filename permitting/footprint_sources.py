"""Opt-in official polygon evidence retrieval (FEMA NFHL and USFWS NWI).

The official services are queried over the entire parcel BBOX and all returned
polygons are clipped locally to the *actual* parcel polygon. Never infer a
complete negative finding from no service features: official coverage masks
are not supplied. A failure cannot be converted to an empty result.
"""
from __future__ import annotations
from shapely.errors import GEOSException
import json
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from permitting.official_gis import FEMA,NWI,remote_enabled
from permitting.footprint import FootprintError,read_geom

MAX_REMOTE_IDS=200
MAX_BYTES=10_000_000
SOURCES={
 'fema':{'url':FEMA,'kind':'flood','name':'FEMA NFHL · Special Flood Hazard Areas',
         'generalize':0.00001,'fields':'FLD_ZONE,SFHA_TF,ZONE_SUBTY,FLD_AR_ID'},
 'nwi':{'url':NWI,'kind':'wetlands','name':'USFWS · National Wetlands Inventory',
        'generalize':0.00001,'fields':'ATTRIBUTE,WETLAND_TYPE,ACRES'}
}

def _http_json(url,params):
    target=url+'?'+urlencode(params)
    request=Request(target,headers={'User-Agent':'PowerPath/30.7.1 parcel-screening','Accept':'application/json'})
    with urlopen(request,timeout=12) as response:
        if response.geturl().split('/')[2]!=url.split('/')[2]:raise ValueError('Unexpected redirect host')
        body=response.read(MAX_BYTES+1)
    if len(body)>MAX_BYTES:raise ValueError('Official GIS response too large')
    result=json.loads(body)
    if not isinstance(result,dict) or result.get('error'):raise ValueError('Official GIS service error')
    return result


def _drop_z(geometry):
    # Some official polygon services advertise 3D geometries; source altitude
    # has no role in a 2D flood/wetlands footprint overlay.
    def walk(value):
        if isinstance(value,(list,tuple)) and len(value)>=2 and all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in value[:2]):
            return list(value[:2])
        return [walk(x) for x in value]
    return {**geometry,'coordinates':walk(geometry['coordinates'])}

def _get_layer(name,geom,fetch):
    spec=SOURCES[name]
    read_geom(geom,'Official query footprint')
    from shapely.geometry import box, mapping, shape
    west,south,east,north=shape(geom).bounds
    bounds=','.join(map(str,(west,south,east,north)))
    search={'where':spec.get('where','1=1'),'geometry':bounds,'geometryType':'esriGeometryEnvelope',
            'inSR':'4326','spatialRel':'esriSpatialRelIntersects','returnIdsOnly':'true','f':'json'}
    first=fetch(spec['url'],search)
    ids=first.get('objectIds')
    if ids is None:
        count_query={k:v for k,v in search.items() if k!='returnIdsOnly'}
        count=fetch(spec['url'],{**count_query,'returnCountOnly':'true'}).get('count')
        if type(count) is int and count==0:
            ids=[]
    if not isinstance(ids,list) or any(not isinstance(i,int) or isinstance(i,bool) for i in ids):
        raise ValueError('No complete object-ID index from official GIS service')
    if len(ids)>MAX_REMOTE_IDS or len(ids)!=len(set(ids)):
        raise ValueError('Official GIS feature count exceeds safe bounded request; subdivide parcel')
    features=[]
    # Restrict enormous source polygons before footprint validation. The padded
    # envelope keeps source clipping well outside the site boundary.
    clip=box(west-.001,south-.001,east+.001,north+.001)
    for off in range(0,len(ids),50):
        params={'f':'geojson','objectIds':','.join(map(str,ids[off:off+50])),
                'outFields':spec['fields'],'returnGeometry':'true','outSR':'4326'}
        if spec.get('generalize'):
            params['maxAllowableOffset']=spec['generalize']
        page=fetch(spec['url'],params)
        rows=page.get('features')
        if page.get('type')!='FeatureCollection' or not isinstance(rows,list) or len(rows)!=len(ids[off:off+50]):
            raise ValueError('Official GIS geometry page incomplete, mismatched or unsupported')
        if page.get('exceededTransferLimit'):raise ValueError('Official GIS result truncated')
        for f in rows:
            if not isinstance(f,dict) or f.get('type')!='Feature':raise ValueError('Invalid official GIS feature')
            f={**f,'geometry':_drop_z(f['geometry'])}
            if name=='fema':
                p=f.get('properties') or {}
                sfha=next((v for k,v in p.items() if str(k).split('.')[-1].upper()=='SFHA_TF'),None)
                # Only special flood hazard area polygons; other NFHL zone types are
                # not represented as SFHA. This is NOT full flood risk clearance.
                if str(sfha or '').strip().upper() not in ('T','TRUE','1','Y','YES'):
                    continue
            raw_geometry=shape(f['geometry'])
            if not clip.covers(raw_geometry):
                if not raw_geometry.is_valid:
                    raise ValueError('Invalid upstream polygon cannot be clipped safely')
                clipped=raw_geometry.intersection(clip)
                if clipped.is_empty or clipped.area<=0:
                    continue
                if clipped.geom_type=='GeometryCollection':
                    from shapely.ops import unary_union
                    clipped=unary_union([g for g in clipped.geoms if g.geom_type in ('Polygon','MultiPolygon')])
                f['geometry']=json.loads(json.dumps(mapping(clipped)))
            read_geom(f['geometry'],'Official GIS feature')
            features.append(f)
    now=datetime.now(timezone.utc).isoformat()
    return {'kind':spec['kind'],'source':{'title':spec['name'],'url':spec['url'],
        'retrieved_at':now,'license':'Official agency public GIS · source caveats apply'},
        'query_generalization_degrees':spec.get('generalize'),
        'features':{'type':'FeatureCollection','features':features},
        # Neither service returns a nationwide complete-coverage extent here.
        # No official feature ≠ zero hazards across the site.
        'coverage_geometry':None},len(ids)


def official_overlays(geom,*,consent=False,fetch=_http_json):
    if not consent or not remote_enabled():
        raise FootprintError('Official polygon lookups require operator enablement and explicit user consent')
    results=[];warnings=[];stats={}
    for name in ('fema','nwi'):
        try:
            layer,count=_get_layer(name,geom,fetch)
            results.append(layer)
            stats[name]={'status':'FEATURES_RETRIEVED','returned_candidates':count,
                         'selected_features':len(layer['features']['features']),
                         'extent':'UNCONFIRMED', 'live_test_status':'REQUIRES_NETWORK_VERIFICATION'}
        except (ValueError,KeyError,TypeError,OSError,TimeoutError,FootprintError,GEOSException) as exc:
            # Do not manufacture empty features on errors.
            stats[name]={'status':'UNAVAILABLE','error_type':type(exc).__name__,'extent':'UNCONFIRMED'}
            warnings.append(f'{name.upper()} polygon service unavailable; no clearance conclusion permitted.')
    return results,stats,warnings
