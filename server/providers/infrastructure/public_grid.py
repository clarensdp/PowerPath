"""Public mapped infrastructure; distance never represents electrical availability."""
import json
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

from pyproj import CRS, Transformer
from shapely.geometry import shape, Point
from shapely.ops import transform
from server.providers.base import ProviderError, ProviderResult, number, unavailable

LINES = 'https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/US_Electric_Power_Transmission_Lines/FeatureServer/0'
NAME = 'US electric transmission lines (federal FWS-hosted HIFLD-derived layer)'


def projection(lat, lon):
    return Transformer.from_crs('EPSG:4326', CRS.from_proj4(
        f'+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m'), always_xy=True).transform


def distance_km(parcel_geometry, asset_geometry):
    parcel, asset = shape(parcel_geometry), shape(asset_geometry)
    point = parcel.representative_point()
    project = projection(point.y, point.x)
    return transform(project, parcel).distance(transform(project, asset)) / 1000


def valid_geometry(geometry):
    if not isinstance(geometry, dict):
        raise ValueError('Missing GIS geometry')
    obj = shape(geometry)
    if obj.is_empty or not obj.is_valid:
        raise ValueError('Invalid GIS geometry')
    w, s, e, n = obj.bounds
    if not (-180 <= w <= e <= 180 and -90 <= s <= n <= 90):
        raise ValueError('Coordinates must be WGS84 longitude/latitude')
    return obj


def source_date(value):
    n = number(value)
    if n is not None and n > 0:
        try:
            return datetime.fromtimestamp(n / 1000, timezone.utc).isoformat()
        except (OverflowError, ValueError, OSError):
            pass
    return None


def normalize(payload, parcel, ts, url=LINES, name=NAME, kind='transmission_line', radius=20, cached=False):
    if payload.get('type') != 'FeatureCollection' or not isinstance(payload.get('features'), list):
        raise ProviderError('GIS service did not return GeoJSON')
    features, rejected = [], 0
    valid_geometry(parcel)
    for feature in payload['features']:
        try:
            geometry, props = feature['geometry'], feature['properties']
            obj = valid_geometry(geometry)
            if kind == 'transmission_line' and obj.geom_type not in ('LineString', 'MultiLineString'):
                raise ValueError('Expected line geometry')
            if kind == 'service_territory' and obj.geom_type not in ('Polygon', 'MultiPolygon'):
                raise ValueError('Expected polygon geometry')
            if kind == 'substation' and obj.geom_type not in ('Point', 'Polygon', 'MultiPolygon'):
                raise ValueError('Expected station geometry')
            distance = distance_km(parcel, geometry)
            if distance > radius or (kind == 'service_territory' and not obj.intersects(shape(parcel))):
                continue
            identity = props.get('ID') or props.get('OBJECTID_1') or props.get('OBJECTID') or feature.get('id')
            if identity is None:
                raise ValueError('Source feature has no identifier')
            voltage = number(props.get('VOLTAGE'))
            features.append({'type': 'Feature', 'id': str(identity), 'geometry': geometry, 'properties': {
                'source_id': str(identity), 'kind': kind,
                'name': str(props.get('NAME') or props.get('OWNER') or f'{kind} {identity}'),
                'owner': props.get('OWNER'), 'voltage_kv': voltage if voltage is not None and voltage > 0 else None,
                'distance_km': round(distance, 3), 'distance_status': 'estimated',
                'distance_methodology': 'Shortest parcel-boundary/footprint to mapped geometry distance in local WGS84 azimuthal equidistant projection; km. Not a connection route.',
                'source_name': name, 'source_url': url, 'retrieved_at': ts,
                'effective_date': source_date(props.get('SOURCEDATE')), 'status': 'observed',
                'available_capacity_mw': None, 'energization_date': None, 'connection_cost_usd': None,
                'availability_status': 'unavailable', 'source_attributes': props}})
        except (ValueError, KeyError, TypeError):
            rejected += 1
    features.sort(key=lambda f: f['properties']['distance_km'])
    truncated = bool(payload.get('exceededTransferLimit')) or len(payload['features']) >= 200
    return ProviderResult(provider=name, source_url=url, retrieved_at=ts, cached=cached,
        status='partial' if rejected or truncated else 'available', features=features,
        warnings=['Public mapped inventory only; no capacity, cost, service commitment or energization date is inferred.',
                  'Territory intersections are screening candidates, not confirmation of service to the entire parcel.'] +
                 ([f'{rejected} invalid source geometries/identifiers omitted'] if rejected else []) +
                 (['Results capped at 200 features; inventory is incomplete'] if truncated else [])).model_dump()


def configured_layer(variable):
    url = os.environ.get(variable, '').strip().rstrip('/')
    if not url:
        return None
    # Administrator configuration only, never a request parameter. Restrict to public
    # official GIS / ArcGIS hosts and layer paths; do not accept arbitrary URLs.
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.port not in (None, 443) or not parsed.hostname
            or not parsed.hostname.endswith(('.gov', '.arcgis.com'))
            or not parsed.path.rsplit('/', 1)[-1].isdigit()):
        raise ProviderError(f'{variable} must be a public HTTPS .gov/ArcGIS layer URL')
    return url


def fetch(http, project_id, parcel, kind='transmission_line'):
    url, name = LINES, NAME
    if kind != 'transmission_line':
        env = 'POWERPATH_TERRITORY_LAYER_URL' if kind == 'service_territory' else 'POWERPATH_SUBSTATION_LAYER_URL'
        try:
            url = configured_layer(env)
        except (ProviderError, ValueError) as exc:
            return unavailable(kind, '', str(exc))
        if not url:
            return unavailable(kind, '', f'No verified accessible {kind} layer configured; set {env} after reviewing source ownership and coverage')
        name = os.environ.get(env.replace('_URL', '_NAME'), '').strip()
        if not name:
            return unavailable(kind, url, 'Configure the layer source NAME with publisher and vintage after source review')
    w, s, e, n = shape(parcel).bounds
    lat = (s + n) / 2
    import math
    dy, dx = 20 / 110, 20 / (110 * max(0.1, math.cos(math.radians(lat))))
    # Broad envelope is filtered with projected footprint distances after retrieval.
    envelope = f'{max(-180,w-dx)},{max(-90,s-dy)},{min(180,e+dx)},{min(90,n+dy)}'
    params = {'f': 'geojson', 'where': '1=1', 'geometry': envelope, 'geometryType': 'esriGeometryEnvelope',
              'inSR': 4326, 'outSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
              'returnGeometry': 'true', 'outFields': '*', 'resultRecordCount': 200}
    try:
        data, ts, hit = http.get(project_id, url + '/query', params, ttl=7 * 86400)
        return normalize(data, parcel, ts, url, name, kind, cached=hit)
    except (ProviderError, ValueError) as exc:
        return unavailable(name, url, str(exc))
