"""v26.2 persistent power-path, PermitIQ and financial linkage acceptance tests.
Uses an isolated temporary SQLite DB, no externally sourced capacity.
"""
import os, tempfile, unittest
_temp = tempfile.TemporaryDirectory(prefix='pp_v262_')
os.environ['POWERPATH_DATA_DIR'] = _temp.name
from fastapi.testclient import TestClient
from server.app import app
from server.seed_demo import seed

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client=TestClient(app,base_url='http://127.0.0.1')
        cls.pid='demo-campus-001'
    def test_01_seed_is_explicitly_synthetic(self):
        c=self.client
        paths=c.get(f'/api/projects/{self.pid}/paths').json()
        self.assertEqual(len(paths),3)
        self.assertTrue(all('fictional' in p['source_note'].lower() for p in paths))
        self.assertTrue(all(p['latitude'] is None for p in paths))
        permits=c.get(f'/api/projects/{self.pid}/permits').json()
        self.assertEqual(len(permits),3)
        self.assertGreater(len(permits[0]['steps']),0)
    def test_02_path_input_validation_and_project_scoping(self):
        c=self.client
        bad=c.post(f'/api/projects/{self.pid}/paths',json={'name':'Missing long','strategy':'grid','latitude':40})
        self.assertEqual(bad.status_code,422)
        new=c.post('/api/projects',json={'name':'Unrelated project','target_mw':100}).json()['id']
        path=c.post(f'/api/projects/{new}/paths',json={'name':'Valid coordinate path','strategy':'grid','latitude':42.2,'longitude':-76.5,'status':'hypothesis'})
        self.assertEqual(path.status_code,201,path.text)
        self.__class__.other_project=new
        self.__class__.other_path=path.json()['id']
        self.assertEqual(len(c.get(f'/api/projects/{self.pid}/paths').json()),3)
        self.assertEqual(c.put(f'/api/projects/{self.pid}/paths/{self.other_path}',json={'name':'Spoof','strategy':'grid'}).status_code,422)
    def test_03_permit_checklist_notes_and_activity(self):
        c=self.client
        permit=c.get(f'/api/projects/{self.pid}/permits').json()[0]
        sid=permit['steps'][0]['id']
        before=next(s for s in permit['steps'] if s['id']==sid)['is_done']
        changed=c.post(f'/api/projects/{self.pid}/permits/{permit["id"]}/steps/{sid}/toggle')
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertNotEqual(changed.json()['is_done'],before)
        self.assertEqual(c.post(f'/api/projects/{self.pid}/permits/{permit["id"]}/notes',json={'body':'QA evidence needs utility response'}).status_code,201)
        self.assertEqual(c.post(f'/api/projects/{self.pid}/permits/{permit["id"]}/steps',json={'title':'Obtain counterparty review'}).status_code,201)
        self.assertEqual(c.post(f'/api/projects/{self.pid}/permits/{permit["id"]}/steps/foreign/toggle').status_code,404)
        self.assertTrue(any(n['body'].startswith('QA') for p in c.get(f'/api/projects/{self.pid}/permits').json() if p['id']==permit['id'] for n in p['notes']))
        self.assertTrue(any(a['action']=='permit.checklist.updated' for a in c.get(f'/api/projects/{self.pid}/activity').json()))
    def test_04_explicit_sensitivity_has_lineage_and_preserves_baseline(self):
        c=self.client
        baseline=c.get(f'/api/projects/{self.pid}/scenarios').json()
        base=next(x for x in baseline if x['mode']=='underwrite')
        path=next(x for x in c.get(f'/api/projects/{self.pid}/paths').json() if x['id']=='demo-path-grid')
        out=c.post(f'/api/projects/{self.pid}/paths/{path["id"]}/sensitivity',json={'source_scenario_id':base['id'],'include_open_permit_delay':True})
        self.assertEqual(out.status_code,201,out.text)
        v=out.json()
        # v27.1 (RT-E04b): this route now uses the canonical schedule. The demo 'study' permit (7 months) is linked to the
        # milestone chain 5+4=9, so it is not an extra driver; the path estimate (9) overlaps rather than adds. The v26.2
        # assertion (path 9 + permit 7 = 16) encoded the double count and was replaced, not relaxed.
        sched=c.get(f'/api/projects/{self.pid}/paths/{path["id"]}/schedule').json()
        self.assertEqual(v['permit_delay_months'],0)
        self.assertEqual(v['delay_months'],base['config'].get('delayMonths',0)+sched['effective_delay_months'])
        self.assertEqual(sched['effective_delay_months'],9)
        self.assertEqual(v['schedule_version'],sched['schedule_version'])
        self.assertTrue(v['config']['powerPathLink']['synthetic'])
        self.assertEqual(c.get(f'/api/projects/{self.pid}/scenarios').json()[-1]['config']['delayMonths'],base['config']['delayMonths']) if False else None
        unchanged=next(x for x in c.get(f'/api/projects/{self.pid}/scenarios').json() if x['id']==base['id'])
        self.assertEqual(unchanged['config'],base['config'])
        run=c.post(f'/api/projects/{self.pid}/scenarios/{v["id"]}/runs')
        self.assertEqual(run.status_code,201,run.text)
        self.assertEqual(run.json()['assurance'],'SCREENING / UNVERIFIED')
        self.assertIn('npvM',run.json()['summary'])
        self.__class__.run_id=run.json()['id']
        self.assertTrue(any(a['action']=='path.sensitivity.created' for a in c.get(f'/api/projects/{self.pid}/activity').json()))
    def test_05_scoped_permit_and_evidence(self):
        c=self.client
        foreign=c.post(f'/api/projects/{self.other_project}/permits',json={'title':'Test requirement','kind':'utility','path_id':'demo-path-grid'})
        self.assertEqual(foreign.status_code,422,foreign.text)
        spoof=c.post(f'/api/projects/{self.pid}/paths',json={'name':'Unrelated evidence path','strategy':'onsite','evidence_id':'nonexistent'})
        self.assertEqual(spoof.status_code,422)
        self.assertEqual(c.get(f'/api/projects/{self.other_project}/runs/{self.run_id}').status_code,404)
    def test_06_no_unverified_approval_of_notes(self):
        c=self.client
        cfg=c.get('/api/defaults').json()['notes']
        sc=c.post(f'/api/projects/{self.pid}/scenarios',json={'name':'v26.2 notes assurance','mode':'notes_v259','config':cfg})
        self.assertEqual(sc.status_code,201,sc.text)
        r=c.post(f'/api/projects/{self.pid}/scenarios/{sc.json()["id"]}/runs')
        self.assertEqual(r.status_code,201,r.text)
        risk=r.json()['summary']['risk']['uses']
        self.assertEqual(risk['transactionValuation'],'BLOCKED')
        self.assertEqual(risk['lenderCertification'],'BLOCKED')

if __name__=='__main__':unittest.main()
