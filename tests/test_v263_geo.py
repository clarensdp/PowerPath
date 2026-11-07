"""v26.3 source integrity, geographic import, DAG semantics and underwriting linkage."""
import os,tempfile,unittest
_temp=tempfile.TemporaryDirectory(prefix='pp_v263_')
os.environ['POWERPATH_DATA_DIR']=_temp.name
from fastapi.testclient import TestClient
from server.app import app
from server.seed_demo import seed

class GeoCriticalPathTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  seed();cls.c=TestClient(app,base_url='http://127.0.0.1');cls.pid='demo-campus-001'
 def test_01_seed_and_geographic_restrictions(self):
  rows=self.c.get(f'/api/projects/{self.pid}/geo-assets').json()
  self.assertEqual(len(rows),2)
  self.assertEqual({r['evidence_level'] for r in rows},{'secondary_extract'})
  self.assertTrue(all(r['capacity_available_mw'] is None and not r['available_power_verified'] for r in rows))
  self.assertTrue(all('upstream_source' in r['attributes'] for r in rows))
 def test_02_import_eia_csv_and_atomic_rollback(self):
  url=f'/api/projects/{self.pid}/geo-assets/import'
  csv='Plant Code,Plant Name,Latitude,Longitude,State,County,Grid Voltage (kV)\n65000,Test plant,30.0,-96.0,TX,Brazos,138\n65001,Test plant 2,31.0,-95.0,TX,Smith,69\n'
  inp={'csv_text':csv,'source_provider':'Local EIA CSV','source_url':'https://www.eia.gov/electricity/data/eia860/','vintage':'2025','evidence_level':'user_supplied'}
  r=self.c.post(url,json=inp);self.assertEqual(r.status_code,201,r.text);self.assertEqual(r.json()['count'],2)
  bad={**inp,'csv_text':csv.replace('65001','65000')}; self.assertEqual(self.c.post(url,json=bad).status_code,422)
  self.assertEqual(len(self.c.get(f'/api/projects/{self.pid}/geo-assets').json()),4)
  self.assertEqual(self.c.post(url,json=inp).status_code,409)
  self.assertEqual(len(self.c.get(f'/api/projects/{self.pid}/geo-assets').json()),4)
 def test_03_geographic_url_and_coordinates(self):
  url=f'/api/projects/{self.pid}/geo-assets'
  base={'name':'Named source','asset_type':'substation','latitude':40,'longitude':-80,'source_provider':'Public source','source_record_id':'unique','vintage':'2026'}
  self.assertEqual(self.c.post(url,json={**base,'source_url':'http://127.0.0.1/private'}).status_code,422)
  self.assertEqual(self.c.post(url,json={**base,'source_url':'https://eia.gov/','latitude':0,'longitude':0}).status_code,422)
  self.assertEqual(self.c.post(url,json={**base,'source_url':'https://eia.gov/'}).status_code,201)
 def test_04_critical_path_parallel_vs_serial(self):
  u=f'/api/projects/{self.pid}/milestones';path='demo-path-grid'
  original=self.c.get(f'/api/projects/{self.pid}/paths/{path}/schedule').json()
  self.assertEqual(original['milestone_critical_delay_months'],9)
  self.assertEqual(original['effective_delay_months'],9)
  a=self.c.post(u,json={'title':'Network-upgrade assessment','category':'interconnection','path_id':path,'delay_months':12,'status':'awaiting'}).json()
  self.assertEqual(self.c.get(f'/api/projects/{self.pid}/paths/{path}/schedule').json()['effective_delay_months'],12)
  b=self.c.post(u,json={'title':'Grid tie construction','category':'construction','path_id':path,'delay_months':3,'predecessor_id':a['id'],'status':'planned'}).json()
  new=self.c.get(f'/api/projects/{self.pid}/paths/{path}/schedule').json()
  self.assertEqual(new['milestone_critical_delay_months'],15)
  self.assertEqual(new['effective_delay_months'],15)
  cycle=self.c.put(u+'/'+a['id'],json={'title':'Network-upgrade assessment','category':'interconnection','path_id':path,'delay_months':12,'predecessor_id':b['id']})
  self.assertEqual(cycle.status_code,422)
  self.__class__.schedule_delay=new['effective_delay_months']
 def test_05_status_completion_and_scoping(self):
  other=self.c.post('/api/projects',json={'name':'Unrelated company','target_mw':90}).json()['id']
  url=f'/api/projects/{other}/milestones'
  self.assertEqual(self.c.post(url,json={'title':'Cross project','category':'utility','path_id':'demo-path-grid'}).status_code,422)
  self.assertEqual(self.c.get(f'/api/projects/{other}/paths/demo-path-grid/schedule').status_code,422)
 def test_06_immutable_underwriting_baseline_and_risk_gate(self):
  url=f'/api/projects/{self.pid}/paths/demo-path-grid/sensitivity-v263'
  base=next(s for s in self.c.get(f'/api/projects/{self.pid}/scenarios').json() if s['mode']=='underwrite')
  v=self.c.post(url,json={'source_scenario_id':base['id']});self.assertEqual(v.status_code,201,v.text)
  self.assertEqual(v.json()['incremental_delay_months'],self.schedule_delay)
  self.assertEqual(v.json()['config']['delayMonths'],base['config']['delayMonths']+self.schedule_delay)
  self.assertFalse(v.json()['valuation_allowed'])
  unchanged=next(s for s in self.c.get(f'/api/projects/{self.pid}/scenarios').json() if s['id']==base['id'])
  self.assertEqual(unchanged['config'],base['config'])
  run=self.c.post(f'/api/projects/{self.pid}/scenarios/{v.json()["id"]}/runs');self.assertEqual(run.status_code,201,run.text)
  self.assertIn('npvM',run.json()['summary'])
  self.assertEqual(run.json()['assurance'],'SCREENING / UNVERIFIED')
if __name__=='__main__':unittest.main()
