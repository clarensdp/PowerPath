"""PowerPath MCP server: lets Claude, Copilot or any MCP client query PowerPath.

It talks to a running PowerPath API over HTTP, so the API's tenant and role checks
apply to every call. Tools are read-only except `returns_bridge`, which computes a
what-if without saving anything. Approving or rejecting changes is deliberately not
exposed: that stays with a human approver in PowerPath.

Run (stdio):
    POWERPATH_URL=http://127.0.0.1:8768 POWERPATH_TOKEN=<session token> python -m tools.powerpath_mcp

Requires the optional dependency in requirements-mcp.txt.
"""
import json
import os

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

BASE = os.environ.get('POWERPATH_URL', 'http://127.0.0.1:8768').rstrip('/')
TIMEOUT = float(os.environ.get('POWERPATH_MCP_TIMEOUT', '60'))
READ = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
COMPUTE = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

server = MCPServer('powerpath', instructions=(
    'PowerPath underwrites data-center power delivery. Every number it returns carries a reference '
    '(assumption id, source and date, evidence id, or the engine run). Quote those references. '
    'Treat proposed changes as unapproved. Deliverability ranges and stress cases are scenario bounds, '
    'not probabilities. Never describe an interconnection queue withdrawal as freed capacity.'))


def _client(transport=None):
    headers = {'Accept': 'application/json'}
    token = os.environ.get('POWERPATH_TOKEN', '').strip()
    if token:
        headers['Authorization'] = f'Bearer {token}'
    tenant = os.environ.get('POWERPATH_TENANT', '').strip()
    if tenant:
        headers['X-PowerPath-Tenant'] = tenant
    return httpx.Client(base_url=BASE, headers=headers, timeout=TIMEOUT, transport=transport)


TRANSPORT = None  # tests inject an ASGI/WSGI transport here


def _call(method, path, **kwargs):
    with _client(TRANSPORT) as c:
        r = c.request(method, path, **kwargs)
    if r.status_code >= 400:
        try:
            detail = r.json().get('detail')
        except ValueError:
            detail = r.text[:500]
        return {'error': f'PowerPath returned HTTP {r.status_code}', 'detail': detail}
    return r.json()


def _uw(project_id, suffix):
    return f'/api/projects/{project_id}/underwriting{suffix}'


@server.tool(annotations=READ)
def list_projects() -> list | dict:
    """List the PowerPath projects this token can see (id, name, location, target MW, status)."""
    out = _call('GET', '/api/projects')
    if isinstance(out, list):
        return [{k: p.get(k) for k in ('id', 'name', 'location', 'target_mw', 'status')} for p in out]
    return out


@server.tool(annotations=READ)
def project_brief(project_id: str, scenario_id: str | None = None) -> dict:
    """Sourced brief: approved-case returns, top diligence priorities by NPV at risk,
    latest deliverability answer, pending changes and forecast track record."""
    return _call('GET', _uw(project_id, '/brief'), params={'scenario_id': scenario_id} if scenario_id else None)


@server.tool(annotations=READ)
def diligence_priorities(project_id: str, scope: str = 'project') -> dict:
    """Every underwriting input ranked by financial exposure × (1 − confidence), with source,
    verification status, NPV at risk and the next diligence action."""
    return _call('GET', _uw(project_id, '/priorities'), params={'scope': scope})


@server.tool(annotations=READ)
def deliverability(project_id: str) -> dict:
    """Latest deliverability assessment: deliverable MW and time-to-target ranges per power
    configuration, critical dependencies and what must be true."""
    out = _call('GET', _uw(project_id, '/deliverability'))
    if 'body' in out:
        body = out['body']
        return {'assessment_id': out['id'], 'version': out['version'], 'assessed_at': out['created_at'],
                'target_mw': body['target_mw'], 'target_month': body['target_month'],
                'configurations': [{k: c[k] for k in ('name', 'answer', 'deliverable_mw_at_target', 'time_to_target_month',
                                                      'meets_target_in', 'evidence_quality', 'what_must_be_true')}
                                   for c in body['configurations']], 'rules': body['rules']}
    return out


@server.tool(annotations=COMPUTE)
def returns_bridge(project_id: str, drivers: str) -> dict:
    """What-if on the approved case. `drivers` is a JSON object of assumption keys to new values,
    e.g. {"energization_delay_months": 9, "power_capex_m": 120}. Returns the change in NPV, levered
    IRR and minimum DSCR split by driver (parts sum to the total). Saves nothing."""
    try:
        parsed = json.loads(drivers)
    except ValueError:
        return {'error': 'drivers must be a JSON object'}
    return _call('POST', _uw(project_id, '/bridge'), json={'drivers': parsed})


@server.tool(annotations=READ)
def pending_changes(project_id: str) -> list | dict:
    """Changes awaiting review (new assumption versions with their returns impact, queue events
    flagged for analysis). Approval happens in PowerPath, not through this server."""
    out = _call('GET', _uw(project_id, '/changes'), params={'pending': 'true'})
    if isinstance(out, list):
        return [{'id': c['id'], 'source': c['source'], 'title': c['body'].get('title'), 'requires': c['body'].get('requires'),
                 'impact': (c['body'].get('impact') or {}).get('explanation'), 'detail': c['body'].get('detail'),
                 'created_at': c['created_at']} for c in out]
    return out


@server.tool(annotations=READ)
def forecast_track_record(project_id: str) -> dict:
    """Backtest board: how PowerPath's issued forecasts compared with what actually happened."""
    return _call('GET', _uw(project_id, '/backtest'))


@server.tool(annotations=READ)
def queue_summary(project_id: str, source: str, latitude: float | None = None, longitude: float | None = None,
                  radius_km: float = 50) -> dict:
    """Interconnection queue concentration near a site, historical withdrawal rate and median
    in-service-date slip, from the queue snapshots loaded into the project."""
    params = {'source': source, 'radius_km': radius_km}
    if latitude is not None and longitude is not None:
        params.update(latitude=latitude, longitude=longitude)
    return _call('GET', _uw(project_id, '/queue/summary'), params=params)


@server.tool(annotations=READ)
def market_snapshot(project_id: str, days: int = 30) -> dict:
    """Latest power market metrics for the project's market profile (day-ahead LMP, Henry Hub,
    spark spread, retail price, grid demand, fuel mix, estimated carbon), each with source,
    as-of date and staleness, plus gaps with reasons."""
    return _call('GET', f'/api/projects/{project_id}/market/snapshot', params={'days': days})


if __name__ == '__main__':
    server.run('stdio')
