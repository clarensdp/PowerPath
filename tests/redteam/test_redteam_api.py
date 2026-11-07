"""Independent red-team API tests for PowerPath v26.4-v26.8 (sections B, C, D, E).

Each test asserts the CORRECT behaviour. A failing test = a reproduced defect against the code under test.
Run against a tree:  RT_ROOT=/path/to/PowerPath_v26_8 python -m unittest test_redteam_api -v
Uses a fresh temporary SQLite store. Synthetic rows only; no network access.
"""
import os, sys, json, tempfile, unittest, hashlib, threading, sqlite3
from pathlib import Path
ROOT = Path(os.environ.get('RT_ROOT') or Path(__file__).resolve().parents[2]).resolve()
sys.path.insert(0, str(ROOT))
TD = tempfile.TemporaryDirectory(prefix='pp_redteam_')
os.environ['POWERPATH_DATA_DIR'] = TD.name
for k in ('POWERPATH_LIVE_AGENTS', 'OPENAI_API_KEY', 'POWERPATH_SHARE_PROJECT_METADATA', 'POWERPATH_AGENT_MODEL'):
    os.environ.pop(k, None)
from fastapi.testclient import TestClient
from server.app import app, db
from server.seed_demo import seed

seed()
C = TestClient(app, base_url='http://127.0.0.1')
PID = 'demo-campus-001'
PJM = 'https://www.pjm.com/planning/services-requests/interconnection-queues'

def new_project(name):
    return C.post('/api/projects', json={'name': name}).json()['id']

def snap(pid, text, src='PJM_QUEUE', url=PJM, published='2026-10-01'):
    return C.post(f'/api/projects/{pid}/intelligence/snapshots', json={'source_key': src, 'source_url': url, 'csv_text': text, 'source_published_date': published, 'import_label': 'analyst_upload'})

def records(snapshot_id):
    with db() as con:
        return {r['record_id']: json.loads(r['record_json']) for r in con.execute('SELECT * FROM intel_records WHERE snapshot_id=?', (snapshot_id,))}

def changes(pid):
    return C.get(f'/api/projects/{pid}/intelligence/changes').json()

def path_project(name):
    """Project with its own path, permit-free milestone, and base underwriting scenario copied from demo."""
    pid = new_project(name)
    base = next(s for s in C.get(f'/api/projects/{PID}/scenarios').json() if s['id'] == 'demo-base-001')
    sid = C.post(f'/api/projects/{pid}/scenarios', json={'name': 'Base', 'mode': 'underwrite', 'config': base['config']}).json()['id']
    path = C.post(f'/api/projects/{pid}/paths', json={'name': 'Grid', 'strategy': 'grid', 'capacity_mw': 150, 'power_month': 30, 'delay_months': 0}).json()['id']
    ms = C.post(f'/api/projects/{pid}/milestones', json={'title': 'Utility study', 'category': 'utility', 'path_id': path, 'delay_months': 0}).json()['id']
    return pid, sid, path, ms


