"""v31.5 market data: NYISO/EIA normalisation, derived metrics, caching, licensed imports, power-cost proposals."""
import json, os, tempfile
from datetime import date, timedelta
os.environ['POWERPATH_DATA_DIR'] = tempfile.mkdtemp(prefix='pp-market-')
os.environ['POWERPATH_V27_AUTH_MODE'] = 'local_only'
os.environ.pop('POWERPATH_DATABASE_URL', None)
import pytest
from fastapi.testclient import TestClient
from server.app import app, db
from server.market import providers as P, service as M

from tests.market_fixtures import ZONES, CALLS, nyiso_csv, fake_fetch


@pytest.fixture
def proj(monkeypatch):
    monkeypatch.setattr(P, 'http_fetch', fake_fetch)
    M._MISSES.clear()
    monkeypatch.setenv('POWERPATH_EIA_API_KEY', 'test-key')
    CALLS.clear()
    c = TestClient(app, base_url='http://127.0.0.1')
    pid = c.post('/api/projects?starter_scenario=true', json={'name': 'Market test', 'target_mw': 150}).json()['id']
    assert c.put(f'/api/projects/{pid}/market/profile', json={'state': 'NY', 'ba': 'NYIS', 'nyiso_zone': 'N.Y.C.', 'heat_rate': 7.0}).status_code == 200
    return c, pid, f'/api/projects/{pid}/market'


def test_nyiso_daily_stats_from_published_layout():
    day = date(2026, 11, 18)  # Wednesday
    obs = P.nyiso_day(lambda u, p: nyiso_csv(day), day, 'N.Y.C.')
    assert obs['hours'] == 24 and obs['avg'] == pytest.approx(40 + 11.5)
    assert obs['on_peak'] == pytest.approx(sum(40 + h for h in range(7, 23)) / 16)
    assert obs['max'] == 63 and obs['min'] == 40 and obs['congestion_avg'] == 2.0
    weekend = P.nyiso_day(lambda u, p: nyiso_csv(date(2026, 11, 21)), date(2026, 11, 21), 'N.Y.C.')
    assert weekend['on_peak'] is None and weekend['off_peak'] == weekend['avg']
    with pytest.raises(P.MarketError):
        P.nyiso_day(lambda u, p: nyiso_csv(day, broken=True), day, 'N.Y.C.')
    with pytest.raises(P.MarketError):
        P.nyiso_day(lambda u, p: '', day, 'MOON')


def test_snapshot_has_provenance_and_derived_metrics(proj):
    c, pid, m = proj
    r = c.get(m + '/snapshot', params={'days': 14})
    assert r.status_code == 200, r.text
    s = r.json()
    items = {i['label']: i for i in s['items']}
    assert s['gaps'] == []
    lmp = items['Day-ahead LMP, 14-day avg']
    assert lmp['value'] == pytest.approx(51.5) and lmp['source'].startswith('NYISO') and lmp['retrieved_at'] and lmp['stale'] is False
    spark = items['Spark spread, 14-day on-peak']
    assert spark['value'] == pytest.approx(sum(40 + h for h in range(7, 23)) / 16 - 7 * 3.0)
    assert items['Industrial retail price, latest month']['value'] == 95.0
    assert items['Grid demand, latest day (avg MW)']['value'] == 20000
    carbon = items['Estimated carbon intensity, 14-day avg']
    assert carbon['value'] == pytest.approx(0.41 * 200000 / 400000) and 'Estimate' in carbon['method']
    assert items['Gas share of generation (latest day)']['value'] == 0.5


def test_cache_avoids_refetching_final_prices(proj):
    c, pid, m = proj
    with db() as con:
        con.execute('DELETE FROM mk_obs')
    CALLS.clear()
    c.get(m + '/snapshot', params={'days': 10})
    nyiso_first = sum('nyiso' in u for u in CALLS)
    CALLS.clear()
    c.get(m + '/snapshot', params={'days': 10})
    assert sum('nyiso' in u for u in CALLS) <= 1 < nyiso_first  # only today's/tomorrow's not-yet-final file
    assert not any('eia.gov' in u for u in CALLS)  # EIA re-pulled only after 6 hours


