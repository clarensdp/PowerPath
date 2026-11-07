"""Regression tests for the Nov 7 2026 audit fixes (v30.8.2-audit). No financial-engine assertions."""
import os, re, stat, tempfile, unittest
from pathlib import Path

_temp = tempfile.TemporaryDirectory()
os.environ['POWERPATH_DATA_DIR'] = _temp.name
from fastapi.testclient import TestClient
from server.app import app
from server.seed_demo import seed

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'web' / 'public'


class AuditApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed()
        cls.client = TestClient(app, base_url='http://127.0.0.1')

    def _project(self, name='Audit QA', mw=200):
        r = self.client.post('/api/projects', json={'name': name, 'target_mw': mw, 'location': 'Synthetic'})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()['id']

    def test_feasibility_empty_state_is_not_an_error_for_ui(self):
        pid = self._project()
        # Existing contract preserved for API callers.
        self.assertEqual(self.client.get(f'/api/projects/{pid}/feasibility').status_code, 404)
        r = self.client.get(f'/api/projects/{pid}/feasibility?allow_empty=true')
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.json())

    def test_transaction_review_can_be_unblocked_from_ui_path(self):
        pid = self._project('Audit TX')
        base = f'/api/projects/{pid}/transactions/core-scientific-2026'
        r = self.client.get(base + '/terms')
        self.assertEqual(r.status_code, 409)
        self.assertIn('Register the v27.1 model inputs', r.json()['detail'])  # string the UI keys on
        self.assertEqual(self.client.post(base + '/model', json={}).status_code, 201)
        self.assertEqual(self.client.get(base + '/terms').status_code, 200)

    def test_scenario_update_cannot_silently_downgrade_engine(self):
        pid = self._project('Audit Engine')
        cfg = self.client.get('/api/defaults').json()['config']
        cfg.pop('engineVersion', None)
        r = self.client.post(f'/api/projects/{pid}/scenarios', json={'name': 'Base', 'mode': 'underwrite', 'config': cfg})
        self.assertEqual(r.status_code, 201, r.text)
        sid = r.json()['id']
        self.assertEqual(r.json()['config']['engineVersion'], '27.1.0')
        # Client re-saves its own copy without the server-assigned field (the pre-fix UI behaviour).
        self.assertEqual(self.client.put(f'/api/projects/{pid}/scenarios/{sid}', json={'name': 'Base', 'mode': 'underwrite', 'config': cfg}).status_code, 200)
        stored = [s for s in self.client.get(f'/api/projects/{pid}/scenarios').json() if s['id'] == sid][0]
        self.assertEqual(stored['config']['engineVersion'], '27.1.0')
        # An explicit engine change is still honoured.
        self.client.put(f'/api/projects/{pid}/scenarios/{sid}', json={'name': 'Base', 'mode': 'underwrite', 'config': {**cfg, 'engineVersion': '25.8.5'}})
        stored = [s for s in self.client.get(f'/api/projects/{pid}/scenarios').json() if s['id'] == sid][0]
        self.assertEqual(stored['config']['engineVersion'], '25.8.5')


class AuditStatic(unittest.TestCase):
    def test_launcher_is_executable(self):
        self.assertTrue(os.stat(ROOT / 'run_local.sh').st_mode & stat.S_IXUSR)

    def test_no_inline_style_attributes_under_csp(self):
        # style-src 'self' blocks style="" attributes in injected HTML; geometry must go through CSSOM.
        for f in ('app.js', 'power-deliverability.js', 'workspace28.js', 'transaction-workspace.js', 'agent-operations.js', 'permitiq-national.js'):
            self.assertIsNone(re.search(r'style="', (PUBLIC / f).read_text()), f)

    def test_hidden_attribute_wins_everywhere(self):
        for css in PUBLIC.glob('*.css'):
            self.assertIn('[hidden]{display:none!important}', css.read_text().replace(' ', ''), css.name)

    def test_npm_check_covers_every_entrypoint(self):
        import json
        check = json.loads((ROOT / 'package.json').read_text())['scripts']['check']
        for js in PUBLIC.glob('*.js'):
            self.assertIn(f'web/public/{js.name}', check, js.name)

    def test_compiled_source_contains_ported_link(self):
        self.assertIn('National screening ↗', (ROOT / 'web/src/app.ts').read_text())

    def test_no_raw_parcel_hash_in_compare_memo(self):
        src = (PUBLIC / 'workspace28.js').read_text()
        self.assertNotIn('${E(s.parcel_id)} ↗', src)
        self.assertIn('plabel(', src)


if __name__ == '__main__':
    unittest.main()
