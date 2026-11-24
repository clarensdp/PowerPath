"""Plant lookup and capacity factors from EIA-860M inventory and EIA-923 generation (recorded payloads)."""
import os, tempfile
os.environ['POWERPATH_DATA_DIR'] = tempfile.mkdtemp(prefix='pp-plants-')
os.environ['POWERPATH_V27_AUTH_MODE'] = 'local_only'
os.environ.pop('POWERPATH_DATABASE_URL', None)
import pytest
from fastapi.testclient import TestClient
from server.app import app
from server.market import plants as PL, providers as P
from tests.market_fixtures import CALLS, INVENTORY, fake_fetch, generation_rows


@pytest.fixture
def proj(monkeypatch):
    monkeypatch.setattr(P, 'http_fetch', fake_fetch)
    monkeypatch.setenv('POWERPATH_EIA_API_KEY', 'test-key')
    CALLS.clear()
    c = TestClient(app, base_url='http://127.0.0.1')
    pid = c.post('/api/projects?starter_scenario=true', json={'name': 'Plants', 'target_mw': 150}).json()['id']
    c.put(f'/api/projects/{pid}/market/profile', json={'state': 'NY', 'ba': 'NYIS', 'nyiso_zone': 'N.Y.C.'})
    return c, f'/api/projects/{pid}/market'


def test_inventory_groups_operating_generators_by_plant():
    plants, month = PL.normalize_inventory(INVENTORY)
    assert month == '2026-09' and set(plants) == {'1001', '1002'}  # standby peaker excluded
    gas = plants['1002']
    assert gas['generators'] == 2 and gas['nameplate_mw'] == 500 and gas['summer_mw'] == 480 and gas['primary_fuel'] == 'gas'
    # alternative field spellings parse the same
    alt = [{'period': '2026-09', 'plantId': 7, 'plant_name': 'Alt', 'state': 'NY', 'statusCode': 'OP', 'energySource': 'SUN', 'nameplateMw': 20, 'summerMw': 18}]
    p, _ = PL.normalize_inventory(alt)
    assert p['7']['summer_mw'] == 18 and p['7']['primary_fuel'] == 'solar'


def test_capacity_factor_math_and_worst_year():
    monthly = PL.normalize_generation(generation_rows('1001', '2022-01'), '1001')
    cf = PL.capacity_factors(monthly, 100)
    assert cf['basis'] == 'net summer capacity'
    jan = next(m for m in cf['months'] if m['period'] == '2024-01')
    assert jan['cf'] == pytest.approx(0.55, abs=1e-4) and jan['avg_mw'] == pytest.approx(55, abs=0.01)
    assert cf['worst_year']['year'] == 2023 and cf['best_year']['year'] != 2023
    assert cf['monthly_profile']['Sep'] < cf['monthly_profile']['Apr']
    assert cf['cf_last_12_months'] is not None and cf['last_12_window'].endswith('2026-08')
    assert [y['complete'] for y in cf['years']][-1] is False  # 2026 partial
    with pytest.raises(ValueError):
        PL.capacity_factors(monthly, 0)


def test_generation_prefers_total_and_falls_back_to_fuel_sum():
    rows = [{'period': '2025-01', 'plantCode': '9', 'fuel2002': 'NG', 'primeMover': 'ALL', 'generation': '100', 'generation-units': 'megawatthours'},
            {'period': '2025-01', 'plantCode': '9', 'fuel2002': 'DFO', 'primeMover': 'ALL', 'generation': '5', 'generation-units': 'megawatthours'}]
    assert PL.normalize_generation(rows, '9') == {'2025-01': 105}
    rows.append({'period': '2025-01', 'plantCode': '9', 'fuel2002': 'ALL', 'primeMover': 'ALL', 'generation': '104', 'generation-units': 'megawatthours'})
    assert PL.normalize_generation(rows, '9') == {'2025-01': 104}


def test_plant_search_and_profile_routes(proj):
    c, m = proj
    near = c.get(m + '/plants', params={'latitude': 40.75, 'longitude': -73.95, 'radius_km': 50}).json()
    assert [p['name'] for p in near['plants']] == ['Harbor Gas CC'] and near['inventory_month'] == '2026-09'
    assert near['plants'][0]['distance_km'] < 10
    hydro = c.get(m + '/plants', params={'fuel': 'hydro'}).json()['plants']
    assert [p['plant_id'] for p in hydro] == ['1001']
    r = c.get(m + '/plants/1001', params={'years': 4})
    assert r.status_code == 200, r.text
    prof = r.json()
    assert prof['plant']['name'] == 'Riverbend Hydro' and prof['capacity_factor']['worst_year']['year'] == 2023
    assert prof['latest_month'] == '2026-08' and len(prof['sources']) == 2
    CALLS.clear()
    c.get(m + '/plants/1001', params={'years': 4})
    assert not any('eia.gov' in u for u in CALLS)  # inventory and generation cached
    assert c.get(m + '/plants/9999').status_code == 404
    assert c.get(m + '/plants', params={'state': 'New York'}).status_code == 422


def test_missing_key_is_reported(proj, monkeypatch):
    c, m = proj
    monkeypatch.delenv('POWERPATH_EIA_API_KEY')
    r = c.get(m + '/plants', params={'state': 'TX'}).json()
    assert r['plants'] == [] and 'POWERPATH_EIA_API_KEY' in r['warnings'][0]
