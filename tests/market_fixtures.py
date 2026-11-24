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
    if start:
        d, e = date.fromisoformat(start), date.fromisoformat(end)
        while d <= e:
            days.append(d.isoformat()); d += timedelta(days=1)
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


