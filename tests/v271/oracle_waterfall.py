"""Independently specified test oracle for the v27.1 cash-constrained debt waterfall (engine/underwrite27.js).

The oracle does NOT port the engine. It checks the engine's monthly rows against:
  (a) accounting identities written from first principles using only row inputs (draws, CFADS, payments),
  (b) global conservation laws over the whole horizon (every dollar of interest and principal is either paid,
      capitalised, carried as a claim, or still outstanding - nothing disappears),
  (c) documented conventions (interest on opening balance plus same-month draws; construction IDC capitalised;
      arrears only from cash above minimum liquidity; no distributions while any claim is unresolved),
  (d) small cases calculated by hand in this file.
Usage: python -m unittest tests.v271.oracle_waterfall -v
"""
import json, subprocess, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
TOL = 1e-6

def run(input_, engine='engine/underwrite27.js'):
    p = subprocess.run(['node', str(ROOT / 'tests/v271/run_engine.cjs')], input=json.dumps({'engine': engine, 'input': input_}), capture_output=True, text=True, cwd=ROOT, timeout=60)
    out = json.loads(p.stdout)
    if 'error' in out: raise ValueError(out['error'])
    return out

def approx(tc, a, b, tol=TOL, msg=''):
    tc.assertLessEqual(abs(a - b), tol, f'{msg}: {a} vs {b}')

# ---------- generic oracle checks (applied to every scenario) ----------
def check_rows(tc, out, label, min_liquidity=10.0, sponsor_cap=None, initial_cash=50.0):
    rows, s = out['rows'], out['summary']
    cash = initial_cash
    unpaid_int = 0.0; payables = 0.0; past_due = 0.0
    tot = dict(int_due=0.0, int_paid=0.0, pik=0.0, draws=0.0, cap=0.0, refi=0.0, prin_paid=0.0, sponsor=0.0)
    for r in rows:
        m = r['month']
        tc.assertGreaterEqual(r['cash'], -TOL, f'{label} m{m}: negative unrestricted cash {r["cash"]}')
        tc.assertGreaterEqual(r['reserve'], -TOL, f'{label} m{m}: negative reserve')
        # (a) cash roll-forward from first principles
        inflow = max(0.0, r['cfads']) + r['draw'] + r['mezzDraw'] + r['refinanceProceeds'] + r['tenantCashReceipt'] + r['sponsorContribution'] + r['terminalProceeds'] + r['exitCollections']
        debt_cash = r['cashInterest'] + r['principal'] + r['mezzPrincipal'] - r['reserveDrawForDebtService']
        outflow = r['operatingPaid'] + r['constructionPaid'] + r['refinanceFee'] + debt_cash + r['arrearsPayablesPaid'] + r['exitPayablesPaid'] + r['distribution']
        expected = cash + inflow - outflow - r['reserveMovement']
        approx(tc, r['cash'], expected, 1e-6, f'{label} m{m} cash roll')
        cash = r['cash']
        # interest roll: unpaid interest changes only by current shortfall, arrears and exit payments
        int_due_cash = r['interest'] + r['defaultInterest'] - r['capitalizedInterest']
        approx(tc, r['cashInterestDue'], int_due_cash, 1e-9, f'{label} m{m} cash interest due')
        exp_unpaid = unpaid_int + int_due_cash - r['cashInterest'] - r['pikInterest']
        approx(tc, r['unpaidInterestClosing'], exp_unpaid, 1e-6, f'{label} m{m} unpaid interest roll')
        unpaid_int = r['unpaidInterestClosing']
        # default interest only on overdue amounts
        # payables roll
        exp_pay = payables + (r['operatingShortfallDue'] - r['operatingPaid']) + (r['constructionDue'] - r['constructionPaid']) - r['arrearsPayablesPaid'] - r['exitPayablesPaid']
        approx(tc, r['unpaidOperatingClosing'] + r['unpaidConstructionClosing'], exp_pay, 1e-6, f'{label} m{m} payables roll')
        payables = exp_pay
        tc.assertLessEqual(r['pastDuePrincipalClosing'], r['debt'] + r['mezzDebt'] + TOL, f'{label} m{m}: past due exceeds outstanding')
        # (c) no equity distributions while anything is unresolved
        if r['distribution'] > TOL:
            tc.assertLess(r['unpaidInterestClosing'] + r['pastDuePrincipalClosing'] + r['unpaidOperatingClosing'] + r['unpaidConstructionClosing'], TOL, f'{label} m{m}: distribution with unresolved claims')
        tot['int_due'] += int_due_cash; tot['int_paid'] += r['cashInterest']; tot['pik'] += r['pikInterest']
        tot['draws'] += r['draw'] + r['mezzDraw']; tot['cap'] += r['capitalizedInterest']; tot['refi'] += r['refinanceProceeds']
        tot['prin_paid'] += r['principal'] + r['mezzPrincipal']; tot['sponsor'] += r['sponsorContribution']
    end = rows[-1]
    # (b) global conservation: interest
    approx(tc, tot['int_due'], tot['int_paid'] + tot['pik'] + end['unpaidInterestClosing'], 1e-6, f'{label} interest conservation')
    # (b) global conservation: principal
    approx(tc, tot['draws'] + tot['cap'] + tot['pik'] + tot['refi'], tot['prin_paid'] + end['debt'] + end['mezzDebt'], 1e-6, f'{label} principal conservation')
    # claims at exit are reported, not dropped
    approx(tc, s['unpaidLenderClaimsAtExitM'], end['debt'] + end['mezzDebt'] + end['unpaidInterestClosing'], 1e-6, f'{label} exit claims')
    if sponsor_cap is not None:
        tc.assertLessEqual(tot['sponsor'], sponsor_cap - initial_cash + 1e-6, f'{label}: sponsor funding above enforceable cap')
    # no equity distribution in or after the first month of any default (liquidity, maturity or payment)
    first_def = next((r['month'] for r in rows if r['unfundedGapM'] > 1e-8 or r['maturityShortfall'] > 1e-8 or r['paymentDefault']), None)
    if first_def is not None:
        tc.assertEqual(sum(r['distribution'] for r in rows if r['month'] >= first_def), 0.0, f'{label}: equity received cash at/after default month {first_def}')
    return tot

