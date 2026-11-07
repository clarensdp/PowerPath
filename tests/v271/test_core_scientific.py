"""v27.1 Core Scientific note reconstruction, evidence controls, immutability and gates (Part VI tests 14-17, 19, 20).
The note oracle below is written independently of engine/fixed_note27.cjs (own date generation, own 30/360, Newton yield).
Run: python -m unittest tests.v271.test_core_scientific -v
"""
import hashlib, json, os, subprocess, tempfile, unittest
from datetime import date
from pathlib import Path
TD = tempfile.TemporaryDirectory(prefix='pp_v271_cs_')
os.environ['POWERPATH_DATA_DIR'] = TD.name
os.environ.pop('POWERPATH_V27_AUTH_MODE', None)
from fastapi.testclient import TestClient
from server.app import app, db
from server.seed_demo import seed
from server import transaction271 as T
ROOT = Path(__file__).resolve().parents[2]
seed()
C = TestClient(app, base_url='http://127.0.0.1')


def d360(a, b):
    """30/360 US bond basis, written from the ISDA definition."""
    y1, m1, dd1 = a.year, a.month, a.day; y2, m2, dd2 = b.year, b.month, b.day
    if dd1 == 31: dd1 = 30
    if dd2 == 31 and dd1 in (30, 31): dd2 = 30
    return 360 * (y2 - y1) + 30 * (m2 - m1) + (dd2 - dd1)


def oracle_schedule(first_installment, principal=3300.0, coupon=0.0775, issue=date(2026, 5, 6)):
    dates = []
    y, mth = 2026, 11
    while True:
        d = date(y, mth, 15); dates.append(d)
        if d >= date(2031, 5, 15): break
        if mth == 11: y, mth = y + 1, 5
        else: mth = 11
    fi = date.fromisoformat(first_installment) if first_installment else None
    out, prev, bal = [], issue, principal
    for d in dates:
        interest = bal * coupon * d360(prev, d) / 360
        inst = min(bal, principal * 0.115 / 2) if fi and d >= fi else 0.0
        prin = bal if d == dates[-1] else inst
        out.append((d, interest, prin, inst)); bal -= prin; prev = d
    return out


def oracle_yield(cfs, net, issue=date(2026, 5, 6)):
    t = [d360(issue, d) / 180 for d, *_ in cfs]                    # semiannual periods
    amt = [i + p for _, i, p, _ in cfs]
    y = 0.08
    for _ in range(100):                                           # Newton on semiannual rate r = y/2
        r = y / 2
        f = sum(a / (1 + r) ** k for a, k in zip(amt, t)) - net
        df = sum(-k * a / (1 + r) ** (k + 1) for a, k in zip(amt, t)) / 2
        y -= f / df
    return y


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pid = C.post('/api/projects', json={'name': 'Core Scientific Finance I'}).json()['id']
        cls.B = f'/api/projects/{cls.pid}/transactions/core-scientific-2026'
        r = C.post(cls.B + '/model'); assert r.status_code == 201, r.text


class T14_DatesDayCountStub(Base):
    def test_schedule_matches_independent_oracle(self):
        for sc in T.SCENARIOS:
            got = C.get(self.B + '/debt-schedule', params={'scenario': sc}).json()
            exp = oracle_schedule(got['first_installment_date'])
            self.assertEqual([p['date'] for p in got['periods']], [d.isoformat() for d, *_ in exp])
            for p, (d, i, pr, inst) in zip(got['periods'], exp):
                self.assertAlmostEqual(p['interestM'], i, places=9, msg=f'{sc} {d} interest')
                self.assertAlmostEqual(p['principalM'], pr, places=9, msg=f'{sc} {d} principal')
            self.assertAlmostEqual(sum(p['principalM'] for p in got['periods']), 3300.0, places=9)

    def test_first_coupon_stub(self):
        s = C.get(self.B + '/debt-schedule').json()['summary']
        self.assertEqual(d360(date(2026, 5, 6), date(2026, 11, 15)), 189)
        self.assertAlmostEqual(s['firstCouponM'], 3300 * 0.0775 * 189 / 360, places=9)          # 134.26875
        self.assertAlmostEqual(s['firstCouponM'], 134.26875, places=9)
        p = C.get(self.B + '/debt-schedule').json()['periods']
        self.assertAlmostEqual(p[1]['interestM'], 3300 * 0.0775 / 2, places=9)                     # full period 127.875

    def test_day_count_is_labelled_assumption(self):
        inp = {x['name']: x for x in C.get(self.B + '/inputs').json()['inputs']}
        self.assertEqual(inp['day_count']['classification'], 'USER_ASSUMPTION')
        self.assertEqual(inp['day_count']['value'], '30/360')

    def test_effective_yield_independent(self):
        s = C.get(self.B + '/debt-schedule').json()['summary']
        y = oracle_yield(oracle_schedule('2029-11-15'), 3300 * 0.9925 - 42.0)
        self.assertAlmostEqual(s['effectiveYieldBondEquivalentPct'], y * 100, places=6)


