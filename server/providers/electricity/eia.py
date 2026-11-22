"""EIA monthly state retail sales statistics; these are not a site tariff."""
import os
import re
from server.providers.base import DataPoint, ProviderResult, ProviderError, number, unavailable

URL = 'https://api.eia.gov/v2/electricity/retail-sales/data/'
NAME = 'EIA electricity retail sales'


def normalize(payload, state, retrieved_at, cached=False):
    rows = payload.get('response', {}).get('data')
    if not isinstance(rows, list):
        raise ProviderError('EIA response is missing its data array')
    points = []
    for row in rows:
        if row.get('stateid') != state or row.get('sectorid') not in ('IND', 'COM'):
            continue
        period = str(row.get('period', ''))
        if not re.fullmatch(r'\d{4}-\d{2}', period):
            continue
        units = str(row.get('price-units', '')).lower()
        if units not in ('cents per kilowatthour', 'cents per kilowatt-hour'):
            raise ProviderError('EIA price units are not recognized')
        value = number(row.get('price'))
        points.append(DataPoint(value=round(value * 10, 6) if value is not None and value >= 0 else None,
            unit='USD/MWh', source_name=NAME, source_url=URL, retrieved_at=retrieved_at,
            effective_date=period, status='observed', category='retail_statistic',
            coverage=f'{state} statewide {row["sectorid"]}',
            methodology='Published revenue / sales average, converted from cents/kWh × 10. Not a utility tariff or data-center contract.'))
    return ProviderResult(provider=NAME, source_url=URL, retrieved_at=retrieved_at, cached=cached,
        points=points, status='available' if any(p.value is not None for p in points) else 'unavailable',
        warnings=['Industrial and commercial classifications do not establish the tariff applicable to this parcel.']).model_dump()


def fetch(http, project_id, state):
    key = os.environ.get('POWERPATH_EIA_API_KEY', '').strip()
    if not key:
        return unavailable(NAME, URL, 'Configure POWERPATH_EIA_API_KEY for EIA retail price statistics')
    if not state:
        return unavailable(NAME, URL, 'Parcel state could not be resolved')
    try:
        data, ts, hit = http.get(project_id, URL, {'api_key': key, 'frequency': 'monthly',
            'data[0]': 'price', 'facets[stateid][]': state, 'facets[sectorid][]': ['IND', 'COM'],
            'sort[0][column]': 'period', 'sort[0][direction]': 'desc', 'length': 24})
        return normalize(data, state, ts, hit)
    except ProviderError as exc:
        return unavailable(NAME, URL, str(exc))
