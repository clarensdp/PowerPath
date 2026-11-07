"""PowerPath v8.2 screening-only feasibility snapshots (local-only additive extension)."""
from __future__ import annotations
import hashlib,json,os,secrets
from datetime import datetime,timezone
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from feasibility.v82.integration import score_one, VALID_MODES, _config
from feasibility.v82.financial_bridge import compare_paths, canonical_hash

router=APIRouter()

class FeasibilityRequest(BaseModel):
    site_name:str=Field(min_length=1,max_length=120)
    mode:str='default'
    inputs:dict
    evidence:list[dict]=Field(default_factory=list)
    gate_dependencies:dict=Field(default_factory=dict)
    milestone_schedules:dict=Field(default_factory=dict)

class FinancialPreviewRequest(BaseModel):
    source_scenario_id: str = Field(min_length=1,max_length=120)
    curtailment_allocation: str = Field(default='tenant_or_compute_operator',pattern='^(tenant_or_compute_operator|owner_contractual_revenue)$')
    acknowledge_contract_assumption: bool = False

SCHEMA='''CREATE TABLE IF NOT EXISTS feasibility_v82_runs(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 model_version TEXT NOT NULL,mode TEXT NOT NULL,config_sha256 TEXT NOT NULL,
 input_sha256 TEXT NOT NULL,input_snapshot_json TEXT NOT NULL,output_json TEXT NOT NULL,
 evidence_json TEXT NOT NULL,created_at TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS feasibility_v82_project ON feasibility_v82_runs(project_id,created_at DESC);
'''

def install(app,db):
    # This alpha has not been security reviewed for a multi-tenant deployment.
    with db() as con:con.executescript(SCHEMA)
    def authorized_or_disabled():
        if os.getenv('POWERPATH_V27_AUTH_MODE')=='required':
            raise HTTPException(503,'v8.2 feasibility API unavailable in authenticated/multi-tenant mode pending access-control review')

    @router.post('/api/projects/{pid}/feasibility',status_code=201)
    def new_run(pid:str,body:FeasibilityRequest):
        authorized_or_disabled()
        if body.mode not in VALID_MODES:raise HTTPException(422,'Unknown scoring mode')
        from server.app import project_exists
        with db() as con:
            project=project_exists(con,pid)
            target=float(project['target_mw'])
            requested=float(body.inputs.get('raw',{}).get('target') or 0)
            if abs(target-requested)>1e-6:
                raise HTTPException(422,'Feasibility target MW must match project target MW')
            try:
                result=score_one(body.site_name,body.inputs,body.mode,body.gate_dependencies,body.milestone_schedules)
            except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError) as exc:
                raise HTTPException(422,str(exc)) from exc
            now=datetime.now(timezone.utc).isoformat()
            input_snapshot={'site_name':body.site_name,'inputs':body.inputs,'mode':body.mode,
                            'gate_dependencies':body.gate_dependencies,'milestone_schedules':body.milestone_schedules}
            canonical=lambda x:json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
            digest=hashlib.sha256(canonical(input_snapshot).encode()).hexdigest()
            config_digest=hashlib.sha256(canonical(_config()).encode()).hexdigest()
            rid='fv82_'+secrets.token_hex(12)
            # Never mutate a prior result. Source confidence remains self-reported until verified.
            con.execute('INSERT INTO feasibility_v82_runs VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (rid,pid,'workbook_v8_2',body.mode,config_digest,digest,canonical(input_snapshot),
                         canonical(result),canonical(body.evidence),now))
        return {'run_id':rid,'model_version':'workbook_v8_2','source':'USER / FIXTURE INPUTS - NOT INDEPENDENTLY VERIFIED',
                'config_sha256':config_digest,'input_sha256':digest,'result':result,'created_at':now}

    @router.get('/api/projects/{pid}/feasibility')
    def latest_run(pid:str):
        authorized_or_disabled()
        from server.app import project_exists
        with db() as con:
            project_exists(con,pid)
            row=con.execute('SELECT * FROM feasibility_v82_runs WHERE project_id=? ORDER BY created_at DESC,id DESC LIMIT 1',(pid,)).fetchone()
            if not row:raise HTTPException(404,'No feasibility run for this project')
            return {'run_id':row['id'],'model_version':row['model_version'],
                    'mode':row['mode'],'result':json.loads(row['output_json']),
                    'evidence':json.loads(row['evidence_json']),'input_sha256':row['input_sha256'],
                    'config_sha256':row['config_sha256'],'created_at':row['created_at']}

    @router.get('/api/projects/{pid}/feasibility/{run_id}')
    def get_run(pid:str,run_id:str):
        authorized_or_disabled()
        from server.app import project_exists
        with db() as con:
            project_exists(con,pid)
            row=con.execute('SELECT * FROM feasibility_v82_runs WHERE id=? AND project_id=?',(run_id,pid)).fetchone()
            if not row:raise HTTPException(404,'Unknown feasibility run')
            return {'run_id':row['id'],'result':json.loads(row['output_json']),
                    'snapshot':json.loads(row['input_snapshot_json']),
                    'evidence':json.loads(row['evidence_json']),
                    'config_sha256':row['config_sha256'],'input_sha256':row['input_sha256']}
    @router.post('/api/projects/{pid}/feasibility/{run_id}/financial-preview')
    def financial_preview(pid: str, run_id: str, body: FinancialPreviewRequest):
        """Read-only comparison through existing v27.1 engine; no scenario/run writes."""
        authorized_or_disabled()
        from server.app import project_exists, scenario_exists, calculate
        with db() as con:
            project = project_exists(con,pid)
            row = con.execute('SELECT * FROM feasibility_v82_runs WHERE project_id=? AND id=?',(pid,run_id)).fetchone()
            if row is None: raise HTTPException(404,'Feasibility run not found')
            scen = scenario_exists(con,pid,body.source_scenario_id)
            if scen['mode']!='underwrite':
                raise HTTPException(422,'Financial comparison requires an underwriting scenario')
            config = json.loads(scen['config_json'])
            snapshot = json.loads(row['input_snapshot_json'])
            if canonical_hash(snapshot) != row['input_sha256']:
                raise HTTPException(409,'Feasibility input snapshot hash mismatch')
            if canonical_hash(_config()) != row['config_sha256']:
                raise HTTPException(409,'Feasibility config has changed since this immutable run; rescore with a new version first')
            if abs(float(project['target_mw'])-float(snapshot['inputs']['raw']['target']))>1e-6:
                raise HTTPException(409,'Stored feasibility and project capacity no longer agree')
        try:
            result=compare_paths(snapshot['site_name'], snapshot['inputs'], snapshot['mode'], config, calculate,
                gate_dependencies=snapshot.get('gate_dependencies'),
                milestone_schedules=snapshot.get('milestone_schedules'),
                curtailment_allocation=body.curtailment_allocation,
                acknowledge_contract_assumption=body.acknowledge_contract_assumption)
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            raise HTTPException(422,str(exc)) from exc
        result.update({'feasibility_run_id':run_id, 'feasibility_input_sha256':row['input_sha256'],
             'source_scenario_id':scen['id'],'source_scenario_version':scen['version'],
             'source_scenario_sha256':canonical_hash(config),
             'source_engine': 'engine/underwrite27.js (frozen)',
             'source_warning':'Snapshot and source scenario contain analyst/user inputs; no executed terms verified'})
        return result

    app.include_router(router)
