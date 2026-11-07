'use strict';
// FACILITY_SPEC_v259 Amendment 1 (AM1-AM5). Each check must PASS on the current engine and FAIL on the
// pre-amendment engine frozen in test/fixtures/underwrite_v259_pre_am1/. All campuses are SYNTHETIC.
const test = require('node:test'),
  assert = require('node:assert/strict');
const current = require('../src/underwrite.cjs');
const pre = require('./fixtures/underwrite_v259_pre_am1/underwrite.cjs');

const near = (a, b, tol, msg) =>
  assert.ok(Math.abs(a - b) <= (tol ?? 1e-9), `${msg || 'value'}: ${a} vs ${b}`);
const B = (name, start, len, extra = {}) => ({
  name,
  itMW: 50,
  constructionStart: start,
  constructionMonths: len,
  powerMonth: start + len,
  leaseMonth: start + len,
  leaseTermMonths: 180,
  rentEscalatorPct: 2.5,
  ...extra,
});
const campus = (over = {}) => ({
  months: 120,
  ltc: 0,
  initialCash: 100,
  minLiquidity: 10,
  reserveTargetM: 10,
  buildings: [B('A', 1, 12), B('B', 7, 12)], // A first rents month 13, B month 19
  ...over,
});
const note = (over = {}) => ({
  id: 'n1',
  name: 'Synthetic note',
  type: 'fixed_note',
  faceM: 400,
  couponPct: 8,
  issuePricePct: 98,
  feePct: 1,
  issueMonth: 2,
  firstPaymentMonth: 7,
  maturityMonth: 61,
  buildings: ['A', 'B'],
  amortization: { type: 'none' },
  ...over,
});
const F = (z, id = 'n1') => z.summary.facilities.find((f) => f.id === id);
const S = (f, m) => f.schedule.find((r) => r.month === m);
const pct10 = { amortization: { type: 'pctOriginalPerYear', annualPct: 10 } };

/** Registers a test that passes on the current engine and demonstrably fails on the pre-AM1 engine. */
const amendmentTest = (name, check) =>
  test(name, () => {
    check(current.evaluate);
    assert.throws(() => check(pre.evaluate), 'expected the pre-Amendment-1 engine to fail: ' + name);
  });

// X (input first, 24-month build) is abandoned at the funding default (halt month 5); Y is tenant-funded.
const haltCase = () => ({
  months: 120,
  ltc: 0,
  initialCash: 50,
  minLiquidity: 10,
  reserveTargetM: 0,
  sponsorCommitmentM: 60,
  distributionPolicy: 'retain',
  buildings: [
    { name: 'X', itMW: 50, constructionStart: 1, constructionMonths: 24, powerMonth: 25, leaseMonth: 25 },
    {
      name: 'Y',
      itMW: 50,
      constructionStart: 1,
      constructionMonths: 1,
      powerMonth: 2,
      leaseMonth: 2,
      tenantCapexPct: 100,
    },
  ],
  powerTranches: [{ month: 30, mw: 50 }],
  facilities: [
    {
      ...note({ id: 'onX', buildings: ['X'], faceM: 1, issuePricePct: 100, feePct: 0, firstPaymentMonth: 8 }),
      maturityMonth: 110,
      ...pct10,
      amortStart: { type: 'afterFirstRent', offsetMonths: 0 },
    },
  ],
});

amendmentTest(
  'AM1: no look-ahead; a halted campus whose collateral never rents does not amortize',
  (evaluate) => {
    const z = evaluate(haltCase());
    assert.equal(z.summary.constructionHaltMonth, 5);
    const f = F(z, 'onX');
    assert.equal(S(f, 32).principalPaid, 0, 'no installment at 32');
    assert.equal(f.amortStartMonth, null);
    assert.equal(f.constructionEndMonth, null, 'E never occurs');
    assert.ok(f.warnings.includes('FACILITY onX: amortization start never resolved within horizon'));
    // Unhalted: E = R = 30 is recognised only when it happens, then A = 32.
    const plan = evaluate({ ...haltCase(), sponsorCommitmentM: null });
    assert.equal(F(plan, 'onX').constructionEndMonth, 30);
    assert.equal(F(plan, 'onX').amortStartMonth, 32);
  },
);

amendmentTest(
  'AM2: constructionThenNextPeriod holds the construction amount until E, then nextPeriod',
  (evaluate) => {
    const z = evaluate({
      ...campus(),
      facilities: [
        note({
          buildings: ['B'],
          ...pct10,
          amortStart: { type: 'afterFirstRent', offsetMonths: 10 },
          dsra: { type: 'constructionThenNextPeriod', constructionAmountM: 25 },
        }),
      ],
    });
    const f = F(z);
    for (let m = 2; m <= 18; m++) assert.equal(S(f, m).dsraRequired, 25, 'construction amount m' + m);
    assert.equal(f.constructionEndMonth, 19, 'E = R = first rent on B');
    assert.equal(f.amortStartMonth, 31, 'smallest p > 19 + 10');
    // Month 19: payment made; next q = 25 is before A = 31, so no installment: 6 months of interest.
    near(S(f, 19).dsraRequired, 16, 1e-9, 'nextPeriod from E');
    near(S(f, 25).dsraRequired, 16 + 20, 1e-9, 'next payment 31 carries the first installment');
  },
);

