import os,tempfile,unittest,io,json,copy
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
os.environ['POWERPATH_DATA_DIR']=tempfile.mkdtemp(prefix='public30_')
from fastapi.testclient import TestClient
from server.app import app,db,ROOT
from server.geo29 import GeoStore
from server.public_parcels30 import PublicParcels,normalize,area_sqft

def feature(pin='abc',x=-78.65):
 return {'type':'Feature','properties':{'nparno':'37183_'+pin,'parno':pin,'stcntyfips':'37183','gisacres':25,'cntyname':'Wake','sourcedate':1748840400000},'geometry':{'type':'Polygon','coordinates':[[[x,35.77],[x+.001,35.77],[x+.001,35.771],[x,35.77]]]}}
class LiveTests(unittest.TestCase):
 def setUp(self):self.store=GeoStore(db,ROOT);self.c=TestClient(app,base_url='http://127.0.0.1')
 def test_default_threshold_inclusive_and_adjustable(self):
  features=[];calls=[]
  for acres in [25,49.99,50,100]:
   f=feature('threshold-'+str(acres));f['properties']['gisacres']=acres;features.append(f)
  def response(url,**kw):calls.append(parse_qs(urlsplit(url).query));return io.BytesIO(json.dumps({'type':'FeatureCollection','features':features}).encode())
  svc=PublicParcels(self.store,response);bbox=[-78.66,35.76,-78.64,35.79]
  result=svc.query(bbox,state='37')
  self.assertEqual(sorted(f['properties']['area_sqft']/43560 for f in result['features']),[50,100])
  self.assertEqual(calls[0]['where'],['(gisacres >= 50.0 OR gisacres IS NULL)'])
  self.assertEqual(len(svc.query(bbox,min_acres=0,state='37')['features']),4)
  self.assertEqual(len(svc.query(bbox,min_acres=100,state='37')['features']),1)
  # The HTTP API also uses 50 when callers omit the parameter, and honors explicit zero.
  with patch.object(PublicParcels,'query',return_value={'features':[]}) as query:
   self.assertEqual(self.c.get('/api/geo30/parcels?bbox=-78.66,35.76,-78.64,35.79').status_code,200)
   self.assertEqual(query.call_args.args[1],50)
   self.c.get('/api/geo30/parcels?bbox=-78.66,35.76,-78.64,35.79&min_acres=0')
   self.assertEqual(query.call_args.args[1],0)
 def test_missing_nc_acreage_uses_real_geometry(self):
  f=feature('geometry-area');f['properties']['gisacres']=None
  f['geometry']['coordinates']=[[[-78.65,35.77],[-78.63,35.77],[-78.63,35.79],[-78.65,35.77]]]
  def response(*a,**kw):return io.BytesIO(json.dumps({'type':'FeatureCollection','features':[f]}).encode())
  result=PublicParcels(self.store,response).query([-78.66,35.76,-78.62,35.80],state='37')
  self.assertEqual(len(result['features']),1)
  props=result['features'][0]['properties']
  self.assertEqual(props['area_sqft'],area_sqft(f['geometry']))
  self.assertIn('geometry',props['area_basis'])
  f['geometry']=None
  self.assertEqual(PublicParcels(self.store,response).query([-78.66,35.76,-78.62,35.80],state='37')['features'],[])
 def test_va_geometry_filter_and_truncated_empty_results(self):
  small=feature('va-small');small['properties']={'VGIN_QPID':999001,'FIPS':'51059','PARCELID':'small'}
  small['geometry']['coordinates']=[[[-77.5,39],[-77.499,39],[-77.499,39.001],[-77.5,39]]]
  large=copy.deepcopy(small);large['properties']['VGIN_QPID']=999002
  large['geometry']['coordinates']=[[[-77.5,39],[-77.48,39],[-77.48,39.02],[-77.5,39]]]
  payload={'type':'FeatureCollection','features':[small,large]}
  def response(*a,**kw):return io.BytesIO(json.dumps(payload).encode())
  bbox=[-77.51,38.99,-77.47,39.03]
  result=PublicParcels(self.store,response).query(bbox,state='51')
  self.assertEqual(len(result['features']),1)
  self.assertGreaterEqual(result['features'][0]['properties']['area_sqft']/43560,50)
  # All 200 source records can be below the threshold; never imply an exhaustive empty search.
  payload['features']=[{**small,'properties':{**small['properties'],'VGIN_QPID':999100+i}} for i in range(200)]
  result=PublicParcels(self.store,response).query(bbox,state='51')
  self.assertEqual(result['features'],[]);self.assertTrue(result['has_more'])
  self.assertIsNone(result['total_matches'])
  self.assertIn('may miss matches',' '.join(result['messages']))
 def test_cached_fallback_retains_incomplete_flag(self):
  def fail(*a,**kw):raise OSError('offline')
  with patch.object(self.store,'query',return_value={'features':[],'has_more':True}):
   result=PublicParcels(self.store,fail).query([-77.51,38.99,-77.47,39.03],state='51')
  self.assertTrue(result['has_more']);self.assertEqual(result['status'],'source_unavailable')
  self.assertIn('may miss matches',' '.join(result['messages']))
 def test_normalization(self):
  f=normalize('37',feature());self.assertEqual(f['properties']['area_sqft'],25*43560);self.assertEqual(f['properties']['source_document_date'],'2025-06-02')
  g=feature();g['properties']={'VGIN_QPID':5176000001,'FIPS':'51760','PARCELID':'x','LOCALITY':'Richmond','LASTUPDATE':None}
  n=normalize('51',g);self.assertGreater(n['properties']['area_sqft'],0);self.assertIn('approximate',n['properties']['area_basis']);self.assertIsNone(n['properties']['source_document_date'])
 def test_cache_and_snapshots(self):
  payload={'type':'FeatureCollection','features':[feature()]};calls=[]
  def response(url,**kw):calls.append(url);return io.BytesIO(json.dumps(payload).encode())
  service=PublicParcels(self.store,response);bbox=[-78.66,35.76,-78.64,35.79]
  first=service.query(bbox,min_acres=0,state='37');self.assertEqual(len(first['features']),1)
  id=first['features'][0]['properties']['workspace_id'];ver=first['features'][0]['properties']['version_id']
  pid=self.c.post('/api/projects',json={'name':'Live parcel test'}).json()['id'];url=f'/api/projects/{pid}/parcels28'
  self.assertEqual(self.c.post(url,json={'parcel_id':id}).status_code,201)
  service.query(bbox,min_acres=0,state='37');self.assertEqual(len(calls),1)
  payload['features']=[feature('def',-78.64)];service.query([-78.65,35.76,-78.63,35.79],min_acres=0,state='37')
  self.assertIsNotNone(self.store.get(id));self.assertEqual(self.c.get(url+'/'+id).json()['source_version'],ver)
  self.assertEqual(len(self.store.query(bbox,'37')['features']),2)
  # Failed live source preserves cached geometry and labels the failure.
  def fail(*a,**k):raise OSError('offline')
  failed=PublicParcels(self.store,fail).query(bbox,min_acres=0,state='37')
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
