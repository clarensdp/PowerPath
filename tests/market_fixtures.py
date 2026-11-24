"""Recorded-format NYISO and EIA payloads for offline tests and previews."""
import json, os
from datetime import date, timedelta
from urllib.parse import urlparse
from server.market import providers as P

ZONES = {'CAPITL': 0, 'N.Y.C.': 10, 'WEST': -5}
CALLS = []


def nyiso_csv(day, broken=False):
    head = 'Time Stamp,Name,PTID,LBMP ($/MWHr),Marginal Cost Losses ($/MWHr),Marginal Cost Congestion ($/MWHr)'
    if broken:
        head = 'When,Zone,Price'
    rows = [head]
    for h in range(24):
        for z, off in ZONES.items():
            rows.append(f'{day.strftime("%m/%d/%Y")} {h:02d}:00,{z},6175{h % 9},{30 + h + off:.2f},1.00,{2.0 if z == "N.Y.C." else 0.0:.2f}')
    return '\n'.join(rows)


def fake_fetch(url, params=None):
    CALLS.append(url)
    host = urlparse(url).netloc
    if host == 'mis.nyiso.com':
        stamp = url.rsplit('/', 1)[1][:8]
        day = date(int(stamp[:4]), int(stamp[4:6]), int(stamp[6:]))
        if day > date.today():
            raise P.MarketError('mis.nyiso.com returned HTTP 404')
        return nyiso_csv(day, broken=os.environ.get('FAKE_NYISO_BROKEN') == '1')
    assert params['api_key'] == 'test-key'
    start, end = params.get('start'), params.get('end')
    days = []
    if start and len(start) == 10:
        d, e = date.fromisoformat(start), date.fromisoformat(end)
        while d <= e:
            days.append(d.isoformat()); d += timedelta(days=1)
    if 'operating-generator-capacity' in url:
        return json.dumps({'response': {'data': INVENTORY if params.get('offset', 0) == 0 else []}})
    if 'facility-fuel' in url:
        return json.dumps({'response': {'data': generation_rows(params['facets[plantCode][]'], params['start'])}})
    if 'natural-gas/pri/fut' in url:
        data = [{'period': d, 'series': 'RNGWHHD', 'value': '3.00', 'units': '$/MMBTU'} for d in days if date.fromisoformat(d).weekday() < 5]
    elif 'daily-region-data' in url:
        data = [{'period': d, 'respondent': params['facets[respondent][]'], 'type': 'D', 'value': '480000', 'value-units': 'megawatthours'} for d in days]
    elif 'daily-fuel-type-data' in url:
        mix = {'NG': 200000, 'NUC': 100000, 'WAT': 60000, 'WND': 30000, 'SUN': 10000}
        data = [{'period': d, 'respondent': params['facets[respondent][]'], 'fueltype': f, 'value': str(v)} for d in days for f, v in mix.items()]
    elif 'retail-sales' in url:
        today = date.today()
        data = [{'period': f'{(today.year * 12 + today.month - 3 - i) // 12}-{(today.year * 12 + today.month - 3 - i) % 12 + 1:02d}',
                 'stateid': params['facets[stateid][]'], 'sectorid': params['facets[sectorid][]'], 'price': '9.50'} for i in range(24)]
    else:
        raise AssertionError(url)
    return json.dumps({'response': {'data': data}})




def _gen(pid, name, state, lat, lon, ba, fuel, tech, mw, summer, gid, status='OP', period=None, op='2005-06'):
    return {'period': period or INVENTORY_MONTH, 'plantid': pid, 'plantName': name, 'stateid': state, 'latitude': str(lat), 'longitude': str(lon),
            'balancing_authority_code': ba, 'energy_source_code': fuel, 'technology': tech, 'status': status, 'generatorid': gid,
            'nameplate-capacity-mw': str(mw), 'net-summer-capacity-mw': str(summer), 'operating-year-month': op, 'entityName': 'Example Power LLC'}


INVENTORY_MONTH = '2026-09'
INVENTORY = [
    _gen('1001', 'Riverbend Hydro', 'NY', 42.0, -74.0, 'NYIS', 'WAT', 'Conventional Hydroelectric', 100, 100, 'H1'),
    _gen('1002', 'Harbor Gas CC', 'NY', 40.7, -73.9, 'NYIS', 'NG', 'Natural Gas Fired Combined Cycle', 300, 290, 'CT1'),
    _gen('1002', 'Harbor Gas CC', 'NY', 40.7, -73.9, 'NYIS', 'NG', 'Natural Gas Fired Combined Cycle', 200, 190, 'ST1'),
    _gen('1003', 'Old Peaker', 'NY', 40.8, -73.8, 'NYIS', 'DFO', 'Petroleum Liquids', 50, 45, 'GT1', status='SB'),
    _gen('1001', 'Riverbend Hydro', 'NY', 42.0, -74.0, 'NYIS', 'WAT', 'Conventional Hydroelectric', 100, 100, 'H1', period='2026-08'),
]
# Hydro: seasonal; 2023 is the dry year. Gas: flat 60%.
HYDRO_SHAPE = [0.55, 0.6, 0.8, 0.9, 0.85, 0.6, 0.45, 0.35, 0.3, 0.4, 0.5, 0.55]


def generation_rows(pid, start):
    import calendar
    rows = []
    for y in range(int(start[:4]), 2027):
        for m in range(1, 13):
            if (y, m) > (2026, 8):
                break
            hours = calendar.monthrange(y, m)[1] * 24
            if pid == '1001':
                cf = HYDRO_SHAPE[m - 1] * (0.7 if y == 2023 else 1.0)
                mwh = round(100 * hours * cf, 3)
            elif pid == '1002':
                mwh = round(480 * hours * 0.6, 3)
            else:
                continue
            rows.append({'period': f'{y}-{m:02d}', 'plantCode': pid, 'plantName': 'x', 'fuel2002': 'ALL', 'primeMover': 'ALL',
                         'generation': str(mwh), 'generation-units': 'megawatthours'})
            rows.append({'period': f'{y}-{m:02d}', 'plantCode': pid, 'fuel2002': 'WAT' if pid == '1001' else 'NG', 'primeMover': 'ALL',
                         'generation': str(mwh), 'generation-units': 'megawatthours'})
    return rows
