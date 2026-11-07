"""Isolated authentication, RBAC, source register and audit tamper tests."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from fastapi.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]
class V27Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  os.environ['POWERPATH_DATA_DIR']=cls.tmp.name
  os.environ['POWERPATH_V27_AUTH_MODE']='required'
  from server.app import app,db
  from server.institutional import init,password_hash,utc
  cls.db=db;cls.client=TestClient(app,base_url='http://localhost')
  with db() as con:
   init(con)
   con.execute('INSERT INTO v27_tenants VALUES(?,?,?)',('a','A',utc()))
   con.execute('INSERT INTO v27_tenants VALUES(?,?,?)',('b','B',utc()))
   for id,email,role,tenant in [('admin','a@example.test','admin','a'),('viewer','v@example.test','viewer','a'),('other','b@example.test','admin','b')]:
    con.execute('INSERT INTO v27_users VALUES(?,?,?,?,?)',(id,email,password_hash('secure-long-test-password'),1,utc()))
    con.execute('INSERT INTO v27_memberships VALUES(?,?,?)',(id,tenant,role))
  cls.tokens={}
  for person in ('a','v','b'):
   r=cls.client.post('/api/v27/auth/login',json={'email':person+'@example.test','password':'secure-long-test-password'})
   assert r.status_code==200,r.text
   cls.tokens[person]=r.json()['access_token']
 @classmethod
 def tearDownClass(cls):cls.client.close();cls.tmp.cleanup()
 def headers(self,person='a',tenant=None):
  h={'Authorization':'Bearer '+self.tokens[person]}
  if tenant:h['X-PowerPath-Tenant']=tenant
  return h
 def test_01_fail_closed(self):
  self.assertEqual(self.client.get('/api/projects').status_code,401)
  self.assertEqual(self.client.post('/api/projects',json={'name':'Test'}).status_code,401)
 def test_02_tenant_isolation_and_rbac(self):
  r=self.client.post('/api/projects',headers=self.headers('a','a'),json={'name':'Core Scientific 2026 financing'})
  self.assertEqual(r.status_code,201,r.text);self.__class__.pid=r.json()['id']
  self.assertEqual(self.client.get('/api/projects',headers=self.headers('b')).json(),[])
  self.assertEqual(self.client.get('/api/projects/'+self.pid,headers=self.headers('b')).status_code,403)
  self.assertEqual(self.client.patch('/api/projects/'+self.pid,headers=self.headers('v'),json={'name':'Changed'}).status_code,403)
 def test_03_public_transaction_registry(self):
  pid=self.__class__.pid
  r=self.client.post(f'/api/projects/{pid}/transactions/core-scientific-2026',headers=self.headers())
  self.assertEqual(r.status_code,201,r.text)
  self.assertFalse(r.json()['valuation_allowed'])
  self.assertEqual(r.json()['open_gaps'],8)
  r=self.client.get(f'/api/projects/{pid}/transactions',headers=self.headers())
  facts={x['field']:x for x in r.json()[0]['facts']}
  self.assertEqual(facts['principal_usd']['value'],3300000000)
  self.assertEqual(facts['coupon_pct']['value'],7.75)
  self.assertEqual(r.json()[0]['g4'],'BLOCKED')
  self.assertEqual(self.client.get(f'/api/projects/{pid}/transactions',headers=self.headers('b')).status_code,403)
 def test_04_approver_identity_version_lock(self):
  pid=self.__class__.pid
  sample={'name':'Baseline','mode':'underwrite','config':{}}
  # Use a standalone scenario with integer version; no modelling call required
  from server.app import db,uid,now
  sid=uid()
  with db() as con:
   con.execute('INSERT INTO scenarios VALUES(?,?,?,?,?,?,?,?)',(sid,pid,'Review baseline','underwrite','{}',1,now(),now()))
  endpoint=f'/api/projects/{pid}/approvals'
  data={'object_type':'scenario','object_id':sid,'version':'1','decision':'approved','reason':'Reviewed by authorized approver'}
  self.assertEqual(self.client.post(endpoint,headers=self.headers('v'),json=data).status_code,403)
  self.assertEqual(self.client.post(endpoint,headers=self.headers('a'),json={**data,'version':'0'}).status_code,409)
  r=self.client.post(endpoint,headers=self.headers('a'),json=data)
  self.assertEqual(r.status_code,201,r.text);self.assertEqual(r.json()['actor_id'],'admin')
  self.assertEqual(self.client.post(endpoint,headers=self.headers('a'),json=data).status_code,409)
 def test_05_hash_chain_detects_tampering(self):
  with self.__class__.db() as con:
   from server.institutional import verify_audit
   self.assertTrue(verify_audit(con)['valid'])
   con.execute("UPDATE v27_audit SET details='{}' WHERE action='approval.approved'")
   self.assertFalse(verify_audit(con)['valid'])
if __name__=='__main__':unittest.main()