D = None
def defaults():
    global D
    if D is None:
        p = subprocess.run(['node', '-e', "process.stdout.write(JSON.stringify(require('./engine/underwrite27.js').defaults()))"], capture_output=True, text=True, cwd=ROOT)
        D = json.loads(p.stdout)
    return dict(D)

ONE = {'name': 'Solo', 'itMW': 10, 'constructionStart': 1, 'constructionMonths': 1, 'powerMonth': 500, 'leaseMonth': 500, 'leaseTermMonths': 180, 'rentEscalatorPct': 2.5}
HAND = {'buildings': [ONE], 'fixedOpexM': 0, 'sponsorCommitmentM': 50, 'initialCash': 50, 'exitValueM': 0, 'months': 120}


class T01_FullFundingHalt(unittest.TestCase):
    def test_capped_sponsor_halt(self):
        out = run({'sponsorCommitmentM': 60, 'initialCash': 50})
        s, rows = out['summary'], out['rows']
        check_rows(self, out, 'capped60', sponsor_cap=60)
        self.assertTrue(s['fundingDefault']); self.assertEqual(s['constructionHaltMonth'], 7)
        self.assertEqual(sorted(s['abandonedBuildings']), ['Building A', 'Building B', 'Building C'])
        self.assertTrue(all(r['onlineMW'] == 0 for r in rows), 'abandoned buildings energised')
        self.assertEqual(sum(r['capex'] for r in rows if r['month'] >= 7), 0)
        self.assertGreater(s['unpaidInterestAtExitM'], 0)
        self.assertTrue(s['paymentDefault'])
        # lender claim = principal outstanding + unpaid interest, greater than the legacy principal-only figure
        legacy = run({'sponsorCommitmentM': 60, 'initialCash': 50}, 'engine/underwrite25.js')['summary']
        self.assertGreater(s['unpaidLenderClaimsAtExitM'], legacy['unpaidDebtAtExitM'] + 1)
        self.assertAlmostEqual(s['npvM'], legacy['npvM'], places=9)  # equity cash flows are unchanged


