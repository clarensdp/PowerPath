"""Separate-process task claiming and per-attempt budget regression."""
import os,tempfile,unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
TD=tempfile.TemporaryDirectory(prefix='pp_agentops_concurrent_')
os.environ['POWERPATH_DATA_DIR']=TD.name
from server.app import db
from agents import operations as ops

class OperationsClaimRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with db() as con:
            t=ops.utc()
            con.execute('INSERT INTO projects(id,name,location,created_at,updated_at) VALUES(?,?,?,?,?)',('unit-project','test','VA',t,t))
    def test_01_concurrent_claim_only_once(self):
        ops.enqueue(db,'unit-project','CTO','rules','concurrent')
        def one(i):return ops.claim(db,'unit-project',f'worker-{i}')
        with ThreadPoolExecutor(max_workers=5) as pool:res=list(pool.map(one,range(5)))
        claimed=[r for r in res if r and r['status']=='running']
        self.assertEqual(len(claimed),1)
        with db() as con:self.assertEqual(con.execute("SELECT attempts FROM agent_ops_jobs WHERE schedule_key='concurrent'").fetchone()[0],1)
    def test_02_live_retry_reserves_new_slot(self):
        project='unit-project';ops.enqueue(db,project,'CDO','live','live-retry')
        env={'POWERPATH_LIVE_AGENTS':'1','POWERPATH_SHARE_PROJECT_METADATA':'1','OPENAI_API_KEY':'test-key','POWERPATH_AGENT_MODEL':'test-model','POWERPATH_MAX_CALLS_PER_DAY':'2'}
        with patch.dict(os.environ,env,clear=False):
            first=ops.process_one(db,project,'testworker',lambda *args:(_ for _ in ()).throw(ValueError('Fake provider error')))
            self.assertEqual(first['status'],'failed')
            ops.retry(db,project,first['job_id'])
            second=ops.process_one(db,project,'testworker',lambda *args:'Non-binding source review; no verified capacity or permitted work')
            self.assertEqual(second['status'],'complete')
        with db() as con:
            entries=con.execute('SELECT attempt,state FROM agent_ops_calls ORDER BY attempt').fetchall()
            self.assertEqual([(x['attempt'],x['state']) for x in entries],[(1,'failed'),(2,'ok')])
    def test_03_review_cannot_be_decided_against_changed_artifact(self):
        with db() as con:
            r=con.execute('SELECT id,job_id FROM agent_ops_reviews LIMIT 1').fetchone()
            con.execute("UPDATE agent_ops_jobs SET result_json='{}' WHERE id=?",(r['job_id'],))
        with self.assertRaisesRegex(ValueError,'changed'):
            ops.decide_review(db,'unit-project',r['id'],'acknowledged','named-user','Reviewed the evidence')

if __name__=='__main__':unittest.main()