amendmentTest(
  'AM3: distributions locked until every collateral building pays rent; proceeds fund capex',
  (evaluate) => {
    const z = evaluate({ ...campus(), facilities: [note({ lockupDscr: 0 })] });
    const f = F(z);
    for (let m = 2; m < 19; m++)
      assert.equal(z.rows[m - 1].distribution, 0, 'no distribution during construction m' + m);
    assert.equal(f.constructionLockupEndMonth, 19, 'B (last collateral building) first rents in 19');
    for (let m = 1; m <= z.rows.length; m++)
      assert.equal(
        z.rows[m - 1].facilityConstructionLockup,
        m >= 2 && m < 19,
        'construction lock-up flag m' + m,
      );
    // 392 proceeds - 4 fees fund ~700 of capex before any sponsor contribution after issuance.
    assert.equal(z.rows[1].sponsorContribution, 0);
    assert.equal(z.rows[5].sponsorContribution, 0, 'month 6 capex still paid from note proceeds');
    assert.ok(z.rows[18].distribution > 0 || z.rows[19].distribution > 0, 'distributions resume after L');
  },
);

amendmentTest(
  'AM4: maturity in the final month settles in the exit waterfall; unpaid-at-exit is possible',
  (evaluate) => {
    const c = campus({ months: 61 });
    // Fully funded: the balloon is paid from terminal proceeds, not from the sponsor.
    const z = evaluate({ ...c, facilities: [note({ dsra: { type: 'fixed', amountM: 15 } })] });
    const f = F(z),
      last = z.rows.at(-1);
    assert.equal(last.facilityDsraDraw, 0, 'deferred maturity amount is not drawn from the DSRA in step 4');
    assert.ok(
      last.sponsorContribution < 50,
      'sponsor does not pre-fund the exit balloon: ' + last.sponsorContribution,
    );
    assert.equal(last.facilityPrincipalPaid, 400);
    near(last.facilityInterestPaid, 16, 1e-9);
    assert.equal(f.unpaidAtExitM, 0);
    assert.equal(f.balloonM, 400);
    assert.ok(f.dscrTests.at(-1).dscr !== null, 'denominator = interest due at maturity');
    // Insufficient exit value: interest first, then principal; the remainder is unpaid at exit.
    const zl = evaluate({ ...c, exitValueM: 100, facilities: [note()] });
    const fl = F(zl);
    assert.ok(fl.unpaidAtExitM > 1, 'unpaid ' + fl.unpaidAtExitM);
    near(S(fl, 61).interestPaid, 16, 1e-9, 'accrued interest paid first');
    near(S(fl, 61).principalPaid + fl.unpaidAtExitM, 400, 1e-9);
    near(zl.summary.unpaidDebtAtExitM, fl.unpaidAtExitM, 1e-12);
    assert.equal(zl.summary.defaulted, true);
    assert.equal(zl.rows.at(-1).distribution, 0);
    assert.ok(zl.summary.sourcesUsesMaxResidual < 1e-6);
  },
);

test('AM5: required field names are emitted', () => {
  const z = current.evaluate({
    ...campus(),
    facilities: [note({ ...pct10, amortStart: { type: 'afterFinalCommencement', offsetMonths: 1 } })],
  });
  const f = F(z);
  for (const k of [
    'id',
    'name',
    'faceM',
    'couponPct',
    'issuePricePct',
    'proceedsM',
    'oidM',
    'feesM',
    'issueMonth',
    'firstPaymentMonth',
    'maturityMonth',
    'amortStartMonth',
    'amortStartBasis',
    'constructionEndMonth',
    'constructionLockupEndMonth',
    'totalInterestPaidM',
    'totalPrincipalPaidM',
    'balloonM',
    'endingBalanceM',
    'unpaidAtExitM',
    'minDscr',
    'dscrTests',
    'lockupMonths',
    'dsraDeficiencyMonths',
    'schedule',
    'evidence',
    'warnings',
  ])
    assert.ok(k in f, 'summary.facilities[] missing ' + k);
  for (const k of [
    'month',
    'opening',
    'accrual',
    'interestPaid',
    'principalPaid',
    'closing',
    'accruedEnd',
    'dsraRequired',
    'dsraBalance',
    'cfadsShare',
  ])
    assert.ok(k in f.schedule[0], 'schedule missing ' + k);
  for (const k of [
    'notesProceeds',
    'notesFees',
    'facilityInterestAccrued',
    'facilityInterestPaid',
    'facilityPrincipalPaid',
    'facilityDebtService',
    'facilityBalance',
    'facilityAccruedInterest',
    'facilityDsra',
    'facilityDsraMovement',
    'facilityDsraDraw',
    'facilityConstructionLockup',
  ])
    assert.ok(k in z.rows[0], 'row missing ' + k);
  assert.equal(f.constructionEndMonth, 19, 'T = C = 19');
  assert.equal(f.amortStartMonth, 25);
  assert.ok('facilityPaymentShortfallMonths' in z.summary);
});

test('Amendment 1 keeps facilities-absent output identical to v25.8.4-ca.1', () => {
  const base = require('./fixtures/underwrite_v2584ca1.cjs');
  for (const over of [{}, { facilities: [] }, { sponsorCommitmentM: 300 }, { leaseExpiryPolicy: 'renew' }])
    assert.equal(JSON.stringify(current.evaluate(over)), JSON.stringify(base.evaluate(over)));
});