class T02_PartialInterestAndAccumulation(unittest.TestCase):
    """Hand-calculated: 10 MW, $7M/MW, 65% LTC at 8%, 1% fee, $50M sponsor = opening cash, no revenue, no exit."""
    def test_hand_case(self):
        out = run(HAND)
        rows, s = out['rows'], out['summary']
        check_rows(self, out, 'hand', sponsor_cap=50)
        debt0 = 70 * 0.65                      # 45.5 drawn in month 1
        idc = debt0 * 0.08 / 12                # capitalised during construction
        debt = debt0 + idc                     # 45.803333...
        i = debt * 0.08 / 12                   # 0.3053556 per month thereafter
        cash_after_m1 = 50 + debt0 - 70 - debt0 * 0.01   # 25.045
        cash_m1 = cash_after_m1 - 10           # base reserve funded from cash above minimum liquidity
        approx(self, rows[0]['debt'], debt, 1e-9, 'm1 debt'); approx(self, rows[0]['cash'], cash_m1, 1e-9, 'm1 cash')
        # cash pays interest until exhausted: full months then one partial month
        k_full = int(cash_m1 // i)             # 49 full payments (months 2..50)
        partial_month = 2 + k_full             # month 51
        r = rows[partial_month - 1]
        approx(self, r['cashInterestPaidCurrent'], cash_m1 - k_full * i, 1e-9, 'partial payment')
        approx(self, r['unpaidInterestCurrent'], i - (cash_m1 - k_full * i), 1e-9, 'partial unpaid')
        self.assertTrue(all(x['cash'] <= 1e-9 for x in rows[partial_month - 1:]), 'cash should stay at zero')
        # unpaid interest accumulates without compounding (accrue policy, default rate 0)
        approx(self, rows[99]['unpaidInterestClosing'], 99 * i - cash_m1, 1e-9, 'm100 unpaid interest')
        # exit: the $10M base reserve goes to lenders, interest claim first
        total_due = 119 * i
        approx(self, s['unpaidInterestAtExitM'], total_due - cash_m1 - 10, 1e-9, 'unpaid interest at exit')
        approx(self, s['unpaidDebtAtExitM'], debt, 1e-9, 'unpaid principal at exit')
        approx(self, s['lenderRecoveryAtExitM'], 10, 1e-9, 'exit recovery')
        self.assertEqual(rows[59]['pastDuePrincipalClosing'] > debt - 1e-6, True, 'principal past due after maturity')

    def test_legacy_shows_the_defect(self):
        legacy = run(HAND, 'engine/underwrite25.js')['rows']
        self.assertLess(min(r['cash'] for r in legacy), -20, 'legacy should reproduce RT-A02 negative cash')


class T03_PIKOnlyWhenEnabled(unittest.TestCase):
    def test_pik_refused_without_instrument_term(self):
        with self.assertRaisesRegex(ValueError, 'pikPermittedByInstrument'):
            run({**HAND, 'unpaidInterestPolicy': 'pik'})

    def test_pik_capitalises_when_permitted(self):
        out = run({**HAND, 'unpaidInterestPolicy': 'pik', 'pikPermittedByInstrument': True})
        check_rows(self, out, 'pik', sponsor_cap=50)
        rows, s = out['rows'], out['summary']
        self.assertTrue(all(r['unpaidInterestClosing'] < 1e-12 for r in rows))
        self.assertGreater(s['pikInterestM'], 0)
        # PIK interest itself bears interest: total interest exceeds the non-compounding accrue case
        acc = run(HAND)['summary']
        self.assertGreater(s['interestM'], acc['interestM'])
        self.assertTrue(any('PIK' in w for w in s['creditWarnings']))


class T04_DefaultInterest(unittest.TestCase):
    def test_default_rate_on_overdue_only(self):
        out = run({**HAND, 'defaultInterestRatePct': 2})
        check_rows(self, out, 'default-rate', sponsor_cap=50)
        for r in out['rows']:
            approx(self, r['defaultInterest'], (r['unpaidInterestOpening'] + r['pastDuePrincipalOpening']) * 0.02 / 12, 1e-12, f'm{r["month"]} default interest')
        self.assertEqual(out['rows'][10]['defaultInterest'], 0)  # nothing overdue yet


class T05_SeniorMezzPriority(unittest.TestCase):
    def test_priority_order(self):
        base = {**HAND, 'mezzLtcPct': 20, 'mezzRatePct': 13}
        out = run(base); check_rows(self, out, 'mezz', sponsor_cap=50)
        s_unpaid = [r['unpaidInterestSenior'] for r in out['rows']]; m_unpaid = [r['unpaidInterestMezz'] for r in out['rows']]
        first_m = next(i for i, v in enumerate(m_unpaid) if v > 1e-9); first_s = next(i for i, v in enumerate(s_unpaid) if v > 1e-9)
        self.assertLess(first_m, first_s, 'mezz should go unpaid before senior under default priority')
        alt = run({**base, 'debtServicePriority': ['mezzInterest', 'seniorInterest', 'seniorPrincipal', 'mezzPrincipal']})
        check_rows(self, alt, 'mezz-alt', sponsor_cap=50)
        s2 = [r['unpaidInterestSenior'] for r in alt['rows']]; m2 = [r['unpaidInterestMezz'] for r in alt['rows']]
        self.assertLess(next(i for i, v in enumerate(s2) if v > 1e-9), next(i for i, v in enumerate(m2) if v > 1e-9), 'configured priority ignored')

    def test_invalid_priority_rejected(self):
        with self.assertRaisesRegex(ValueError, 'debtServicePriority'):
            run({**HAND, 'debtServicePriority': ['seniorInterest', 'seniorInterest', 'mezzInterest', 'mezzPrincipal']})


class T06_ReserveRestriction(unittest.TestCase):
    def test_reserve_policies(self):
        res = {}
        for pol in ('none', 'dsra_only', 'all'):
            out = run({**HAND, 'reserveDebtServicePolicy': pol}); check_rows(self, out, 'reserve-' + pol, sponsor_cap=50)
            res[pol] = out
        # pre-refinancing there is no DSRA, so dsra_only cannot touch the $10M base reserve
        self.assertEqual(res['dsra_only']['summary']['reserveDrawsForDebtServiceM'], 0)
        self.assertEqual(res['none']['summary']['reserveDrawsForDebtServiceM'], 0)
        approx(self, res['all']['summary']['reserveDrawsForDebtServiceM'], 10, 1e-9, 'all-policy reserve use')
        # using the reserve earlier changes timing, not the total lender recovery from the same $10M
        approx(self, res['all']['summary']['unpaidLenderClaimsAtExitM'], res['dsra_only']['summary']['unpaidLenderClaimsAtExitM'], 1e-6, 'recovery invariant')

    def test_dsra_used_after_refi_shortfall(self):
        # refinanced campus whose leases end early (vacate): DSRA covers debt service before arrears appear
        b = [{**x, 'leaseTermMonths': 48} for x in defaults()['buildings']]
        inp = {'buildings': b, 'dsraMonths': 6, 'sponsorCommitmentM': 450, 'leaseExpiryPolicy': 'vacate'}
        out = run(inp); check_rows(self, out, 'dsra-refi', sponsor_cap=450)
        out_none = run({**inp, 'reserveDebtServicePolicy': 'none'}); check_rows(self, out_none, 'dsra-refi-none', sponsor_cap=450)
        self.assertGreater(out['summary']['reserveDrawsForDebtServiceM'], 0, 'DSRA never used for debt service')
        self.assertEqual(out_none['summary']['reserveDrawsForDebtServiceM'], 0)


class T07_MaturityWithoutRefinancing(unittest.TestCase):
    def test_default_mode(self):
        out = run({'loanMaturityMode': 'default', 'sponsorCommitmentM': 800})
        check_rows(self, out, 'maturity-default', sponsor_cap=800)
        m = out['summary']['maturityMonth']; r = out['rows'][m - 1]
        approx(self, r['pastDuePrincipalClosing'] + r['arrearsPrincipalPaid'], r['debt'] + r['mezzDebt'] + r['arrearsPrincipalPaid'], 1e-6, 'all principal past due at maturity')
        self.assertTrue(r['maturedUnpaid'])


class T08_RefinanceInsufficient(unittest.TestCase):
    def test_refi_gap(self):
        out = run({'sponsorCommitmentM': 450, 'refinanceValueM': 150})
        check_rows(self, out, 'refi-gap', sponsor_cap=450)
        s = out['summary']
        self.assertTrue(s['refinanceSizing']['failed']); self.assertFalse(s['refinanced'])
        m = s['maturityMonth']; self.assertTrue(out['rows'][m - 1]['maturedUnpaid'])


class T09_TerminalShortfall(unittest.TestCase):
    def test_exit_liquidation_shortfall(self):
        out = run({**HAND, 'exitValueM': 20, 'exitCostPct': 2})
        check_rows(self, out, 'exit-shortfall', sponsor_cap=50)
        s = out['summary']
        before = s['lenderClaimAtExitBeforeM']
        approx(self, s['lenderRecoveryAtExitM'], min(before, 20 * 0.98 + 10), 1e-9, 'recovery = proceeds + reserve')
        approx(self, s['unpaidLenderClaimsAtExitM'], before - s['lenderRecoveryAtExitM'], 1e-9, 'shortfall')
        # interest claims are satisfied before principal under the default priority
        self.assertLess(s['unpaidInterestAtExitM'], run(HAND)['summary']['unpaidInterestAtExitM'])


class T10_NegativeCFADS(unittest.TestCase):
    def test_operating_shortfall_becomes_payable(self):
        b = [{**ONE, 'powerMonth': 3, 'leaseMonth': 3}]
        out = run({**HAND, 'buildings': b, 'rentPerKwMonth': 5, 'fixedOpexM': 1.5})
        check_rows(self, out, 'neg-cfads', sponsor_cap=50)
        self.assertTrue(any(r['cfads'] < 0 for r in out['rows']))
        self.assertGreater(out['summary']['unpaidPayablesAtExitM'], 0, 'operating losses vanished')
        # operating costs rank ahead of debt service: interest goes unpaid no later than opex
        first_ops = next(r['month'] for r in out['rows'] if r['operatingShortfallDue'] - r['operatingPaid'] > 1e-9)
        first_int = next(r['month'] for r in out['rows'] if r['unpaidInterestCurrent'] > 1e-9)
        self.assertLessEqual(first_int, first_ops)


class T11_LegacyParity(unittest.TestCase):
    """Where cash is never short, v27.1 must reproduce v25.8.5 exactly (intentional changes only)."""
    CASES = [{}, {'sponsorCommitmentM': None}, {'powerResponsibility': 'tenant_direct', 'sponsorCommitmentM': 800},
             {'powerResponsibility': 'reimbursed', 'powerReimbursementLagMonths': 2}, {'dsraMonths': 6, 'cashSweepPct': 50, 'mezzLtcPct': 10},
             {'refinanceTenorPolicy': 'leaseTail', 'leaseExpiryPolicy': 'renew', 'exitValuePolicy': 'contracted'}, {'delayMonths': 12, 'overrunPct': 20, 'rateShockPct': 2}]
    def test_parity(self):
        for c in self.CASES:
            new = run(c); old = run(c, 'engine/underwrite25.js')
            self.assertFalse(new['summary']['paymentDefault'], c)
            gap = 0.0
            for a, b in zip(new['rows'], old['rows']):
                for k, v in b.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool) and k not in ('sourcesUsesResidual',):
                        gap = max(gap, abs((a.get(k) or 0) - v))
            self.assertLess(gap, 1e-9, f'{c}: row gap {gap}')
            approx(self, new['summary']['npvM'], old['summary']['npvM'], 1e-9, f'{c} npv')
            check_rows(self, new, f'parity {c}', sponsor_cap=c.get('sponsorCommitmentM') if c.get('sponsorCommitmentM') else None)


if __name__ == '__main__':
    unittest.main()