class B_ImportProvenance(unittest.TestCase):
    def test_B01_pjm_header_order_state_before_status_parses_status(self):
        """Real PJM queue exports list 'State' before 'Status'. 'state' is also a STATUS alias."""
        pid = new_project('B01')
        csv1 = 'Queue Number,Name,State,County,Status,Projected In Service Date\nAG1-001,Synthetic Solar,VA,Loudoun,Active,2029-06-30\n'
        r = snap(pid, csv1); self.assertEqual(r.status_code, 201, r.text)
        rec = records(r.json()['id'])['AG1-001']
        self.assertEqual(rec['status'], 'Active', f'status parsed as {rec["status"]!r}')

    def test_B02_status_withdrawal_detected_with_pjm_header_order(self):
        pid = new_project('B02')
        h = 'Queue Number,Name,State,County,Status,Projected In Service Date\n'
        self.assertEqual(snap(pid, h + 'AG1-001,Synthetic Solar,VA,Loudoun,Active,2029-06-30\n').status_code, 201)
        r = snap(pid, h + 'AG1-001,Synthetic Solar,VA,Loudoun,Withdrawn,2029-06-30\n', published='2026-10-15')
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()['changes'], 1, 'queue withdrawal produced no change record')

    def test_B03_european_decimal_not_silently_rescaled(self):
        pid = new_project('B03')
        r = snap(pid, 'record_id,name,capacity_mw\nX1,Synthetic,"1.234,5"\n')
        if r.status_code == 201:
            self.assertAlmostEqual(records(r.json()['id'])['X1']['capacity_mw'], 1234.5, msg='1.234,5 MW stored with wrong magnitude')

    def test_B04_unmapped_columns_are_reported(self):
        pid = new_project('B04')
        r = snap(pid, 'Queue Number,Name,MW Capacity,Fuel Type\nQ9,Synthetic,250,Gas\n')
        self.assertEqual(r.status_code, 201, r.text)
        body = r.json()
        self.assertTrue(any(k in body for k in ('unmapped_columns', 'warnings')), f'no warning for dropped column "MW Capacity": {body}')

    def test_B05_original_source_bytes_retrievable(self):
        pid = new_project('B05')
        raw = 'record_id,name,status,extra_col\r\nR1,Synthetic,Study,kept?\r\n'
        r = snap(pid, raw); self.assertEqual(r.status_code, 201)
        got = C.get(f'/api/projects/{pid}/intelligence/snapshots/{r.json()["id"]}/raw')
        self.assertEqual(got.status_code, 200, f'original CSV text not retrievable (HTTP {got.status_code}); only parsed fields are stored')
        self.assertEqual(got.text, raw, 'retained text differs from what was imported')
        self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(), r.json()['sha256'])

    def test_B06_future_publication_date_rejected(self):
        pid = new_project('B06')
        r = snap(pid, 'record_id,name\nF1,Synthetic\n', published='2099-01-01')
        self.assertEqual(r.status_code, 422, 'publication date in 2099 accepted')

    def test_B07_older_vintage_imported_late_is_not_diffed_as_new_change(self):
        pid = new_project('B07')
        newer = 'record_id,name,status\nV1,Synthetic,Restudy\n'
        older = 'record_id,name,status\nV1,Synthetic,Study\n'
        self.assertEqual(snap(pid, newer, published='2026-10-15').status_code, 201)
        r = snap(pid, older, published='2026-10-01')
        if r.status_code == 201:
            ch = [c for c in changes(pid)]
            self.assertFalse(any(c['delta'].get('status', {}).get('after') == 'Study' for c in ch),
                             'older 2026-10-01 vintage diffed as if status moved Restudy -> Study after 2026-10-15')

    def test_B08_revert_to_previous_bytes_is_recorded(self):
        pid = new_project('B08')
        a = 'record_id,name,status\nR1,Synthetic,Study\n'; b = 'record_id,name,status\nR1,Synthetic,Restudy\n'
        snap(pid, a, published='2026-10-01'); snap(pid, b, published='2026-10-08')
        r = snap(pid, a, published='2026-10-15')
        self.assertEqual(r.status_code, 201, f'reversion Restudy->Study rejected: HTTP {r.status_code} {r.text[:120]}')

    def test_B09_domain_spoofing(self):
        pid = new_project('B09')
        for url in ['https://pjm.com.evil.example/', 'https://www.pjm.com@evil.example/', 'http://www.pjm.com/', 'https://evilpjm.com/']:
            self.assertEqual(snap(pid, 'record_id,name\nS1,x\n', url=url).status_code, 422, url)

    def test_B10_operator_bytes_not_labelled_public_source(self):
        """Fabricated bytes with an official URL must not be described as a public-source snapshot."""
        pid = new_project('B10')
        r = snap(pid, 'record_id,name,status\nFAKE-1,Fabricated by operator,Energized\n')
        self.assertEqual(r.status_code, 201)
        self.assertNotIn('PUBLIC SOURCE SNAPSHOT', r.json()['status'], 'unauthenticated upload labelled as a public source snapshot')

    def test_B11_bom_header_csv_accepted(self):
        pid = new_project('B11')
        r = snap(pid, '﻿record_id,name\nB1,Synthetic\n')
        self.assertEqual(r.status_code, 201, f'UTF-8 BOM CSV rejected: {r.text[:120]}')

    def test_B12_parse_failure_is_atomic(self):
        pid = new_project('B12')
        rows = ''.join(f'R{i},n,{i}\n' for i in range(1000)) + 'R1000,n,not-a-number\n'
        r = snap(pid, 'record_id,name,capacity_mw\n' + rows)
        self.assertEqual(r.status_code, 422)
        self.assertEqual(C.get(f'/api/projects/{pid}/intelligence/snapshots').json(), [])

    def test_B13_oversize_rejected(self):
        pid = new_project('B13')
        r = snap(pid, 'record_id,name\n' + ''.join(f'R{i},n\n' for i in range(2501)))
        self.assertEqual(r.status_code, 422)

    def test_B14_long_field_change_beyond_180_chars_detected(self):
        pid = new_project('B14')
        pre = 'x' * 180
        snap(pid, f'record_id,name\nL1,{pre}A\n')
        r = snap(pid, f'record_id,name\nL1,{pre}B\n', published='2026-10-02')
        self.assertEqual(r.json().get('changes'), 1, 'change after character 180 silently discarded')

    def test_B15_concurrent_imports_diff_against_true_predecessor(self):
        pid = new_project('B15')
        snap(pid, 'record_id,status\nK1,s0\n')
        errs = []
        def go(i):
            r = snap(pid, f'record_id,status\nK1,s{i}\n', published='2026-10-02')
            if r.status_code != 201: errs.append(r.status_code)
        ts = [threading.Thread(target=go, args=(i,)) for i in range(1, 9)]
        [t.start() for t in ts]; [t.join() for t in ts]
        with db() as con:
            snaps = [r['id'] for r in con.execute('SELECT id FROM intel_snapshots WHERE project_id=? ORDER BY created_at,rowid', (pid,))]
            bad = 0
            for prev, cur in zip(snaps, snaps[1:]):
                p = records(prev)['K1']['status']; c = records(cur)['K1']['status']
                rows = con.execute('SELECT delta_json FROM intel_changes WHERE snapshot_id=?', (cur,)).fetchall()
                before = json.loads(rows[0]['delta_json'])['status']['before'] if rows else c
                if before != p: bad += 1
        self.assertEqual(bad, 0, f'{bad} snapshot diff(s) computed against a stale predecessor under concurrent import')