class T15_ContingentTrigger(unittest.TestCase):
    def test_trigger_definition(self):
        f = T.first_installment_date
        self.assertEqual(f('2029-10-31', '2029-10-31'), '2029-11-15')        # exactly 15 days
        self.assertEqual(f('2029-11-01', '2029-06-30'), '2030-05-15')        # 14 days short -> next date; later event governs
        self.assertEqual(f('2028-01-31', '2028-04-30'), '2028-05-15')
        self.assertIsNone(f('2031-01-31', '2031-05-01'))                     # nothing on/before maturity
        self.assertEqual(f('2026-01-01', '2026-01-01'), '2026-11-15')

    def test_scenarios_start_amortisation_at_trigger(self):
        pid = C.post('/api/projects', json={'name': 'trig'}).json()['id']; B = f'/api/projects/{pid}/transactions/core-scientific-2026'; C.post(B + '/model')
        res = {x['scenario']: x for x in C.get(B + '/scenarios').json()['scenarios']}
        self.assertEqual(res['base']['first_installment_date'], '2029-11-15')        # reproduces the issuer's 10-Q assumption
        self.assertEqual(res['no_trigger']['installments_before_maturity'], 0)
        self.assertAlmostEqual(res['no_trigger']['balloonM'], 3300, places=9)
        self.assertGreater(res['early']['installments_before_maturity'], res['base']['installments_before_maturity'])
        for k in ('early', 'base', 'delayed'):
            sched = C.get(B + '/debt-schedule', params={'scenario': k}).json()['periods']
            first = next(p['date'] for p in sched if p['scheduledPrincipalM'] > 0)
            self.assertEqual(first, res[k]['first_installment_date'])
            self.assertTrue(all(p['scheduledPrincipalM'] == 0 for p in sched if p['date'] < first))
        self.assertIn('hypothetical', json.dumps(T.SCENARIOS).lower())


class T16_Reconciliation(Base):
    def test_maturity_table_and_no_plugs(self):
        rows = {r['item']: r for r in C.get(self.B + '/reconciliation').json()['rows']}
        for k in ('Principal due 2029', 'Principal due 2030', 'Principal due 2031 (final maturity payment)', 'Gross principal'):
            self.assertEqual(rows[k]['status'], 'RECONCILED'); self.assertAlmostEqual(rows[k]['variance'], 0, places=9)
        self.assertEqual(rows['Net proceeds']['status'], 'OPEN_UNEXPLAINED')                    # variance stays visible
        self.assertAlmostEqual(rows['Net proceeds']['variance'], -6.75, places=9)
        self.assertEqual(rows['Effective interest rate']['status'], 'WITHIN_ROUNDING')
        self.assertLess(abs(rows['Effective interest rate']['variance']), 0.05)
        self.assertLessEqual(rows['Unamortised discount and costs (notes)']['model_value'], 87.033)  # notes portion <= all-debt total

    def test_carrying_amount_roll_forward(self):
        s = C.get(self.B + '/debt-schedule').json()['summary']
        self.assertAlmostEqual(s['netProceedsM'], 3300 * 0.9925 - 42.0, places=9)
        self.assertAlmostEqual(s['originalIssueDiscountM'], 24.75, places=9)
        c1, c2 = s['carrying']                                                      # 2026-06-30, 2026-12-31
        # interest expense between the dates = change in carrying amount + coupon paid in between (no principal yet)
        expense = c2['interestExpenseToDateM'] - c1['interestExpenseToDateM']
        coupon_paid = 134.26875
        self.assertAlmostEqual(expense, (c2['carryingAmountM'] + c2['accruedCouponM']) - (c1['carryingAmountM'] + c1['accruedCouponM']) + coupon_paid, places=6)
        self.assertGreater(c2['carryingAmountM'], c1['carryingAmountM'])          # discount accretes
        self.assertAlmostEqual(c1['accruedCouponM'], 3300 * 0.0775 * 54 / 360, places=9)

    def test_balloon_definition(self):
        base = {x['scenario']: x for x in C.get(self.B + '/scenarios').json()['scenarios']}['base']
        self.assertAlmostEqual(base['balloonM'], 2541.0, places=9)
        self.assertAlmostEqual(base['final_maturity_principalM'], 2730.75, places=9)


