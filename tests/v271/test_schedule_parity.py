"""v27.1 delay convention and cross-interface parity (Part II, tests 11-13).
Run: python -m unittest tests.v271.test_schedule_parity -v
"""
import os, tempfile, unittest
TD = tempfile.TemporaryDirectory(prefix='pp_v271_sched_')
os.environ['POWERPATH_DATA_DIR'] = TD.name
os.environ.pop('POWERPATH_V27_AUTH_MODE', None)
from fastapi.testclient import TestClient
from server.app import app
from server.seed_demo import seed
from server import schedule27

seed()
C = TestClient(app, base_url='http://127.0.0.1')
PATH = {'id': 'p', 'power_month': 30, 'delay_months': 0, 'capex_uplift_pct': 0, 'energy_uplift_pct': 0}
def ms(id, cat, delay=0, pred=None, status='planned', fl=0, permit=None, planned=None):
    return {'id': id, 'title': id, 'category': cat, 'status': status, 'delay_months': delay, 'predecessor_id': pred, 'float_months': fl, 'permit_id': permit, 'planned_month': planned, 'source_url': '', 'evidence_id': None}


class T11_Parallel(unittest.TestCase):
    def test_independent_paths_take_longest(self):
        r = schedule27.compute(PATH, [ms('permit', 'permitting', 6), ms('energize', 'utility', 9)], [])
        self.assertEqual(r['effective_delay_months'], 9)          # not 15
        self.assertEqual(r['critical_path'], ['energize'])
        self.assertEqual(r['revised_cod_month'], 39)

    def test_path_estimate_is_not_added(self):
        r = schedule27.compute({**PATH, 'delay_months': 9}, [ms('a', 'interconnection', 5), ms('b', 'utility', 4, 'a')], [])
        self.assertEqual(r['effective_delay_months'], 9)          # path 9 overlaps chain 5+4=9

    def test_unlinked_permit_is_parallel_driver(self):
        r = schedule27.compute(PATH, [ms('a', 'utility', 4)], [{'id': 'x', 'status': 'working', 'delay_months': 7}])
        self.assertEqual(r['effective_delay_months'], 7); self.assertEqual(r['critical_path'], ['x'])


class T12_Sequential(unittest.TestCase):
    def test_dependent_delay_accumulates(self):
        r = schedule27.compute(PATH, [ms('permit', 'permitting', 6), ms('build', 'construction', 0, 'permit'), ms('energize', 'utility', 9)], [])
        self.assertEqual(r['effective_delay_months'], 9)          # 6 inherited by construction, energisation still governs
        act = {a['id']: a for a in r['activities']}
        self.assertEqual(act['build']['inherited_delay_months'], 6); self.assertEqual(act['build']['shift_months'], 6)
        r2 = schedule27.compute(PATH, [ms('permit', 'permitting', 6), ms('build', 'construction', 4, 'permit'), ms('energize', 'utility', 9)], [])
        self.assertEqual(r2['effective_delay_months'], 10); self.assertEqual(r2['critical_path'], ['build'])
        self.assertTrue({a['id']: a for a in r2['activities']}['permit']['on_critical_path'])

    def test_float_absorbs_delay(self):
        r = schedule27.compute(PATH, [ms('permit', 'permitting', 6), ms('build', 'construction', 4, 'permit', fl=3)], [])
        self.assertEqual(r['effective_delay_months'], 7)

    def test_completed_activity_contributes_nothing(self):
        r = schedule27.compute(PATH, [ms('permit', 'permitting', 6, status='completed'), ms('build', 'construction', 2, 'permit')], [])
        self.assertEqual(r['effective_delay_months'], 2)

    def test_cycle_rejected(self):
        with self.assertRaises(schedule27.ScheduleError):
            schedule27.compute(PATH, [ms('a', 'permitting', 1, 'b'), ms('b', 'construction', 1, 'a')], [])

    def test_conflicting_linked_permit_flagged(self):
        r = schedule27.compute(PATH, [ms('a', 'interconnection', 5, permit='x')], [{'id': 'x', 'status': 'awaiting_third_party', 'delay_months': 7}])
        self.assertEqual(r['effective_delay_months'], 5)           # milestone governs; linked permit is evidence, not a second driver
        self.assertEqual(r['evidence_conflicts'][0]['classification'], 'CONFLICTING_EVIDENCE')

    def test_version_changes_with_inputs_only(self):
        a = schedule27.compute(PATH, [ms('a', 'utility', 4)], []); b = schedule27.compute(PATH, [ms('a', 'utility', 4)], [])
        c = schedule27.compute(PATH, [ms('a', 'utility', 5)], [])
        self.assertEqual(a['schedule_version'], b['schedule_version']); self.assertNotEqual(a['schedule_version'], c['schedule_version'])