class C_ChangeDetection(unittest.TestCase):
    def test_C01_reorder_is_not_a_change(self):
        pid = new_project('C01')
        snap(pid, 'record_id,name\nA,1\nB,2\n'); r = snap(pid, 'record_id,name\nB,2\nA,1\n', published='2026-10-02')
        self.assertEqual(r.json()['changes'], 0)

    def test_C02_sources_isolated(self):
        pid = new_project('C02')
        snap(pid, 'record_id,status\nSAME,Study\n')
        r = snap(pid, 'record_id,status\nSAME,Operating\n', src='ERCOT_GIS', url='https://www.ercot.com/gridinfo/resource')
        self.assertEqual(r.json()['changes'], 0, 'ERCOT snapshot diffed against PJM rows')

    def test_C03_cross_project_proposal_decision_and_impact_blocked(self):
        pid, sid, path, ms = path_project('C03-owner')
        snap(pid, 'record_id,status\nX,a\n'); snap(pid, 'record_id,status\nX,b\n', published='2026-10-02')
        ch = changes(pid)[0]['id']
        prop = C.post(f'/api/projects/{pid}/intelligence/proposals', json={'change_id': ch, 'milestone_id': ms, 'proposed_delay_months': 4, 'reason': 'Synthetic test linkage only.'}).json()['id']
        attacker = new_project('C03-attacker')
        self.assertEqual(C.get(f'/api/projects/{attacker}/intelligence/proposals/{prop}/impact').status_code, 404)
        self.assertEqual(C.post(f'/api/projects/{attacker}/intelligence/proposals/{prop}/approve').status_code, 404)

    def test_C04_import_never_touches_milestones_or_scenarios(self):
        def dumpdb():
            with db() as con:
                return [tuple(r) for r in con.execute('SELECT id,delay_months,updated_at FROM delivery_milestones ORDER BY id')] + \
                       [tuple(r) for r in con.execute('SELECT id,version,config_json FROM scenarios ORDER BY id')]
        before = dumpdb()
        snap(PID, 'record_id,status\nZ9,Study\n', published='2026-09-01'); snap(PID, 'record_id,status\nZ9,Withdrawn\n', published='2026-09-02')
        self.assertEqual(before, dumpdb())


