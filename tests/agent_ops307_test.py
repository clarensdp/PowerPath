"""Run separately: python -m unittest tests.agent_ops307_test -v (isolated DB)."""
import os,tempfile,unittest,json
from datetime import datetime,timezone
from unittest.mock import patch
TD=tempfile.TemporaryDirectory(prefix='pp_agentops307_')
os.environ['POWERPATH_DATA_DIR']=TD.name
from fastapi.testclient import TestClient
from server.seed_demo import seed
from server.app import app,db
from agents import operations as ops
from agents.ops_worker import tick
from agents import run_live

class AgentOps307(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed();cls.c=TestClient(app,base_url='http://127.0.0.1');cls.pid='demo-campus-001'
    def test_01_disabled_default_and_migration(self):
        a=self.c.get(f'/api/projects/{self.pid}/agents/ops/overview')
        self.assertEqual(a.status_code,200)
        self.assertFalse(a.json()['configuration']['enabled'])
        with db() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM schema_migrations WHERE version='agent_ops_0001'").fetchone()[0],1)
        self.assertEqual(ops.schedule_daily(db,self.pid)['scheduled'],0)
        self.assertEqual(tick(self.pid)['status'],'DISABLED')
    def test_02_queue_and_idempotent_schedule(self):
        x=self.c.post(f'/api/projects/{self.pid}/agents/ops/config',json={'enabled':True,'mode':'rules'});self.assertEqual(x.status_code,200)
        self.assertEqual(x.json()['worker_started'],False)
        a=ops.schedule_daily(db,self.pid,day=datetime.now(timezone.utc).date().isoformat())
        b=ops.schedule_daily(db,self.pid,day=datetime.now(timezone.utc).date().isoformat())
        self.assertEqual(a['scheduled_or_existing'],10)
        self.assertEqual(b['scheduled_or_existing'],10)
        with db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM agent_ops_jobs WHERE project_id=?',(self.pid,)).fetchone()[0],10)
    def test_03_offline_runs_without_provider_and_no_financial_changes(self):
        with db() as con:
            before=con.execute('SELECT COUNT(*) FROM runs').fetchone()[0]
            permits=con.execute('SELECT COUNT(*) FROM permit_items').fetchone()[0]
        with patch.object(run_live,'response',side_effect=AssertionError('No real API should be called')):
            result=tick(self.pid,max_jobs=10)
        self.assertEqual(len(result['jobs']),10)
        self.assertTrue(all(a['status']=='complete' for a in result['jobs']))
        self.assertEqual(self.c.get(f'/api/projects/{self.pid}/agents/ops/overview').json()['pending_reviews'],10)
        with db() as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM runs').fetchone()[0],before)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM permit_items').fetchone()[0],permits)
            self.assertEqual(con.execute('SELECT COUNT(*) FROM agent_ops_calls').fetchone()[0],0)
        self.assertTrue(self.c.get(f'/api/projects/{self.pid}/agents/ops/audit-verify').json()['valid'])
        report=self.c.get(f'/api/projects/{self.pid}/agents/ops/jobs/{result["jobs"][0]["job_id"]}').json()
        self.assertEqual(report['result']['mode'],'rules')
        self.assertTrue(report['result']['no_actions_performed'])
    def test_04_review_requires_real_approver(self):
        reviews=self.c.get(f'/api/projects/{self.pid}/agents/ops/reviews').json()
        self.assertEqual(len(reviews),10)
        r=self.c.post(f'/api/projects/{self.pid}/agents/ops/reviews/{reviews[0]["id"]}/decision',json={'decision':'acknowledged','reason':'Approve reading only'})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.c.get(f'/api/projects/{self.pid}/agents/ops/reviews').json()[0]['status'],'pending')
    def test_05_allowlisted_roles_and_isolation(self):
        bad=self.c.post(f'/api/projects/{self.pid}/agents/ops/jobs',json={'role':'Unrestricted Agent'})
        self.assertEqual(bad.status_code,422)
        other=self.c.post('/api/projects',json={'name':'Second tenant scenario','location':'Pennsylvania','target_mw':200,'status':'Qualify','description':'separate'}).json()['id']
        jobs=self.c.get(f'/api/projects/{self.pid}/agents/ops/jobs').json()
        self.assertEqual(self.c.get(f'/api/projects/{other}/agents/ops/jobs/{jobs[0]["id"]}').status_code,404)
        self.assertEqual(self.c.get(f'/api/projects/{other}/agents/ops/reviews').json(),[])
    def test_06_live_off_is_fail_closed(self):
        self.c.post(f'/api/projects/{self.pid}/agents/ops/config',json={'enabled':True,'mode':'live'})
        self.c.post(f'/api/projects/{self.pid}/agents/ops/jobs',json={'role':'CTO','mode':'live'})
        with patch.dict(os.environ,{'POWERPATH_LIVE_AGENTS':'0','OPENAI_API_KEY':'not-real','POWERPATH_AGENT_MODEL':'fake'},clear=False):
            claimed=ops.claim(db,self.pid,'worker-test')
        # Other older daily rules jobs have completed; the live CTO should be queued.
        self.assertEqual(claimed['status'],'LIVE_DISABLED')
        with db() as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM agent_ops_calls").fetchone()[0],0)
    def test_07_live_budget_and_safe_mock(self):
        with patch.dict(os.environ,{'POWERPATH_LIVE_AGENTS':'1','POWERPATH_SHARE_PROJECT_METADATA':'1','OPENAI_API_KEY':'test','POWERPATH_AGENT_MODEL':'fake','POWERPATH_MAX_CALLS_PER_DAY':'1'},clear=False):
            calls=[]
            def fake(role,mission,source,prior):
                calls.append(role)
                self.assertNotIn('lease',source.lower())
                self.assertEqual(prior,'')
                return ('Observed column changes need human verification. No utility deliverability confirmed.',{'input_tokens':6,'output_tokens':10})
            a=ops.process_one(db,self.pid,'mocked-test',fake)
            self.assertEqual(a['status'],'complete')
            self.assertEqual(len(calls),1)
            self.c.post(f'/api/projects/{self.pid}/agents/ops/jobs',json={'role':'CDO','mode':'live'})
            blocked=ops.process_one(db,self.pid,'mocked-test',fake)
            self.assertEqual(blocked['status'],'BUDGET_BLOCKED')
            self.assertEqual(len(calls),1)
        with db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM agent_ops_calls').fetchone()[0],1)
    def test_08_crash_recovery_requires_explicit_retry(self):
        j=ops.enqueue(db,self.pid,'CMO','rules')
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute("UPDATE agent_ops_jobs SET status='running',attempts=1,lease_until=? WHERE id=?",('2020-01-01T00:00:00+00:00',j['id']))
            con.execute('COMMIT')
        self.assertIn(j['id'],ops.recover_interrupted(db,self.pid))
        job=self.c.get(f'/api/projects/{self.pid}/agents/ops/jobs/{j["id"]}').json()
        self.assertEqual(job['status'],'abandoned')
        self.assertEqual(self.c.post(f'/api/projects/{self.pid}/agents/ops/jobs/{j["id"]}/retry').json()['status'],'queued')
    def test_09_hash_chain_and_no_replays(self):
        a=self.c.get(f'/api/projects/{self.pid}/agents/ops/audit-verify').json()
        self.assertTrue(a['valid'])
        self.assertGreater(a['checked'],10)
        with db() as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM agent_ops_jobs WHERE status="running"').fetchone()[0],0)

if __name__=='__main__':unittest.main()
