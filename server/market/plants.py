"""Power plant lookup and capacity factors from public EIA data.

Inventory: EIA-860M monthly generator inventory (electricity/operating-generator-capacity),
grouped by plant: location, balancing authority, fuels, technology, nameplate and net summer MW.
Generation: EIA-923 plant-level monthly net generation (electricity/facility-fuel).

Capacity factor = net generation ÷ (net summer capacity × hours in the period), the EIA
convention. Capacity comes from the latest inventory, so a plant that added or retired units
during the history window is flagged. Capacity factor shows how much a plant ran, not how
much it could run: a gas plant may run little for economic reasons. Hydro output depends on
water, so the worst year and the monthly profile matter more than the average.
"""
import calendar
import json
import math
from datetime import date, datetime, timedelta, timezone

from server.market import providers as P

INVENTORY_REFRESH_DAYS = 7
GEN_REFRESH_DAYS = 7
FUEL_GROUPS = {
    'NUC': 'nuclear', 'NG': 'gas', 'WAT': 'hydro', 'SUN': 'solar', 'WND': 'wind', 'MWH': 'storage',
    'BIT': 'coal', 'SUB': 'coal', 'LIG': 'coal', 'ANT': 'coal', 'RC': 'coal', 'WC': 'coal', 'SGC': 'coal',
    'DFO': 'oil', 'RFO': 'oil', 'JF': 'oil', 'KER': 'oil', 'PC': 'oil', 'WO': 'oil', 'GEO': 'geothermal',
    'WDS': 'biomass', 'LFG': 'biomass', 'OBG': 'biomass', 'AB': 'biomass', 'MSW': 'biomass', 'BLQ': 'biomass',
}


def _pick(row, *names):
    for n in names:
        if n in row and row[n] not in (None, ''):
            return row[n]
    return None


