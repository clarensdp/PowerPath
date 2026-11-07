"""Separate-process required-auth access and human review gate."""
import os,tempfile,unittest
TD=tempfile.TemporaryDirectory(prefix='pp307_auth_')
os.environ['POWERPATH_DATA_DIR']=TD.name
os.environ['POWERPATH_V27_AUTH_MODE']='required'
from fastapi.testclient import TestClient
from server.app import app,db
from server.institutional import password_hash,utc
from agents import operations as ops

class AgentOpsAuth307(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=TestClient(app,base_url='http://localhost')
        with db() as con:
            for t in ('a','b'):con.execute('INSERT INTO v27_tenants VALUES(?,?,?)',(t,t,utc()))
            for uid,tenant,role in [('approver','a','approver'),('analyst','a','analyst'),('other','b','admin')]:
                con.execute('INSERT INTO v27_users VALUES(?,?,?,?,?)',(uid,uid+'@test.example',password_hash('very-long-secure-test-pw'),1,utc()))
                con.execute('INSERT INTO v27_memberships VALUES(?,?,?)',(uid,tenant,role))
        cls.tokens={uid:cls.c.post('/api/v27/auth/login',json={'email':uid+'@test.example','password':'very-long-secure-test-pw'}).json()['access_token'] for uid in ('approver','analyst','other')}
        cls.headers=staticmethod(lambda who,tenant=None:{'Authorization':'Bearer '+cls.tokens[who],**({'X-PowerPath-Tenant':tenant} if tenant else {})})
        cls.pid=cls.c.post('/api/projects',headers=cls.headers('analyst','a'),json={'name':'Auth agent project'}).json()['id']
    def test_01_project_isolation(self):
        url=f'/api/projects/{self.pid}/agents/ops/overview'
        self.assertEqual(self.c.get(url).status_code,401)
        self.assertEqual(self.c.get(url,headers=self.headers('other')).status_code,403)
        self.assertEqual(self.c.get(url,headers=self.headers('analyst')).status_code,200)
    def test_02_schedule_approval_role(self):
        url=f'/api/projects/{self.pid}/agents/ops/config';body={'enabled':True,'mode':'rules'}
        self.assertEqual(self.c.post(url,headers=self.headers('analyst'),json=body).status_code,403)
        self.assertEqual(self.c.post(url,headers=self.headers('approver'),json=body).status_code,200)
    def test_03_agent_output_approval_named_no_side_effect(self):
        ops.enqueue(db,self.pid,'Chief Risk Officer','rules')
        done=ops.process_one(db,self.pid,'test-auth')
        self.assertEqual(done['status'],'complete')
        review_id=done['review_id'];path=f'/api/projects/{self.pid}/agents/ops/reviews/{review_id}/decision';body={'decision':'acknowledged','reason':'Reviewed memo; no external action'}
        self.assertEqual(self.c.post(path,headers=self.headers('analyst'),json=body).status_code,403)
        self.assertEqual(self.c.post(path,headers=self.headers('other'),json=body).status_code,403)
        self.assertEqual(self.c.post(path,headers=self.headers('approver'),json=body).json()['action_executed'],False)
        self.assertEqual(self.c.post(path,headers=self.headers('approver'),json=body).status_code,409)
        with db() as con:self.assertEqual(con.execute('SELECT reviewed_by FROM agent_ops_reviews WHERE id=?',(review_id,)).fetchone()[0],'approver')

if __name__=='__main__':unittest.main()
