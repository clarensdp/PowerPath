"""Run separately: imports the repository's required-auth test harness."""
import os
os.environ.pop('POWERPATH_DATABASE_URL', None)
os.environ.pop('POWERPATH_IDENTITY_PROVIDER', None)
from tests.v271.test_v271_required_auth import C, H


def test_underwriting_roles_and_tenants():
    pid = C.post('/api/projects?starter_scenario=true', headers=H('analyst', 'a'), json={'name': 'UW auth', 'target_mw': 100}).json()['id']
    u = f'/api/projects/{pid}/underwriting'
    for path in ('/assumptions', '/priorities', '/changes', '/ledger', '/backtest', '/brief'):
        assert C.get(u + path).status_code == 401
        assert C.get(u + path, headers=H('other')).status_code == 403
        assert C.get(u + path, headers=H('viewer')).status_code == 200, path
    body = {'key': 'pue', 'value': 1.25, 'rationale': 'Design basis PUE from mechanical consultant'}
    assert C.post(u + '/assumptions', headers=H('viewer'), json=body).status_code == 403
    r = C.post(u + '/assumptions', headers=H('analyst'), json=body)
    assert r.status_code == 201, r.text
    change = r.json()['change']['id']
    # Accepting changes the approved case: approver only.
    assert C.post(u + f'/approvals/{change}/accept', headers=H('analyst'), json={'note': 'self-approve'}).status_code == 403
    assert C.post(u + f'/approvals/{change}/accept', headers=H('approver'), json={'note': 'IC approved'}).status_code == 200


def test_market_routes_follow_roles():
    pid = C.post('/api/projects?starter_scenario=true', headers=H('analyst', 'a'), json={'name': 'Market auth', 'target_mw': 100}).json()['id']
    m = f'/api/projects/{pid}/market'
    assert C.get(m + '/catalog').status_code == 401
    assert C.get(m + '/catalog', headers=H('other')).status_code == 403
    assert C.get(m + '/catalog', headers=H('viewer')).status_code == 200
    body = {'metric': 'fwd', 'location': 'X', 'unit': 'USD/MWh', 'source': 'Broker', 'license': 'Internal use', 'as_of': '2026-11-20',
            'observations': [{'period': '2027-01', 'value': 60}]}
    assert C.post(m + '/import', headers=H('viewer'), json=body).status_code == 403
    assert C.post(m + '/import', headers=H('analyst'), json=body).status_code == 201
