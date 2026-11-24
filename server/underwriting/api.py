"""HTTP routes for the v31.5 underwriting layer.

All routes live under /api/projects/{pid}/underwriting so the existing tenant/role
gate applies: viewers read, analysts propose and run, and anything under
/approvals/ needs an approver. SQLite local workspace only until the PostgreSQL
runtime accepts these tables (same convention as the v31 site-energy routes).
"""
import os
from datetime import date as Date
from typing import Any, Literal

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from server.underwriting import bridge as B
from server.underwriting import brief as BR
from server.underwriting import changes as CH
from server.underwriting import deliverability as DV
from server.underwriting import evidence as EV
from server.underwriting import forecasts as FC
from server.underwriting import ledger as LG
from server.underwriting import store as S


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class BaseCaseIn(Strict):
    scenario_id: str


class AssumptionIn(Strict):
    key: str
    scope: str = Field(default='project', pattern=r'^(project|parcel:[^\s]{1,120}|path:[^\s]{1,120})$')
    value: Any
    downside_value: Any = None
    source_kind: Literal[EV.SOURCE_KINDS] = 'assumption'
    source_name: str = Field(default='', max_length=300)
    source_date: Date | None = None
    source_url: str | None = Field(default=None, max_length=1500, pattern=r'^https?://')
    evidence_id: str | None = None
    verification: Literal[tuple(EV.VERIFICATION)] = 'assumed'
    rationale: str = Field(min_length=10, max_length=3000)


class DecisionIn(Strict):
    note: str = Field(default='', max_length=3000)


class Dependency(Strict):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=200)
    kind: Literal['network_upgrade', 'substation', 'permit', 'equipment', 'construction', 'agreement', 'other'] = 'other'
    status: Literal['not_started', 'in_progress', 'complete'] = 'not_started'
    start_month: int = Field(default=1, ge=1, le=600)
    complete_month: int | None = Field(default=None, ge=0, le=600)
    earliest_months: int = Field(default=0, ge=0, le=240)
    likely_months: int = Field(default=0, ge=0, le=240)
    latest_months: int = Field(default=0, ge=0, le=240)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    evidence_id: str | None = None


class Study(Strict):
    type: Literal['feasibility', 'system_impact', 'facilities', 'power_flow_screen', 'utility_letter', 'other']
    issuer: str = Field(max_length=200)
    study_date: Date | None = None
    max_mw: float | None = Field(default=None, ge=0, le=100000)
    evidence_id: str | None = None


class Source(Strict):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=200)
    kind: Literal['grid', 'bridge_generation', 'dedicated_generation', 'onsite_solar', 'wind', 'storage'] = 'grid'
    label: Literal[DV.LABELS]
    mw: float = Field(gt=0, le=100000)
    earliest_month: int = Field(ge=1, le=600)
    likely_month: int = Field(ge=1, le=600)
    latest_month: int = Field(ge=1, le=600)
    until_month: int | None = Field(default=None, ge=1, le=600)
    firm: bool | None = None
    capex_m: float = Field(default=0, ge=0, le=100000)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    evidence_id: str | None = None
    source_date: Date | None = None
    study: Study | None = None


class Configuration(Strict):
    name: str = Field(min_length=2, max_length=120)
    source_ids: list[str] = Field(min_length=1, max_length=50)


class DeliverabilityIn(Strict):
    target_mw: float | None = Field(default=None, gt=0, le=100000)
    target_month: int = Field(ge=1, le=600)
    basis: Literal['IT', 'gross'] = 'gross'
    sources: list[Source] = Field(min_length=1, max_length=50)
    dependencies: list[Dependency] = Field(default_factory=list, max_length=100)
    configurations: list[Configuration] = Field(default_factory=list, max_length=10)
    issue_forecasts: bool = True


class FromDeliverability(Strict):
    assessment_id: str
    configuration: str
    case: Literal['upside', 'base', 'downside']


class BridgeIn(Strict):
    scenario_id: str | None = None
    scope: str = 'project'
    drivers: dict[str, Any] = Field(default_factory=dict)
    order: list[str] | None = None
    from_deliverability: FromDeliverability | None = None


class OutcomeIn(Strict):
    observed: float
    observed_at: Date
    evidence_id: str | None = None
    notes: str = Field(default='', max_length=2000)


