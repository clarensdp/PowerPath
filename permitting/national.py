"""v30.5 nationwide *screening*, distinct from v30.4's Loudoun assessment.

National coverage here means national state navigation and county reference lookup,
NOT nationwide parcel coverage, zoning rules or legal clearance.

This module is intentionally deterministic, offline and read-only. A missing value
is UNKNOWN, including when a trigger tests `false`. Existing v30.4 scheduling is
untouched, including its known assumptions and locality limitations.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path

from .engine import ENGINE_VERSION, load_jurisdiction

ROOT = Path(__file__).resolve().parent.parent
STATES_FILE = ROOT / 'data_sources' / 'us_states.geojson'
COUNTIES_FILE = ROOT / 'data_sources' / 'us_county_locations.json'
COUNTY_GEOMETRIES_FILE = ROOT / 'data_sources' / 'us_counties_500k.geojson'  # optional, not bundled
FEDERAL_RULES = Path(__file__).resolve().parent / 'data' / 'rules' / 'us-federal.json'
VA_RULES = Path(__file__).resolve().parent / 'data' / 'rules' / 'us-va.json'
LOUDOUN_RULES = Path(__file__).resolve().parent / 'data' / 'rules' / 'us-va-loudoun.json'
DOMINION_RULES = Path(__file__).resolve().parent / 'data' / 'rules' / 'utility-dominion-va.json'
SCHEMA_VERSION = 'permitiq-national-0.1'
STATES_51 = {'AL','AK','AZ','AR','CA','CO','CT','DE','DC','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA',
             'ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR',
             'PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY'}
FACT_MISSING = object()


class NationalScreenError(ValueError):
    pass


def sha(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@lru_cache(maxsize=1)
def state_geojson():
    data = json.loads(STATES_FILE.read_text())
    features = [{**f, 'properties': {**f['properties'],
                 'powerpath_state_rules': 'PARTIAL_RULE_PREVIEW' if f['properties']['STUSAB']=='VA' else 'UNMAPPED',
                 'powerpath_local_rules': 'UNMAPPED'}}
                for f in data['features'] if f['properties']['STUSAB'] in STATES_51]
    if len(features) != 51 or len({f['properties']['STUSAB'] for f in features}) != 51:
        raise NationalScreenError('National state catalog failed completeness check')
    return {'type': 'FeatureCollection', 'features': features, 'powerpath_source': data['powerpath_source'],
            'limitations': 'Generalized navigation boundaries. Near-border results and local permitting authority require confirmation.'}


@lru_cache(maxsize=1)
def county_catalog():
    data = json.loads(COUNTIES_FILE.read_text())
    by_state = {}
    for r in data['records']:
        st = r.get('STATE')
        if not st or not r.get('GEOID') or not r.get('NAME'):
            continue
        by_state.setdefault(st, []).append({'geoid': r['GEOID'], 'name': r['NAME'],
                                              'latitude': float(r['INTPTLAT']), 'longitude': float(r['INTPTLON'])})
    return by_state, data['powerpath_source']


def counties(state_fips, q='', limit=400):
    if len(q) > 90:
        raise NationalScreenError('Search term too long')
    features = state_geojson()['features']
    if state_fips not in {f['properties']['STATE'] for f in features}:
        raise NationalScreenError('Unknown state FIPS')
    candidates = county_catalog()[0].get(state_fips, [])
    text = q.strip().casefold()
    return {'state_fips': state_fips, 'counties': sorted((r for r in candidates if text in r['name'].casefold()),
                                                        key=lambda r: (r['name'], r['geoid']))[:limit],
            'source': county_catalog()[1],
            'disclaimer': 'County names and interior reference points are not county boundary polygons. Choosing one is an analyst assertion, not a GIS determination.'}


def _point_in_ring(lon, lat, ring):
    # Ray casting, with explicit boundary inclusion. Polygon is generalized, not cadastral-grade.
    inside = False
    for a, b in zip(ring, ring[1:]):
        x1, y1 = a[:2]; x2, y2 = b[:2]
        cross = (x2-x1)*(lat-y1) - (y2-y1)*(lon-x1)
        if abs(cross) < 1e-10 and min(x1,x2)-1e-10 <= lon <= max(x1,x2)+1e-10 and min(y1,y2)-1e-10 <= lat <= max(y1,y2)+1e-10:
            return True
        if (y1 > lat) != (y2 > lat):
            xcross = x1 + (x2-x1)*(lat-y1)/(y2-y1)
            if lon < xcross:
                inside = not inside
    return inside


def _inside_geometry(lon, lat, geom):
    polys = [geom['coordinates']] if geom['type'] == 'Polygon' else geom['coordinates']
    for poly in polys:
        if poly and _point_in_ring(lon, lat, poly[0]) and not any(_point_in_ring(lon, lat, ring) for ring in poly[1:]):
            return True
    return False


@lru_cache(maxsize=1)
def county_geometries():
    """Optional official Census county polygon import. No centroid-based assignment.

    Import with scripts/prepare_tiger_counties.py; missing data means unknown.
    """
    if not COUNTY_GEOMETRIES_FILE.exists():
        return None
    d = json.loads(COUNTY_GEOMETRIES_FILE.read_text())
    if d.get('type') != 'FeatureCollection' or not d.get('powerpath_source'):
        raise NationalScreenError('Unattributed county boundaries cannot be loaded')
    by_state={}
    for f in d['features']:
        p=f['properties']
        if p.get('STATE') and p.get('GEOID') and p['GEOID'].startswith(p['STATE']) and f['geometry']['type'] in ('Polygon','MultiPolygon'):
            by_state.setdefault(p['STATE'],[]).append(f)
    return by_state


def resolve_county(lat, lon, state_fips):
    """Only geometry evidence qualifies; catalog interior points are never treated as boundaries."""
    geometry=county_geometries()
    if geometry is None:
        return None
    found=[f['properties'] for f in geometry.get(state_fips,[]) if _inside_geometry(lon,lat,f['geometry'])]
    if len(found)!=1:return None
    return {'geoid':found[0]['GEOID'],'name':found[0]['NAME'], 'basis':'generalized_census_county_polygon'}


def _validate_point(lat, lon):
    if any(isinstance(x, bool) or not isinstance(x, (int,float)) or not math.isfinite(x) for x in (lat,lon)):
        raise NationalScreenError('Latitude and longitude must be finite numbers')
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise NationalScreenError('Coordinates outside WGS84 range')


def resolve_state(lat, lon):
    _validate_point(lat, lon)
    matches = [f['properties'] for f in state_geojson()['features'] if _inside_geometry(lon, lat, f['geometry'])]
    if len(matches) != 1:
        return None
    p = matches[0]
    return {'name': p['NAME'], 'abbr': p['STUSAB'], 'fips': p['STATE'], 'geoid': p['GEOID'],
            'basis': 'generalized_census_boundary', 'verified_local_boundary': False}


def _get(ctx, path):
    obj = ctx
    for key in path.split('.'):
        if not isinstance(obj, dict) or key not in obj or obj[key] is None:
            return FACT_MISSING
        obj = obj[key]
    return obj


def tri_evaluate(cond, ctx):
    """Return TRUE/FALSE/UNKNOWN and the unresolved leaf fact names."""
    if 'all' in cond or 'any' in cond:
        mode = 'all' if 'all' in cond else 'any'
        children = [tri_evaluate(c, ctx) for c in cond[mode]]
        if mode == 'all':
            if any(v == 'FALSE' for v, _ in children): return 'FALSE', []
            if all(v == 'TRUE' for v, _ in children): return 'TRUE', []
        else:
            if any(v == 'TRUE' for v, _ in children): return 'TRUE', []
            if all(v == 'FALSE' for v, _ in children): return 'FALSE', []
        return 'UNKNOWN', sorted({f for v, missing in children if v == 'UNKNOWN' for f in missing})
    path = cond['field']
    v = _get(ctx, path)
    if v is FACT_MISSING:
        return 'UNKNOWN', [path]
    op, ref = cond['op'], cond.get('value')
    if op in ('true','false'):
        if not isinstance(v, bool):
            return 'UNKNOWN', [path + ' (must be boolean)']
        return ('TRUE' if (v if op == 'true' else not v) else 'FALSE'), []
    try:
        if op == 'gt': test = v > ref
        elif op == 'ge': test = v >= ref
        elif op == 'lt': test = v < ref
        elif op == 'le': test = v <= ref
        elif op == 'eq': test = v == ref
        elif op == 'ne': test = v != ref
        elif op == 'in': test = v in (ref or [])
        else: raise NationalScreenError('Unknown operator ' + op)
    except (TypeError, ValueError):
        return 'UNKNOWN', [path + ' (invalid type)']
    return ('TRUE' if test else 'FALSE'), []


def _loudoun_derived(ctx):
    p = ctx.get('parcel', {})
    grandfathered = _get(ctx, 'parcel.grandfathered_by_right')
    distance = _get(ctx, 'parcel.residential_within_ft')
    if grandfathered is FACT_MISSING or (grandfathered is True and distance is FACT_MISSING):
        # Do not infer a legislative approval requirement from absent grandfathering evidence.
        return {'legislative_required': None, 'by_right_grandfathered': None}
    if not isinstance(grandfathered,bool):
        return {'legislative_required': None, 'by_right_grandfathered': None}
    result = bool(grandfathered and distance is not FACT_MISSING and isinstance(distance,(int,float)) and distance > 500)
    return {'legislative_required': not result, 'by_right_grandfathered': result}


def screen(lat, lon, *, county_geoid=None, facts=None, as_of=None, proposed=False):
    """Nationwide screening. Optional county is *user-asserted*, not coordinate-verified.

    No modeled statutory completeness or clearance is emitted. Rules are a deliberately
    incomplete preview: two federal rules, VA rules, and Loudoun/utility only for its
    exact user-selected county GEOID.
    """
    state = resolve_state(lat,lon)
    if not state:
        raise NationalScreenError('Point is outside available 50-state + DC generalized boundaries or on an ambiguous border')
    mapped_county=resolve_county(lat,lon,state['fips'])
    if county_geoid is not None:
        if not isinstance(county_geoid, str) or len(county_geoid) != 5 or not county_geoid.isdigit() or not county_geoid.startswith(state['fips']):
            raise NationalScreenError('County GEOID must be five digits and belong to the resolved state')
        selected = next((r for r in county_catalog()[0].get(state['fips'], []) if r['geoid']==county_geoid), None)
        if selected is None:
            raise NationalScreenError('County GEOID is not in the reference catalog for this state')
        if mapped_county and mapped_county['geoid']!=county_geoid:
            raise NationalScreenError('Selected county conflicts with imported Census county boundary; verify parcel location')
    else:
        selected = mapped_county
        county_geoid=mapped_county['geoid'] if mapped_county else None
    if facts is None: facts = {}
    if not isinstance(facts, dict) or not isinstance(facts.get('design',{}),dict) or not isinstance(facts.get('parcel',{}),dict):
        raise NationalScreenError('Facts must contain design/parcel objects')
    if as_of is None: as_of = date.today().isoformat()
    try: date.fromisoformat(as_of)
    except (ValueError,TypeError): raise NationalScreenError('as_of must be ISO date') from None
    is_loudoun = state['abbr']=='VA' and county_geoid=='51107'
    packages = [FEDERAL_RULES]
    if state['abbr']=='VA': packages.append(VA_RULES)
    if is_loudoun: packages += [DOMINION_RULES,LOUDOUN_RULES]
    ctx = {'design': facts.get('design',{}), 'parcel': facts.get('parcel',{}), '_derived': _loudoun_derived(facts) if is_loudoun else {}}
    rows=[]
    for package in packages:
        ruleset=json.loads(package.read_text())
        for rule in ruleset['rules']:
            outcome,missing=tri_evaluate(rule['trigger'],ctx)
            eff=rule.get('effective_from')
            if eff and as_of < eff:
                outcome='FALSE'; missing=[]
            authority=rule.get('authority') or 'Agency determination required'
            if rule['id']=='WETLANDS_404':
                authority='U.S. Army Corps of Engineers; Section 401 certifying authority varies by jurisdiction'
            row={'id':rule['id'], 'package':ruleset['jurisdiction']['id'], 'layer':ruleset['jurisdiction']['layer'],
                 'authority':authority,'finding':{'TRUE':'POTENTIALLY_REQUIRED','FALSE':'NOT_TRIGGERED','UNKNOWN':'POSSIBLE_VERIFY'}[outcome],
                 'missing_facts':missing, 'trigger':rule['trigger'], 'trigger_note':rule.get('trigger_note'),
                 'source_ids':rule.get('sources',[]), 'jurisdiction_confirmed':False,
                 'status':'unreviewed_rule_preview', 'duration_basis':(rule.get('duration') or {}).get('basis','prior')}
            if rule['id']=='WETLANDS_404':
                row['limitation']='Mapped wetlands or streams are not a jurisdictional delineation; a permit depends on activity and agency determination.'
            if rule['id']=='FAA_7460':
                row['limitation']='Simplified notice proxy; official FAA notice criteria require structure details and elevation analysis.'
            rows.append(row)
    unverified=['Confirm actual county/municipal zoning authority, zoning code and data-center use classification',
                'Check local moratoria, overlays, discretionary approvals and proposed ordinances',
                'Determine actual electrical service provider and utility large-load queue',
                'Obtain site-specific wetlands, flood, aviation and other environmental assessments',
                'Confirm local and state permits not covered by the preview rule packages']
    if not selected:
        unverified.insert(0, 'Identify the parcel’s county and any incorporated municipality using official boundary data')
    else:
        unverified.insert(0, 'Confirm municipal/tribal/federal land jurisdiction and any overlapping special districts; generalized county boundaries are not legal certification')
    if proposed:
        unverified.append('User requested proposed-policy scenario; no proposed law was promoted into baseline requirements')
    known = sum(1 for r in rows if r['finding']=='POTENTIALLY_REQUIRED')
    unknown = sum(1 for r in rows if r['finding']=='POSSIBLE_VERIFY')
    snapshot={'version':SCHEMA_VERSION,'as_of':as_of,'point':{'latitude':lat,'longitude':lon},
              'state':state,'county_geoid':county_geoid,'facts':facts,'proposed_scenario':proposed,
              'rules_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in packages},
              'states_sha256':hashlib.sha256(STATES_FILE.read_bytes()).hexdigest(),
              'counties_reference_sha256':hashlib.sha256(COUNTIES_FILE.read_bytes()).hexdigest(),
              'county_geometry_sha256':hashlib.sha256(COUNTY_GEOMETRIES_FILE.read_bytes()).hexdigest() if COUNTY_GEOMETRIES_FILE.exists() else None}
    return {'assessment_type':'national_screening_preview','engine_version':SCHEMA_VERSION,
            'prior_permitting_engine_version':ENGINE_VERSION,'snapshot_sha256':sha(snapshot),'as_of':as_of,
            'site':{'point':snapshot['point'],'state':state,
                    'county':({'geoid':selected['geoid'],'name':selected['name'], 'basis':('generalized_census_county_polygon' if mapped_county else 'user_selected_unverified')} if selected else None)},
            'coverage':{'geography':'STATE_NAVIGATION_ONLY','parcel':'NOT_ASSESSED','county_boundary':'GENERALIZED_CENSUS_POLYGON' if mapped_county else 'UNVERIFIED',
                        'state_rules':'PARTIAL_RULE_PREVIEW' if state['abbr']=='VA' else 'UNMAPPED',
                        'local_rules':'LOUDOUN_ALPHA_PREVIEW' if is_loudoun else 'UNMAPPED',
                        'utility':'USER_CONFIRMATION_REQUIRED','schedule':'NOT_CALIBRATED',
                        'classification':'SCREENING' if is_loudoun else 'INCOMPLETE',
                        'no_all_clear':True},
            'findings':{'potentially_required':known,'verify':unknown,'preview_rule_count':len(rows)},
            'rules':rows,'next_diligence':unverified,
            'policy_scenario':{'proposed_enabled':proposed,'applied_to_baseline':False},
            'warnings':['This is not a complete permit list or legal opinion; a NOT_TRIGGERED preview is not regulatory clearance.',
                        'No parcel geometry, ordinance verification, utility capacity or approval date is established by this screening.',
                        'County centroids are not service areas or permitting boundaries.',
                        'Legacy Loudoun P50/P90 forecasts are not applied to national screening.']}


def coverage(lat,lon, county_geoid=None):
    result=screen(lat,lon,county_geoid=county_geoid)
    return {k:result[k] for k in ('assessment_type','as_of','site','coverage','next_diligence','warnings','snapshot_sha256')}
