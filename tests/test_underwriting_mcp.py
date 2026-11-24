"""MCP server exposes read tools over the authenticated API and no approval tools."""
import asyncio, os, tempfile, json
os.environ.setdefault('POWERPATH_DATA_DIR', tempfile.mkdtemp(prefix='pp-mcp-'))
os.environ['POWERPATH_V27_AUTH_MODE'] = 'local_only'
os.environ.pop('POWERPATH_DATABASE_URL', None)
import pytest
pytest.importorskip('mcp')
from fastapi.testclient import TestClient
from server.app import app
from tools import powerpath_mcp as M


@pytest.fixture
def wired(monkeypatch):
    monkeypatch.setattr(M, '_client', lambda transport=None: TestClient(app, base_url='http://127.0.0.1'))
    c = TestClient(app, base_url='http://127.0.0.1')
    pid = c.post('/api/projects?starter_scenario=true', json={'name': 'MCP test', 'target_mw': 150}).json()['id']
    return pid


def test_tool_surface_is_read_only():
    tools = {t.name: t for t in asyncio.run(M.server.list_tools())}
    assert set(tools) == {'list_projects', 'project_brief', 'diligence_priorities', 'deliverability', 'returns_bridge',
                          'pending_changes', 'forecast_track_record', 'queue_summary', 'market_snapshot', 'power_plants', 'plant_capacity_factor'}
    assert all(t.annotations.read_only_hint for t in tools.values())
    assert not any('approv' in n or 'accept' in n for n in tools)


def test_tools_return_api_data(wired):
    pid = wired
    assert any(p['id'] == pid for p in M.list_projects())
    pr = M.diligence_priorities(pid)
    assert pr['priorities'] and 'base_result' in pr
    b = M.returns_bridge(pid, json.dumps({'energization_delay_months': 6}))
    assert b['total_change']['npvM'] < 0 and b['reconciliation_residual']['npvM'] == pytest.approx(0, abs=1e-9)
    assert M.returns_bridge(pid, 'not json')['error']
    assert M.deliverability(pid)['error'] == 'PowerPath returned HTTP 404'
    assert M.pending_changes(pid) == []
    assert 'top_diligence_priorities' in M.project_brief(pid)
