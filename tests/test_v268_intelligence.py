"""Integration gates for each of five PowerPath intelligence milestones.
These are synthetic test rows, NOT real queue projects or utility service commitments.
"""
import os,tempfile,unittest,json
TD=tempfile.TemporaryDirectory(prefix='powerpath_v268_')
os.environ['POWERPATH_DATA_DIR']=TD.name
from fastapi.testclient import TestClient
from server.app import app,db
from server.seed_demo import seed
from agents.run_live import live_available

PID='demo-campus-001'; OTHER='other-project'
U=f'/api/projects/{PID}/intelligence'
BASE='https://www.pjm.com/planning/services-requests/interconnection-queues'
CSV1='record_id,name,status,planned_date,capacity_mw,state\nA1,SYNTHETIC Queue A,Study,2029-01-01,300,PA\nA2,SYNTHETIC Queue B,Study,2030-01-01,150,NJ\n'
CSV2='record_id,name,status,planned_date,capacity_mw,state\nA1,SYNTHETIC Queue A,Restudy,2029-07-01,300,PA\nA3,SYNTHETIC Queue C,Study,2031-01-01,90,PA\n'

def batch(text,url=BASE):return {'source_key':'PJM_QUEUE','source_url':url,'csv_text':text,'source_published_date':'2026-10-01','import_label':'analyst_upload'}

class FiveMilestones(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    seed();cls.c=TestClient(app,base_url='http://127.0.0.1')
 def test_01_canonical_source_registry_and_immutability(self):
    sources=self.c.get('/api/intelligence/sources').json()
    self.assertEqual(len(sources),3);self.assertTrue(all(s['utility_available_mw'] is None for s in sources))
    r=self.c.post(U+'/snapshots',json=batch(CSV1));self.assertEqual(r.status_code,201,r.text)
    self.assertEqual(r.json()['changes'],0)
    self.assertEqual(self.c.post(U+'/snapshots',json=batch(CSV1)).status_code,409)
    self.assertEqual(self.c.post(U+'/snapshots',json=batch(CSV2,url='https://evil.example.invalid/')).status_code,422)
    self.assertEqual(self.c.post(U+'/snapshots',json=batch(CSV2.replace('A3','A1'))).status_code,422)
 def test_02_diff_provenance_and_project_isolation(self):
    r=self.c.post(U+'/snapshots',json=batch(CSV2));self.assertEqual(r.status_code,201,r.text)
    self.assertEqual(r.json()['changes'],3)
    changes=self.c.get(U+'/changes').json();self.assertEqual(len(changes),3)
    self.assertEqual({x['change_type'] for x in changes},{'updated','added','removed'})
    self.assertTrue(any('status' in c['delta'] for c in changes))
    snaps=self.c.get(U+'/snapshots').json();self.assertEqual(len(snaps),2)
    self.assertEqual(len(snaps[0]['data_sha256']),64)
    other=self.c.post('/api/projects',json={'name':'Other company project'}).json()['id'];self.__class__.other=other
    self.assertEqual(self.c.get(f'/api/projects/{other}/intelligence/changes').json(),[])
    self.assertEqual(self.c.get(f'/api/projects/{other}/intelligence/snapshots').json(),[])
 def test_03_human_review_no_auto_change(self):
    change=next(x for x in self.c.get(U+'/changes').json() if x['change_type']=='updated')
    m=next(x for x in self.c.get(f'/api/projects/{PID}/milestones').json() if x['path_id']=='demo-path-grid')
    self.__class__.milestone=m;self.__class__.change=change
    old=self.c.get(f'/api/projects/{PID}/paths/demo-path-grid/schedule').json()
    p=self.c.post(U+'/proposals',json={'change_id':change['id'],'milestone_id':m['id'],'proposed_delay_months':22,'reason':'Synthetic customer relevance hypothesis; requires independent utility study.'})
    self.assertEqual(p.status_code,201,p.text);self.__class__.proposal=p.json()['id']
    self.assertEqual(self.c.get(f'/api/projects/{PID}/paths/demo-path-grid/schedule').json(),old)
    bad=self.c.post(f'/api/projects/{self.other}/intelligence/proposals',json={'change_id':change['id'],'milestone_id':m['id'],'proposed_delay_months':8,'reason':'Cross project invalid link'})
    self.assertEqual(bad.status_code,422)
 def test_04_independent_readonly_finance_impact_and_approval(self):
    pre=self.c.get(f'/api/projects/{PID}/paths/demo-path-grid/schedule').json()
    scenarios=self.c.get(f'/api/projects/{PID}/scenarios').json()
    baseline=next(s for s in scenarios if s['mode']=='underwrite' and not s['config'].get('powerPathLink'))
    r=self.c.get(U+'/proposals/'+self.proposal+'/impact');self.assertEqual(r.status_code,200,r.text[:200])
    x=r.json();self.assertFalse(x['persisted_changes']);self.assertFalse(x['valuation_allowed']);self.assertEqual(x['before']['delay_months'],pre['effective_delay_months'])
    self.assertEqual(self.c.get(f'/api/projects/{PID}/paths/demo-path-grid/schedule').json(),pre)
    approved=self.c.post(U+'/proposals/'+self.proposal+'/approve');self.assertEqual(approved.status_code,200,approved.text)
    self.assertEqual(self.c.post(U+'/proposals/'+self.proposal+'/approve').status_code,409)
    sched=self.c.get(f'/api/projects/{PID}/paths/demo-path-grid/schedule').json();self.assertGreaterEqual(sched['effective_delay_months'],22)
    self.assertFalse(sched['ready_to_assert_delivery'])
    v=self.c.post(f'/api/projects/{PID}/paths/demo-path-grid/sensitivity-v263',json={'source_scenario_id':baseline['id']})
    self.assertEqual(v.status_code,201,v.text[:200]);self.assertFalse(v.json()['valuation_allowed'])
    baseline_after=next(s for s in self.c.get(f'/api/projects/{PID}/scenarios').json() if s['id']==baseline['id'])
    self.assertEqual(baseline_after['config'],baseline['config'])
 def test_05_ten_role_council_offline_and_no_unapproved_tools(self):
    self.assertFalse(live_available()) # testing environment must not have explicit opt-in
    r=self.c.post(f'/api/projects/{PID}/agents/meetings',json={'mission':'Identify due diligence blockers and advise on public-source drift, without making any external decisions.'})
    self.assertEqual(r.status_code,201,r.text)
    x=r.json();self.assertEqual(x['mode'],'OFFLINE_RULES');self.assertEqual(x['api_calls'],0);self.assertEqual(len(x['roles']),10)
    detail=self.c.get(f'/api/projects/{PID}/agents/meetings/{x["id"]}').json();self.assertEqual(len(detail['messages']),10)
    self.assertTrue(all(m['mode']=='OFFLINE_RULES' for m in detail['messages']))
    self.assertEqual(self.c.get(f'/api/projects/{self.other}/agents/meetings/{x["id"]}').status_code,404)
    with db() as con:
      self.assertTrue(con.execute('SELECT COUNT(*) FROM activity WHERE project_id=? AND action=?',(PID,'agents.offline_review')).fetchone()[0]>=1)

if __name__=='__main__': unittest.main()
