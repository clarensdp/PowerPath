"""Run in its own process: required-auth globals are initialized on import."""
import unittest
from tests.v271.test_v271_required_auth import C,H
class ParcelAuthTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.pid=C.post('/api/projects',headers=H('analyst','a'),json={'name':'Parcel access test'}).json()['id']
  cls.pin=str(C.get('/api/parcels28/catalog',headers=H('analyst')).json()['features'][0]['properties']['PA_MCPI'])
  cls.url=f'/api/projects/{cls.pid}/parcels28'
 def test_catalog_requires_session(self):self.assertEqual(C.get('/api/parcels28/catalog').status_code,401)
 def test_cross_tenant_cannot_read_or_write(self):
  self.assertEqual(C.get(self.url,headers=H('other')).status_code,403)
  self.assertEqual(C.post(self.url,headers=H('other'),json={'parcel_id':self.pin}).status_code,403)
 def test_viewer_cannot_mutate_but_analyst_can(self):
  self.assertEqual(C.post(self.url,headers=H('viewer'),json={'parcel_id':self.pin}).status_code,403)
  self.assertEqual(C.post(self.url,headers=H('analyst'),json={'parcel_id':self.pin}).status_code,201)
  self.assertEqual(C.get(self.url,headers=H('viewer')).status_code,200)
if __name__=='__main__':unittest.main()