class D_Milestones(unittest.TestCase):
    def _two_proposals(self, tag, d1, d2):
        pid, sid, path, ms = path_project(tag)
        snap(pid, 'record_id,status\nQ,a\n'); snap(pid, 'record_id,status\nQ,b\n', published='2026-10-02')
        ch = changes(pid)[0]['id']
        mk = lambda d: C.post(f'/api/projects/{pid}/intelligence/proposals', json={'change_id': ch, 'milestone_id': ms, 'proposed_delay_months': d, 'reason': 'Synthetic test linkage only.'}).json()['id']
        return pid, sid, path, ms, mk(d1), mk(d2)

    def test_D01_stale_proposal_cannot_silently_shorten_an_approved_delay(self):
        pid, sid, path, ms, p6, p3 = self._two_proposals('D01', 6, 3)
        self.assertEqual(C.post(f'/api/projects/{pid}/intelligence/proposals/{p6}/approve').status_code, 200)
        r = C.post(f'/api/projects/{pid}/intelligence/proposals/{p3}/approve')
        delay = next(m for m in C.get(f'/api/projects/{pid}/milestones').json() if m['id'] == ms)['delay_months']
        self.assertTrue(r.status_code == 409 or delay >= 6, f'approved 6-month delay silently reduced to {delay} by stale proposal (HTTP {r.status_code})')

    def test_D02_manual_edit_after_proposal_not_overwritten_silently(self):
        pid, sid, path, ms, p2, _ = self._two_proposals('D02', 2, 2)
        m = next(x for x in C.get(f'/api/projects/{pid}/milestones').json() if x['id'] == ms)
        upd = {k: m[k] for k in ('title', 'category', 'status', 'path_id', 'permit_id', 'planned_month', 'predecessor_id', 'source_url', 'source_note', 'evidence_id')}
        upd['delay_months'] = 10
        self.assertEqual(C.put(f'/api/projects/{pid}/milestones/{ms}', json=upd).status_code, 200)
        r = C.post(f'/api/projects/{pid}/intelligence/proposals/{p2}/approve')
        delay = next(x for x in C.get(f'/api/projects/{pid}/milestones').json() if x['id'] == ms)['delay_months']
        self.assertTrue(r.status_code == 409 or delay == 10, f'analyst 10-month estimate overwritten to {delay} by proposal drafted earlier')

    @unittest.expectedFailure  # KNOWN OPEN RT-D03: needs authentication/RBAC (milestone NM-2); not faked with a self-declared string
    def test_D03_approval_records_an_authenticated_approver(self):
        pid, sid, path, ms, p, _ = self._two_proposals('D03', 1, 1)
        r = C.post(f'/api/projects/{pid}/intelligence/proposals/{p}/approve')
        self.assertEqual(r.status_code, 200)
        with db() as con:
            cols = [c[1] for c in con.execute('PRAGMA table_info(intel_proposals)')] + [c[1] for c in con.execute('PRAGMA table_info(activity)')]
        self.assertTrue(any(c in cols for c in ('approved_by', 'actor', 'user_id', 'decided_by')), 'no approver identity stored anywhere')

    def test_D04_change_review_state_updated_after_decision(self):
        pid, sid, path, ms, p, _ = self._two_proposals('D04', 1, 1)
        C.post(f'/api/projects/{pid}/intelligence/proposals/{p}/approve')
        ch = changes(pid)[0]
        self.assertNotEqual(ch['review_state'], 'open', 'source change still open after its proposal was approved')

    def test_D05_proposal_on_completed_milestone_rejected(self):
        pid, sid, path, ms = path_project('D05')
        m = next(x for x in C.get(f'/api/projects/{pid}/milestones').json() if x['id'] == ms)
        upd = {k: m[k] for k in ('title', 'category', 'path_id', 'permit_id', 'planned_month', 'delay_months', 'predecessor_id', 'source_url', 'source_note', 'evidence_id')}
        upd['status'] = 'completed'
        C.put(f'/api/projects/{pid}/milestones/{ms}', json=upd)
        snap(pid, 'record_id,status\nQ,a\n'); snap(pid, 'record_id,status\nQ,b\n', published='2026-10-02')
        r = C.post(f'/api/projects/{pid}/intelligence/proposals', json={'change_id': changes(pid)[0]['id'], 'milestone_id': ms, 'proposed_delay_months': 9, 'reason': 'Synthetic test linkage only.'})
        self.assertEqual(r.status_code, 422, 'delay proposal accepted for a completed milestone (approval would have no modeled effect)')

    def test_D06_cycle_via_edit_rejected(self):
        pid, sid, path, ms = path_project('D06')
        b = C.post(f'/api/projects/{pid}/milestones', json={'title': 'ESA', 'category': 'utility', 'path_id': path, 'predecessor_id': ms}).json()['id']
        m = next(x for x in C.get(f'/api/projects/{pid}/milestones').json() if x['id'] == ms)
        upd = {k: m[k] for k in ('title', 'category', 'status', 'path_id', 'permit_id', 'planned_month', 'delay_months', 'source_url', 'source_note', 'evidence_id')}
        upd['predecessor_id'] = b
        self.assertEqual(C.put(f'/api/projects/{pid}/milestones/{ms}', json=upd).status_code, 422)


