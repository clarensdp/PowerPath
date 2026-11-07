import os,tempfile,unittest,io,json,copy
os.environ['POWERPATH_DATA_DIR']=tempfile.mkdtemp(prefix='public30_')
from fastapi.testclient import TestClient
from server.app import app,db,ROOT
from server.geo29 import GeoStore
from server.public_parcels30 import PublicParcels,normalize,area_sqft

def feature(pin='abc',x=-78.65):
 return {'type':'Feature','properties':{'nparno':'37183_'+pin,'parno':pin,'stcntyfips':'37183','gisacres':25,'cntyname':'Wake','sourcedate':1748840400000},'geometry':{'type':'Polygon','coordinates':[[[x,35.77],[x+.001,35.77],[x+.001,35.771],[x,35.77]]]}}
class LiveTests(unittest.TestCase):
 def setUp(self):self.store=GeoStore(db,ROOT);self.c=TestClient(app,base_url='http://127.0.0.1')
 def test_normalization(self):
  f=normalize('37',feature());self.assertEqual(f['properties']['area_sqft'],25*43560);self.assertEqual(f['properties']['source_document_date'],'2025-06-02')
  g=feature();g['properties']={'VGIN_QPID':5176000001,'FIPS':'51760','PARCELID':'x','LOCALITY':'Richmond','LASTUPDATE':None}
  n=normalize('51',g);self.assertGreater(n['properties']['area_sqft'],0);self.assertIn('approximate',n['properties']['area_basis']);self.assertIsNone(n['properties']['source_document_date'])
 def test_cache_and_snapshots(self):
  payload={'type':'FeatureCollection','features':[feature()]};calls=[]
  def response(url,**kw):calls.append(url);return io.BytesIO(json.dumps(payload).encode())
  service=PublicParcels(self.store,response);bbox=[-78.66,35.76,-78.64,35.79]
  first=service.query(bbox,state='37');self.assertEqual(len(first['features']),1)
  id=first['features'][0]['properties']['workspace_id'];ver=first['features'][0]['properties']['version_id']
  pid=self.c.post('/api/projects',json={'name':'Live parcel test'}).json()['id'];url=f'/api/projects/{pid}/parcels28'
  self.assertEqual(self.c.post(url,json={'parcel_id':id}).status_code,201)
  service.query(bbox,state='37');self.assertEqual(len(calls),1)
  payload['features']=[feature('def',-78.64)];service.query([-78.65,35.76,-78.63,35.79],state='37')
  self.assertIsNotNone(self.store.get(id));self.assertEqual(self.c.get(url+'/'+id).json()['source_version'],ver)
  self.assertEqual(len(self.store.query(bbox,'37')['features']),2)
  # Failed live source preserves cached geometry and labels the failure.
  def fail(*a,**k):raise OSError('offline')
  failed=PublicParcels(self.store,fail).query(bbox,state='37')
  self.assertEqual(failed['status'],'source_unavailable');self.assertGreater(len(failed['features']),0)
 def test_guards_and_truncation(self):
  calls=[]
  def response(url,**kw):calls.append(url);return io.BytesIO(json.dumps({'type':'FeatureCollection','features':[feature()],'exceededTransferLimit':True}).encode())
  svc=PublicParcels(self.store,response)
  self.assertEqual(svc.query([-85,33,-75,37])['status'],'zoom_required');self.assertEqual(calls,[])
  d=svc.query([-78.66,35.76,-78.64,35.79],min_acres=50,state='37');self.assertTrue(d['has_more']);self.assertEqual(d['features'],[])
  self.assertEqual(self.c.get('/api/geo30/parcels?bbox=nan,1,2,3').status_code,422)
  self.assertEqual(self.c.get('/api/geo30/parcels?bbox=-79,35,-78.9,35.1&limit=1000').status_code,422)
 def test_hole_area(self):
  g=feature()['geometry'];outer=area_sqft(g);g=copy.deepcopy(g);g['coordinates'].append(g['coordinates'][0]);self.assertAlmostEqual(area_sqft(g),0);self.assertGreater(outer,0)
if __name__=='__main__':unittest.main()
