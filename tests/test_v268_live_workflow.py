"""Controlled live-agent workflow replay using a fake provider; makes ZERO real API requests."""
import os,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
TD=tempfile.TemporaryDirectory(prefix='pp_v268_agents_')
os.environ['POWERPATH_DATA_DIR']=TD.name
from server.seed_demo import seed
from server.app import app
from fastapi.testclient import TestClient
from agents import run_live,watch

class ControlledAgentTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  seed();cls.c=TestClient(app,base_url='http://127.0.0.1');cls.pid='demo-campus-001'
 def test_01_user_must_enable_live_and_share_consent(self):
  with patch.dict(os.environ,{'POWERPATH_LIVE_AGENTS':'0','POWERPATH_SHARE_PROJECT_METADATA':'1','OPENAI_API_KEY':'synthetic_key','POWERPATH_AGENT_MODEL':'example-model'},clear=True):
   self.assertFalse(run_live.live_available())
   with self.assertRaisesRegex(RuntimeError,'Live agents OFF'):run_live.run(self.pid)
 def test_02_local_watch_reads_csv_files_and_creates_diffs(self):
  with tempfile.TemporaryDirectory() as temp:
   f=os.path.join(temp,'PJM_QUEUE__2026-10-01.csv')
   Path(f).write_text('record_id,name,status,planned_date\nWATCH-01,SYNTHETIC QUEUE,Study,2029-01-01\n')
   a=watch.check_once(self.pid,temp,False);self.assertEqual(len(a['imported_snapshots']),1)
   again=watch.check_once(self.pid,temp,False);self.assertFalse(again['imported_snapshots'])
   Path(f).write_text('record_id,name,status,planned_date\nWATCH-01,SYNTHETIC QUEUE,Restudy,2029-07-01\n')
   b=watch.check_once(self.pid,temp,False)
   self.assertEqual(b['imported_snapshots'][0]['changes'],1)
   self.assertEqual(b['model_calls'],0)
 def test_03_live_model_provider_is_independent_mocked_ten_calls(self):
  with patch.dict(os.environ,{'POWERPATH_LIVE_AGENTS':'1','POWERPATH_SHARE_PROJECT_METADATA':'1','OPENAI_API_KEY':'synthetic_key','POWERPATH_AGENT_MODEL':'example-model','POWERPATH_MAX_CALLS_PER_DAY':'20'},clear=True):
   calls=[]
   def mock(role,mission,source,prior):
    calls.append(role);return f'{role}: hypothetical review. Public generation queue status does not confirm large-load utility service.'
   with patch.object(run_live,'response',mock):
    a=run_live.run(self.pid);self.assertEqual(a['api_calls'],10);self.assertEqual(len(calls),10)
    b=run_live.run(self.pid);self.assertEqual(b['api_calls'],0);self.assertEqual(len(calls),10)
   record=self.c.get(f'/api/projects/{self.pid}/agents/meetings/{a["meeting_id"]}').json()
   self.assertEqual(record['mode'],'LIVE_API');self.assertEqual(len(record['messages']),10)
   self.assertTrue(all(m['mode']=='LIVE_API' for m in record['messages']))
   with patch.object(run_live,'response',mock),patch.dict(os.environ,{'POWERPATH_FORCE_REPEAT':'1','POWERPATH_MAX_CALLS_PER_DAY':'15'}):
    with self.assertRaisesRegex(RuntimeError,'Daily model-call budget'):run_live.run(self.pid)
 def test_04_live_does_not_approve_actions(self):
  self.assertFalse(any(x['status']=='approved' for x in self.c.get(f'/api/projects/{self.pid}/intelligence/proposals').json()))
  meetings=self.c.get(f'/api/projects/{self.pid}/agents/meetings').json()
  self.assertTrue(all(m['result'].get('no_actions_performed') or m['mode']=='OFFLINE_RULES' for m in meetings))

if __name__=='__main__':unittest.main()
