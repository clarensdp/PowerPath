import os,tempfile,unittest,json
from datetime import date,timedelta
os.environ['POWERPATH_DATA_DIR']=tempfile.mkdtemp(prefix='pp28_')
from fastapi.testclient import TestClient
from server.app import app
from server.parcels28 import score,Assessment

class ParcelTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=TestClient(app,base_url='http://127.0.0.1')
  cls.pid=cls.c.post('/api/projects',json={'name':'Parcel integration test','target_mw':100}).json()['id']
  cls.cat=cls.c.get('/api/parcels28/catalog').json()
  cls.parcel=str(cls.cat['features'][0]['properties']['PA_MCPI'])
  cls.url=f'/api/projects/{cls.pid}/parcels28'
 def test_01_real_catalog(self):
  self.assertEqual(len(self.cat['features']),120)
  self.assertEqual(len(set(str(f['properties']['PA_MCPI']) for f in self.cat['features'])),120)
  self.assertIn('loudoun.gov',self.cat['powerpath_source']['layer_url'])
  for f in self.cat['features']:
   self.assertIn(f['geometry']['type'],['Polygon','MultiPolygon'])
   self.assertGreaterEqual(f['properties']['PA_LEGAL_SQFT'],871200)
 def test_02_unknown_and_invalid_assessment(self):
  d=self.c.get(self.url+'/'+self.parcel).json()
  self.assertIsNone(d['assessment']['score']);self.assertEqual(d['assessment']['coverage_pct'],0)
  self.assertEqual(self.c.post(self.url,json={'parcel_id':'not-a-parcel'}).status_code,404)
  self.assertEqual(self.c.post(self.url,json={'parcel_id':self.parcel}).status_code,201)
  r=self.c.put(self.url+'/'+self.parcel+'/assessment',json={'factor':'power','gate':'pass','rating':5,'source_url':'javascript:alert(1)','source_date':str(date.today()),'notes':'a real rationale'})
  self.assertEqual(r.status_code,422)
 def test_03_coverage_and_critical_gate(self):
  fresh=str(date.today());rows=[{'factor':f,'rating':5,'gate':'pass','source_date':fresh} for f in ['land','environment','delivery','connectivity']]
  self.assertIsNone(score(rows)['score']) # non-critical factors alone cannot yield a score
  rows += [{'factor':f,'rating':4,'gate':'pass','source_date':fresh} for f in ['power','permitting']]
  self.assertEqual(score(rows)['score'],90)
  rows[0]['gate']='fail';self.assertEqual(score(rows)['status'],'blocked');self.assertIsNone(score(rows)['score'])
 def test_04_stale_adverse_gate(self):
  old=str(date.today()-timedelta(days=181))
  a=score([{'factor':'power','rating':5,'gate':'pass','source_date':old}]);self.assertEqual(a['coverage_pct'],0);self.assertIn('power',a['stale_factors'])
  a=score([{'factor':'power','rating':0,'gate':'fail','source_date':old}]);self.assertEqual(a['status'],'blocked')
 def test_05_persistence_and_scope(self):
  self.c.post(self.url,json={'parcel_id':self.parcel})
  body={'factor':'power','rating':3,'gate':'flag','source_url':'https://www.loudoun.gov/','source_date':str(date.today()),'notes':'Illustrative test assessment only; service unconfirmed.'}
  self.assertEqual(self.c.put(self.url+'/'+self.parcel+'/assessment',json=body).status_code,200)
  a=self.c.get(self.url+'/'+self.parcel).json();self.assertEqual(a['assessment']['coverage_pct'],30)
  other=self.c.post('/api/projects',json={'name':'Other project'}).json()['id']
  self.assertEqual(self.c.get(f'/api/projects/{other}/parcels28').json(),[])
  self.assertEqual(self.c.get(f'/api/projects/{other}/parcels28/{self.parcel}').json()['factors'],[])
  t=self.c.post(self.url+'/'+self.parcel+'/tasks',json={'title':'Request utility study','owner':'Development lead'});self.assertEqual(t.status_code,201)
  self.assertEqual(self.c.patch(f'/api/projects/{other}/parcels28/{self.parcel}/tasks/{t.json()["id"]}',json={'title':'Illicit change','done':True}).status_code,404)
 def test_06_routes_and_origin_protection(self):
  for u in ['/','/advanced','/assets/vendor/leaflet.js','/assets/workspace28.js']:
   self.assertEqual(self.c.get(u).status_code,200)
  self.assertIn('workspace28.js',self.c.get('/').text)
  self.assertIn('/assets/app.js',self.c.get('/advanced').text)
  self.assertIn("script-src 'self'",self.c.get('/').headers['content-security-policy'])
  self.assertEqual(self.c.post(self.url,json={'parcel_id':self.parcel},headers={'origin':'https://bad.example'}).status_code,403)
 def test_07_future_and_missing_sources(self):
  for changes in [{'source_date':str(date.today()+timedelta(days=1))},{'rating':None},{'notes':''},{'source_url':''}]:
   with self.assertRaises(ValueError):Assessment(**({'factor':'power','rating':5,'gate':'pass','source_date':str(date.today()),'source_url':'https://www.loudoun.gov/','notes':'A documented test source rationale'}|changes))

 def test_08_failed_gate_needs_sourced_clearance(self):
  base={'factor':'power','rating':0,'gate':'fail','source_url':'https://www.loudoun.gov/','source_date':str(date.today()),'notes':'Test: documented adverse gate blocks this parcel.'}
  u=self.url+'/'+self.parcel+'/assessment'
  self.assertEqual(self.c.put(u,json=base).json()['status'],'blocked')
  self.assertEqual(self.c.put(u,json={'factor':'power','gate':'unknown'}).status_code,422)
  self.assertEqual(self.c.get(self.url+'/'+self.parcel).json()['assessment']['status'],'blocked')
  self.assertEqual(self.c.put(u,json=base|{'gate':'flag','rating':2,'notes':'Test: current documented reassessment of adverse evidence.'}).status_code,200)

if __name__=='__main__':unittest.main()
