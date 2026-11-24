"""Project-scoped market data routes: /api/projects/{pid}/market/*.

Project scoping keeps licensed imports inside the tenant and lets the existing role gate
apply (viewers read; analysts set the profile, import and propose).
"""
import os
from datetime import date as Date
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from server.market import providers as P
from server.market import service as M
from server.underwriting import changes as CH
from server.underwriting import evidence as EV
from server.underwriting import store as S


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class ProfileIn(Strict):
    state: str | None = Field(default=None, pattern=r'^[A-Z]{2}$')
    ba: str | None = Field(default=None, pattern=r'^[A-Z0-9-]{2,10}$')
    nyiso_zone: Literal[P.NYISO_ZONES] | None = None
    heat_rate: float = Field(default=7.0, ge=5, le=15)


class Obs(Strict):
    period: str = Field(pattern=r'^\d{4}-\d{2}(-\d{2})?$')
    value: float


class ImportIn(Strict):
    metric: str = Field(pattern=r'^[a-z0-9_]{2,60}$', description='e.g. pjm_west_forward, ercot_north_rt')
    location: str = Field(min_length=1, max_length=80)
    unit: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=2, max_length=200, description='e.g. FactSet, Bloomberg, Platts, Ask the Grid export')
    license: str = Field(min_length=3, max_length=300)
    as_of: Date
    observations: list[Obs] = Field(min_length=1, max_length=20000)


class ProposeIn(Strict):
    metric: str
    location: str | None = None
    stat: str = 'avg'
    window: int = Field(default=30, ge=1, le=730)
    adder_mwh: float = Field(default=0, ge=0, le=1000, description='Transmission / capacity / delivery adder on top of a wholesale price')
    downside_pct: float = Field(default=25, ge=0, le=300)
    rationale: str = Field(default='', max_length=2000)


