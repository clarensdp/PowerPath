"""v27.2 institutional transaction workspace smoke/security tests. Runs in isolated auth-required process."""
import os,tempfile,unittest
TD=tempfile.TemporaryDirectory(prefix='pp272_')
os.environ['POWERPATH_DATA_DIR']=TD.name
os.environ['POWERPATH_V27_AUTH_MODE']='required'
from fastapi.testclient import TestClient
from server.app import app,db
from server.institutional import password_hash,utc
C=TestClient(app,base_url='http://localhost')
class Workspace(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with db() as con:
   con.execute('INSERT INTO v27_tenants VALUES(?,?,?)',('alpha','Alpha',utc()))
   con.execute('INSERT INTO v27_users VALUES(?,?,?,?,?)',('user','u@a.test',password_hash('secure-long-password-for-test'),1,utc()))
   con.execute('INSERT INTO v27_memberships VALUES(?,?,?)',('user','alpha','analyst'))
  token=C.post('/api/v27/auth/login',json={'email':'u@a.test','password':'secure-long-password-for-test'}).json()['access_token']
  cls.headers={'Authorization':'Bearer '+token,'X-PowerPath-Tenant':'alpha'}
  cls.pid=C.post('/api/projects',headers=cls.headers,json={'name':'Core'}).json()['id']
 def test_workspace_served_with_csp_and_no_inline_js(self):
  r=C.get('/transaction-workspace');self.assertEqual(r.status_code,200)
  self.assertIn("script-src 'self'",r.headers['content-security-policy'])
  self.assertIn('transaction-workspace.js',r.text)
  self.assertNotIn('<script>',r.text)
 def test_api_requires_auth_and_evidence_gates_stay_blocked(self):
  b=f'/api/projects/{self.pid}/transactions/core-scientific-2026'
  self.assertEqual(C.get(b+'/terms').status_code,401)
  self.assertEqual(C.post(b+'/model',headers=self.headers).status_code,201)
  for url in ('/terms','/scenarios','/reconciliation','/debt-schedule'):
   r=C.get(b+url,headers=self.headers);self.assertEqual(r.status_code,200,r.text)
   self.assertEqual(r.json()['g4'],'BLOCKED');self.assertEqual(r.json()['g5'],'BLOCKED')
 def test_static_assets(self):
  for file in ('transaction-workspace.js','transaction-workspace.css'):
   self.assertEqual(C.get('/assets/'+file).status_code,200)
if __name__=='__main__':unittest.main()
