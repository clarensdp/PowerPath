import os,tempfile,json
os.environ['POWERPATH_DATA_DIR']=tempfile.mkdtemp(prefix='pp-connected-')
os.environ['POWERPATH_V27_AUTH_MODE']='local_only'
os.environ.pop('POWERPATH_DATABASE_URL',None)
import pytest
from fastapi.testclient import TestClient
from server.app import app,db

@pytest.fixture
def flow():
    c=TestClient(app,base_url='http://127.0.0.1')
    p=c.post('/api/projects?starter_scenario=true',json={'name':'Connected 75 MW test','target_mw':75}).json()['id']
    parcels=[str(f['properties']['PA_MCPI']) for f in c.get('/api/parcels28/catalog').json()['features'][:3]]
    for parcel in parcels:assert c.post(f'/api/projects/{p}/parcels28',json={'parcel_id':parcel}).status_code==201
    sc=c.get(f'/api/projects/{p}/scenarios').json()[0]
    return c,p,parcels,sc

def test_land_versions_scope_and_geometry(flow):
    c,p,parcels,sc=flow;u=f'/api/projects/{p}/parcels28/{parcels[0]}/feasibility'
    a=c.post(u+'/land',json={'layers':[]});assert a.status_code==200,a.text
    assert a.json()['body']['summary']['residual_geometry']
    assert not a.json()['body']['summary']['assessment_complete']
    b=c.post(u+'/land',json={'layers':[]});assert b.json()['version']==2
    assert c.get(u).json()['land']['version']==2
    assert c.get(u.replace(parcels[0],'missing')).status_code==404
    with db() as con:
        with pytest.raises(Exception):con.execute('DELETE FROM parcel_analysis_versions WHERE id=?',(a.json()['id'],))

def test_path_phases_are_saved_and_bind_finance(flow):
    c,p,parcels,sc=flow
    body={'name':'Phased grid','strategy':'grid','parcel_id':parcels[0],'capacity_basis':'IT','power_phases':[{'month':20,'mw':25},{'month':30,'mw':50},{'month':36,'mw':75}]}
    r=c.post(f'/api/projects/{p}/paths',json=body);assert r.status_code==201,r.text
    path=c.get(f'/api/projects/{p}/paths').json()[0];assert path['power_phases']==body['power_phases']
    result=c.get(f'/api/projects/{p}/paths/{path["id"]}/schedule-impact',params={'source_scenario_id':sc['id']});assert result.status_code==200,result.text
    rows=result.json()['revised']['power_periods']
    assert next(r for r in rows if r['month']==20)['available_it_mw']==25