class QueueEntry(Strict):
    queue_id: str = Field(min_length=1, max_length=80)
    name: str = Field(default='', max_length=200)
    status: Literal[CH.QUEUE_STATUSES]
    fuel: str = Field(default='', max_length=60)
    mw: float = Field(ge=0, le=100000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    poi: str = Field(default='', max_length=200)
    queue_date: Date | None = None
    requested_cod: Date | None = None
    in_service_date: Date | None = None


class Site(Strict):
    name: str = Field(default='', max_length=200)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class QueueSnapshotIn(Strict):
    source: str = Field(min_length=2, max_length=200)
    as_of: Date
    source_url: str | None = Field(default=None, max_length=1500, pattern=r'^https?://')
    sites: list[Site] = Field(default_factory=list, max_length=50)
    radius_km: float = Field(default=50, gt=0, le=500)
    entries: list[QueueEntry] = Field(max_length=20000)


class ForecastIn(Strict):
    adapter: Literal['json', 'csv'] = 'json'
    provider: str = Field(min_length=2, max_length=120)
    product: str = Field(default='', max_length=200)
    market: str = Field(default='', max_length=60)
    location: str = Field(default='', max_length=120)
    issued_at: Date
    license: str = Field(min_length=3, max_length=300)
    source_url: str | None = Field(default=None, max_length=1500, pattern=r'^https?://')
    periods: list[dict] | None = Field(default=None, max_length=1200)
    csv: str | None = Field(default=None, max_length=500_000)


class CaseIn(Strict):
    start_price: float | None = Field(default=None, ge=0, le=10000)
    escalation_pct: float = Field(default=0, ge=-20, le=50)


class PriceScenarioIn(Strict):
    scenario_id: str | None = None
    forecast_id: str | None = None
    blend_months: int = Field(default=12, ge=0, le=120)
    cases: dict[Literal['low', 'base', 'high'], CaseIn]


def install(app, db, project_exists, audit, calculate, schedule_for, path_inputs):
    postgres = bool(os.environ.get('POWERPATH_DATABASE_URL', '').strip())
    if not postgres:
        S.initialize(db)
    root = '/api/projects/{pid}/underwriting'

    def open_project(con, pid):
        if postgres:
            raise HTTPException(503, 'The underwriting layer awaits PostgreSQL migration acceptance; use the local SQLite workspace')
        return dict(project_exists(con, pid))

    def actor(request):
        return getattr(request.state, 'user_id', None) or 'local'

    def guard(fn):
        try:
            return fn()
        except HTTPException:
            raise
        except LookupError as exc:
            raise HTTPException(404, str(exc).strip("'"))
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    # --------------------------------------------------------------- evidence
    @app.put(root + '/base-case')
    def set_base(pid: str, data: BaseCaseIn):
        with db() as con:
            open_project(con, pid)
            row = con.execute('SELECT mode FROM scenarios WHERE project_id=? AND id=?', (pid, data.scenario_id)).fetchone()
            if not row or row['mode'] != 'underwrite':
                raise HTTPException(422, 'Choose an underwriting scenario in this project')
            con.execute('INSERT INTO uw_settings VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET base_scenario_id=excluded.base_scenario_id,updated_at=excluded.updated_at',
                        (pid, data.scenario_id, S.now()))
            audit(con, pid, 'underwriting.base_case.set', data.scenario_id, {})
        return {'project_id': pid, 'base_scenario_id': data.scenario_id}

    @app.get(root + '/assumptions')
    def list_assumptions(pid: str):
        with db() as con:
            open_project(con, pid)
            return EV.register(con, pid)

    @app.post(root + '/assumptions', status_code=201)
    def propose(pid: str, data: AssumptionIn, request: Request):
        body = data.model_dump(mode='json')
        body['proposed_by'] = actor(request)
        with db() as con:
            open_project(con, pid)

            def go():
                with S.transaction(con):
                    proposal = EV.propose(con, pid, body)
                    change = CH.on_assumption(con, pid, calculate, proposal)
                    audit(con, pid, 'underwriting.assumption.proposed', proposal['id'], {'key': body['key'], 'scope': body['scope']})
                return {'assumption': proposal, 'change': change}
            return guard(go)

    @app.get(root + '/approved-case')
    def approved_case(pid: str, scenario_id: str | None = None):
        with db() as con:
            open_project(con, pid)

            def go():
                case = EV.approved_case(con, pid, scenario_id)
                from server.underwriting import drivers as DR
                return {**{k: case[k] for k in ('scenario_id', 'scenario_version', 'assignments', 'fingerprint')},
                        'result': DR.summarize(calculate('underwrite', case['config'])), 'calculated_at': S.now()}
            return guard(go)

    @app.get(root + '/priorities')
    def priorities(pid: str, scenario_id: str | None = None, scope: str = 'project'):
        with db() as con:
            open_project(con, pid)
            return guard(lambda: EV.priorities(con, pid, calculate, scenario_id, scope))

    # ------------------------------------------------------- change pipeline
    @app.get(root + '/changes')
    def list_changes(pid: str, pending: bool = False):
        with db() as con:
            open_project(con, pid)
            return CH.listing(con, pid, pending)

    def decision(pid, change_id, verdict, data, request):
        with db() as con:
            open_project(con, pid)

            def go():
                with S.transaction(con):
                    out = CH.decide(con, pid, calculate, change_id, verdict, data.note, actor(request))
                    audit(con, pid, f'underwriting.change.{verdict}', change_id, {'note': data.note})
                return out
            return guard(go)

    @app.post(root + '/approvals/{change_id}/accept')
    def accept(pid: str, change_id: str, data: DecisionIn, request: Request):
        return decision(pid, change_id, 'accepted', data, request)

    @app.post(root + '/approvals/{change_id}/reject')
    def reject(pid: str, change_id: str, data: DecisionIn, request: Request):
        return decision(pid, change_id, 'rejected', data, request)

    @app.post(root + '/approvals/{change_id}/acknowledge')
    def acknowledge(pid: str, change_id: str, data: DecisionIn, request: Request):
        return decision(pid, change_id, 'acknowledged', data, request)

    @app.post(root + '/changes/scan-utility-studies')
    def scan(pid: str):
        with db() as con:
            open_project(con, pid)

            def go():
                with S.transaction(con):
                    found = CH.scan_utility_studies(con, pid, calculate)
                    if found:
                        audit(con, pid, 'underwriting.utility_studies.scanned', pid, {'changes': [c['id'] for c in found]})
                return {'changes': found}
            return guard(go)

    @app.post(root + '/queue/snapshots', status_code=201)
    def queue_snapshot(pid: str, data: QueueSnapshotIn):
        with db() as con:
            open_project(con, pid)

            def go():
                with S.transaction(con):
                    out = CH.ingest_queue(con, pid, data.model_dump(mode='json'))
                    audit(con, pid, 'underwriting.queue.snapshot', out['snapshot_id'], {'source': data.source, 'entries': out['entries']})
                return out
            return guard(go)

    @app.get(root + '/queue/summary')
    def queue_summary(pid: str, source: str, latitude: float | None = None, longitude: float | None = None, radius_km: float = 50):
        sites = [{'latitude': latitude, 'longitude': longitude}] if latitude is not None and longitude is not None else []
        with db() as con:
            open_project(con, pid)
            return guard(lambda: CH.queue_summary(con, pid, source, sites, radius_km))

    # --------------------------------------------------------- deliverability
    @app.post(root + '/deliverability', status_code=201)
    def deliverability(pid: str, data: DeliverabilityIn):
        payload = data.model_dump(mode='json')
        with db() as con:
            project = open_project(con, pid)
            payload['target_mw'] = payload['target_mw'] or project['target_mw']
            if not payload['target_mw']:
                raise HTTPException(422, 'Set a target MW on the project or in the request')

            def go():
                result = DV.assess(payload, pid, con)
                with S.transaction(con):
                    v = con.execute('SELECT COALESCE(MAX(version),0)+1 FROM uw_deliverability WHERE project_id=?', (pid,)).fetchone()[0]
                    aid, ts = S.uid(), S.now()
                    body = {**result, 'inputs': payload}
                    con.execute('INSERT INTO uw_deliverability VALUES(?,?,?,?,?)', (aid, pid, v, S.encode(body), ts))
                    issued = []
                    if payload['issue_forecasts']:
                        for conf in result['configurations']:
                            subject = f'{conf["name"]} · {result["target_mw"]:g} MW by month {result["target_month"]}'
                            source = {'deliverability_id': aid, 'version': v, 'method_version': result['method_version']}
                            issued.append(LG.issue(con, pid, 'time_to_power_month', subject, conf['time_to_target_month'], source)['id'])
                            issued.append(LG.issue(con, pid, 'deliverable_mw_at_target', subject, conf['deliverable_mw_at_target'], source)['id'])
                    audit(con, pid, 'underwriting.deliverability.assessed', aid, {'version': v, 'forecasts': issued})
                return {'id': aid, 'version': v, 'created_at': ts, 'forecast_ids': issued, 'body': body}
            return guard(go)

    @app.get(root + '/deliverability')
    def latest_deliverability(pid: str):
        with db() as con:
            open_project(con, pid)
            r = S.one(con, 'SELECT * FROM uw_deliverability WHERE project_id=? ORDER BY version DESC LIMIT 1', (pid,))
            if not r:
                raise HTTPException(404, 'No deliverability assessment yet')
            return r

    # ------------------------------------------------------------------ bridge
    @app.post(root + '/bridge')
    def run_bridge(pid: str, data: BridgeIn):
        with db() as con:
            open_project(con, pid)

            def go():
                case = EV.approved_case(con, pid, data.scenario_id, data.scope)
                changes = dict(data.drivers)
                if data.from_deliverability:
                    f = data.from_deliverability
                    a = S.one(con, 'SELECT * FROM uw_deliverability WHERE project_id=? AND id=?', (pid, f.assessment_id))
                    if not a:
                        raise LookupError('Deliverability assessment not found')
                    changes = {**DV.bridge_drivers(a['body'], f.configuration, f.case), **changes}
                result = B.run(calculate, case['config'], changes, data.order)
                result['approved_case'] = {k: case[k] for k in ('scenario_id', 'scenario_version', 'assignments', 'fingerprint')}
                return result
            return guard(go)

    @app.get(root + '/paths/{pathid}/bridge')
    def path_bridge(pid: str, pathid: str, scenario_id: str | None = None, include_approved: bool = True):
        with db() as con:
            open_project(con, pid)
            schedule = schedule_for(con, pid, pathid)
            row = con.execute('SELECT * FROM power_paths WHERE project_id=? AND id=?', (pid, pathid)).fetchone()
            path = path_inputs(con, dict(row))

            def go():
                case = EV.approved_case(con, pid, scenario_id)
                if not include_approved:  # match the raw-scenario schedule-impact table
                    sid, version, cfg = EV.base_config(con, pid, scenario_id)
                    case = {**case, 'config': cfg, 'assignments': {}, 'approved_not_applied': case['assignments']}
                changes = B.path_drivers(case['config'], path, schedule)
                if not changes:
                    raise ValueError('This path makes no schedule, capex, energy or capacity change to bridge')
                result = B.run(calculate, case['config'], changes, ['grid_capacity', 'energization_delay_months', 'construction_cost_mw', 'power_cost_mwh'])
                result['path'] = {'id': pathid, 'name': path['name'], 'strategy': path['strategy']}
                result['approved_not_applied'] = case.get('approved_not_applied', {})
                return result
            return guard(go)

    # ------------------------------------------------------------------ ledger
    @app.get(root + '/ledger')
    def ledger_entries(pid: str, kind: str | None = None):
        with db() as con:
            open_project(con, pid)
            return LG.entries(con, pid, kind)

    @app.post(root + '/ledger/{forecast_id}/outcome', status_code=201)
    def outcome(pid: str, forecast_id: str, data: OutcomeIn):
        with db() as con:
            open_project(con, pid)

            def go():
                with S.transaction(con):
                    out = LG.resolve(con, pid, forecast_id, data.observed, data.observed_at.isoformat(), data.evidence_id, data.notes)
                    audit(con, pid, 'underwriting.forecast.resolved', forecast_id, out['body'])
                return out
            return guard(go)

    @app.get(root + '/backtest')
    def backtest(pid: str):
        with db() as con:
            open_project(con, pid)
            return LG.board(con, pid)

    # --------------------------------------------------------------- forecasts
    @app.post(root + '/forecasts', status_code=201)
    def import_forecast(pid: str, data: ForecastIn):
        meta = data.model_dump(mode='json', exclude={'adapter', 'periods', 'csv'})
        with db() as con:
            open_project(con, pid)

            def go():
                if data.adapter == 'csv':
                    if not data.csv:
                        raise ValueError('Provide csv text with period,p10,p50,p90')
                    body = FC.ADAPTERS['csv'](meta, data.csv)
                else:
                    if not data.periods:
                        raise ValueError('Provide periods')
                    body = FC.ADAPTERS['json'](meta, data.periods)
                with S.transaction(con):
                    out = FC.save(con, pid, body)
                    audit(con, pid, 'underwriting.forecast.imported', out['id'], {'provider': body['provider'], 'coverage': body['coverage']})
                return out
            return guard(go)

    @app.get(root + '/forecasts')
    def list_forecasts(pid: str):
        with db() as con:
            open_project(con, pid)
            return FC.listing(con, pid)

    @app.post(root + '/price-scenarios')
    def price_scenarios(pid: str, data: PriceScenarioIn):
        with db() as con:
            open_project(con, pid)

            def go():
                case = EV.approved_case(con, pid, data.scenario_id)
                forecast = FC.get(con, pid, data.forecast_id)['body'] if data.forecast_id else None
                out = FC.run_scenarios(calculate, case['config'], {k: v.model_dump() for k, v in data.cases.items()}, forecast, data.blend_months)
                out['approved_case'] = {k: case[k] for k in ('scenario_id', 'scenario_version', 'assignments', 'fingerprint')}
                return out
            return guard(go)

    # ------------------------------------------------------------------- brief
    @app.get(root + '/brief')
    def project_brief(pid: str, scenario_id: str | None = None):
        with db() as con:
            project = open_project(con, pid)
            return guard(lambda: BR.build(con, pid, calculate, project, scenario_id))