def install(app, db, project_exists, audit, calculate):
    postgres = bool(os.environ.get('POWERPATH_DATABASE_URL', '').strip())
    if not postgres:
        M.initialize(db)
    root = '/api/projects/{pid}/market'

    def open_project(con, pid):
        if postgres:
            raise HTTPException(503, 'Market data awaits PostgreSQL migration acceptance; use the local SQLite workspace')
        return dict(project_exists(con, pid))

    def profile_of(con, pid):
        r = con.execute('SELECT body FROM mk_profiles WHERE project_id=?', (pid,)).fetchone()
        import json
        return {**M.DEFAULT_PROFILE, **(json.loads(r['body']) if r else {})}

    def guard(fn):
        try:
            return fn()
        except HTTPException:
            raise
        except P.MarketError as exc:
            raise HTTPException(502, str(exc))
        except LookupError as exc:
            raise HTTPException(404, str(exc).strip("'"))
        except ValueError as exc:
            raise HTTPException(422, str(exc))

    @app.get(root + '/catalog')
    def catalog(pid: str):
        with db() as con:
            open_project(con, pid)
            imported = [{'metric': r['metric'], 'location': r['location'], 'observations': r['n'], 'latest': r['p'], 'source': r['source']}
                        for r in con.execute('SELECT metric, location, COUNT(*) n, MAX(period) p, MAX(source) source FROM mk_obs WHERE scope=? GROUP BY metric, location', (f'project:{pid}',))]
        return {'public': {k: {kk: v[kk] for kk in ('label', 'unit', 'frequency', 'location', 'stats', 'source')} for k, v in M.CATALOG.items()},
                'imported': imported, 'nyiso_zones': list(P.NYISO_ZONES),
                'eia_key_configured': bool(os.environ.get(P.EIA_KEY_ENV, '').strip())}

    @app.get(root + '/profile')
    def get_profile(pid: str):
        with db() as con:
            open_project(con, pid)
            return profile_of(con, pid)

    @app.put(root + '/profile')
    def put_profile(pid: str, data: ProfileIn):
        import json
        with db() as con:
            open_project(con, pid)
            body = data.model_dump()
            con.execute('INSERT INTO mk_profiles VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET body=excluded.body, updated_at=excluded.updated_at',
                        (pid, json.dumps(body), M.now()))
            audit(con, pid, 'market.profile.set', pid, body)
        return body

    @app.get(root + '/snapshot')
    def snapshot(pid: str, days: int = 30, live: bool = True):
        if not 7 <= days <= 365:
            raise HTTPException(422, 'days must be between 7 and 365')
        with db() as con:
            open_project(con, pid)
            return guard(lambda: M.snapshot(con, profile_of(con, pid), days, live=live))

    @app.get(root + '/series')
    def get_series(pid: str, metric: str, location: str | None = None, start: Date | None = None, end: Date | None = None, live: bool = True):
        end = end or Date.today()
        start = start or Date.fromordinal(end.toordinal() - 30)
        if start > end:
            raise HTTPException(422, 'start must be on or before end')
        with db() as con:
            open_project(con, pid)
            prof = profile_of(con, pid)

            def go():
                if not metric.startswith('imported:') and metric not in M.CATALOG:
                    raise ValueError(f'Unknown metric "{metric}"')
                loc = location or ('HENRY' if metric == 'henry_hub' else prof.get(M.CATALOG[metric]['profile']) if metric in M.CATALOG else None)
                if not loc:
                    raise ValueError('Give a location or set it in the market profile')
                if metric in ('lmp_da', 'spark_spread') and loc not in P.NYISO_ZONES:
                    raise ValueError(f'Unknown NYISO zone "{loc}". Zones: {", ".join(P.NYISO_ZONES)}')
                s = M.series(con, metric, loc, start, end, pid, heat_rate=prof['heat_rate'], live=live)
                spec = M.CATALOG.get(metric, {})
                return {**s, 'unit': spec.get('unit'), 'source': spec.get('source'), 'source_url': spec.get('url'), 'frequency': spec.get('frequency'), 'stats': spec.get('stats', ['value'])}
            return guard(go)

    @app.get(root + '/value')
    def trailing(pid: str, metric: str, stat: str = 'avg', window: int = 30, location: str | None = None, live: bool = True):
        if not 1 <= window <= 730:
            raise HTTPException(422, 'window must be between 1 and 730')
        with db() as con:
            open_project(con, pid)
            prof = profile_of(con, pid)

            def go():
                spec = M.CATALOG.get(metric)
                if not spec and not metric.startswith('imported:'):
                    raise ValueError(f'Unknown metric "{metric}"')
                if spec and stat not in spec['stats']:
                    raise ValueError(f'Stat for {metric} must be one of {", ".join(spec["stats"])}')
                loc = location or ('HENRY' if metric == 'henry_hub' else prof.get(spec['profile']) if spec else None)
                if not loc:
                    raise ValueError('Give a location or set it in the market profile')
                value, first, last, n = M.trailing_value(con, metric, loc, stat, window, pid, live=live, heat_rate=prof['heat_rate'])
                return {'metric': metric, 'location': loc, 'stat': stat, 'value': value, 'unit': spec['unit'] if spec else None,
                        'first': first, 'last': last, 'count': n, 'source': spec['source'] if spec else 'licensed import', 'calculated_at': M.now()}
            return guard(go)

    @app.post(root + '/import', status_code=201)
    def import_series(pid: str, data: ImportIn):
        with db() as con:
            open_project(con, pid)

            def go():
                with S.transaction(con):
                    out = M.import_series(con, pid, data.model_dump(mode='json'), S.uid)
                    audit(con, pid, 'market.import', out['id'], {'metric': out['metric'], 'source': data.source, 'license': data.license, 'count': out['count']})
                return out
            return guard(go)

    @app.post(root + '/propose-power-cost', status_code=201)
    def propose_power_cost(pid: str, data: ProposeIn):
        """Turn a market average into a proposed power_cost_mwh assumption (enters review)."""
        with db() as con:
            open_project(con, pid)
            prof = profile_of(con, pid)

            def go():
                spec = M.CATALOG.get(data.metric)
                if not spec and not data.metric.startswith('imported:'):
                    raise ValueError(f'Unknown metric "{data.metric}"')
                if data.metric in ('fuel_mix', 'ba_demand', 'henry_hub'):
                    raise ValueError('Use a power price metric (lmp_da, retail_industrial, retail_commercial or an imported price series)')
                loc = data.location or (prof.get(spec['profile']) if spec else None)
                if not loc:
                    raise ValueError('Give a location or set it in the market profile')
                value, first, last, n = M.trailing_value(con, data.metric, loc, data.stat, data.window, pid, heat_rate=prof['heat_rate'])
                price = round(value + data.adder_mwh, 4)
                label = spec['label'] if spec else data.metric
                wholesale = data.metric == 'lmp_da' or data.metric.startswith('imported:')
                source_name = (f'{spec["source"] if spec else data.metric}, {loc}, {data.stat} over {n} '
                               f'{"months" if spec and spec["frequency"] == "monthly" else "periods" if not spec else "days"} {first} to {last}'
                               + (f' + ${data.adder_mwh:g}/MWh delivery adder' if data.adder_mwh else ''))
                why = (data.rationale.strip() + ' ' if data.rationale.strip() else '') + (
                    'Wholesale energy price only; delivered cost also carries transmission, capacity and utility charges.' if wholesale and not data.adder_mwh else
                    'Statewide average retail price; not the tariff for this site.' if not wholesale else 'Wholesale price plus a stated delivery adder.')
                with S.transaction(con):
                    proposal = EV.propose(con, pid, {
                        'key': 'power_cost_mwh', 'scope': 'project', 'value': price,
                        'downside_value': round(price * (1 + data.downside_pct / 100), 4),
                        'source_kind': 'third_party_forecast' if data.metric.startswith('imported:') else 'public_data',
                        'source_name': source_name[:300], 'source_date': last if len(last) == 10 else last + '-01',
                        'source_url': (P.NYISO_DAM.rsplit('/', 1)[0] + '/' if data.metric == 'lmp_da' else spec.get('url')) if spec else None,
                        'evidence_id': None, 'verification': 'observed', 'rationale': f'{label} from PowerPath market data. {why}'[:3000],
                        'proposed_by': 'market-data'})
                    change = CH.on_assumption(con, pid, calculate, proposal)
                    audit(con, pid, 'market.power_cost.proposed', proposal['id'], {'metric': data.metric, 'location': loc, 'value': price})
                return {'assumption': proposal, 'change': change, 'market_value': value, 'adder_mwh': data.adder_mwh, 'window': {'first': first, 'last': last, 'count': n}}
            return guard(go)