def test_connected_three_parcel_report_and_stale_runs(flow,monkeypatch):
    from tests.site_energy_samples import MockTransport
    c,p,parcels,sc=flow
    monkeypatch.setattr(app.state.site_energy.http,'transport',MockTransport())
    project=f'/api/projects/{p}'
    cases=[]
    for i,parcel in enumerate(parcels):
        base=f'{project}/parcels28/{parcel}/feasibility'
        assert c.post(base+'/land',json={}).status_code==200
        infra=c.post(base+'/infrastructure');assert infra.status_code==200,infra.text
        assert infra.json()['body']['grid_infrastructure']['transmission_line']['features']
        study=None
        if i==0:
            eid=c.post(project+'/evidence',json={'title':'Synthetic utility letter','category':'utility'}).json()['id']
            assert c.post(project+f'/evidence/{eid}/file',files={'attachment':('utility.txt',b'Synthetic test only','text/plain')}).status_code==200
            study=c.put(base.replace('/feasibility','/energy/utility-study'),json={'evidence_id':eid,'source_date':'2026-01-01',
                'source_url':'https://example.gov/study','notes':'Synthetic utility letter for isolated testing','capacity_mw':97.5,
                'connection_cost_usd':2000000,'energization_date':'2027-01-01'})
            assert study.status_code==200,study.text
        grid={'phases':[{'month':12+i*12,'mw':97.5}],'price_mwh':70}
        gas={'mw':97.5,'month':24,'efficiency':.5,'fuel_usd_mmbtu':5,'emissions_kg_mmbtu':53,'capex_m':60,'variable_opex_mwh':10}
        solar={'system':{'capacity_kw':10000},'month':24,'capex_m':12,'fixed_opex_year_m':.2,'monthly_mwh':[500,600]*6}
        alternatives=[dict(grid={'use_utility_study':True,'price_mwh':75} if study else grid),
                      dict(gas=gas),dict(grid=grid,solar=solar),dict(grid={**grid,'phases':[{'month':24,'mw':50}]},gas={**gas,'mw':47.5},solar=solar)]
        for index,inputs in enumerate(alternatives):
            body={'name':f'Case {index}','scenario_id':sc['id'],'rationale':'Explicit synthetic engineering assumptions',**inputs}
            saved=c.post(base+'/power-cases',json=body);assert saved.status_code==201,saved.text
            case_id=saved.json()['id'];run=c.post(base+'/power-cases/'+case_id+'/run');assert run.status_code==201,run.text
            result=run.json()['body']
            for period in result['periods']:
                assert sum(period['energy_mwh'].values())==pytest.approx(period['facility_load_mwh'])
                assert period['operating_it_mw']*result['pue']<=period['firm_gross_mw']+1e-7
            assert result['full_operation_month'] is not None
            if inputs.get('gas'):
                assert result['totals']['direct_co2_tonnes']>0
                sample=next(r for r in result['periods'] if r['energy_mwh']['gas'])
                assert sample['gas_fuel_mmbtu']==pytest.approx(sample['energy_mwh']['gas']*3.412141633/.5)
            if inputs.get('solar'):
                assert result['totals']['solar_mwh']>0
                assert len({r['energy_mwh']['solar'] for r in result['periods'] if r['energy_mwh']['solar']})>=2
            if study and index==0:
                assert result['power_capex_m']==2
                assert result['engine_inputs']['powerCapacityAssumptions']['phases']==[{'month':13,'mw':97.5}]
                assert result['utility_study']['evidence_sha256']
            cases.append((base,case_id,body,result['finance']['npvM']))
    assert len({entry[3] for entry in cases})>3
    reports=project+'/site-feasibility/reports'
    response=c.post(reports);assert response.status_code==201,response.text
    report=response.json();assert len(report['snapshot']['parcels'])==3
    assert all(len(item['cases'])==4 for item in report['snapshot']['parcels'])
    assert c.get(reports+'/'+report['id']).json()['current']
    base,case_id,body,_=cases[0]
    edited=c.put(base+'/power-cases/'+case_id+'?expected_version=1',json={**body,'rationale':'Changed assumption invalidates old calculation'})
    assert edited.status_code==200,edited.text
    comparison=c.get(project+'/site-feasibility').json()
    changed=next(case for parcel in comparison['parcels'] for case in parcel['cases'] if case['id']==case_id)
    assert changed['status']=='stale' and changed['result'] is None
    assert c.post(reports).status_code==409
    assert not c.get(reports+'/'+report['id']).json()['current']
    assert c.post(base+'/power-cases/'+case_id+'/run').status_code==201
    assert c.post(reports).json()['version']==2


def test_solar_only_has_no_firm_capacity(flow):
    c,p,parcels,sc=flow
    b=f'/api/projects/{p}/parcels28/{parcels[0]}/feasibility/power-cases'
    case={'name':'Solar only','scenario_id':sc['id'],'rationale':'A hypothetical sunny parcel',
          'solar':{'system':{'capacity_kw':10000},'month':12,'capex_m':10,'fixed_opex_year_m':.25,'monthly_mwh':[700]*12}}
    saved=c.post(b,json=case);assert saved.status_code==201,saved.text
    run=c.post(b+'/'+saved.json()['id']+'/run');assert run.status_code==201,run.text
    data=run.json()['body']
    assert data['first_operation_month'] is None
    assert all(r['operating_it_mw']==0 for r in data['periods'])
    assert sum(r['unused_solar_mwh'] for r in data['periods'])>0


def test_pvwatts_monthly_profile_reaches_parcel_case(flow, monkeypatch):
    c, project, parcels, scenario = flow
    from io import BytesIO
    def transport(request, timeout):
        assert '/pvwatts/' in request.full_url
        monthly = [400000, 500000] * 6
        return BytesIO(json.dumps({'outputs':{'ac_annual':sum(monthly),'ac_monthly':monthly},
                                   'station_info':{'location':'Synthetic weather'},'version':'8.0'}).encode())
    monkeypatch.setenv('POWERPATH_NREL_API_KEY','SYNTHETIC_TEST_KEY')
    monkeypatch.setattr(app.state.site_energy.http,'transport',transport)
    route=f'/api/projects/{project}/parcels28/{parcels[0]}/feasibility/power-cases'
    payload={'name':'Grid plus solar','scenario_id':scenario['id'],'rationale':'Synthetic API acceptance inputs',
             'grid':{'phases':[{'month':12,'mw':97.5}],'price_mwh':80},
             'solar':{'system':{'capacity_kw':10000},'month':12,'capex_m':10,'fixed_opex_year_m':.2}}
    new=c.post(route,json=payload)
    assert new.status_code==201,new.text
    run=c.post(route+'/'+new.json()['id']+'/run')
    assert run.status_code==201,run.text
    assert run.json()['body']['solar_source']['monthly_mwh']==[400,500]*6
    assert run.json()['body']['totals']['solar_mwh']>0