def test_missing_eia_key_reported_not_hidden(proj, monkeypatch):
    c, pid, m = proj
    monkeypatch.delenv('POWERPATH_EIA_API_KEY')
    with db() as con:  # public cache is shared across projects; start cold to exercise the fetch path
        con.execute("DELETE FROM mk_obs WHERE metric != 'lmp_da'")
    s = c.get(m + '/snapshot', params={'days': 7}).json()
    reasons = {g['metric']: g['reason'] for g in s['gaps']}
    assert 'POWERPATH_EIA_API_KEY' in reasons['henry_hub'] and 'POWERPATH_EIA_API_KEY' in reasons['fuel_mix']
    assert any(i['metric'] == 'lmp_da' for i in s['items'])


def test_series_and_validation(proj):
    c, pid, m = proj
    r = c.get(m + '/series', params={'metric': 'lmp_da', 'start': (date.today() - timedelta(days=5)).isoformat()}).json()
    assert r['location'] == 'N.Y.C.' and r['unit'] == 'USD/MWh' and len(r['observations']) >= 5
    assert c.get(m + '/series', params={'metric': 'lmp_da', 'location': 'MOON'}).status_code == 422
    assert c.get(m + '/series', params={'metric': 'magic'}).status_code == 422
    assert c.put(m + '/profile', json={'state': 'New York'}).status_code == 422


def test_licensed_import_stays_inside_project(proj):
    c, pid, m = proj
    r = c.post(m + '/import', json={'metric': 'pjm_west_forward', 'location': 'PJM WEST', 'unit': 'USD/MWh', 'source': 'Broker curve export',
               'license': 'Internal use under firm licence', 'as_of': '2026-11-20',
               'observations': [{'period': f'2027-{mo:02d}', 'value': 60 + mo} for mo in range(1, 13)]})
    assert r.status_code == 201, r.text
    assert c.get(m + '/catalog').json()['imported'][0]['metric'] == 'imported:pjm_west_forward'
    other = c.post('/api/projects?starter_scenario=true', json={'name': 'Other', 'target_mw': 50}).json()['id']
    assert c.get(f'/api/projects/{other}/market/catalog').json()['imported'] == []
    assert c.get(f'/api/projects/{other}/market/series', params={'metric': 'imported:pjm_west_forward', 'location': 'PJM WEST',
                 'start': '2000-01-01', 'end': '2030-01-01'}).json()['observations'] == []
    with db() as con:
        with pytest.raises(Exception):
            con.execute('DELETE FROM mk_imports')


def test_propose_power_cost_enters_review_with_source(proj):
    c, pid, m = proj
    r = c.post(m + '/propose-power-cost', json={'metric': 'lmp_da', 'window': 14, 'adder_mwh': 25})
    assert r.status_code == 201, r.text
    a = r.json()['assumption']['body']
    assert a['key'] == 'power_cost_mwh' and a['value'] == pytest.approx(51.5 + 25)
    assert 'NYISO' in a['source_name'] and '$25/MWh delivery adder' in a['source_name'] and a['verification'] == 'observed'
    ch = r.json()['change']
    assert ch['body']['requires'] == 'approval'
    assert ch['body']['recommendation'].startswith('Ready') and ch['body']['proposed']['unit'] == 'USD/MWh'
    assert ch['body']['impact']['change']['npvM'] > 0 and 'note' not in ch['body']['impact']  # cheaper market power raises NPV here
    u = f'/api/projects/{pid}/underwriting'
    assert c.post(u + f'/approvals/{ch["id"]}/accept', json={'note': 'Use market-based power cost'}).status_code == 200
    assert c.get(u + '/approved-case').json()['assignments']['power_cost_mwh'] == pytest.approx(76.5)
    retail = c.post(m + '/propose-power-cost', json={'metric': 'retail_industrial', 'stat': 'value', 'window': 12}).json()
    assert retail['assumption']['body']['value'] == 95.0 and 'not the tariff' in retail['assumption']['body']['rationale']
    assert c.post(m + '/propose-power-cost', json={'metric': 'fuel_mix'}).status_code == 422


def test_trailing_value_endpoint(proj):
    c, pid, m = proj
    v = c.get(m + '/value', params={'metric': 'henry_hub', 'stat': 'value', 'window': 14}).json()
    assert v['value'] == 3.0 and v['location'] == 'HENRY' and v['count'] >= 8
    assert c.get(m + '/value', params={'metric': 'lmp_da', 'stat': 'bogus'}).status_code == 422
