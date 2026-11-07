"""Regrid adapter. Evaluation only until licensed retention/export rights are confirmed.
Reference: https://support.regrid.com/docs/search-parcels
"""
import json, math, os, re, urllib.parse, urllib.request, urllib.error
from collections import Counter
from datetime import datetime, timezone
from server.geo29 import geometry_bounds, STATE_FIPS

SOURCE_URL = 'https://app.regrid.com/store/samples'
API_URL = 'https://app.regrid.com/api/v2/parcels/point'


def collection_from(payload):
    collection = payload.get('parcels', payload) if isinstance(payload, dict) else None
    if not isinstance(collection, dict) or collection.get('type') != 'FeatureCollection' or not isinstance(collection.get('features'), list):
        raise ValueError('Expected a GeoJSON FeatureCollection or Regrid parcels envelope')
    crs = collection.get('crs')
    if crs and crs.get('properties', {}).get('name') not in ('urn:ogc:def:crs:OGC:1.3:CRS84', 'EPSG:4326', 'urn:ogc:def:crs:EPSG::4326'):
        raise ValueError('Reproject to WGS84 before importing')
    return collection


def number(value):
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValueError('Boolean acreage is invalid')
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError('Area must be finite and nonnegative')
    return value


def normalize(payload):
    """Normalize both bulk fields and nested API properties.fields without guessing IDs."""
    coll = collection_from(payload)
    if len(coll['features']) > 100000:
        raise ValueError('Pilot importer supports at most 100,000 records per complete snapshot')
    features, seen = [], set()
    for index, f in enumerate(coll['features']):
        try:
            p = f['properties']
            fields = p.get('fields', p)
            geoid = str(fields.get('geoid', ''))
            if not re.fullmatch(r'\d{5}', geoid) or geoid[:2] not in STATE_FIPS:
                raise ValueError('Missing or unsupported five-digit county FIPS')
            uuid = str(fields.get('ll_uuid') or p.get('ll_uuid') or '').lower()
            if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', uuid):
                raise ValueError('Missing stable Regrid UUID')
            key = (geoid, uuid)
            if key in seen:
                raise ValueError('Duplicate stable parcel ID')
            seen.add(key)
            geometry_bounds(f['geometry'])
            sqft = number(fields.get('ll_gissqft'))
            basis = 'provider_computed_geometry'
            if sqft is None:
                acre = number(fields.get('ll_gisacre'))
                sqft = None if acre is None else acre * 43560
            if sqft is None:
                basis = 'unknown'
            # Keep only required screening fields; never map vendor search/quality scores to feasibility.
            props = {'provider_id': uuid, 'parcelnumb': fields.get('parcelnumb'), 'geoid': geoid,
                     'area_sqft': sqft, 'area_basis': basis, 'provider': 'regrid',
                     'provider_refresh_date': fields.get('ll_last_refresh'),
                     'provider_updated_at': fields.get('ll_updated_at')}
            features.append({'type': 'Feature', 'properties': props, 'geometry': f['geometry']})
        except (ValueError, TypeError, KeyError, AttributeError, IndexError) as exc:
            raise ValueError(f'Record {index}: invalid identity, geometry or area ({exc})') from None
    return {'type': 'FeatureCollection', 'features': features}


def summarize(collection):
    fs = collection['features']
    dates = sorted({str(f['properties']['provider_refresh_date']) for f in fs if f['properties'].get('provider_refresh_date')})
    return {'records': len(fs), 'counties': dict(Counter(f['properties']['geoid'] for f in fs)),
            'geometry_types': dict(Counter(f['geometry']['type'] for f in fs)),
            'area_present': sum(f['properties']['area_sqft'] is not None for f in fs),
            'refresh_date_present': sum(bool(f['properties'].get('provider_refresh_date')) for f in fs),
            'provider_refresh_dates': dates, 'area_basis': 'provider-computed geometry; not deeded/buildable acreage',
            'power_availability': 'not assessed', 'feasibility_scores_created': 0}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def fetch_point(lat, lon, limit=1, count_only=False, transport=None):
    """One bounded operator request, no automatic pagination/retries or token logging."""
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lon)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Invalid WGS84 coordinates')
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError('Pilot limit must be 1–25 records')
    token = os.environ.get('POWERPATH_REGRID_TOKEN', '').strip()
    if not token:
        raise ValueError('Set POWERPATH_REGRID_TOKEN in the local server environment; do not place it in source files')
    params = {'lat': lat, 'lon': lon, 'limit': limit, 'token': token,
              'return_matched_buildings': 'false', 'return_matched_addresses': 'false',
              'return_enhanced_ownership': 'false', 'return_zoning': 'false'}
    if count_only:
        params['return_count'] = 'true'
    request = urllib.request.Request(API_URL+'?'+urllib.parse.urlencode(params), headers={'Accept': 'application/json'})
    opener = transport or urllib.request.build_opener(NoRedirect()).open
    try:
        with opener(request, timeout=20) as response:
            raw = response.read(8*1024*1024+1)
        if len(raw) > 8*1024*1024:
            raise ValueError('Provider response exceeded pilot size limit')
        payload = json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Regrid HTTP {exc.code}; no automatic retry. Check account access or usage limits.') from None
    except Exception:
        # URL-bearing exceptions can expose query-string tokens.
        raise RuntimeError('Regrid request failed; no automatic retry and no response stored.') from None
    if count_only:
        count = payload.get('count') if isinstance(payload, dict) else None
        if type(count) is not int or count < 0:
            raise ValueError('Unexpected provider count response')
        return {'count': count}
    normalized = normalize(payload)
    if len(normalized['features']) > limit:
        raise ValueError('Provider returned more records than requested; nothing imported')
    return normalized


def import_snapshot(store, collection, metadata):
    """One complete county snapshot; caller supplies documented rights, not a self-serve assumption."""
    required = ('license_reference', 'retention_authorized', 'application_display_authorized', 'export_authorized')
    if not metadata.get('license_reference') or any(metadata.get(k) is not True for k in required[1:]):
        raise ValueError('This workspace retains and exports geometry. Record confirmed retention, application-display and export rights before importing licensed data.')
    fs = collection['features']
    counties = {f['properties']['geoid'] for f in fs}
    if len(counties) != 1:
        raise ValueError('Import exactly one county snapshot at a time')
    geoid = next(iter(counties))
    if metadata.get('county_fips') != geoid:
        raise ValueError('Source county does not match all records')
    if metadata.get('complete_snapshot') is not True:
        raise ValueError('Only a declared complete source snapshot can replace active coverage; API pages are not snapshots')
    source = {'id': 'regrid-'+geoid, 'name': 'Regrid county snapshot '+geoid,
              'state_fips': geoid[:2], 'county_fips': geoid[2:],
              'source_url': metadata['source_url'], 'retrieved_at': metadata['retrieved_at'],
              'coverage_scope': metadata['coverage_scope'], 'license_note': metadata['license_reference'],
              'provenance': 'licensed_provider_snapshot', 'license_reference': metadata['license_reference']}
    return store.ingest(source, collection, 'provider_id', 'area_sqft')
