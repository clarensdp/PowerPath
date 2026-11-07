"""Read-only parcel FOOTPRINT intersections, not a permitting or buildability decision.

All geometries are WGS84 GeoJSON, analyzed with a local equal-area projection.
User-provided zoning/constraint layers are evidence inputs, not independently verified maps.
No overlap is not clearance, particularly when layer coverage is unknown.
"""
from __future__ import annotations
import hashlib
import json
import math
from datetime import datetime, timezone

from pyproj import CRS, Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union

VERSION = 'permitiq-footprint-0.1'
ACRE_M2 = 4046.8564224
MAX_POLY_VERTICES = 12000
MAX_FEATURES = 250
VALID_KINDS = {'flood','wetlands','zoning','protected_land','setback','easement','other'}

class FootprintError(ValueError):
    pass


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def _all_coords(obj):
    if isinstance(obj,(list,tuple)):
        if len(obj)>=2 and all(isinstance(x,(int,float)) and not isinstance(x,bool) for x in obj[:2]):
            yield obj
        else:
            for x in obj:
                yield from _all_coords(x)


def read_geom(g, label):
    if not isinstance(g,dict) or g.get('type') not in ('Polygon','MultiPolygon'):
        raise FootprintError(f'{label} must be a GeoJSON Polygon or MultiPolygon')
    polygons=[g.get('coordinates')] if g['type']=='Polygon' else g.get('coordinates')
    if not isinstance(polygons,list) or not polygons:raise FootprintError(f'{label}: empty polygon collection')
    for polygon in polygons:
        if not isinstance(polygon,list) or not polygon:raise FootprintError(f'{label}: missing rings')
        for ring in polygon:
            if not isinstance(ring,list) or len(ring)<4 or ring[0]!=ring[-1]:
                raise FootprintError(f'{label}: polygon rings must be explicitly closed')
    coords=list(_all_coords(g.get('coordinates')))
    if not 4 <= len(coords) <= MAX_POLY_VERTICES:
        raise FootprintError(f'{label} has invalid or excessive vertex count')
    for coord in coords:
        if len(coord)!=2 or not all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in coord):
            raise FootprintError(f'{label}: only 2D finite WGS84 coordinates are accepted')
        if not(-180<=coord[0]<=180 and -90<=coord[1]<=90):
            raise FootprintError(f'{label}: coordinate outside WGS84 range')
    try:
        poly=shape(g)
    except (ValueError,TypeError,KeyError,IndexError) as exc:
        raise FootprintError(f'{label}: malformed polygon') from exc
    if poly.is_empty or not poly.is_valid or poly.area<=0:
        raise FootprintError(f'{label}: invalid, self-intersecting or empty polygon; repair at source')
    if poly.bounds[2]-poly.bounds[0]>2 or poly.bounds[3]-poly.bounds[1]>2:
        raise FootprintError(f'{label}: geometry exceeds 2-degree local-area analysis limit')
    return poly


def _layer(doc, index):
    if not isinstance(doc,dict): raise FootprintError('Each layer requires metadata and a feature collection')
    kind=doc.get('kind')
    if kind not in VALID_KINDS:raise FootprintError(f'Layer {index}: unsupported kind')
    source=doc.get('source')
    if not isinstance(source,dict) or not (isinstance(source.get('title'),str) and source['title'].strip()):
        raise FootprintError(f'Layer {index}: source.title is required')
    for name in ('title','url','published_at','retrieved_at','license'):
        if name in source and (not isinstance(source[name],str) or len(source[name])>500):
            raise FootprintError(f'Layer {index}: invalid source {name}')
    features=doc.get('features')
    if not isinstance(features,dict) or features.get('type')!='FeatureCollection' or not isinstance(features.get('features'),list):
        raise FootprintError(f'Layer {index}: features must be a FeatureCollection')
    if len(features['features'])>MAX_FEATURES:raise FootprintError(f'Layer {index}: more than {MAX_FEATURES} features')
    clean=[]
    for i,item in enumerate(features['features']):
        if not isinstance(item,dict) or item.get('type')!='Feature':raise FootprintError('Each feature must be a GeoJSON Feature')
        geom=read_geom(item.get('geometry'),f'Layer {index} feature {i}')
        props=item.get('properties') or {}
        if not isinstance(props,dict):raise FootprintError('Feature properties must be an object')
        clean.append((geom,{str(k)[:80]:str(v)[:300] for k,v in list(props.items())[:20]}))
    coverage=read_geom(doc['coverage_geometry'],f'Layer {index} coverage') if doc.get('coverage_geometry') else None
    return kind,source,clean,coverage


