"""Project/parcel-scoped connected feasibility. Local SQLite MVP."""
import json
import os
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from permitting.footprint import assess
from starlette.concurrency import run_in_threadpool
from permitting.land_sources import fetch_layers
from permitting.official_gis import remote_enabled
from server.services import feasibility_store as fs

class LandRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    layers:list[dict]=Field(default_factory=list,max_length=12)
    official:bool=False
    consent_remote:bool=False
    slope_threshold_pct:float=Field(default=15,gt=0,le=100,allow_inf_nan=False)


def install(app,db,store,project_exists,calculate):
    if not os.environ.get('POWERPATH_DATABASE_URL'):fs.initialize(db)
    energy=app.state.site_energy
    def check(pid,parcel=None):
        if os.environ.get('POWERPATH_DATABASE_URL'):
            raise HTTPException(503,'Connected feasibility awaits PostgreSQL migration acceptance')
        with db() as con:
            project_exists(con,pid)
            if parcel is not None and not con.execute('SELECT 1 FROM parcel_shortlist28 WHERE project_id=? AND parcel_id=?',(pid,parcel)).fetchone():
                raise HTTPException(404,'Parcel is not shortlisted in this project')
        return energy.parcel(pid,parcel) if parcel else None
    base='/api/projects/{pid}/parcels28/{parcel}/feasibility'

    @app.get(base)
    def parcel_analysis(pid:str,parcel:str):
        p=check(pid,parcel)
        with db() as con:
            return {'parcel':p,'land':fs.latest(con,pid,parcel,'land'),'infrastructure':fs.latest(con,pid,parcel,'infrastructure')}

    @app.post(base+'/land')
    async def land(pid:str,parcel:str,request:Request):
        raw=bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw)>3_000_000:raise HTTPException(413,'Land layers exceed 3 MB')
        try:body=LandRequest.model_validate_json(raw)
        except ValueError as exc:raise HTTPException(422,str(exc))
        p=check(pid,parcel);layers=body.layers;stats={};warnings=[]
        if body.official:
            if not body.consent_remote or not remote_enabled():raise HTTPException(422,'Remote GIS requires operator enablement and explicit consent')
            extra,stats,warnings=await run_in_threadpool(fetch_layers,p['feature']['geometry'],body.slope_threshold_pct)
            layers=[*layers,*extra]
        try:result=await run_in_threadpool(assess,p['feature']['geometry'],layers,parcel_source=p['source'])
        except (ValueError,TypeError) as exc:raise HTTPException(422,str(exc))
        result.update(parcel_source_version=p['source_version'],official_services=stats,persisted=True,inputs={**body.model_dump(),'resolved_layers':layers})
        result['warnings']+=warnings
        with db() as con:return fs.save(con,pid,parcel,'land',result)

    @app.post(base+'/infrastructure')
    def infrastructure(pid:str,parcel:str):
        check(pid,parcel)
        result=energy.context(pid,parcel,category='infrastructure')
        with db() as con:return fs.save(con,pid,parcel,'infrastructure',result)

    from server.services.power_dispatch import PowerCase, model, target_it
    from server.providers.base import now
    from server.parcels28 import score
    import uuid
    project_base='/api/projects/{pid}/site-feasibility'

    def study_for(con,pid,parcel):
        row=con.execute('SELECT body FROM site_energy_studies WHERE project_id=? AND parcel_id=?',(pid,parcel)).fetchone()
        return json.loads(row['body']) if row else None

    def case_inputs(con,pid,parcel,body,source_version,case_version=None):
        row=con.execute('SELECT * FROM scenarios WHERE project_id=? AND id=?',(pid,body['scenario_id'])).fetchone()
        if not row or row['mode']!='underwrite':raise HTTPException(422,'Choose a project underwriting scenario')
        config=json.loads(row['config_json'])
        if config.get('engineVersion')!='27.1.0' or config.get('powerPathLink') or config.get('powerTranches'):
            raise HTTPException(422,'Choose an original 27.1.0 scenario without separately entered power tranches')
        project=project_exists(con,pid)
        if abs(target_it(config)-project['target_mw'])>1e-6:
            raise HTTPException(422,'Underwriting building IT MW must match the project target')
        study=study_for(con,pid,parcel) if (body.get('grid') or {}).get('use_utility_study') else None
        if (body.get('grid') or {}).get('use_utility_study'):
            if not study or study.get('parcel_source_version')!=source_version:
                raise HTTPException(422,'Select a utility study attached to this parcel version')
        metadata=config.get('siteEnergyInputs') or {}
        if body.get('grid') and body['grid']['price_mwh'] is None and metadata.get('parcel_id') not in (None,parcel):
            raise HTTPException(422,'Enter an explicit grid price or choose a base scenario with price evidence for this parcel')
        return {'case_version':case_version,'case':body,'config':config,'base_version':row['version'],'study':study,
                'parcel_source_version':source_version,'model_version':'parcel-dispatch-1'}

    @app.post(base+'/power-cases',status_code=201)
    def create_case(pid:str,parcel:str,body:PowerCase):
        p=check(pid,parcel);data=body.model_dump();case_id=uuid.uuid4().hex
        with db() as con:
            case_inputs(con,pid,parcel,data,p['source_version'])
            con.execute('INSERT INTO parcel_power_cases VALUES(?,?,?,?,?,?)',(case_id,pid,parcel,1,fs.encode(data),now()))
        return {'id':case_id,'version':1,'body':data}

    @app.put(base+'/power-cases/{case_id}')
    def update_case(pid:str,parcel:str,case_id:str,expected_version:int,body:PowerCase):
        p=check(pid,parcel);data=body.model_dump()
        with db() as con:
            case_inputs(con,pid,parcel,data,p['source_version'])
            count=con.execute('UPDATE parcel_power_cases SET version=version+1,body=?,updated_at=? WHERE id=? AND project_id=? AND parcel_id=? AND version=?',
                (fs.encode(data),now(),case_id,pid,parcel,expected_version)).rowcount
        if not count:raise HTTPException(409,'Case changed or no longer exists. Reload before saving.')
        return {'id':case_id,'version':expected_version+1,'body':data}

    @app.post(base+'/power-cases/{case_id}/run',status_code=201)
    def run_case(pid:str,parcel:str,case_id:str):
        p=check(pid,parcel)
        with db() as con:
            row=con.execute('SELECT * FROM parcel_power_cases WHERE project_id=? AND parcel_id=? AND id=?',(pid,parcel,case_id)).fetchone()
            if not row:raise HTTPException(404,'Power case not found')
            body=json.loads(row['body']);inputs=case_inputs(con,pid,parcel,body,p['source_version'],row['version'])
        solar=body.get('solar');profile=None;solar_source=None
        if solar:
            profile=solar['monthly_mwh']
            if profile is None:
                from server.providers.renewables.nrel import SolarSystem
                solar_source=energy.generation(pid,parcel,SolarSystem(**solar['system']))
                profile=solar_source.get('monthly_mwh')
                if profile is None:raise HTTPException(422,solar_source.get('error') or 'PVWatts monthly estimates unavailable. Provide explicit monthly assumptions.')
            else:solar_source={'status':'assumed','monthly_mwh':profile}
        try:result=model(body,inputs['config'],calculate,inputs['study'],profile)
        except ValueError as exc:raise HTTPException(422,str(exc))
        result.update(solar_source=solar_source,inputs=inputs,case_version=row['version'])
        run_id=uuid.uuid4().hex
        with db() as con:
            con.execute('INSERT INTO parcel_power_results VALUES(?,?,?,?,?,?)',(run_id,pid,case_id,fs.fingerprint(inputs),fs.encode(result),now()))
        return {'id':run_id,'body':result}

    def comparison(pid,include_periods=False,connection=None,only_parcel=None):
        from contextlib import nullcontext
        with (nullcontext(connection) if connection is not None else db()) as con:
            project=dict(project_exists(con,pid));parcels=[]
            shortlist=con.execute('SELECT parcel_id FROM parcel_shortlist28 WHERE project_id=? ORDER BY parcel_id',(pid,)).fetchall()
            for item in shortlist:
                parcel=item['parcel_id']
                if only_parcel and parcel != only_parcel:continue
                record=store.get(parcel,pid)
                if not record:continue
                feature=json.loads(record['feature_json']);version=record['version_id']
                land=fs.latest(con,pid,parcel,'land');infra=fs.latest(con,pid,parcel,'infrastructure')
                study=study_for(con,pid,parcel)
                factors=[json.loads(r['body']) for r in con.execute('SELECT body FROM parcel_assessments28 WHERE project_id=? AND parcel_id=? ORDER BY factor',(pid,parcel))]
                cases=[];missing=[]
                if not land or not land['body']['summary']['assessment_complete']:missing.append('Land constraints incomplete')
                if not infra:missing.append('Infrastructure assessment missing')
                else:
                    missing.extend(f'{kind} unavailable' for kind,result in infra['body']['grid_infrastructure'].items() if result['status']!='available' or not result['features'])
                if not study:missing.append('Utility study missing')
                if study and study.get('parcel_source_version')!=version:missing.append('Utility study refers to a different parcel source version')
                for row in con.execute('SELECT * FROM parcel_power_cases WHERE project_id=? AND parcel_id=? ORDER BY id',(pid,parcel)):
                    case=json.loads(row['body']);run=con.execute('SELECT * FROM parcel_power_results WHERE project_id=? AND case_id=? ORDER BY rowid DESC LIMIT 1',(pid,row['id'])).fetchone()
                    try:current=fs.fingerprint(case_inputs(con,pid,parcel,case,version,row['version']))
                    except HTTPException:current=None
                    valid=run is not None and run['fingerprint']==current
                    result=json.loads(run['body']) if valid else None
                    if result and not include_periods:
                        result={k:v for k,v in result.items() if k not in ('periods','engine_inputs','inputs')}
                    cases.append({'id':row['id'],'version':row['version'],'body':case,'status':'current' if valid else 'stale' if run else 'not_run',
                                  'run_id':run['id'] if valid else None,'run_date':run['created_at'] if valid else None,'result':result})
                if not cases:missing.append('No parcel power cases')
                if any(c['status']!='current' for c in cases):missing.append('Power cases require calculation')
                parcels.append({'parcel_id':parcel,'feature':feature,'source_version':version,'land':land,'infrastructure':infra,
                                'utility_study':study,'manual_assessment':score(factors),'analyst_factors':factors,'cases':cases,'missing_evidence':missing})
            return {'project':project,'parcels':parcels,'limitations':['Preliminary GIS and modeled power screening. Utility service and land development rights require independent confirmation.']}

    @app.get(base+'/comparison')
    def parcel_comparison(pid:str,parcel:str):
        check(pid,parcel)
        return comparison(pid,include_periods=True,only_parcel=parcel)

    @app.get(project_base)
    def compare(pid:str):
        check(pid);return comparison(pid)

    @app.post(project_base+'/reports',status_code=201)
    def save_report(pid:str):
        check(pid)
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            try:
                snapshot=comparison(pid,include_periods=True,connection=con)
                if not snapshot['parcels']:raise HTTPException(422,'Shortlist parcels first')
                if any(c['status']!='current' for p in snapshot['parcels'] for c in p['cases']):
                    raise HTTPException(409,'Calculate outstanding power cases before saving the report')
                version=con.execute('SELECT COALESCE(MAX(version),0)+1 FROM feasibility_reports WHERE project_id=?',(pid,)).fetchone()[0]
                report_id=uuid.uuid4().hex;stamp=now();digest=fs.fingerprint(snapshot)
                con.execute('INSERT INTO feasibility_reports VALUES(?,?,?,?,?,?)',(report_id,pid,version,digest,fs.encode(snapshot),stamp))
                con.execute('COMMIT')
            except Exception:con.execute('ROLLBACK');raise
        return {'id':report_id,'version':version,'created_at':stamp,'fingerprint':digest,'current':True,'snapshot':snapshot}

    @app.get(project_base+'/reports')
    def reports(pid:str):
        check(pid)
        with db() as con:
            return [dict(r) for r in con.execute('SELECT id,version,created_at FROM feasibility_reports WHERE project_id=? ORDER BY version DESC',(pid,))]

    @app.get(project_base+'/reports/{report_id}')
    def report(pid:str,report_id:str):
        check(pid)
        with db() as con:
            row=con.execute('SELECT * FROM feasibility_reports WHERE project_id=? AND id=?',(pid,report_id)).fetchone()
            if not row:raise HTTPException(404,'Report not found')
        current=fs.fingerprint(comparison(pid,include_periods=True))==row['fingerprint']
        return {'id':report_id,'version':row['version'],'created_at':row['created_at'],'fingerprint':row['fingerprint'],
                'current':current,'snapshot':json.loads(row['body'])}
