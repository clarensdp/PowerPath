"""Separate-process local API smoke test: never shares FastAPI globals with legacy tests."""
import copy,json
from pathlib import Path
from fastapi.testclient import TestClient
from server.app import app
F=json.loads((Path(__file__).parent/'fixtures_v8_2.json').read_text())
cl=TestClient(app,base_url='http://127.0.0.1')
created=cl.post('/api/projects',json={'name':'v8.2 fixture project','location':'Ohio','target_mw':300})
assert created.status_code==201,created.text
pid=created.json()['id']
body={'site_name':'Site D','mode':'default','inputs':F['inputs']['Site D']}
resp=cl.post(f'/api/projects/{pid}/feasibility',json=body)
assert resp.status_code==201,resp.text
first=resp.json()
assert first['result']['selected']=='BTM' and first['result']['first_power']==18
rid=first['run_id']
assert cl.get(f'/api/projects/{pid}/feasibility').json()['run_id']==rid
past=cl.get(f'/api/projects/{pid}/feasibility/{rid}').json()
assert past['snapshot']['mode']=='default' and past['input_sha256']==first['input_sha256']
changed=copy.deepcopy(body);changed['inputs']['raw']['btm_first']=21
r2=cl.post(f'/api/projects/{pid}/feasibility',json=changed)
assert r2.status_code==201,r2.text
assert r2.json()['run_id']!=rid
assert cl.get(f'/api/projects/{pid}/feasibility/{rid}').json()['result']['first_power']==18
print('LOCAL API POST/GET IMMUTABILITY SMOKE PASSED')