def assess(parcel_geojson, layers, *, parcel_source=None):
    """Intersect each full parcel with data supplied as polygons (never centroids).

    `coverage_geometry` is a *declared* mapped extent; no false clearance when absent.
    Categories union overlaps to avoid double counting; different categories can overlap.
    """
    parcel=read_geom(parcel_geojson,'Parcel')
    if not isinstance(layers,list) or len(layers)>12:raise FootprintError('Maximum 12 overlay layers')
    west,south,east,north=parcel.bounds
    mid=parcel.representative_point()
    # Local Lambert azimuthal equal-area: preserve area, including holes, at site scale.
    if abs(mid.y)>89:raise FootprintError('Polar locations require a specialist projection')
    crs=CRS.from_proj4(f'+proj=laea +lat_0={mid.y:.10f} +lon_0={mid.x:.10f} +datum=WGS84 +units=m +no_defs')
    project=Transformer.from_crs('EPSG:4326',crs,always_xy=True).transform
    inverse=Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform
    p=transform(project,parcel)
    pa=p.area/ACRE_M2
    if pa<=0 or pa>1000000:raise FootprintError('Parcel area outside supported local screening limit')
    total_hazards=[];reported=[];zoning_seen=[];hazard_coverage={k:[] for k in ('flood','wetlands')}
    for idx,layer in enumerate(layers):
        kind,source,features,extent=_layer(layer,idx)
        pcs=[];hits=[]
        for g,props in features:
            if not g.intersects(parcel):continue
            intersection=transform(project,g).intersection(p)
            if intersection.is_empty or intersection.area<=0:continue
            pcs.append(intersection)
            hits.append({'properties':props,'intersection_acres':round(intersection.area/ACRE_M2,5)})
        union=unary_union(pcs) if pcs else None
        acres=min(pa,union.area/ACRE_M2) if union is not None else 0.0
        mapped_area=0.0
        if extent is not None:
            projected_extent=transform(project,extent)
            mapped_area=min(pa,projected_extent.intersection(p).area/ACRE_M2)
        complete=extent is not None and mapped_area >= pa-1e-8*max(pa,1)
        status='FULL_EXTENT_DECLARED' if complete else 'PARTIAL_EXTENT_DECLARED' if extent is not None else 'EXTENT_UNKNOWN'
        item={'kind':kind,'source':source,'coverage_status':status,'mapped_extent_acres':round(mapped_area,5) if extent is not None else None,
              'polygon_count':len(features),'intersecting_features':len(hits),
              'intersection_acres':round(acres,5),'intersection_pct':round(100*acres/pa,3),
              'intersection_geometry':mapping(transform(inverse,union)) if union is not None else None,
              'no_intersection_meaning':'NO_MAPPED_FEATURE_IN_SUPPLIED_DATA; NOT CLEARANCE' if not hits else None,
              'features':hits[:40], 'features_truncated':len(hits)>40,
              'source_verification':'OPERATOR_DECLARED_NOT_INDEPENDENTLY_VERIFIED'}
        if kind=='zoning':
            item['zoning_authority_verified']=False
            zoning_seen.append(item)
        if kind in hazard_coverage:hazard_coverage[kind].append(complete)
        if kind in ('flood','wetlands','protected_land','setback','easement','other') and union is not None:total_hazards.append(union)
        reported.append(item)
    # This is exclusively a geometric residual against the *supplied* layers;
    # missing overlays or permit constraints make it nonbuildable-eligibility evidence.
    covered_hazards=all(hazard_coverage[k] and all(hazard_coverage[k]) for k in hazard_coverage)
    combination=unary_union(total_hazards) if total_hazards else None
    constraint_area=min(pa,combination.area/ACRE_M2) if combination is not None else 0.0
    measured={'intersecting_supplied_constraints_acres':round(constraint_area,5),
              'no_mapped_overlap_acres':round(max(0,pa-constraint_area),5),
              'no_mapped_overlap_is_buildable':False,
              'complete_flood_wetlands_extent_declared':covered_hazards,
              'certified_buildable_acres':None}
    warnings=['A parcel boundary is not a surveyed, title-verified or legally buildable boundary.',
              'No mapped overlap is not a determination of developability or permit eligibility.',
              'All zoning classifications and constraint layers supplied by operators require official-source verification.']
    if not covered_hazards:warnings.append('Flood and/or wetlands mapped extent is incomplete or unverified; negative findings cannot be treated as clear.')
    if not zoning_seen:warnings.append('Municipal zoning has not been supplied; jurisdictional zoning/use approval is UNKNOWN.')
    elif not all(v['coverage_status']=='FULL_EXTENT_DECLARED' for v in zoning_seen):warnings.append('Zoning coverage does not encompass the full parcel or its mapped extent is unknown.')
    evidence={'engine':VERSION,'parcel_geometry':parcel_geojson,'parcel_source':parcel_source or {'title':'Operator supplied / not verified'},
              'layers':layers}
    return {'engine_version':VERSION,'basis':'FULL_POLYGON_INTERSECTION','parcel':{'area_acres':round(pa,5),
            'bounding_box':[round(v,7) for v in (west,south,east,north)],'geometry_sha256':digest(parcel_geojson),
            'source':parcel_source or {'title':'Operator supplied / not verified'},'geometry':parcel_geojson,'area_method':'LOCAL_LAMBERT_AZIMUTHAL_EQUAL_AREA_WGS84'},
            'layers':reported,'summary':measured,'coverage':{'flood':'DECLARED_COMPLETE' if hazard_coverage['flood'] and all(hazard_coverage['flood']) else 'UNKNOWN',
            'wetlands':'DECLARED_COMPLETE' if hazard_coverage['wetlands'] and all(hazard_coverage['wetlands']) else 'UNKNOWN',
            'zoning':'DECLARED_COMPLETE_UNVERIFIED' if zoning_seen and all(z['coverage_status']=='FULL_EXTENT_DECLARED' for z in zoning_seen) else 'UNKNOWN',
            'overall':'SCREENING_NOT_CLEARED'},'warnings':warnings,'next_diligence':[
            'Verify parcel boundary against official local cadastre and a survey.',
            'Obtain jurisdiction-specific zoning polygons, zoning ordinance and official permitted-use determination.',
            'Verify FEMA NFHL effective coverage/panels and USFWS wetlands mapping status across the entire site.',
            'Commission floodplain/wetlands and site-specific engineering studies where appropriate.',
            'Review easements, setbacks, grading, floodplain regulations and utility access before assigning buildable acreage.'],
            'snapshot_sha256':digest(evidence), 'persisted':False, 'financial_engine_modified':False}
