import copy, io, json, os, unittest, urllib.error
from unittest.mock import patch
from server.providers.regrid import normalize, summarize, fetch_point, import_snapshot

def sample():
 return {'type':'FeatureCollection','features':[{'type':'Feature','properties':{'ll_uuid':'00000000-0000-0000-0000-000000000001','geoid':'31059','parcelnumb':'test/1','ll_gissqft':'43560','ll_last_refresh':'2026-01-01','score':99,'owner':'Synthetic owner'},'geometry':{'type':'Polygon','coordinates':[[[-97,40],[-96.99,40],[-96.99,40.01],[-97,40]]]}}]}

class ProviderTests(unittest.TestCase):
 def test_bulk_and_nested(self):
  a=sample();b=copy.deepcopy(a);b['features'][0]['properties']={'fields':b['features'][0]['properties']}
  x=normalize(a);self.assertEqual(x,normalize({'parcels':b}));p=x['features'][0]['properties'];self.assertEqual(p['area_sqft'],43560);self.assertNotIn('score',p);self.assertNotIn('owner',p)
 def test_unknown_area_not_zero(self):
  s=sample();s['features'][0]['properties']['ll_gissqft']=None
  self.assertIsNone(normalize(s)['features'][0]['properties']['area_sqft'])
 def test_invalid_and_duplicate(self):
  for key,val in [('ll_gissqft','nan'),('geoid','059'),('ll_uuid','')]:
   s=sample();s['features'][0]['properties'][key]=val
   with self.assertRaises(ValueError):normalize(s)
  s=sample();s['features']*=2
  with self.assertRaises(ValueError):normalize(s)
  s=sample();s['features'][0]['geometry']['coordinates'][0][0][0]=999
  with self.assertRaises(ValueError):normalize(s)
 def test_license_and_partial_blocks(self):
  class Store:
   def ingest(self,*args):raise AssertionError('must not ingest')
  with self.assertRaises(ValueError):import_snapshot(Store(),normalize(sample()),{})
  m={'license_reference':'synthetic test','retention_authorized':True,'application_display_authorized':True,'export_authorized':True,'county_fips':'31059','complete_snapshot':False}
  with self.assertRaises(ValueError):import_snapshot(Store(),normalize(sample()),m)
 @patch.dict(os.environ,{'POWERPATH_REGRID_TOKEN':'TEST_SECRET'})
 def test_bounded_fetch(self):
  requests=[]
  def response(req,**kwargs):requests.append(req.full_url);return io.BytesIO(json.dumps({'parcels':sample()}).encode())
  self.assertEqual(len(fetch_point(40,-97,transport=response)['features']),1)
  self.assertIn('limit=1',requests[0]);self.assertNotIn('return_count',requests[0]);self.assertEqual(len(requests),1)
  with self.assertRaises(ValueError):fetch_point(40,-97,limit=1000,transport=response)
 @patch.dict(os.environ,{'POWERPATH_REGRID_TOKEN':'TEST_SECRET'})
 def test_count_only(self):
  def response(req,**kwargs):self.assertIn('return_count=true',req.full_url);return io.BytesIO(b'{"count":1}')
  self.assertEqual(fetch_point(40,-97,count_only=True,transport=response),{'count':1})
 @patch.dict(os.environ,{'POWERPATH_REGRID_TOKEN':'TEST_SECRET'})
 def test_errors_redact_token_and_no_retry(self):
  calls=[]
  def bad(req,**kwargs):calls.append(1);raise urllib.error.HTTPError(req.full_url,429,'TEST_SECRET',{},None)
  with self.assertRaises(RuntimeError) as ctx:fetch_point(40,-97,transport=bad)
  self.assertNotIn('TEST_SECRET',str(ctx.exception));self.assertEqual(len(calls),1)
 @patch.dict(os.environ,{},clear=True)
 def test_missing_token(self):
  with self.assertRaises(ValueError):fetch_point(40,-97)
if __name__=='__main__':unittest.main()