def _num(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _operating(status):
    s = str(status or '').upper()
    return s.startswith('OP') or s.startswith('(OP)') or s == 'OPERATING' or 'OPERATING' in s and 'NOT' not in s


def normalize_inventory(rows):
    """Generator rows (any common field spelling) -> {plant_id: plant}."""
    plants, periods = {}, set()
    for r in rows:
        if not _operating(_pick(r, 'status', 'statusCode', 'status_code')):
            continue
        pid = str(_pick(r, 'plantid', 'plantId', 'plant_id', 'plantCode') or '').strip()
        if not pid:
            continue
        periods.add(str(r.get('period', ''))[:7])
        p = plants.setdefault(pid, {
            'plant_id': pid, 'name': _pick(r, 'plantName', 'plant_name', 'plantname') or f'Plant {pid}',
            'state': _pick(r, 'stateid', 'state', 'plant_state'), 'county': _pick(r, 'county'),
            'latitude': _num(_pick(r, 'latitude')), 'longitude': _num(_pick(r, 'longitude')),
            'ba': _pick(r, 'balancing_authority_code', 'balancingAuthority', 'balancing-authority-code'),
            'operator': _pick(r, 'entityName', 'entity_name', 'entityname'),
            'nameplate_mw': 0.0, 'summer_mw': 0.0, 'generators': 0, 'fuels': {}, 'technologies': set(), 'first_operating': None})
        mw = _num(_pick(r, 'nameplate-capacity-mw', 'nameplate_capacity_mw', 'nameplateMw')) or 0.0
        summer = _num(_pick(r, 'net-summer-capacity-mw', 'net_summer_capacity_mw', 'summerMw'))
        p['nameplate_mw'] += mw
        p['summer_mw'] += summer if summer is not None else mw
        p['generators'] += 1
        fuel = FUEL_GROUPS.get(str(_pick(r, 'energy_source_code', 'energySource', 'energy-source-code') or '').upper(), 'other')
        p['fuels'][fuel] = p['fuels'].get(fuel, 0.0) + mw
        tech = _pick(r, 'technology')
        if tech:
            p['technologies'].add(tech)
        op = _pick(r, 'operating-year-month', 'operating_year_month', 'operatingYearMonth')
        if op and (not p['first_operating'] or str(op) < p['first_operating']):
            p['first_operating'] = str(op)[:7]
    for p in plants.values():
        p['primary_fuel'] = max(p['fuels'], key=p['fuels'].get) if p['fuels'] else 'other'
        p['technologies'] = sorted(p['technologies'])
        p['nameplate_mw'] = round(p['nameplate_mw'], 3)
        p['summer_mw'] = round(p['summer_mw'], 3)
        p['fuels'] = {k: round(v, 3) for k, v in sorted(p['fuels'].items(), key=lambda kv: -kv[1])}
    return plants, (max(periods) if periods else None)


def fetch_inventory(fetch, state):
    """Latest month of the EIA-860M inventory for one state (pages newest-first until the month changes)."""
    key = P._eia_key()
    rows, offset, latest = [], 0, None
    while offset <= 50000:
        text = fetch(P.EIA + 'electricity/operating-generator-capacity/data/', {
            'api_key': key, 'frequency': 'monthly', 'data[0]': 'nameplate-capacity-mw', 'data[1]': 'net-summer-capacity-mw',
            'facets[stateid][]': state, 'sort[0][column]': 'period', 'sort[0][direction]': 'desc', 'length': 5000, 'offset': offset})
        try:
            payload = json.loads(text)
        except ValueError:
            raise P.MarketError('EIA response was not JSON') from None
        batch = (payload.get('response') or {}).get('data')
        if not isinstance(batch, list):
            raise P.MarketError(str(payload.get('error') or 'EIA response is missing its data array')[:200])
        if not batch:
            break
        latest = latest or str(batch[0].get('period', ''))[:7]
        rows.extend(r for r in batch if str(r.get('period', ''))[:7] == latest)
        if len(batch) < 5000 or str(batch[-1].get('period', ''))[:7] != latest:
            break
        offset += 5000
    return rows


def normalize_generation(rows, plant_id):
    """facility-fuel rows -> {YYYY-MM: MWh}. Prefers the all-fuel, all-prime-mover total."""
    totals, parts = {}, {}
    for r in rows:
        if str(_pick(r, 'plantCode', 'plantid', 'plant_id')) != str(plant_id):
            continue
        period = str(r.get('period', ''))[:7]
        mwh = _num(_pick(r, 'generation'))
        if mwh is None:
            continue
        units = str(r.get('generation-units', 'megawatthours')).lower()
        if units not in ('megawatthours', 'megawatt hours', 'mwh'):
            raise P.MarketError('EIA generation units not recognised')
        fuel, pm = str(r.get('fuel2002', '')).upper(), str(r.get('primeMover', '')).upper()
        if fuel in ('ALL', 'TOT') and pm in ('ALL', ''):
            totals[period] = mwh
        elif pm in ('ALL', '') and fuel not in ('ALL', 'TOT'):
            parts[period] = parts.get(period, 0.0) + mwh
    return {p: totals.get(p, parts.get(p)) for p in sorted(set(totals) | set(parts))}


def fetch_generation(fetch, plant_id, start):
    text = fetch(P.EIA + 'electricity/facility-fuel/data/', {
        'api_key': P._eia_key(), 'frequency': 'monthly', 'data[0]': 'generation', 'facets[plantCode][]': str(plant_id),
        'facets[primeMover][]': 'ALL', 'start': start, 'sort[0][column]': 'period', 'sort[0][direction]': 'asc', 'length': 5000})
    try:
        payload = json.loads(text)
    except ValueError:
        raise P.MarketError('EIA response was not JSON') from None
    rows = (payload.get('response') or {}).get('data')
    if not isinstance(rows, list):
        raise P.MarketError(str(payload.get('error') or 'EIA response is missing its data array')[:200])
    return normalize_generation(rows, plant_id)


def capacity_factors(monthly_mwh, summer_mw, first_operating=None):
    if not summer_mw or summer_mw <= 0:
        raise ValueError('Plant has no net summer capacity to divide by')
    months = []
    for period, mwh in sorted(monthly_mwh.items()):
        y, m = int(period[:4]), int(period[5:7])
        hours = calendar.monthrange(y, m)[1] * 24
        months.append({'period': period, 'mwh': mwh, 'hours': hours, 'cf': round(mwh / (summer_mw * hours), 4), 'avg_mw': round(mwh / hours, 3)})
    by_year = {}
    for row in months:
        by_year.setdefault(row['period'][:4], []).append(row)
    years = []
    for y, rows in sorted(by_year.items()):
        complete = len(rows) == 12
        mwh, hours = sum(r['mwh'] for r in rows), sum(r['hours'] for r in rows)
        years.append({'year': int(y), 'months': len(rows), 'complete': complete, 'mwh': round(mwh, 3), 'cf': round(mwh / (summer_mw * hours), 4),
                      'worst_month_cf': min(r['cf'] for r in rows), 'worst_month': min(rows, key=lambda r: r['cf'])['period']})
    full = [y for y in years if y['complete']]
    last12 = months[-12:]
    profile = {}
    for row in months:
        profile.setdefault(int(row['period'][5:7]), []).append(row['cf'])
    flags = []
    if any(r['cf'] > 1.05 for r in months):
        flags.append('Some months exceed 100% of net summer capacity (winter ratings or capacity changes); treat with care.')
    if first_operating and months and first_operating > months[0]['period']:
        flags.append(f'Plant capacity first operating {first_operating}; earlier months reflect a smaller or different plant.')
    if any(r['mwh'] < 0 for r in months):
        flags.append('Negative net generation in some months (station use exceeded output, typical for storage or idle plants).')
    worst = min(full, key=lambda y: y['cf']) if full else None
    return {
        'basis': 'net summer capacity', 'summer_mw': summer_mw, 'months': months, 'years': years,
        'cf_last_12_months': round(sum(r['mwh'] for r in last12) / (summer_mw * sum(r['hours'] for r in last12)), 4) if len(last12) == 12 else None,
        'last_12_window': f'{last12[0]["period"]} to {last12[-1]["period"]}' if len(last12) == 12 else None,
        'cf_average_full_years': round(sum(y['cf'] for y in full) / len(full), 4) if full else None,
        'worst_year': {'year': worst['year'], 'cf': worst['cf']} if worst else None,
        'best_year': {'year': max(full, key=lambda y: y['cf'])['year'], 'cf': max(y['cf'] for y in full)} if full else None,
        'worst_month': min(months, key=lambda r: r['cf']) if months else None,
        'monthly_profile': {calendar.month_abbr[m]: round(sum(v) / len(v), 4) for m, v in sorted(profile.items())},
        'flags': flags,
        'method': 'Net generation ÷ (current net summer capacity × hours). Shows how much the plant ran, not its availability.'}


def km(a_lat, a_lon, b_lat, b_lon):
    la1, lo1, la2, lo2 = map(math.radians, (a_lat, a_lon, b_lat, b_lon))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))


