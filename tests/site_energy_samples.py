"""Synthetic API response fixtures ONLY. Never imported by application runtime."""
import json
from io import BytesIO
from urllib.parse import urlsplit, parse_qs

EIA = {'response': {'data': [
    {'period': '2026-08', 'stateid': 'VA', 'sectorid': 'IND', 'price': '8.25', 'price-units': 'cents per kilowatt-hour'},
    {'period': '2026-08', 'stateid': 'VA', 'sectorid': 'COM', 'price': None, 'price-units': 'cents per kilowatthour'}]}}
SOLAR = {'outputs': {'avg_ghi': {'annual': 4.5, 'monthly': {'jan': 2.1}},
                      'avg_dni': {'annual': None}, 'avg_lat_tilt': {'annual': 5.0}}, 'errors': []}
PV = {'outputs': {'ac_annual': 1500000}, 'station_info': {'location': 'SYNTHETIC TEST WEATHER'}, 'version': '8.0'}


class MockTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append(request.full_url)
        url = request.full_url
        if 'api.eia.gov' in url:
            result = EIA
        elif 'solar_resource' in url:
            result = SOLAR
        elif 'pvwatts' in url:
            result = PV
        elif 'arcgis' in url:
            bounds = [float(x) for x in parse_qs(urlsplit(url).query)['geometry'][0].split(',')]
            lon, lat = (bounds[0]+bounds[2])/2, (bounds[1]+bounds[3])/2
            result = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {
                'ID': 'TEST-LINE-1', 'OWNER': 'SYNTHETIC TEST LINE', 'VOLTAGE': 230, 'SOURCEDATE': 1577836800000},
                'geometry': {'type': 'LineString', 'coordinates': [[lon, lat-.01],[lon,lat+.01]]}}]}
        else:
            raise AssertionError('Unexpected external URL in offline test')
        return BytesIO(json.dumps(result).encode())
