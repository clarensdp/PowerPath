"""NREL (now NLR) modeled solar resource and PVWatts v8 generation estimates."""
import os
from pydantic import BaseModel, ConfigDict, Field
from server.providers.base import DataPoint, ProviderResult, ProviderError, number, unavailable

RESOURCE_URL = 'https://developer.nlr.gov/api/solar/solar_resource/v1.json'
PV_URL = 'https://developer.nlr.gov/api/pvwatts/v8.json'
NAME = 'NREL/NLR solar resource'


class SolarSystem(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    capacity_kw: float = Field(ge=0.05, le=500000)
    tilt: float = Field(default=20, ge=0, le=90)
    azimuth: float = Field(default=180, ge=0, lt=360)
    losses_pct: float = Field(default=14, ge=0, le=99)


def normalize_resource(payload, lat, lon, ts, cached=False):
    outputs = payload.get('outputs')
    if not isinstance(outputs, dict):
        raise ProviderError('Solar resource response is missing outputs')
    points = []
    for metric in ('avg_ghi', 'avg_dni', 'avg_lat_tilt'):
        values = outputs.get(metric) or {}
        if not isinstance(values, dict):
            raise ProviderError('Unexpected solar resource series')
        periods = {'annual': values.get('annual'), **(values.get('monthly') or {})}
        for period, value in periods.items():
            if period != 'annual' and period not in ('jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec'):
                continue
            n = number(value)
            points.append(DataPoint(value=n if n is not None and n >= 0 else None, unit='kWh/m²/day',
                source_name=NAME, source_url=RESOURCE_URL, retrieved_at=ts, status='estimated',
                effective_date='1998–2009 climatology', category=metric, coverage=f'~10 km grid near {lat:.5f}, {lon:.5f}; {period}',
                methodology='SUNY satellite model climatological daily irradiation. Not measured site generation or buildable capacity.'))
    return ProviderResult(provider=NAME, source_url=RESOURCE_URL, retrieved_at=ts, cached=cached,
        points=points, status='available' if any(p.value is not None for p in points) else 'unavailable',
        warnings=['Historical modeled resource; parcel-scale shading and installation constraints are not assessed.']).model_dump()


def normalize_generation(payload, system, ts, cached=False):
    outputs = payload.get('outputs')
    if not isinstance(outputs, dict):
        raise ProviderError('PVWatts response is missing outputs')
    value = number(outputs.get('ac_annual'))
    station = payload.get('station_info', {})
    if not isinstance(station, dict):
        raise ProviderError('PVWatts response has invalid station metadata')
    point = DataPoint(value=value / 1000 if value is not None and value >= 0 else None, unit='MWh/year',
        source_name='NREL/NLR PVWatts v8', source_url=PV_URL, retrieved_at=ts,
        effective_date='NSRDB typical meteorological year (TMY), not a forecast year',
        status='estimated', category='solar_generation', coverage=f'Weather station/grid {station.get("location", "not supplied")}',
        methodology=f'PVWatts v8; {system.capacity_kw} kW DC, standard modules, fixed open rack, tilt {system.tilt}°, azimuth {system.azimuth}°, losses {system.losses_pct}%; default DC/AC ratio 1.2 and inverter efficiency 96%. No storage or firm-power claim.')
    result = ProviderResult(provider='NREL/NLR PVWatts v8', source_url=PV_URL, retrieved_at=ts, cached=cached,
        points=[point], status='available' if point.value is not None else 'unavailable',
        warnings=['Installed capacity is user-assumed; no acreage-to-capacity conversion. Generation is intermittent and does not establish utility availability.']).model_dump()
    result['system_assumptions'] = {**system.model_dump(), 'status': 'assumed', 'module_type': 0,
                                    'array_type': 0, 'dc_ac_ratio': 1.2, 'inv_eff': 96}
    result['weather_station'] = station
    result['model_version'] = payload.get('version')
    return result


def fetch(http, project_id, lat, lon, system=None):
    url = PV_URL if system else RESOURCE_URL
    key = os.environ.get('POWERPATH_NREL_API_KEY', '').strip()
    if not key:
        return unavailable(NAME, url, 'Configure POWERPATH_NREL_API_KEY for solar resource / PVWatts')
    params = {'api_key': key, 'lat': lat, 'lon': lon}
    if system:
        params.update(system_capacity=system.capacity_kw, tilt=system.tilt, azimuth=system.azimuth,
                      losses=system.losses_pct, array_type=0, module_type=0, dataset='nsrdb',
                      timeframe='monthly', dc_ac_ratio=1.2, inv_eff=96)
    try:
        data, ts, hit = http.get(project_id, url, params, ttl=30 * 86400)
        return normalize_generation(data, system, ts, hit) if system else normalize_resource(data, lat, lon, ts, hit)
    except ProviderError as exc:
        return unavailable(NAME, url, str(exc))
    except (ValueError, KeyError, TypeError, AttributeError):
        return unavailable(NAME, url, 'Solar response did not match the documented schema')
