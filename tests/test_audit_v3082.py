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

    def test_financial_runs_and_audit_log_are_append_only(self):
        import sqlite3
        from server.app import db
        pid = self._project('Audit Append')
        cfg = self.client.get('/api/defaults').json()['config']
        sid = self.client.post(f'/api/projects/{pid}/scenarios', json={'name': 'Base', 'mode': 'underwrite', 'config': cfg}).json()['id']
        rid = self.client.post(f'/api/projects/{pid}/scenarios/{sid}/runs').json()['id']
        with db() as con:
            for sql in ("UPDATE runs SET summary_json='{}' WHERE id=?", 'DELETE FROM runs WHERE id=?'):
                with self.assertRaises(sqlite3.DatabaseError):
                    con.execute(sql, (rid,))
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute('DELETE FROM activity WHERE project_id=?', (pid,))
        self.assertEqual(self.client.get(f'/api/projects/{pid}/runs/{rid}').status_code, 200)

    def test_evidence_attaches_once_and_never_deletes(self):
        import io, sqlite3
        from server.app import db
        pid = self._project('Audit Evidence')
        eid = self.client.post(f'/api/projects/{pid}/evidence', json={'title': 'Utility letter', 'category': 'utility'}).json()['id']
        up = self.client.post(f'/api/projects/{pid}/evidence/{eid}/file', files={'attachment': ('letter.pdf', io.BytesIO(b'%PDF-1.4 test'), 'application/pdf')})
        self.assertEqual(up.status_code, 200, up.text)  # the one permitted update still works through the API
        with db() as con:
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute("UPDATE evidence SET title='Edited' WHERE id=?", (eid,))
            with self.assertRaises(sqlite3.DatabaseError):
                con.execute('DELETE FROM evidence WHERE id=?', (eid,))

    def test_postgres_policies_grant_no_update_or_delete_on_financial_records(self):
        from infrastructure.runtime_policies import compile_policies
        sql = compile_policies('pp', {'runs': ['id', 'scenario_id'], 'scenarios': ['id', 'project_id'], 'activity': ['id', 'project_id'],
                                      'feasibility_v82_runs': ['id', 'project_id'], 'evidence': ['id', 'project_id', 'stored_filename']})
        for t in ('runs', 'activity', 'feasibility_v82_runs', 'evidence'):
            self.assertNotIn(f'GRANT UPDATE,DELETE ON pp.{t} ', sql)
            self.assertNotIn(f'FOR DELETE TO powerpath_app USING', sql.split(f'ON pp.{t} ')[1].split('ALTER TABLE')[0] if f'ON pp.{t} ' in sql else '')
        self.assertIn("attach_file_once ON pp.evidence", sql)
        self.assertIn('GRANT UPDATE,DELETE ON pp.scenarios ', sql)  # ordinary editable tables unchanged

    def test_starter_scenario_is_opt_in_sized_and_runs(self):
        plain = self.client.post('/api/projects', json={'name': 'No starter', 'target_mw': 120}).json()
        self.assertIsNone(plain['starter_scenario_id'])
        self.assertEqual(self.client.get(f"/api/projects/{plain['id']}/scenarios").json(), [])
        for mw in (37.5, 120, 200, 1000):
            p = self.client.post('/api/projects?starter_scenario=true', json={'name': f'Starter {mw}', 'target_mw': mw}).json()
            sc = self.client.get(f"/api/projects/{p['id']}/scenarios").json()
            self.assertEqual(len(sc), 1)
            cfg = sc[0]['config']
            self.assertAlmostEqual(sum(b['itMW'] for b in cfg['buildings']), mw, places=6)
            self.assertEqual(cfg['engineVersion'], '27.1.0')
            self.assertLessEqual(len(cfg['buildings']), 10)
            run = self.client.post(f"/api/projects/{p['id']}/scenarios/{sc[0]['id']}/runs")
            self.assertEqual(run.status_code, 201, run.text)
        zero = self.client.post('/api/projects?starter_scenario=true', json={'name': 'Zero MW', 'target_mw': 0}).json()
        self.assertIsNone(zero['starter_scenario_id'])


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


def test_restore_drill_passes():
    """Backup (DB + evidence files) -> verify -> restore into an empty dir -> identical API state + triggers."""
    from scripts.restore_drill import run

    result = run()
    assert result["passed"], result["checks"]