class E_FinanceImpact(unittest.TestCase):
    def _setup(self, tag, delay):
        pid, sid, path, ms = path_project(tag)
        snap(pid, 'record_id,status\nQ,a\n'); snap(pid, 'record_id,status\nQ,b\n', published='2026-10-02')
        p = C.post(f'/api/projects/{pid}/intelligence/proposals', json={'change_id': changes(pid)[0]['id'], 'milestone_id': ms, 'proposed_delay_months': delay, 'reason': 'Synthetic test linkage only.'}).json()['id']
        return pid, sid, path, ms, p

    def test_E01_preview_is_read_only(self):
        pid, sid, path, ms, p = self._setup('E01', 7)
        def dumpall():
            with db() as con:
                return {t: [tuple(r) for r in con.execute(f'SELECT * FROM {t}')] for t in ('scenarios', 'runs', 'delivery_milestones', 'intel_proposals', 'activity')}
        before = dumpall(); r = C.get(f'/api/projects/{pid}/intelligence/proposals/{p}/impact'); self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(before, dumpall())

    def test_E02_preview_matches_approved_versioned_run_and_hash_traces(self):
        pid, sid, path, ms, p = self._setup('E02', 7)
        prev = C.get(f'/api/projects/{pid}/intelligence/proposals/{p}/impact').json()
        C.post(f'/api/projects/{pid}/intelligence/proposals/{p}/approve')
        s = C.post(f'/api/projects/{pid}/paths/{path}/sensitivity-v263', json={'source_scenario_id': sid}).json()
        run = C.post(f'/api/projects/{pid}/scenarios/{s["id"]}/runs').json()
        self.assertAlmostEqual(run['summary']['npvM'], prev['proposed']['npvM'], places=6)
        # Traceability: the run must be linkable to the proposal by a structured key or by the preview's input hash.
        cfg = dict(run_cfg := C.get(f'/api/projects/{pid}/runs/{run["id"]}').json()['input']); cfg.pop('powerPathLink', None)
        dump = json.dumps(cfg, sort_keys=True, separators=(',', ':'))
        linked = p in json.dumps(run_cfg.get('powerPathLink', {}).get('proposal_ids', [])) or hashlib.sha256(dump.encode()).hexdigest() == prev['proposed']['assumptions_hash']
        self.assertTrue(linked, 'approved run cannot be traced to the proposal/preview by structured id or input hash')

    def test_E03_derived_scenario_edit_cannot_bypass_double_count_guard(self):
        pid, sid, path, ms, p = self._setup('E03', 7)
        C.post(f'/api/projects/{pid}/intelligence/proposals/{p}/approve')
        s1 = C.post(f'/api/projects/{pid}/paths/{path}/sensitivity-v263', json={'source_scenario_id': sid}).json()
        cfg = {k: v for k, v in s1['config'].items() if k != 'powerPathLink'}
        put = C.put(f'/api/projects/{pid}/scenarios/{s1["id"]}', json={'name': 'edited', 'mode': 'underwrite', 'config': cfg})
        if put.status_code == 422: return  # lineage removal refused: guard cannot be bypassed
        self.assertEqual(put.status_code, 200)
        r = C.post(f'/api/projects/{pid}/paths/{path}/sensitivity-v263', json={'source_scenario_id': s1['id']})
        base_delay = next(x for x in C.get(f'/api/projects/{pid}/scenarios').json() if x['id'] == sid)['config'].get('delayMonths', 0)
        self.assertTrue(r.status_code == 422 or r.json()['config']['delayMonths'] == base_delay + 7,
                        f'critical-path delay applied twice (delayMonths={r.json()["config"]["delayMonths"] if r.status_code==201 else "-"})')

    def test_E04a_v262_path_sensitivity_rejects_linked_base(self):
        r = C.post(f'/api/projects/{PID}/paths/demo-path-grid/sensitivity', json={'source_scenario_id': 'demo-base-001', 'include_open_permit_delay': True}).json()
        again = C.post(f'/api/projects/{PID}/paths/demo-path-grid/sensitivity', json={'source_scenario_id': r['id'], 'include_open_permit_delay': True})
        self.assertEqual(again.status_code, 422, f'v26.2 sensitivity accepted an already path-linked base (delays chained to {again.json().get("delay_months")})')

    # RT-E04b fixed in v27.1: both routes use the canonical schedule engine (server/schedule27.py).
    def test_E04b_one_delay_convention_across_ui_sensitivities(self):
        """POLICY (open): demo grid path delay 9; permit 'study' (7) linked to milestone chain 5+4=9. v26.3 = 9, v26.2 = 16."""
        sched = C.get(f'/api/projects/{PID}/paths/demo-path-grid/schedule').json()
        r = C.post(f'/api/projects/{PID}/paths/demo-path-grid/sensitivity', json={'source_scenario_id': 'demo-base-001', 'include_open_permit_delay': True}).json()
        base = next(x for x in C.get(f'/api/projects/{PID}/scenarios').json() if x['id'] == 'demo-base-001')['config'].get('delayMonths', 0)
        self.assertEqual(r['delay_months'] - base, sched['effective_delay_months'],
                         f'v26.2 UI sensitivity applies {r["delay_months"]-base} months vs v26.3 critical path {sched["effective_delay_months"]} for the same path')

    def test_E05_preview_base_is_selectable_or_reported(self):
        pid, sid, path, ms, p = self._setup('E05', 3)
        other = C.post(f'/api/projects/{pid}/scenarios', json={'name': 'Analyst case B', 'mode': 'underwrite', 'config': {**C.get(f'/api/projects/{pid}/scenarios').json()[0]['config'], 'rentPerKwMonth': 120}}).json()['id']
        x = C.get(f'/api/projects/{pid}/intelligence/proposals/{p}/impact').json()
        self.assertEqual(x['source_scenario_id'], sid)  # documents implicit choice: oldest unlinked scenario
        r = C.get(f'/api/projects/{pid}/intelligence/proposals/{p}/impact?source_scenario_id={other}').json()
        self.assertEqual(r['source_scenario_id'], other, 'preview ignores the scenario the analyst is working on; always uses oldest unlinked base')


