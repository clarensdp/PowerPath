import sys, unittest, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gridpilot.feasibility import CRITERIA, blank_records, evaluate, export_report, drafting_checklist
class FeasibilityTests(unittest.TestCase):
    def test_complete_catalog_and_safe_defaults(self):
        rows=blank_records(); self.assertEqual(len(rows),30)
        result=evaluate(rows)
        self.assertIn('Unverified',result['determination'])
        self.assertEqual(result['verified_with_support'],0)
        self.assertGreater(result['critical_unresolved'],0)
    def test_verified_requires_evidence(self):
        rows=blank_records(); rows[0]['status']='Verified — requirement met'
        self.assertEqual(evaluate(rows)['verified_with_support'],0)
        self.assertEqual(evaluate(rows)['evidence_deficiencies'],1)
        rows[0]['evidence_reference']='Written utility letter #123';rows[0]['verified_by']='Reviewer'
        self.assertEqual(evaluate(rows)['verified_with_support'],1)
    def test_blocked_requires_evidence(self):
        rows=blank_records(); rows[0]['status']='Verified — blocked'
        self.assertEqual(evaluate(rows)['supported_critical_blockers'],0)
        rows[0]['evidence_reference']='Agency letter';rows[0]['verified_by']='Counsel'
        self.assertEqual(evaluate(rows)['supported_critical_blockers'],1)
    def test_exports(self):
        rows=blank_records(); project={'name':'Example','location':'TX'}
        payload=json.loads(export_report(project,rows))
        self.assertEqual(payload['project']['name'],'Example')
        self.assertIn('PRELIMINARY',drafting_checklist(project,rows))
if __name__=='__main__':unittest.main()
