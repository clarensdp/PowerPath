"""PowerPath v30.6 opt-in *point-only* official GIS lookup.

This module deliberately does not assert parcel coverage, environmental clearance,
local legal rules, or zoning authority. All network hosts and paths are constants;
user input is only validated WGS84 coordinates. Remote access can be disabled.

Run with explicit operator opt-in POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1 and explicit
end-user consent on each request. Raw coordinates leave the deployment and are
transmitted to the U.S. Census Bureau, FEMA and USFWS. No results are persisted.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from permitting.national import sha, resolve_state, resolve_county, county_catalog, NationalScreenError

VERSION = 'permitiq-official-point-gis-0.1'
MAX_RESPONSE_BYTES = 1_000_000
CENSUS = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates'
FEMA = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query'
NWI = 'https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services/Wetlands/MapServer/0/query'
SOURCES = {
    'census': {'publisher':'U.S. Census Bureau', 'url': CENSUS,
               'description':'Census GeoLookup coordinate geography; not a zoning determination'},
    'fema': {'publisher':'FEMA', 'url':FEMA,
             'description':'NFHL effective Flood Hazard Zones layer 28; point-only screening, incomplete spatial coverage possible'},
    'usfws_nwi': {'publisher':'USFWS', 'url':NWI,
                  'description':'NWI mapped wetlands, not a delineation or federal jurisdiction decision'},
}


def remote_enabled():
    return os.getenv('POWERPATH_PERMITIQ_REMOTE_OVERLAYS', '').lower() in ('1', 'true', 'yes')


def _read_json(url, params):
    """Fixed-source HTTPS GET; bounded response, timeout and no user-selected target."""
    request = Request(url + '?' + urlencode(params), headers={'User-Agent':'PowerPath-PermitIQ/30.6 (official-source-screening)',
                                                              'Accept':'application/json'})
    with urlopen(request, timeout=6) as stream:
        if stream.geturl().split('/')[2] != url.split('/')[2]:
            raise ValueError('Redirect to a different host rejected')
        payload = stream.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise ValueError('Official GIS response exceeded size limit')
    doc = json.loads(payload)
    if not isinstance(doc, dict):
        raise ValueError('Expected JSON object from official service')
    if doc.get('error'):
        raise ValueError('Official service returned an error')
    return doc


def _attrs(row):
    """Some ArcGIS services qualify field names with a table prefix."""
    obj = row.get('attributes') if isinstance(row,dict) else None
    return {str(k).split('.')[-1].upper(): v for k,v in obj.items()} if isinstance(obj,dict) else {}


def _arcgis(url,lat,lon,fields,fetch):
    doc=fetch(url, {'f':'json', 'geometry':f'{lon},{lat}', 'geometryType':'esriGeometryPoint',
                    'inSR':'4326','spatialRel':'esriSpatialRelIntersects','outFields':','.join(fields),
                    'returnGeometry':'false', 'resultRecordCount':'20', 'outSR':'4326', 'where':'1=1'})
    features=doc.get('features')
    if not isinstance(features,list):
        raise ValueError('Official GIS response lacks a feature array')
    if len(features)>20 or doc.get('exceededTransferLimit'):
        raise ValueError('Official GIS results truncated; cannot report the intersection')
    return [_attrs(f) for f in features]


def _source_result(source_id,status,*,features=None,detail=None):
    row={'source_id':source_id,'publisher':SOURCES[source_id]['publisher'], 'service_url':SOURCES[source_id]['url'],
         'status':status, 'intersection_type':'POINT_ONLY',
         'meaning':'No parcel boundary was supplied. A missing point feature does not clear the site.'}
    if features is not None:
        row['feature_count_at_point']=len(features)
        row['features']=features
    if detail is not None:row['note']=detail
    return row


def census_lookup(lat,lon,expected_state,fetch=_read_json):
    """Official coordinate lookup returns *candidate* county/municipality, never zoning authority."""
    try:
        data=fetch(CENSUS,{'x':f'{lon:.7f}','y':f'{lat:.7f}','benchmark':'Public_AR_Current',
                           'vintage':'Current_Current','format':'json'})
        geog=data.get('result',{}).get('geographies',{})
        if not isinstance(geog,dict):raise ValueError('Invalid census geographies object')
        def extract(term):
            matches=[]
            for name,items in geog.items():
                if term in name.lower() and isinstance(items,list):
                    for item in items[:5]:
                        if isinstance(item,dict):
                            matches.append({'geoid':item.get('GEOID'),'name':item.get('NAME'),
                                            'state_fips':item.get('STATE')})
            return matches
        counties=extract('counties')
        # Some Census geocoder versions use 'Counties' while some also show County Subdivisions.
        counties=[r for r in counties if isinstance(r['geoid'],str) and len(r['geoid'])==5]
        places=extract('incorporated places')
        if len(counties)!=1 or counties[0]['state_fips'] != expected_state['fips']:
            return _source_result('census','NO_UNAMBIGUOUS_MATCH',detail='No single county agreeing with local state geometry; review location.')
        known={x['geoid'] for x in county_catalog()[0].get(expected_state['fips'],[])}
        if counties[0]['geoid'] not in known:
            return _source_result('census','CONFLICT_REVIEW',detail='Geocoder county absent from bundled county reference catalog')
        polygon=resolve_county(lat,lon,expected_state['fips'])
        if polygon and counties[0]['geoid']!=polygon['geoid']:
            return _source_result('census','CONFLICT_REVIEW',detail='Official Census GeoLookup and imported county geometry disagree')
        return {**_source_result('census','MATCHED'), 'county':counties[0],
                'incorporated_place_candidates':places[:3], 'county_basis':'CENSUS_COORDINATE_LOOKUP',
                'jurisdiction_warning':'Census geographic place boundaries do not identify the legal zoning or utility authority.'}
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        return _source_result('census','UNAVAILABLE',detail='Official Census lookup failed; no county confirmation: '+type(exc).__name__)


def fema_lookup(lat,lon,fetch=_read_json):
    try:
        rows=_arcgis(FEMA,lat,lon,['FLD_ZONE','SFHA_TF','ZONE_SUBTY','FLD_AR_ID'],fetch)
        clean=[{k:r.get(k) for k in ['FLD_ZONE','SFHA_TF','ZONE_SUBTY','FLD_AR_ID'] if r.get(k) is not None} for r in rows]
        return {**_source_result('fema','MAPPED_INTERSECTION' if rows else 'NO_MAPPED_INTERSECTION_AT_POINT',features=clean),
                'caveat':'Mapped zone labels are not a flood risk determination. Confirm panel status, map changes and parcel footprint.'}
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        return _source_result('fema','UNAVAILABLE',detail='FEMA service not confirmed: '+type(exc).__name__)


def wetlands_lookup(lat,lon,fetch=_read_json):
    try:
        rows=_arcgis(NWI,lat,lon,['ATTRIBUTE','WETLAND_TYPE','ACRES'],fetch)
        clean=[{k:r.get(k) for k in ['ATTRIBUTE','WETLAND_TYPE','ACRES'] if r.get(k) is not None} for r in rows]
        return {**_source_result('usfws_nwi','MAPPED_INTERSECTION' if rows else 'NO_MAPPED_INTERSECTION_AT_POINT',features=clean),
                'caveat':'NWI records are not conclusive delineations. No mapped feature does not establish absence of jurisdictional waters.'}
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        return _source_result('usfws_nwi','UNAVAILABLE',detail='USFWS service not confirmed: '+type(exc).__name__)


def assess_official(lat,lon,*,consent=False,fetch=_read_json):
    """No persistence; caller and deployment operator must BOTH authorize transmission.

    The returned hash includes the entire source observations. It is a digest of
    evidence as received, not a reproducible guarantee that services won't change.
    """
    if not consent:
        raise NationalScreenError('Explicit consent required before sending site coordinates to official external services')
    if not remote_enabled():
        raise NationalScreenError('Remote GIS disabled by operator; enable POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1')
    state=resolve_state(lat,lon)
    if not state:
        raise NationalScreenError('Point outside 50 states + DC generalized state boundaries')
    geo=census_lookup(lat,lon,state,fetch)
    flood=fema_lookup(lat,lon,fetch)
    wetlands=wetlands_lookup(lat,lon,fetch)
    checked_at=datetime.now(timezone.utc).isoformat()
    evidence={'engine_version':VERSION,'point':{'latitude':lat,'longitude':lon},'state':state,
              'checked_at':checked_at, 'jurisdiction':geo,'environmental_layers':[flood,wetlands],
              'coverage':{'jurisdiction':'CENSUS_CANDIDATE_ONLY' if geo['status']=='MATCHED' else 'UNCONFIRMED',
                          'environmental':'POINT_LAYER_SCREENING_ONLY', 'parcel_footprint':'NOT_EVALUATED',
                          'zoning':'NOT_VERIFIED', 'permit_status':'NOT_VERIFIED','approval':'NOT_ESTABLISHED',
                          'no_all_clear':True},
              'next_diligence':['Verify boundaries and municipal/county zoning authority against current local GIS and legal sources',
                                'Screen the entire actual parcel and construction disturbance footprint',
                                'Confirm FEMA panel map status and perform site-specific flood diligence',
                                'Request qualified wetlands delineation and jurisdiction review when warranted'],
              'source_registry':SOURCES,'privacy':'Coordinates sent to Census, FEMA and USFWS. No results saved by PowerPath.'}
    evidence['evidence_sha256']=sha(evidence)
    return evidence