# ------------------------------------------------------------------ cache

SCHEMA = '''
CREATE TABLE IF NOT EXISTS mk_plants (
 state TEXT NOT NULL, plant_id TEXT NOT NULL, body TEXT NOT NULL, inventory_month TEXT, retrieved_at TEXT NOT NULL,
 PRIMARY KEY(state, plant_id));
'''


def initialize(db):
    with db() as con:
        con.executescript(SCHEMA)


def _now():
    return datetime.now(timezone.utc)


def inventory(con, state, fetch=None, live=True):
    fetch = fetch or P.http_fetch
    row = con.execute('SELECT MAX(retrieved_at) t, MAX(inventory_month) m FROM mk_plants WHERE state=?', (state,)).fetchone()
    fresh = row['t'] and datetime.fromisoformat(row['t']) > _now() - timedelta(days=INVENTORY_REFRESH_DAYS)
    warnings = []
    if live and not fresh:
        try:
            plants, month = normalize_inventory(fetch_inventory(fetch, state))
            if plants:
                ts = _now().isoformat(timespec='seconds')
                con.execute('DELETE FROM mk_plants WHERE state=?', (state,))
                for p in plants.values():
                    con.execute('INSERT INTO mk_plants VALUES(?,?,?,?,?)', (state, p['plant_id'], json.dumps(p), month, ts))
        except P.MarketError as exc:
            warnings.append(str(exc))
    rows = con.execute('SELECT body, inventory_month, retrieved_at FROM mk_plants WHERE state=?', (state,)).fetchall()
    meta = {'inventory_month': rows[0]['inventory_month'] if rows else None, 'retrieved_at': rows[0]['retrieved_at'] if rows else None}
    return [json.loads(r['body']) for r in rows], meta, warnings


