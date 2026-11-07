import os,tempfile,unittest,json,copy
os.environ['POWERPATH_DATA_DIR']=tempfile.mkdtemp(prefix='pp29_')
from fastapi.testclient import TestClient
from server.app import app,db,ROOT
from server.geo29 import GeoStore
class NationalTests(unittest.TestCase):
 def setUp(self):self.c=TestClient(app,base_url='http://127.0.0.1');self.store=GeoStore(db,ROOT)
 def test_coverage(self):
  d=self.c.get('/api/geo29/coverage').json();self.assertEqual(len(d['states']),51);self.assertEqual(sum(s['parcel_records'] for s in d['states']),120)
  self.assertEqual(len(self.c.get('/api/geo29/states').json()['features']),51)
  self.assertTrue(self.c.get('/api/geo29/locations?q=Loudoun').json()['results'])
 def test_viewport(self):
  self.assertEqual(self.c.get('/api/geo29/parcels?bbox=-78,38,-77,40').json()['total_matches'],120)
  self.assertEqual(self.c.get('/api/geo29/parcels?bbox=-120,30,-110,35').json()['total_matches'],0)
  for b in ['nan,0,1,1','2,0,1,1','-181,0,1,1']:
   self.assertEqual(self.c.get('/api/geo29/parcels',params={'bbox':b}).status_code,422)
 def test_versions_and_jurisdictions(self):
  f={'type':'Feature','properties':{'pin':'TEST','sqft':43560},'geometry':{'type':'Polygon','coordinates':[[[-100,31],[-99,31],[-99,32],[-100,31]]]}}
  coll={'type':'FeatureCollection','features':[f]}
  source={'id':'test-source','name':'Synthetic test only','state_fips':'48','county_fips':'001','source_url':'https://example.com/test','license_note':'Test only','coverage_scope':'Synthetic test fixture','retrieved_at':'2026-01-01T00:00:00Z'}
  first=self.store.ingest(source,coll,'pin','sqft');self.assertTrue(self.store.ingest(source,coll,'pin','sqft')['idempotent'])
  key='48001:test-source:TEST';pid=self.c.post('/api/projects',json={'name':'Version test'}).json()['id'];url=f'/api/projects/{pid}/parcels28'
  self.assertEqual(self.c.post(url,json={'parcel_id':key}).status_code,201)
  changed=copy.deepcopy(coll);changed['features'][0]['properties']['sqft']=87120
  second=self.store.ingest(source,changed,'pin','sqft');self.assertNotEqual(first['version_id'],second['version_id'])
  self.assertEqual(self.c.get(url+'/'+key).json()['source_version'],first['version_id'])
  self.assertEqual(self.store.get(key)['version_id'],second['version_id'])
  bad=copy.deepcopy(coll);bad['features'][0]['geometry']['coordinates'][0][0][0]=999
  with self.assertRaises(ValueError):self.store.ingest(source,bad,'pin','sqft')
if __name__=='__main__':unittest.main()