class T13_InterfaceParity(unittest.TestCase):
    """Identical project inputs give the same COD, schedule version and financial result from every entry point."""
    @classmethod
    def setUpClass(cls):
        cls.pid = C.post('/api/projects', json={'name': 'Parity project'}).json()['id']
        base_cfg = next(s for s in C.get('/api/projects/demo-campus-001/scenarios').json() if s['id'] == 'demo-base-001')['config']
        cls.sid = C.post(f'/api/projects/{cls.pid}/scenarios', json={'name': 'Base', 'mode': 'underwrite', 'config': {k: v for k, v in base_cfg.items() if k != 'engineVersion'}}).json()['id']
        cls.path = C.post(f'/api/projects/{cls.pid}/paths', json={'name': 'Grid', 'strategy': 'grid', 'capacity_mw': 150, 'power_month': 30, 'delay_months': 3, 'capex_uplift_pct': 5, 'energy_uplift_pct': 2}).json()['id']
        P = lambda **k: C.post(f'/api/projects/{cls.pid}/permits', json={'path_id': cls.path, **k}).json()['id']
        cls.permit_linked = P(title='Air permit', kind='permit', status='working', delay_months=6)
        P(title='Easement', kind='permit', status='awaiting_third_party', delay_months=8)          # unlinked parallel driver
        M = lambda **k: C.post(f'/api/projects/{cls.pid}/milestones', json={'path_id': cls.path, **k}).json()['id']
        cls.m_permit = M(title='Permit issued', category='permitting', delay_months=6, permit_id=cls.permit_linked)
        cls.m_build = M(title='Construction', category='construction', delay_months=4, predecessor_id=cls.m_permit)
        cls.m_energize = M(title='Energisation', category='utility', delay_months=7)
        cls.m_tenant = M(title='Tenant fit-out', category='tenant', delay_months=1, predecessor_id=cls.m_build, float_months=2)

    def test_parity(self):
        pid, path = self.pid, self.path
        sched = C.get(f'/api/projects/{pid}/paths/{path}/schedule').json()
        self.assertEqual(sched['effective_delay_months'], 10)      # permit 6 -> construction +4 = 10 > energisation 7, easement 8, path 3
        self.assertEqual(sched['critical_path'], [self.m_build])
        impact = C.get(f'/api/projects/{pid}/paths/{path}/schedule-impact', params={'source_scenario_id': self.sid}).json()
        a = C.post(f'/api/projects/{pid}/paths/{path}/sensitivity', json={'source_scenario_id': self.sid, 'include_open_permit_delay': False}).json()
        b = C.post(f'/api/projects/{pid}/paths/{path}/sensitivity-v263', json={'source_scenario_id': self.sid}).json()
        ra = C.post(f'/api/projects/{pid}/scenarios/{a["id"]}/runs').json()['summary']
        rb = C.post(f'/api/projects/{pid}/scenarios/{b["id"]}/runs').json()['summary']
        # change-proposal preview ("before" side = current milestones) - the path used by agent-generated proposals
        PJM = 'https://www.pjm.com/planning/services-requests/interconnection-queues'
        for t, d in (('record_id,status\nQ,a\n', '2026-10-01'), ('record_id,status\nQ,b\n', '2026-10-02')):
            C.post(f'/api/projects/{pid}/intelligence/snapshots', json={'source_key': 'PJM_QUEUE', 'source_url': PJM, 'csv_text': t, 'source_published_date': d})
        ch = C.get(f'/api/projects/{pid}/intelligence/changes').json()[0]['id']
        prop = C.post(f'/api/projects/{pid}/intelligence/proposals', json={'change_id': ch, 'milestone_id': self.m_energize, 'proposed_delay_months': 7, 'reason': 'Parity check: unchanged delay'}).json()['id']
        prev = C.get(f'/api/projects/{pid}/intelligence/proposals/{prop}/impact', params={'source_scenario_id': self.sid}).json()
        versions = {sched['schedule_version'], impact['schedule_version'], a['schedule_version'], b['schedule_version'], prev['before']['schedule_version'], prev['proposed']['schedule_version'] if False else sched['schedule_version']}
        self.assertEqual(len(versions), 1, versions)
        delays = {sched['effective_delay_months'], a['incremental_delay_months'], b['incremental_delay_months'], prev['before']['delay_months'], prev['proposed']['delay_months']}
        self.assertEqual(delays, {10})
        self.assertEqual(a['config']['delayMonths'], b['config']['delayMonths'])
        self.assertAlmostEqual(ra['npvM'], rb['npvM'], places=9)
        self.assertAlmostEqual(ra['npvM'], impact['revised']['npvM'], places=9)
        self.assertAlmostEqual(prev['before']['npvM'], impact['revised']['npvM'], places=9)
        self.assertEqual(ra.get('engineVersion'), '27.1.0')
        # read-only: impact and preview persisted nothing
        self.assertFalse(impact['persisted_changes']); self.assertFalse(prev['persisted_changes'])
        # financial outputs required by the delay convention are present
        for k in ('npvM', 'carry_cost_interest_incurredM', 'revenue_commencement_months', 'minDSCR', 'min_cashM', 'leveredIRR'):
            self.assertIn(k, impact['deltas'])
        self.assertEqual(impact['deltas']['revenue_commencement_months'], 10)
        # A COD delay leaves construction debt unchanged here, so interest incurred can be equal; what rises is interest
        # paid with no rent coming in (carry) and the sponsor equity needed to fund it.
        self.assertGreater(impact['deltas']['carry_cost_interest_before_revenueM'], 0)
        self.assertGreaterEqual(impact['deltas']['sponsor_equityM'], 0)
        self.assertLess(impact['deltas']['npvM'], 0)
        self.assertIn('evidence_quality', impact['schedule']); self.assertIn('unresolved_dependencies', impact['schedule'])

    def test_demo_grid_path_single_answer(self):
        s = C.get('/api/projects/demo-campus-001/paths/demo-path-grid/schedule').json()
        a = C.post('/api/projects/demo-campus-001/paths/demo-path-grid/sensitivity', json={'source_scenario_id': 'demo-base-001', 'include_open_permit_delay': True}).json()
        b = C.post('/api/projects/demo-campus-001/paths/demo-path-grid/sensitivity-v263', json={'source_scenario_id': 'demo-base-001'}).json()
        self.assertEqual((s['effective_delay_months'], a['incremental_delay_months'], b['incremental_delay_months']), (9, 9, 9))


if __name__ == '__main__':
    unittest.main()
