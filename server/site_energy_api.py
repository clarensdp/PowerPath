"""Project-scoped routes use the existing auth middleware; no public private-data alias."""
import copy
import json
import os
from datetime import date
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from server.providers.base import DataPoint, now
from server.providers.renewables.nrel import SolarSystem
from server.services import data_provenance
from server.services.site_energy_data import SiteEnergyService


class Study(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    evidence_id: str
    source_date: date
    source_url: str = Field(pattern=r'^https?://', max_length=1500)
    notes: str = Field(min_length=10, max_length=3000)
    capacity_mw: float | None = Field(default=None, ge=0, le=100000)
    connection_cost_usd: float | None = Field(default=None, ge=0, le=1e12)
    energization_date: date | None = None

    @model_validator(mode='after')
    def historical_source(self):
        if self.source_date > date.today():
            raise ValueError('Source date cannot be in the future')
        return self


class EnergySelection(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra='forbid')
    scenario_id: str
    expected_version: int = Field(ge=1)
    price_mode: Literal['assumed', 'user_supplied', 'eia_reference']
    price_mwh: float | None = Field(default=None, ge=0, le=10000)
    reference_index: int = Field(default=0, ge=0, le=1000)
    reference_period: str | None = None
    reference_coverage: str | None = None
    reference_value: float | None = None
    evidence_id: str | None = None
    rationale: str = Field(min_length=10, max_length=3000)
    solar: SolarSystem | None = None
    blend_solar: bool = False
    annual_load_mwh: float | None = Field(default=None, gt=0, le=1e10)
    solar_cost_mwh: float | None = Field(default=None, ge=0, le=10000)
    solar_self_use_pct: float = Field(default=100, ge=0, le=100)


def install(app, db, store, project_exists, audit, root, calculate):
    # Preserve the separately gated PostgreSQL runtime: it must not gain implicit DDL
    # or unreviewed cache-write policies on GET. This additive MVP uses SQLite.
    postgres = bool(os.environ.get('POWERPATH_DATABASE_URL', '').strip())
    if not postgres:
        data_provenance.initialize(db)
    service = SiteEnergyService(db, store, root)
    app.state.site_energy = service

    def check(pid):
        if postgres:
            raise HTTPException(503, 'Site energy integration awaits PostgreSQL migration/policy acceptance; existing workflows remain available')
        with db() as con:
            project_exists(con, pid)

    def evidence(con, pid, eid):
        row = con.execute('SELECT * FROM evidence WHERE project_id=? AND id=?', (pid, eid)).fetchone()
        if not row or not row['stored_filename']:
            raise HTTPException(422, 'Attach a supporting document to an evidence record in this project first')
        return dict(row)

    prefix = '/api/projects/{pid}/parcels28/{parcel}/energy'

    @app.get(prefix + '-context')
    def context(pid: str, parcel: str):
        check(pid)
        return service.context(pid, parcel)

    @app.get(prefix + '/electricity-prices')
    def electricity(pid: str, parcel: str):
        check(pid)
        return service.context(pid, parcel, category='electricity')

    @app.get(prefix + '/infrastructure')
    def infrastructure(pid: str, parcel: str):
        check(pid)
        return service.context(pid, parcel, category='infrastructure')

    @app.get(prefix + '/renewables')
    def renewables(pid: str, parcel: str):
        check(pid)
        return service.context(pid, parcel, category='renewables')

    @app.post(prefix + '/solar-estimate')
    def solar(pid: str, parcel: str, data: SolarSystem):
        check(pid)
        return service.generation(pid, parcel, data)

    @app.put(prefix + '/utility-study')
    def study(pid: str, parcel: str, data: Study):
        check(pid)
        record = service.parcel(pid, parcel)
        ts = now()
        body = {**data.model_dump(mode='json'), 'status': 'user_supplied', 'retrieved_at': ts,
                'verification': 'User transcribed from attached study; not independently verified by PowerPath',
                'parcel_source_version': record['source_version']}
        with db() as con:
            ev = evidence(con, pid, data.evidence_id)
            body['evidence_sha256'] = ev['content_hash']
            con.execute('BEGIN IMMEDIATE')
            try:
                con.execute('''INSERT INTO site_energy_studies VALUES(?,?,?,?) ON CONFLICT(project_id,parcel_id)
                    DO UPDATE SET body=excluded.body,updated_at=excluded.updated_at''', (pid, parcel, json.dumps(body), ts))
                audit(con, pid, 'site_energy.utility_study', parcel, body)
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        return body

    @app.post(prefix + '/scenario-inputs')
    def apply(pid: str, parcel: str, data: EnergySelection):
        check(pid)
        record = service.parcel(pid, parcel)
        with db() as con:
            row = con.execute('SELECT * FROM scenarios WHERE project_id=? AND id=?', (pid, data.scenario_id)).fetchone()
            if not row:
                raise HTTPException(404, 'Scenario not found in this project')
            if row['version'] != data.expected_version:
                raise HTTPException(409, 'Scenario changed; reload before selecting inputs')
            config = json.loads(row['config_json'])
            if row['mode'] != 'underwrite' or config.get('powerPathLink'):
                raise HTTPException(422, 'Select an original underwriting scenario')
            if data.evidence_id:
                evidence(con, pid, data.evidence_id)
        ts, reference = now(), None
        if data.price_mode in ('assumed', 'user_supplied'):
            if data.price_mwh is None:
                raise HTTPException(422, 'Explicit scenario price is required (85 USD/MWh is the illustrative default)')
            price, status = data.price_mwh, data.price_mode
        else:
            result = service.context(pid, parcel, category='electricity')
            points = result['electricity']['eia']['points']
            if data.reference_index >= len(points) or points[data.reference_index]['value'] is None:
                raise HTTPException(422, 'Selected public price is unavailable; choose an explicit assumption instead')
            reference = points[data.reference_index]
            if (data.reference_period, data.reference_coverage, data.reference_value) != (
                    reference['effective_date'], reference['coverage'], reference['value']):
                raise HTTPException(409, 'Public reference changed or was not explicitly selected; reload observations')
            price, status = reference['value'], 'assumed'
            if price < 0:
                raise HTTPException(422, 'Combined scenario price must be nonnegative for this engine')
        point = DataPoint(value=price, unit='USD/MWh', source_name='Explicit scenario input selection',
            retrieved_at=ts, status=status, category='scenario_delivered_cost', evidence_id=data.evidence_id,
            methodology=data.rationale, coverage='Selected parcel scenario; not a confirmed tariff').model_dump()
        renewable = None
        if data.blend_solar and data.solar is None:
            raise HTTPException(422, 'Solar system assumptions are required for blending')
        if data.solar:
            renewable = service.generation(pid, parcel, data.solar)
            if renewable['status'] != 'available':
                raise HTTPException(422, 'Solar estimate unavailable; apply price without solar or configure the provider')
            if data.blend_solar:
                if data.annual_load_mwh is None or data.solar_cost_mwh is None:
                    raise HTTPException(422, 'Blending requires assumed annual facility load and all-in solar energy cost')
                used = min(data.annual_load_mwh, renewable['points'][0]['value'] * data.solar_self_use_pct / 100)
                share = used / data.annual_load_mwh
                price = (1 - share) * price + share * data.solar_cost_mwh
                renewable['annual_cost_blend'] = {'annual_load_mwh': data.annual_load_mwh,
                    'solar_cost_mwh': data.solar_cost_mwh, 'self_use_pct': data.solar_self_use_pct,
                    'used_solar_mwh': used, 'share': share, 'blended_cost_mwh': price, 'status': 'estimated',
                    'methodology': 'Annual energy-weighted cost sensitivity, capped at load. Constant across engine months; no hourly matching, firm capacity, solar capex or tariff-demand-charge model.'}
        remaining = data_provenance.assumptions(config)
        previous_price = remaining.pop('powerCostMWh')
        effective_point = {**point, 'value': price}
        if data.blend_solar:
            effective_point.update(status='estimated', methodology=renewable['annual_cost_blend']['methodology'])
        config = copy.deepcopy(config)
        config['powerCostMWh'] = price
        config['siteEnergyInputs'] = {'parcel_id': parcel, 'parcel_source_version': record['source_version'],
            'selected_at': ts, 'price_mode': data.price_mode, 'electricity': point, 'reference': reference,
            'renewables': renewable,
            'effective_power_cost_mwh': price, 'effective_electricity': effective_point,
            'previous_power_cost': previous_price, 'remaining_assumptions': remaining}
        # Validate with the exact existing engine before saving; do not alter engine code.
        calculate('underwrite', config)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                updated = con.execute('''UPDATE scenarios SET config_json=?,version=version+1,updated_at=?
                    WHERE project_id=? AND id=? AND version=?''',
                    (json.dumps(config), ts, pid, data.scenario_id, data.expected_version))
                if updated.rowcount != 1:
                    raise HTTPException(409, 'Scenario changed; reload before selecting inputs')
                audit(con, pid, 'site_energy.inputs_selected', data.scenario_id, config['siteEnergyInputs'])
                con.execute('COMMIT')
            except Exception:
                con.execute('ROLLBACK')
                raise
        return {'id': data.scenario_id, 'version': data.expected_version + 1, 'config': config}
