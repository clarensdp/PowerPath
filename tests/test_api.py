"""Local backend acceptance tests; no assertions of contractual accuracy."""
import io, json, os, tempfile, unittest
from pathlib import Path

_temp=tempfile.TemporaryDirectory()
os.environ['POWERPATH_DATA_DIR']=_temp.name
from fastapi.testclient import TestClient
from server.app import app, ENGINE, sha
from server.seed_demo import seed

class ApiAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client=TestClient(app,base_url='http://127.0.0.1')

    def test_01_health_frozen_engine(self):
        v=self.client.get('/api/health').json()
        self.assertEqual(v['engine_hash'],sha(ENGINE/'underwrite25.js'))
        self.assertFalse(v['lender_grade'])
        self.assertEqual(v['authentication'],'NOT_IMPLEMENTED')

    def test_02_demo_project_is_illustrative(self):
        p=self.client.get('/api/projects').json()
        self.assertTrue(any(x['id']=='demo-campus-001' and 'Illustrative' in x['name'] for x in p))
        self.assertTrue(self.client.get('/api/defaults').json()['config']['buildings'])

    def test_03_project_and_scenario_persistence(self):
        r=self.client.post('/api/projects',json={'name':'QA Case','target_mw':75,'location':'Synthetic site'})
        self.assertEqual(r.status_code,201,r.text)
        self.__class__.pid=r.json()['id']
        c=self.client.get('/api/defaults').json()['config'];c['months']=48
        sc=self.client.post(f'/api/projects/{self.pid}/scenarios',json={'name':'QA base','mode':'underwrite','config':c})
        self.assertEqual(sc.status_code,201,sc.text)
        self.__class__.sid=sc.json()['id'];self.__class__.config=c
        self.assertEqual(len(self.client.get(f'/api/projects/{self.pid}/scenarios').json()),1)

    def test_04_calculation_run_is_versioned(self):
        r=self.client.post(f'/api/projects/{self.pid}/scenarios/{self.sid}/runs')
        self.assertEqual(r.status_code,201,r.text)
        d=r.json();self.assertEqual(len(d['rows']),48)
        self.assertEqual(d['assurance'],'SCREENING / UNVERIFIED')
        self.assertLess(d['summary']['sourcesUsesMaxResidual'],1e-6)
        self.__class__.rid=d['id']
        csv=self.client.get(f'/api/projects/{self.pid}/runs/{d["id"]}/csv')
        self.assertIn('SCREENING ONLY',csv.text)
        self.assertIn(d['engine_sha256'],csv.text)
        config=dict(self.config);config['rentPerKwMonth']=185
        rr=self.client.put(f'/api/projects/{self.pid}/scenarios/{self.sid}',json={'name':'QA base','mode':'underwrite','config':config})
        self.assertEqual(rr.json()['version'],2)
        d2=self.client.post(f'/api/projects/{self.pid}/scenarios/{self.sid}/runs').json()
        self.assertEqual(d2['scenario_version'],2)
        self.assertNotEqual(d2['summary']['npvM'],d['summary']['npvM'])
        old=self.client.get(f'/api/projects/{self.pid}/runs/{d["id"]}').json()
        self.assertEqual(old['scenario_version'],1)
        self.assertEqual(old['input']['rentPerKwMonth'],self.config['rentPerKwMonth'])

    def test_05_reject_invalid_engine_config(self):
        sc=self.client.post(f'/api/projects/{self.pid}/scenarios',json={'name':'Bad units','mode':'underwrite','config':{'pue':0}})
        bad=self.client.post(f'/api/projects/{self.pid}/scenarios/{sc.json()["id"]}/runs')
        self.assertEqual(bad.status_code,422)

    def test_06_facility_engine_outputs(self):
        d=self.client.get('/api/defaults').json()
        cfg={'project':{**d['config'],'months':120,'sponsorCommitmentM':800,'powerResponsibility':'tenant_direct','distributionPolicy':'none'},'facilities':d['facilities']}
        sc=self.client.post(f'/api/projects/{self.pid}/scenarios',json={'name':'QA facilities','mode':'facilities','config':cfg})
        self.assertEqual(sc.status_code,201,sc.text)
        out=self.client.post(f'/api/projects/{self.pid}/scenarios/{sc.json()["id"]}/runs')
        self.assertEqual(out.status_code,201,out.text)
        self.assertIn('assurance',out.json()['summary'])
        self.assertLess(out.json()['summary']['maxDebtResidual'],1e-6)

    def test_07_evidence_immutable_and_scoped(self):
        r=self.client.post(f'/api/projects/{self.pid}/evidence',json={'title':'Illustrative test PDF','category':'Lease','evidence_status':'unverified'})
        self.assertEqual(r.status_code,201,r.text)
        eid=r.json()['id']
        attach=self.client.post(f'/api/projects/{self.pid}/evidence/{eid}/file',files={'attachment':('demo.txt',b'synthetic evidence', 'text/plain')})
        self.assertEqual(attach.status_code,200,attach.text)
        self.assertEqual(self.client.get(f'/api/projects/{self.pid}/evidence/{eid}/download').content,b'synthetic evidence')
        self.assertEqual(self.client.post(f'/api/projects/{self.pid}/evidence/{eid}/file',files={'attachment':('again.txt',b'x')}).status_code,409)
        self.assertEqual(self.client.get(f'/api/projects/demo-campus-001/evidence/{eid}/download').status_code,404)
        self.assertEqual(self.client.get(f'/api/projects/demo-campus-001/runs/{self.rid}').status_code,404)

    def test_08_activity_and_ui(self):
        events=self.client.get(f'/api/projects/{self.pid}/activity').json()
        self.assertTrue(any(x['action']=='run.completed' for x in events))
        html=self.client.get('/')
        self.assertEqual(html.status_code,200)
        self.assertIn('PowerPath',html.text)
        self.assertEqual(self.client.get('/assets/app.js').status_code,200)

if __name__=='__main__':unittest.main()
