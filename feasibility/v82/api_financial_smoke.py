"""Run the preview API smoke in an isolated local-auth process."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from server.app import app, db, calculate

fixture=json.loads((Path(__file__).parent/'fixtures_v8_2.json').read_text())
client=TestClient(app,base_url='http://127.0.0.1')
response=client.post('/api/projects',json={'name':'Financial bridge 200MW fixture', 'target_mw':200})
assert response.status_code==201,response.text
pid=response.json()['id']
base=calculate('defaults27',{})['project']
base['buildings']=[{'name':'One campus','itMW':200,'constructionStart':1,'constructionMonths':12,'powerMonth':1,'leaseMonth':1,'leaseTermMonths':120}]
base['months']=120
s=client.post(f'/api/projects/{pid}/scenarios',json={'name':'Original', 'mode':'underwrite', 'config':base})
assert s.status_code==201,s.text
sid=s.json()['id']
f=client.post(f'/api/projects/{pid}/feasibility',json={'site_name':'Site G','mode':'default','inputs':fixture['inputs']['Site G']})
assert f.status_code==201,f.text
rid=f.json()['run_id']
with db() as con:
    n_before=con.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
    s_before=con.execute('SELECT COUNT(*) FROM scenarios').fetchone()[0]
    f_before=con.execute('SELECT COUNT(*) FROM feasibility_v82_runs').fetchone()[0]
p=client.post(f'/api/projects/{pid}/feasibility/{rid}/financial-preview',json={'source_scenario_id':sid})
assert p.status_code==200,p.text
r=p.json()
assert r['source_scenario_id']==sid and r['source_scenario_version']==1
assert {x['path_key'] for x in r['paths']}=={'grid','hyb'}
assert r['paths'][0]['name']=='Hybrid' and r['paths'][0]['first_power_month']==17
assert r['paths'][0]['summary']['first_rent_month']==17
assert r['paths'][0]['assumptions']['extra_capex_musd']==90.4
assert r['certification']['g5']=='BLOCKED'
assert r['persisted_changes'] is False
with db() as con:
    assert n_before==con.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
    assert s_before==con.execute('SELECT COUNT(*) FROM scenarios').fetchone()[0]
    assert f_before==con.execute('SELECT COUNT(*) FROM feasibility_v82_runs').fetchone()[0]
# Other project's scenario must never be readable by the preview route.
q=client.post('/api/projects',json={'name':'Other Project','target_mw':200})
assert q.status_code==201
pid2=q.json()['id']
f2=client.post(f'/api/projects/{pid2}/feasibility',json={'site_name':'Site G','inputs':fixture['inputs']['Site G']})
assert f2.status_code==201
bad=client.post(f'/api/projects/{pid2}/feasibility/{f2.json()["run_id"]}/financial-preview',json={'source_scenario_id':sid})
assert bad.status_code==404,bad.text
# Tampered input or drifting config cannot be silently used for financial comparisons.
with db() as con:
    old=con.execute('SELECT config_sha256 FROM feasibility_v82_runs WHERE id=?',(rid,)).fetchone()[0]
    con.execute('UPDATE feasibility_v82_runs SET config_sha256=? WHERE id=?',('x'*64,rid))
invalid=client.post(f'/api/projects/{pid}/feasibility/{rid}/financial-preview',json={'source_scenario_id':sid})
assert invalid.status_code==409,invalid.text
with db() as con:
    con.execute('UPDATE feasibility_v82_runs SET config_sha256=? WHERE id=?',(old,rid))
print('FINANCIAL PREVIEW API: OK, read-only, project-scoped and config drift protected')