class T17_EvidencePromotionGuard(Base):
    def test_public_and_assumptions_cannot_become_executed(self):
        for name in ('coupon', 'day_count', 'net_proceeds_8k'):
            r = C.post(self.B + f'/inputs/{name}/reclassify', json={'classification': 'EXECUTED_CONTRACT_VERIFIED', 'rationale': 'Attempted promotion without executed document', 'source_url': 'https://www.sec.gov/x'})
            self.assertEqual(r.status_code, 403, r.text)               # local mode has no named approver
        r = C.post(self.B + '/inputs/day_count/reclassify', json={'classification': 'PUBLIC_PRIMARY_SOURCE', 'rationale': 'No locator supplied for this claim'})
        self.assertEqual(r.status_code, 422)
        r = C.post(self.B + '/inputs/coupon/reclassify', json={'classification': 'MODEL_DERIVED', 'rationale': 'Not allowed to relabel as derived'})
        self.assertEqual(r.status_code, 422)

    def test_versioned_history(self):
        r = C.post(self.B + '/inputs/site_leased_mw/reclassify', json={'classification': 'CONFLICTING_EVIDENCE', 'rationale': 'Flag disagreement between catalog and filings'})
        self.assertEqual(r.status_code, 201, r.text); self.assertEqual(r.json()['version'], 2)
        with db() as con:
            rows = con.execute('SELECT version,classification FROM v271_inputs WHERE project_id=? AND name=? ORDER BY version', (self.pid, 'site_leased_mw')).fetchall()
        self.assertEqual([tuple(x) for x in rows], [(1, 'UNVERIFIED'), (2, 'CONFLICTING_EVIDENCE')])
        self.assertEqual(r.json()['g4'], 'BLOCKED')


