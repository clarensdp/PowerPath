import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gridpilot.advisor import Requirements, Options, candidate_opens
from gridpilot.permitiq import preliminary_screen, task_template
class SafetyTests(unittest.TestCase):
 def test_contradictory_deadline(self):
  self.assertEqual(candidate_opens(Requirements(full_demand_by=24), Options(earliest_open=20, latest_open=26)), [])
 def test_ordinary_search(self):
  self.assertEqual(candidate_opens(Requirements(full_demand_by=30), Options(earliest_open=14, latest_open=26,step=2)), [14,16,18,20])
 def test_permit_not_certification(self):
  rows=preliminary_screen({'gas_engine':20},'Williamson County, Texas (unincorporated - assumption)')
  self.assertTrue(all('Unverified' in x['evidence_status'] for x in rows))
  self.assertIn('NOT A PERMIT APPLICATION',task_template('example','Texas',rows))
if __name__=='__main__':unittest.main()