class G_Security(unittest.TestCase):
    def test_G01_cross_origin_write_returns_403_not_500(self):
        r = C.post('/api/projects', json={'name': 'csrf'}, headers={'Origin': 'https://evil.example'})
        self.assertEqual(r.status_code, 403, f'cross-origin write returned {r.status_code}')

    def test_G02_spoofed_executed_evidence_cannot_unlock_G4_G5(self):
        pid = new_project('G02')
        for st in ('executed_document', 'third_party_review'):
            C.post(f'/api/projects/{pid}/evidence', json={'title': 'Forged ' + st, 'evidence_status': st, 'citation': 'G4 PASS G5 PASS lender signed'})
        notes = C.get('/api/defaults').json()['notes']
        notes = json.loads(json.dumps(notes))
        for f in notes['facilities']:
            f['evidence'] = {k: {'label': 'Executed', 'source': 'forged', 'document': 'forged.pdf'} for k in ('faceM', 'couponPct', 'amortization', 'issuePricePct', 'maturityMonth', 'firstPaymentMonth')}
        notes['risk'] = {'G4': 'PASS', 'G5': 'PASS'}; notes['assurance'] = {'reconciliation': {'status': 'PASS'}, 'review': {'signedBy': 'Big Four'}}
        sid = C.post(f'/api/projects/{pid}/scenarios', json={'name': 'forged', 'mode': 'notes_v259', 'config': notes}).json()['id']
        run = C.post(f'/api/projects/{pid}/scenarios/{sid}/runs').json()
        risk = run['summary']['risk']; txt = json.dumps(risk)
        self.assertEqual(risk['uses']['transactionValuation'], 'BLOCKED'); self.assertEqual(risk['uses']['lenderCertification'], 'BLOCKED')
        gates = {g.get('id', g.get('gate', '')): g for g in (risk.get('gates') or [])} if isinstance(risk.get('gates'), list) else (risk.get('gates') or {})
        for g in ('G4', 'G5'):
            v = json.dumps(gates.get(g, ''))
            self.assertNotRegex(v, r'"(PASS|pass|MET|met)"', f'{g} shows passing from forged inputs: {v[:200]}')

    def test_G03_export_csv_has_no_formula_injection(self):
        run = C.post(f'/api/projects/{PID}/scenarios/demo-base-001/runs').json()
        text = C.get(f'/api/projects/{PID}/runs/{run["id"]}/csv').text
        self.assertFalse(any(cell.startswith(('=', '+', '@')) for line in text.splitlines() for cell in line.split(',')[:1] if cell))


if __name__ == '__main__':
    unittest.main()