def search(con, state, latitude=None, longitude=None, radius_km=None, fuel=None, q=None, limit=25, fetch=None, live=True):
    plants, meta, warnings = inventory(con, state, fetch, live)
    out = []
    for p in plants:
        if fuel and p['primary_fuel'] != fuel and fuel not in p['fuels']:
            continue
        if q and q.lower() not in p['name'].lower() and q.lower() not in str(p.get('operator') or '').lower():
            continue
        d = None
        if latitude is not None and longitude is not None and p['latitude'] is not None and p['longitude'] is not None:
            d = round(km(latitude, longitude, p['latitude'], p['longitude']), 2)
            if radius_km and d > radius_km:
                continue
        elif radius_km and latitude is not None:
            continue
        out.append({**{k: p[k] for k in ('plant_id', 'name', 'state', 'county', 'ba', 'operator', 'primary_fuel', 'fuels', 'technologies',
                                          'nameplate_mw', 'summer_mw', 'generators', 'latitude', 'longitude', 'first_operating')}, 'distance_km': d})
    out.sort(key=lambda p: (p['distance_km'] is None, p['distance_km'] or 0, -p['summer_mw']))
    return {'state': state, 'plants': out[:limit], 'matched': len(out), **meta, 'source': 'EIA-860M via EIA API (operating generators)', 'warnings': warnings}


def profile(con, state, plant_id, years=5, fetch=None, live=True):
    fetch = fetch or P.http_fetch
    plants, meta, warnings = inventory(con, state, fetch, live)
    plant = next((p for p in plants if p['plant_id'] == str(plant_id)), None)
    if not plant:
        raise LookupError(f'Plant {plant_id} not found among operating plants in {state}' + (f' ({"; ".join(warnings)})' if warnings else ''))
    start = f'{date.today().year - years}-01'
    location = f'plant:{plant_id}'
    last = con.execute("SELECT MAX(retrieved_at) t, MIN(period) p FROM mk_obs WHERE scope='public' AND metric='plant_gen' AND location=?", (location,)).fetchone()
    fresh = last['t'] and datetime.fromisoformat(last['t']) > _now() - timedelta(days=GEN_REFRESH_DAYS) and last['p'] and last['p'] <= start
    if live and not fresh:
        try:
            gen = fetch_generation(fetch, plant_id, start)
            ts = _now().isoformat(timespec='seconds')
            for period, mwh in gen.items():
                con.execute("INSERT INTO mk_obs VALUES('public','plant_gen',?,?,?,?,?) ON CONFLICT(scope,metric,location,period) DO UPDATE SET body=excluded.body, retrieved_at=excluded.retrieved_at",
                            (location, period, json.dumps({'value': mwh}), 'EIA-923 via EIA API (facility-fuel)', ts))
        except P.MarketError as exc:
            warnings.append(str(exc))
    rows = con.execute("SELECT period, body, retrieved_at FROM mk_obs WHERE scope='public' AND metric='plant_gen' AND location=? AND period>=? ORDER BY period",
                       (location, start)).fetchall()
    monthly = {r['period']: json.loads(r['body'])['value'] for r in rows}
    if not monthly:
        raise ValueError('; '.join(warnings) or 'No generation reported for this plant in the window')
    cf = capacity_factors(monthly, plant['summer_mw'], plant.get('first_operating'))
    return {'plant': plant, 'capacity_factor': cf, 'inventory_month': meta['inventory_month'],
            'generation_retrieved_at': rows[-1]['retrieved_at'], 'latest_month': rows[-1]['period'],
            'sources': ['EIA-860M via EIA API (operating-generator-capacity)', 'EIA-923 via EIA API (facility-fuel)'], 'warnings': warnings}