class T19_HistoricalImmutability(unittest.TestCase):
    def test_legacy_fixtures_byte_identical(self):
        fx = json.loads((ROOT / 'tests/v271/fixtures/legacy_v2585_outputs.json').read_text())
        self.assertEqual(hashlib.sha256((ROOT / 'engine/underwrite25.js').read_bytes()).hexdigest(), fx['engine_sha256'])
        for name, case in fx['cases'].items():
            js = ("const L=require('./engine/underwrite25.js'),c=require('crypto');const r=L.evaluate({...L.defaults(),..." + json.dumps(case['input']) +
                  "});process.stdout.write(c.createHash('sha256').update(JSON.stringify({rows:r.rows,summary:r.summary})).digest('hex'))")
            out = subprocess.run(['node', '-e', js], capture_output=True, text=True, cwd=ROOT).stdout
            self.assertEqual(out, case['output_sha256'], name)

    def test_stored_legacy_run_unchanged_and_reproducible(self):
        pid = C.post('/api/projects', json={'name': 'legacy'}).json()['id']
        cfg = next(s for s in C.get('/api/projects/demo-campus-001/scenarios').json() if s['id'] == 'demo-base-001')['config']
        legacy_cfg = {**{k: v for k, v in cfg.items() if k != 'engineVersion'}, 'engineVersion': '25.8.5', 'sponsorCommitmentM': 60, 'initialCash': 50}
        sid = C.post(f'/api/projects/{pid}/scenarios', json={'name': 'Legacy capped', 'mode': 'underwrite', 'config': legacy_cfg}).json()['id']
        r1 = C.post(f'/api/projects/{pid}/scenarios/{sid}/runs').json()
        self.assertEqual(r1['engine_sha256'], hashlib.sha256((ROOT / 'engine/underwrite25.js').read_bytes()).hexdigest())
        self.assertEqual(r1['engine_version'], '25.8.5')
        stored = C.get(f'/api/projects/{pid}/runs/{r1["id"]}').json()
        # a new corrected-engine run of the same inputs does not disturb the stored legacy run
        sid2 = C.post(f'/api/projects/{pid}/scenarios', json={'name': 'Corrected capped', 'mode': 'underwrite', 'config': {**legacy_cfg, 'engineVersion': '27.1.0'}}).json()['id']
        r2 = C.post(f'/api/projects/{pid}/scenarios/{sid2}/runs').json()
        self.assertEqual(r2['engine_version'], '27.1.0'); self.assertGreaterEqual(min(x['cash'] for x in r2['rows']), -1e-9)
        self.assertLess(min(x['cash'] for x in r1['rows']), -1)                     # legacy defect preserved for reproducibility
        self.assertEqual(C.get(f'/api/projects/{pid}/runs/{r1["id"]}').json(), stored)
        r3 = C.post(f'/api/projects/{pid}/scenarios/{sid}/runs').json()
        self.assertEqual(json.dumps(r3['summary'], sort_keys=True), json.dumps(r1['summary'], sort_keys=True))

    def test_missing_engine_version_means_legacy(self):
        with db() as con:
            sid = 'pre-v271-scenario'
            cfg = next(s for s in C.get('/api/projects/demo-campus-001/scenarios').json() if s['id'] == 'demo-base-001')['config']
            con.execute('INSERT INTO scenarios VALUES (?,?,?,?,?,?,?,?)', (sid, 'demo-campus-001', 'Stored before v27.1', 'underwrite', json.dumps({k: v for k, v in cfg.items() if k != 'engineVersion'}), 1, '2026-10-01', '2026-10-01'))
        r = C.post(f'/api/projects/demo-campus-001/scenarios/{sid}/runs').json()
        self.assertEqual(r['engine_version'], '25.8.5')

    def test_unknown_engine_version_rejected(self):
        r = C.post('/api/projects/demo-campus-001/scenarios', json={'name': 'bad engine', 'mode': 'underwrite', 'config': {'engineVersion': '99.0'}})
        self.assertEqual(r.status_code, 422)


class T20_GatesPreserved(Base):
    def test_every_transaction_response_blocks_g4_g5(self):
        for method, url, body in (('get', '/inputs', None), ('get', '/terms', None), ('get', '/debt-schedule', None), ('get', '/scenarios', None),
                                  ('get', '/reconciliation', None), ('post', '/illustrative-project', {'scenario': 'base'})):
            r = getattr(C, method)(self.B + url, json=body) if body is not None else getattr(C, method)(self.B + url)
            self.assertEqual(r.status_code, 200, url); j = r.json()
            self.assertEqual((j['g4'], j['g5'], j['valuation_allowed']), ('BLOCKED', 'BLOCKED', False), url)
        il = C.post(self.B + '/illustrative-project', json={'scenario': 'base'}).json()
        self.assertTrue(il['NOT_A_CORE_SCIENTIFIC_VALUATION']); self.assertIn('UNVERIFIED', il['input_labels']['site_leased_mw'])
        self.assertIn('NOT a CoreWeave contract rent', il['input_labels']['rent_per_kw_month'])
        legacy = C.get(f'/api/projects/{self.pid}/transactions').json()
        self.assertTrue(all(t['g4'] == 'BLOCKED' and t['g5'] == 'BLOCKED' for t in legacy))


if __name__ == '__main__':
    unittest.main()
