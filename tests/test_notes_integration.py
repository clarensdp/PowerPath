"""Independent integration gates for imported fixed-rate notes v25.9.
Tests do not confer legal, credit or transaction assurance.
"""
import json, os, tempfile, unittest, subprocess
from pathlib import Path

_tmp=tempfile.TemporaryDirectory(prefix='powerpath_v261_notes_')
os.environ['POWERPATH_DATA_DIR']=_tmp.name
from fastapi.testclient import TestClient
from server.app import app, ENGINE, sha

class NotesIntegration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.client=TestClient(app,base_url='http://127.0.0.1')
  resp=cls.client.post('/api/projects',json={'name':'Synthetic 150 MW Note Project'})
  assert resp.status_code==201,resp.text
  cls.pid=resp.json()['id']
  cls.sample=cls.client.get('/api/defaults').json()['notes']
  cls.url=f'/api/projects/{cls.pid}/scenarios'

 def make_scenario(self,name,config=None):
  res=self.client.post(self.url,json={'name':name,'mode':'notes_v259','config':config or self.sample})
  self.assertEqual(res.status_code,201,res.text)
  return res.json()['id']

 def test_01_sample_is_explicitly_hypothetical(self):
  self.assertEqual(self.sample['facilities'][0]['id'],'SYNTHETIC-NOTE')
  self.assertEqual(self.sample['facilities'][0]['evidence']['faceM']['label'],'Assumption')
  self.assertEqual(self.sample['ltc'],0)

 def test_02_new_engine_is_versioned_and_risk_blocked(self):
  sid=self.make_scenario('Note Case')
  res=self.client.post(self.url+'/'+sid+'/runs')
  self.assertEqual(res.status_code,201,res.text[:500])
  run=res.json(); self.assertEqual(len(run['rows']),120)
  s=run['summary'];risk=s['risk']
  self.assertTrue(len(s['facilities'])==1)
  self.assertTrue(s['facilityDscrBreachMonths'])
  self.assertTrue(s['screeningReadiness'].startswith('BLOCKED'))
  self.assertTrue(risk['uses']['screening'].startswith('BLOCKED'))
  self.assertEqual(risk['gates']['G4']['status'],'FAIL')
  self.assertEqual(risk['gates']['G5']['status'],'NOT STARTED')
  self.assertEqual(risk['uses']['transactionValuation'],'BLOCKED')
  self.assertEqual(risk['uses']['lenderCertification'],'BLOCKED')
  self.assertEqual(run['engine_sha256'],sha(ENGINE/'v259_verified/src/underwrite.cjs'))
  self.assertLess(s['sourcesUsesMaxResidual'],1e-6)
  persisted=self.client.get(f'/api/projects/{self.pid}/runs/{run["id"]}').json()
  self.assertEqual(persisted['summary']['risk']['uses']['lenderCertification'],'BLOCKED')
  self.assertEqual(persisted['engine_sha256'],run['engine_sha256'])

 def test_03_self_reported_claims_do_not_authorize_model(self):
  config=json.loads(json.dumps(self.sample))
  config['evidence']={'documents':{'executedLeases':True,'indentureSchedules':True,'utilityAgreements':True},
                      'reconciliation':{'contractMatched':True},
                      'externalReview':{'reviewer':'Dr. Reviewer','signedOff':True}}
  config['allApproved']=True
  sid=self.make_scenario('Forged approvals',config)
  r=self.client.post(self.url+'/'+sid+'/runs')
  self.assertEqual(r.status_code,201,r.text[:200])
  risk=r.json()['summary']['risk']
  self.assertEqual(risk['uses']['transactionValuation'],'BLOCKED')
  self.assertEqual(risk['uses']['lenderCertification'],'BLOCKED')
  self.assertEqual(risk['gates']['G4']['status'],'FAIL')
  evidence=self.client.post(f'/api/projects/{self.pid}/evidence',json={
    'title':'Unverified uploaded document', 'category':'Financing', 'evidence_status':'executed_document'})
  self.assertEqual(evidence.status_code,201)
  r=self.client.post(self.url+'/'+sid+'/runs').json()
  self.assertEqual(r['summary']['risk']['gates']['G4']['status'],'FAIL')
  self.assertEqual(r['summary']['risk']['uses']['lenderCertification'],'BLOCKED')

 def test_04_rejects_invalid_note_contract(self):
  cfg=json.loads(json.dumps(self.sample))
  cfg['facilities'][0]['buildings']=['NOT AN ASSET']
  sid=self.make_scenario('Invalid facility',cfg)
  r=self.client.post(self.url+'/'+sid+'/runs')
  self.assertEqual(r.status_code,422)

 def test_05_legacy_calculator_not_rewritten(self):
  self.assertNotEqual(sha(ENGINE/'underwrite25.js'),sha(ENGINE/'v259_verified/src/underwrite.cjs'))
  self.assertEqual(self.client.get('/api/health').json()['authentication'],'NOT_IMPLEMENTED')
  self.assertFalse(self.client.get('/api/health').json()['lender_grade'])

if __name__=='__main__':unittest.main()
