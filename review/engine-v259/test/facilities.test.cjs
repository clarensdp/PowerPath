'use strict';
// v25.9 debt facilities (FACILITY_SPEC_v259). All campuses here are SYNTHETIC test fixtures.
const test = require('node:test'),
  assert = require('node:assert/strict'),
  path = require('node:path'),
  vm = require('node:vm');
const { evaluate } = require('../src/underwrite.cjs');
const baseline = require('./fixtures/underwrite_v2584ca1.cjs');
const fac = require('../src/facilities.cjs');
const specs = require('./fixtures/frozen_inputs_16.json');
const templates = require('../data/transactions_v259.json').templates;

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
// A ready (first rent) month 13, B ready month 19.
const campus = (over = {}) => ({
  months: 120,
  ltc: 0,
  initialCash: 100,
  minLiquidity: 10,
  reserveTargetM: 10,
  buildings: [B('A', 1, 12), B('B', 7, 12)],
  ...over,
});
// "Quiet" campus: no capex, revenue or opex before month 30.
const quiet = (over = {}) =>
  campus({ initialCash: 15, buildings: [B('A', 30, 12)], exitValueM: 500, ...over });
const note = (over = {}) => ({
  id: 'n1',
  name: 'Synthetic note 1',
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
const run = (c, notes) => evaluate({ ...c, facilities: notes });
const F = (z, id = 'n1') => z.summary.facilities.find((f) => f.id === id);
const S = (f, m) => f.schedule.find((r) => r.month === m);
const row = (z, m) => z.rows[m - 1];

// ---------------------------------------------------------------- identities used across scenarios
function assertIdentities(z, label) {
  const s = z.summary;
  assert.ok(s.sourcesUsesMaxResidual < 1e-6, label + ' sources/uses residual ' + s.sourcesUsesMaxResidual);
  assert.ok(s.reserveMaxResidual < 1e-6, label + ' reserve residual');
  for (const r of z.rows) assert.ok(Math.abs(r.sourcesUsesResidual) < 1e-6, label + ' residual m' + r.month);
  const months = z.rows.length;
  for (const f of s.facilities) {
    assert.equal(f.schedule.length, months - f.issueMonth + 1, label + ' schedule length');
    let prev = null;
    for (const r of f.schedule) {
      const L = `${label} ${f.id} m${r.month}`;
      near(r.closing, r.opening - r.principalPaid, 1e-9, L + ' closing = opening - principal');
      const accruedStart = prev ? prev.accruedEnd : 0;
      near(r.accruedEnd, accruedStart + r.accrual - r.interestPaid, 1e-9, L + ' accrued roll');
      const dsraStart = prev ? prev.dsraBalance : 0;
      near(r.dsraBalance, dsraStart + r.dsraMovement, 1e-9, L + ' DSRA roll');
      assert.ok(r.dsraBalance >= -1e-12, L + ' DSRA non-negative');
      if (prev) near(r.opening, prev.closing, 1e-12, L + ' opening = prior closing');
      if (r.month > f.maturityMonth) assert.equal(r.closing, 0, L + ' repaid after maturity');
      prev = r;
    }
    near(f.totalPrincipalPaidM + f.endingBalanceM, f.faceM, 1e-7, label + ' principal conservation');
    near(
      f.totalInterestPaidM,
      f.schedule.reduce((x, r) => x + r.accrual, 0),
      1e-7,
      label + ' all accrued interest paid',
    );
  }
  for (const r of z.rows) {
    const m = r.month,
      L = `${label} row m${m}`;
    const live = s.facilities.map((f) => S(f, m)).filter(Boolean);
    near(
      r.facilityBalance,
      live.reduce((x, q) => x + q.closing, 0),
      1e-7,
      L + ' balance',
    );
    near(
      r.facilityDsra,
      live.reduce((x, q) => x + q.dsraBalance, 0),
      1e-7,
      L + ' DSRA',
    );
    near(
      r.facilityDsraMovement,
      live.reduce((x, q) => x + q.dsraMovement, 0),
      1e-7,
      L + ' DSRA movement',
    );
    near(r.facilityDebtService, r.facilityInterestPaid + r.facilityPrincipalPaid, 1e-7, L + ' debt service');
    assert.equal(r.draw + r.mezzDraw + r.interest + r.principal + r.debt, 0, L + ' generic debt inert');
  }
}

// ---------------------------------------------------------------- issuance, coupons, amortization
test('OID, proceeds and fees at issuance', () => {
  const z = run(campus(), [note()]);
  const f = F(z);
  near(row(z, 2).notesProceeds, 392, 1e-12, 'proceeds = face x price');
  near(row(z, 2).notesFees, 4, 1e-12, 'fees = face x feePct');
  near(f.proceedsM, 392, 1e-12);
  near(f.oidM, 8, 1e-12, 'OID = face - proceeds');
  near(f.feesM, 4, 1e-12);
  for (const r of z.rows) if (r.month !== 2) assert.equal(r.notesProceeds + r.notesFees, 0);
  assert.equal(S(f, 2).opening, 400);
  assert.equal(S(f, 2).closing, 400);
  assert.equal(S(f, 2).accrual, 0, 'no accrual in the issue month');
  assert.equal(z.rows[0].facilityBalance, 0, 'nothing outstanding before issuance');
});

test('stub first coupon pays (firstPaymentMonth - issueMonth) months of accrual; dates map to months', () => {
  const z = run(campus(), [note()]);
  near(S(F(z), 7).interestPaid, (5 * 400 * 8) / 1200, 1e-9, 'five-month stub');
  // Same terms from ISO dates on a calendar starting Nov 2025 (day ignored); integer months take precedence.
  const z2 = run(campus({ calendarStartYear: 2025, calendarStartMonth: 11 }), [
    note({
      issueMonth: undefined,
      issueDate: '2025-12-20',
      firstPaymentMonth: undefined,
      firstPaymentDate: '2026-05-15',
      maturityMonth: undefined,
      maturityDate: '2030-11-15',
    }),
  ]);
  const f2 = F(z2);
  assert.deepEqual([f2.issueMonth, f2.firstPaymentMonth, f2.maturityMonth], [2, 7, 61]);
  const z3 = run(campus({ calendarStartYear: 2025, calendarStartMonth: 11 }), [
    note({ issueMonth: 3, issueDate: '2025-12-20' }),
  ]);
  assert.equal(F(z3).issueMonth, 3, 'integer month beats date');
  near(S(F(z3), 7).interestPaid, (4 * 400 * 8) / 1200, 1e-9, 'four-month stub');
  assert.equal(fac.dateToMonth('2026-01-31', 2026, 1, 'd'), 1);
  assert.equal(fac.dateToMonth('2025-12-01', 2026, 1, 'd'), 0);
});

test('interest is paid only on semiannual payment months; regular periods pay six months', () => {
  const z = run(campus(), [note()]);
  const f = F(z);
  const paid = f.schedule.filter((r) => r.interestPaid > 0).map((r) => r.month);
  const P = [];
  for (let p = 7; p <= 61; p += 6) P.push(p);
  assert.deepEqual(paid, P);
  for (const p of P.slice(1)) near(S(f, p).interestPaid, 16, 1e-9, 'regular coupon m' + p);
  for (const r of z.rows) if (!P.includes(r.month)) assert.equal(r.facilityInterestPaid, 0);
  assert.deepEqual(
    f.dscrTests.map((t) => t.month),
    P,
  );
});

test('pctOriginalPerYear installments from a fixed start; balloon net of the maturity installment', () => {
  const z = run(campus(), [
    note({
      amortization: { type: 'pctOriginalPerYear', annualPct: 10 },
      amortStart: { type: 'fixedMonth', month: 19 },
    }),
  ]);
  const f = F(z);
  assert.equal(f.amortStartMonth, 19);
  assert.equal(f.amortStartBasis, 'fixedMonth');
  assert.equal(S(f, 7).principalPaid, 0);
  assert.equal(S(f, 13).principalPaid, 0);
  for (const p of [19, 25, 31, 37, 43, 49, 55]) near(S(f, p).principalPaid, 20, 1e-12, 'installment m' + p);
  near(S(f, 61).principalPaid, 260, 1e-9, 'maturity pays the remaining balance');
  near(S(f, 61).scheduledPrincipal, 20, 1e-12, 'scheduled installment at maturity');
  near(f.balloonM, 240, 1e-9, 'balloon = maturity principal - installment');
  // A date-based fixed start (2027-07 on a 2026-01 calendar = month 19) gives the same schedule.
  const z2 = run(campus(), [
    note({
      amortization: { type: 'pctOriginalPerYear', annualPct: 10 },
      amortStart: { type: 'fixedMonth', date: '2027-07-01' },
    }),
  ]);
  assert.deepEqual(F(z2).schedule, f.schedule);
});

test('explicit schedule: j-th payment on/after A pays amountsM[j], capped at the balance; 0 beyond the list', () => {
  const z = run(campus(), [
    note({
      maturityMonth: 49,
      amortization: { type: 'explicit', amountsM: [10, 20, 30] },
      amortStart: { type: 'fixedMonth', month: 37 },
    }),
  ]);
  const f = F(z);
  near(S(f, 37).principalPaid, 10, 1e-12);
  near(S(f, 43).principalPaid, 20, 1e-12);
  near(S(f, 49).scheduledPrincipal, 30, 1e-12, 'third entry is the maturity installment');
  near(S(f, 49).principalPaid, 370, 1e-9);
  near(f.balloonM, 340, 1e-9);
  const z2 = run(campus(), [
    note({
      maturityMonth: 61,
      amortization: { type: 'explicit', amountsM: [300, 300] },
      amortStart: { type: 'fixedMonth', month: 37 },
    }),
  ]);
  const f2 = F(z2);
  near(S(f2, 37).principalPaid, 300, 1e-12);
  near(S(f2, 43).principalPaid, 100, 1e-12, 'capped at the opening balance');
  assert.equal(S(f2, 49).principalPaid, 0);
  assert.equal(S(f2, 49).interestPaid, 0, 'no accrual once repaid');
  assert.equal(f2.balloonM, 0);
  assert.equal(S(f2, 61).principalPaid, 0, 'beyond the list: 0');
});

test('bullet (none) pays the whole face as the maturity balloon', () => {
  const f = F(run(campus(), [note()]));
  assert.equal(f.amortStartMonth, null);
  assert.equal(f.amortStartBasis, 'none');
  for (const r of f.schedule) if (r.month !== 61) assert.equal(r.principalPaid, 0);
  assert.equal(S(f, 61).principalPaid, 400);
  assert.equal(f.balloonM, 400);
  assert.equal(f.endingBalanceM, 0);
  assert.equal(f.unpaidAtExitM, 0);
});

// ---------------------------------------------------------------- amortization start resolution
const pct10 = { amortization: { type: 'pctOriginalPerYear', annualPct: 10 } };
test('afterFirstRent: A = smallest payment month > R + offset (R from collateral gross rent)', () => {
  const A = (buildings, offsetMonths) =>
    F(run(campus(), [note({ ...pct10, buildings, amortStart: { type: 'afterFirstRent', offsetMonths } })]))
      .amortStartMonth;
  assert.equal(A(['B'], 0), 25, 'R=19 -> first p > 19');
  assert.equal(A(['B'], 6), 31, 'R+6=25 -> strictly after 25');
  assert.equal(A(['A', 'B'], 0), 19, 'any collateral building: R=13');
  assert.equal(A(['A'], 5), 19, 'R+5=18');
  // Gross rent BEFORE credits: a 100% credit still counts as first rent.
  const z = run(
    campus({
      buildings: [B('A', 1, 12, { tenantRentCreditPct: 100, tenantCreditMonths: 24 }), B('B', 7, 12)],
    }),
    [note({ ...pct10, buildings: ['A'], amortStart: { type: 'afterFirstRent', offsetMonths: 0 } })],
  );
  assert.equal(F(z).amortStartMonth, 19);
  assert.ok(row(z, 13).grossRevenue > 0, 'A rents from month 13');
  assert.equal(row(z, 13).leaseRevenue, 0, 'A fully credited, B not yet leasing');
  assert.ok(
    F(z).warnings.includes(
      'FACILITY n1: amortization start derived from modeled commencement, not contractual confirmation',
    ),
  );
});

test('afterFinalCommencement: T = max(C, latest cohort start + credit months); A = smallest p >= T + offset', () => {
  const A = (c, offsetMonths = 1, buildings = ['A', 'B']) =>
    F(run(c, [note({ ...pct10, buildings, amortStart: { type: 'afterFinalCommencement', offsetMonths } })]))
      .amortStartMonth;
  assert.equal(A(campus()), 25, 'C=19, no credits -> p >= 20');
  assert.equal(A(campus(), 0), 19, 'p >= 19');
  assert.equal(
    A(campus({ buildings: [B('A', 1, 12), B('B', 7, 12, { tenantCreditMonths: 10 })] })),
    31,
    'building credit months: K=29 -> p >= 30',
  );
  assert.equal(A(campus({ tenantCreditMonths: 14 })), 37, 'global credit months: K=33 -> p >= 34');
  assert.equal(
    A(
      campus({
        tenantCreditMonths: 14,
        buildings: [B('A', 1, 12), B('B', 7, 12, { tenantCreditMonths: 0 })],
      }),
    ),
    31,
    'building override 0 beats global: K=max(13+14, 19)=27 -> p >= 28',
  );
  // Power-limited: B full only when its second dedicated tranche lands in month 40 (latest cohort start 40).
  const tranches = [
    { month: 13, mw: 50, building: 'A' },
    { month: 19, mw: 30, building: 'B' },
    { month: 40, mw: 20, building: 'B' },
  ];
  assert.equal(A(campus({ powerTranches: tranches }), 0), 43, 'C=40 -> p >= 40');
  // Never fully energized -> unresolved, with warning.
  const z = run(campus({ powerTranches: tranches.slice(0, 2) }), [
    note({ ...pct10, amortStart: { type: 'afterFinalCommencement', offsetMonths: 0 } }),
  ]);
  const f = F(z);
  assert.equal(f.amortStartMonth, null);
  assert.ok(
    f.schedule.every((r) => r.month === 61 || r.principalPaid === 0),
    'no amortization',
  );
  assert.equal(f.balloonM, 400);
  assert.ok(f.warnings.includes('FACILITY n1: amortization start never resolved within horizon'));
  assert.ok(
    z.summary.creditWarnings.includes('FACILITY n1: amortization start never resolved within horizon'),
  );
});

// X (input first) needs 24 months and is abandoned at the funding default; Y is tenant-funded and complete.
// A shared 50 MW tranche lands at month 30: in the original plan X takes it, so Y is never fully energized.
const haltCampus = (sponsorCommitmentM) => ({
  months: 120,
  ltc: 0,
  initialCash: 50,
  minLiquidity: 10,
  reserveTargetM: 0,
  sponsorCommitmentM,
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
});
const haltNotes = () => {
  const t = {
    type: 'fixed_note',
    couponPct: 8,
    issuePricePct: 100,
    faceM: 1,
    issueMonth: 2,
    firstPaymentMonth: 8,
    maturityMonth: 110,
    ...pct10,
  };
  return [
    {
      ...t,
      id: 'onY',
      name: 'Y note',
      buildings: ['Y'],
      amortStart: { type: 'afterFinalCommencement', offsetMonths: 0 },
      dsra: { type: 'constructionThenNextPeriod', constructionAmountM: 0.5 },
    },
    {
      ...t,
      id: 'onX',
      name: 'X note',
      buildings: ['X'],
      amortStart: { type: 'afterFirstRent', offsetMonths: 0 },
    },
  ];
};
test('construction halt (AM1): events resolve on the schedule current at each month; set values never change', () => {
  const plan = run(haltCampus(null), haltNotes());
  assert.equal(plan.summary.constructionHaltMonth, null);
  assert.equal(F(plan, 'onY').amortStartMonth, null, 'original plan: Y never fully energized');
  assert.equal(F(plan, 'onY').constructionEndMonth, null);
  assert.equal(F(plan, 'onX').amortStartMonth, 32, 'original plan: X first rent at 30');
  assert.equal(F(plan, 'onX').constructionEndMonth, 30);
  const z = run(haltCampus(60), haltNotes());
  assert.equal(z.summary.constructionHaltMonth, 5);
  assert.deepEqual(z.summary.abandonedBuildings, ['X']);
  const y = F(z, 'onY'),
    x = F(z, 'onX');
  assert.equal(y.constructionEndMonth, 30, 'after the halt Y receives the shared tranche at 30');
  assert.equal(y.amortStartMonth, 32);
  assert.equal(x.constructionEndMonth, null, 'X is abandoned and never rents');
  assert.equal(x.amortStartMonth, null, 'no look-ahead: the halted plan never resolves X');
  assert.ok(x.warnings.includes('FACILITY onX: amortization start never resolved within horizon'));
  assert.ok(
    x.schedule.every((r) => r.month === 110 || r.principalPaid === 0),
    'halted collateral: no amortization',
  );
  // constructionThenNextPeriod: construction amount until E (30), then nextPeriod with A = 32.
  for (const m of [2, 5, 29]) assert.equal(S(y, m).dsraRequired, 0.5);
  near(
    S(y, 30).dsraRequired,
    (4 * 8) / 1200 + ((1 * 8) / 1200) * 2 + 0.05,
    1e-12,
    'accrued 4m + 2m + installment',
  );
  assertIdentities(z, 'halt');
});

// ---------------------------------------------------------------- DSRA
test('fixed DSRA: funded at issuance from cash, held, released when repaid', () => {
  const z = run(campus(), [note({ dsra: { type: 'fixed', amountM: 15 } })]);
  const f = F(z);
  assert.equal(S(f, 2).dsraRequired, 15);
  assert.equal(S(f, 2).dsraMovement, 15);
  assert.equal(S(f, 2).dsraBalance, 15);
  assert.equal(row(z, 2).sponsorContribution, 0, 'funded from note proceeds, not sponsor');
  assert.equal(S(f, 60).dsraBalance, 15);
  assert.equal(S(f, 61).dsraRequired, 0, 'requirement is 0 once the balance is 0');
  assert.equal(S(f, 61).dsraMovement, -15, 'release');
  assert.ok(f.schedule.filter((r) => r.month > 61).every((r) => r.dsraBalance === 0));
  assertIdentities(z, 'fixed DSRA');
});

test('nextPeriod DSRA: accrued + forward interest to the next payment + scheduled installment', () => {
  const z = run(campus(), [
    note({ ...pct10, amortStart: { type: 'fixedMonth', month: 13 }, dsra: { type: 'nextPeriod' } }),
  ]);
  const f = F(z);
  near(S(f, 2).dsraRequired, ((400 * 8) / 1200) * 5, 1e-12, 'issue month: 5 months to first payment');
  near(S(f, 4).dsraRequired, ((400 * 8) / 1200) * 2 + ((400 * 8) / 1200) * 3, 1e-12, 'accrued 2 + forward 3');
  near(S(f, 7).dsraRequired, 16 + 20, 1e-12, 'after a payment: 6 months + next installment');
  near(
    S(f, 55).dsraRequired,
    ((240 * 8) / 1200) * 6 + 20,
    1e-9,
    'q = maturity: installment, not the balloon',
  );
  assert.equal(S(f, 61).dsraRequired, 0);
  // Not yet amortizing: no installment in Q.
  const z2 = run(campus(), [note({ dsra: { type: 'nextPeriod' } })]);
  near(S(F(z2), 7).dsraRequired, 16, 1e-12);
  assertIdentities(z, 'nextPeriod');
});

test('constructionThenNextPeriod: construction amount until the event month E; never-occurring E keeps it', () => {
  const tranches = [
    { month: 13, mw: 50, building: 'A' },
    { month: 19, mw: 30, building: 'B' },
  ];
  const cTNP = {
    ...pct10,
    amortStart: { type: 'afterFinalCommencement', offsetMonths: 0 },
    dsra: { type: 'constructionThenNextPeriod', constructionAmountM: 25 },
  };
  const z = run(campus({ powerTranches: tranches }), [note(cTNP)]);
  const f = F(z);
  assert.equal(f.amortStartMonth, null);
  assert.equal(f.constructionEndMonth, null);
  for (const r of f.schedule) assert.equal(r.dsraRequired, r.month < 61 ? 25 : 0);
  // Event at C = T = 19: construction amount through 18, nextPeriod (with A = 19) from 19.
  const f2 = F(run(campus(), [note(cTNP)]));
  assert.equal(f2.constructionEndMonth, 19);
  assert.equal(f2.amortStartMonth, 19);
  for (const m of [2, 13, 18]) assert.equal(S(f2, m).dsraRequired, 25);
  near(
    S(f2, 19).dsraRequired,
    ((380 * 8) / 1200) * 6 + 20,
    1e-9,
    'after the 19 payment: 6m on 380 + installment',
  );
  // fixedMonth: E is the given month.
  const f3 = F(run(campus(), [note({ ...cTNP, amortStart: { type: 'fixedMonth', month: 25 } })]));
  assert.equal(f3.constructionEndMonth, 25);
  assert.equal(S(f3, 24).dsraRequired, 25);
  near(S(f3, 25).dsraRequired, ((380 * 8) / 1200) * 6 + 20, 1e-9);
  assertIdentities(z, 'cTNP unresolved');
});

test('DSRA top-up: cash above minLiquidity first, then sponsor; capped sponsor -> deficiency and lock-up', () => {
  const n = note({
    faceM: 10,
    issuePricePct: 100,
    feePct: 0,
    buildings: ['A'],
    dsra: { type: 'fixed', amountM: 50 },
  });
  const z = run(quiet(), [n]);
  assert.equal(row(z, 1).sponsorContribution, 5, 'month 1 base reserve top-up');
  assert.equal(row(z, 2).sponsorContribution, 40, '50 required: 10 from cash above minLiquidity, 40 sponsor');
  assert.equal(row(z, 2).cash, 10);
  assert.equal(S(F(z), 2).dsraBalance, 50);
  assert.deepEqual(F(z).dsraDeficiencyMonths, []);
  const zc = run(quiet({ sponsorCommitmentM: 40 }), [n]);
  const f = F(zc);
  near(S(f, 2).dsraBalance, 30, 1e-12, 'sponsor cap leaves 20 unfunded');
  assert.ok(f.dsraDeficiencyMonths.includes(2));
  assert.ok(f.lockupMonths.includes(2));
  assert.equal(row(zc, 2).facilityLockup, true);
  assert.equal(row(zc, 2).unfundedGapM, 0, 'a DSRA deficiency is not a funding default');
  assertIdentities(zc, 'capped DSRA');
});

test('DSRA draw before sponsor: capped by balance, by the facility debt service due and by the shortfall', () => {
  // Payment month 8 with no revenue: shortfall = interest due (4). Issue price 0 so no unspent proceeds sit in
  // project cash (AM3 would otherwise retain them until the collateral pays rent).
  const n = note({
    faceM: 100,
    issuePricePct: 0,
    feePct: 0,
    firstPaymentMonth: 8,
    maturityMonth: 50,
    buildings: ['A'],
  });
  const z = run(quiet(), [{ ...n, dsra: { type: 'nextPeriod' } }]);
  const f = F(z);
  near(S(f, 7).dsraBalance, 4, 1e-12);
  near(row(z, 8).facilityDsraDraw, 4, 1e-12, 'DSRA covers the coupon');
  near(S(f, 8).dsraDraw, 4, 1e-12);
  near(row(z, 8).sponsorContribution, 4, 1e-12, 'sponsor only refills the DSRA in step 6');
  near(row(z, 8).facilityDsraMovement, 0, 1e-12, 'draw -4, refill +4');
  const none = run(quiet(), [n]);
  near(row(none, 8).sponsorContribution, 4, 1e-12, 'without DSRA the sponsor pays the coupon');
  assert.equal(row(none, 8).facilityDsraDraw, 0);
  // Capex in month 8 widens the shortfall; the draw is still capped at the facility's own debt service.
  const zc = run(quiet({ buildings: [B('A', 8, 12)] }), [{ ...n, dsra: { type: 'fixed', amountM: 20 } }]);
  near(row(zc, 8).facilityDsraDraw, 4, 1e-12, 'min(20, due 4, shortfall 33.2)');
  // Priority order and the remaining-shortfall cap: shortfall 1 goes to the priority-1 facility only.
  const two = (id, priority) => ({
    ...n,
    id,
    priority,
    faceM: 20,
    couponPct: 20,
    issuePricePct: 100,
    dsra: { type: 'fixed', amountM: 20 },
  });
  const zp = run(quiet({ initialCash: 13, reserveTargetM: 0, distributionPolicy: 'retain' }), [
    two('lo', 2),
    two('hi', 1),
  ]);
  near(row(zp, 8).preFundingCash, 9, 1e-9);
  near(S(F(zp, 'hi'), 8).dsraDraw, 1, 1e-12, 'priority 1 draws the 1 shortfall');
  assert.equal(S(F(zp, 'lo'), 8).dsraDraw, 0, 'nothing left for priority 2');
  near(row(zp, 8).sponsorContribution, 1, 1e-12, 'refill of the drawn DSRA');
  assertIdentities(z, 'draw');
  assertIdentities(zp, 'priority draw');
});

// ---------------------------------------------------------------- lock-up
test('lock-up while the most recent DSCR test is below lockupDscr (test month to the next test month)', () => {
  // Single building (no capex after month 12), so cash builds up whenever distributions are locked.
  const c = campus({ buildings: [B('A', 1, 12)] }),
    n = note({ faceM: 300, buildings: ['A'] });
  const z = run(c, [n]);
  const f = F(z);
  const t = (m) => f.dscrTests.find((x) => x.month === m).dscr;
  assert.equal(t(7), 0, 'no cfads yet, debt service due -> 0');
  assert.ok(t(13) < 1.2 && t(19) >= 1.2, `tests 13=${t(13)} 19=${t(19)}`);
  for (let m = 7; m <= 18; m++) assert.ok(f.lockupMonths.includes(m), 'locked m' + m);
  assert.ok(!f.lockupMonths.includes(19));
  for (let m = 14; m <= 18; m++) assert.equal(row(z, m).distribution, 0, 'no distribution m' + m);
  assert.ok(row(z, 18).cash > row(z, 14).cash, 'cash is trapped while locked');
  assert.ok(row(z, 19).distribution > 0, 'released after a passing test');
  // DSCR = trailing 6 months of allocated CFADS / (interest + scheduled principal).
  const sum = [8, 9, 10, 11, 12, 13].reduce((x, m) => x + S(f, m).cfadsShare, 0);
  near(t(13), sum / 12, 1e-12);
  const open = run(c, [{ ...n, lockupDscr: 0 }]);
  assert.deepEqual(
    F(open).lockupMonths,
    [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    'only the AM3 construction lock-up (A first rents in month 13)',
  );
  assert.ok(row(open, 15).distribution > 0, 'lockupDscr 0 never locks');
});

test('cfadsShare allocates CFADS by collateral lease revenue (gross rent - credits)', () => {
  const c = campus({
    buildings: [B('A', 1, 12), B('B', 7, 12, { tenantRentCreditPct: 50, tenantCreditMonths: 12 })],
  });
  const z = run(c, [note({ buildings: ['A'] }), note({ id: 'all', buildings: ['A', 'B'] })]);
  const leaseA = (50 * 1000 * 170 * 1.025) / 1e6,
    leaseB = ((50 * 1000 * 170) / 1e6) * 0.5;
  near(S(F(z), 25).cfadsShare, (row(z, 25).cfads * leaseA) / (leaseA + leaseB), 1e-9, 'A share at month 25');
  near(S(F(z, 'all'), 25).cfadsShare, row(z, 25).cfads, 1e-9, 'all buildings -> full CFADS');
  assert.equal(S(F(z), 5).cfadsShare, 0, 'zero lease revenue -> 0');
});

// ---------------------------------------------------------------- exit
test('exit payoff: priority order, accrued interest before principal, unpaid balance reported', () => {
  const st = (id, priority, index, bal, accrued) => ({
    id,
    priority,
    index,
    bal,
    accrued,
    totalInterestPaidM: 0,
    totalPrincipalPaidM: 0,
    unpaidAtExitM: 0,
    cur: null,
  });
  const states = [st('junior', 2, 0, 100, 5), st('senior', 1, 1, 50, 3), st('senior2', 1, 2, 10, 1)];
  const ordered = fac.byPriority(states);
  assert.deepEqual(
    ordered.map((s) => s.id),
    ['senior', 'senior2', 'junior'],
  );
  const paid = fac.exitPayoff(ordered, 70);
  assert.equal(paid, 70);
  assert.deepEqual(
    states.map((s) => [s.id, s.totalInterestPaidM, s.totalPrincipalPaidM, s.unpaidAtExitM]),
    [
      ['junior', 5, 1, 99],
      ['senior', 3, 50, 0],
      ['senior2', 1, 10, 0],
    ],
  );
  assert.equal(fac.exitPayoff([st('x', 1, 0, 10, 1)], -5), 0, 'negative availability pays nothing');
});

test('maturity before the horizon: a payment shortfall is unfunded cash, recorded as paid, not arrears', () => {
  const c = campus({ months: 67 });
  const zc = run({ ...c, sponsorCommitmentM: 400 }, [note()]);
  const r = row(zc, 61);
  assert.ok(r.unfundedGapM > 0);
  assert.equal(r.facilityPrincipalPaid, 400, 'payment recorded as made in step 2');
  assert.equal(zc.summary.unpaidDebtAtExitM, 0);
  assert.equal(F(zc).unpaidAtExitM, 0);
  assert.ok(zc.summary.facilityPaymentShortfallMonths.includes(61));
  assert.equal(zc.summary.defaulted, true);
  assert.ok(zc.summary.creditWarnings.includes(fac.ARREARS_WARNING));
  assertIdentities(zc, 'pre-horizon balloon shortfall');
});

// ---------------------------------------------------------------- validation
test('validation errors', () => {
  const bad = (over, re, c = campus()) => assert.throws(() => run(c, [note(over)]), re);
  assert.throws(() => evaluate({ ...campus(), ltc: 65, facilities: [note()] }), {
    message: 'Generic construction debt must be disabled (ltc=0, mezzLtcPct=0) when facilities are modeled',
  });
  assert.throws(
    () => evaluate({ ...campus(), mezzLtcPct: 10, facilities: [note()] }),
    /Generic construction debt/,
  );
  const { ltc, ...noLtc } = campus();
  void ltc;
  assert.throws(
    () => evaluate({ ...noLtc, facilities: [note()] }),
    /Generic construction debt/,
    'default ltc 65',
  );
  bad({ issueMonth: 0 }, /issueMonth must be >= 1/);
  bad({ issueMonth: undefined, issueDate: '2025-12-01' }, /issueMonth must be >= 1/);
  bad({ issueMonth: undefined, issueDate: '2026/02/01' }, /ISO date/);
  bad({ issueMonth: undefined, issueDate: '2026-13-01' }, /not a valid calendar date/);
  bad({ issueMonth: undefined }, /requires issueMonth or issueDate/);
  bad({ issueMonth: 2.5 }, /integer month/);
  bad({ firstPaymentMonth: 2 }, /firstPaymentMonth must be after issueMonth/);
  bad({ maturityMonth: 1, firstPaymentMonth: 7 }, /maturityMonth must be >= firstPaymentMonth/);
  bad({ maturityMonth: 127 }, /beyond the horizon/);
  bad({ maturityMonth: 60 }, /not on the semiannual payment cycle/);
  bad({ buildings: ['Nope'] }, /unknown building Nope/);
  bad({ buildings: [] }, /non-empty/);
  bad(
    {
      amortization: { type: 'pctOriginalPerYear', annualPct: 150 },
      amortStart: { type: 'fixedMonth', month: 7 },
    },
    /annualPct/,
  );
  bad(
    { amortization: { type: 'pctOriginalPerYear' }, amortStart: { type: 'fixedMonth', month: 7 } },
    /annualPct/,
  );
  bad(
    { amortization: { type: 'explicit', amountsM: [1, -1] }, amortStart: { type: 'fixedMonth', month: 7 } },
    /finite and >= 0/,
  );
  bad(
    { amortization: { type: 'explicit', amountsM: [1, NaN] }, amortStart: { type: 'fixedMonth', month: 7 } },
    /finite and >= 0/,
  );
  bad({ amortization: { type: 'pctOriginalPerYear', annualPct: 5 } }, /amortStart may be omitted only/);
  bad({ amortStart: { type: 'afterFirstRent', offsetMonths: -1 } }, /offsetMonths/);
  bad({ dsra: { type: 'monthsOfDebtService' } }, /invalid dsra type/);
  bad({ faceM: 0 }, /faceM/);
  bad({ couponPct: 101 }, /couponPct/);
  bad({ issuePricePct: 201 }, /issuePricePct/);
  bad({ type: 'floating_note' }, /fixed_note/);
  bad({ evidence: { faceM: { label: 'Rumour' } } }, /invalid label/);
  bad({ modelable: false, modelableReason: 'dates Unknown' }, /modelable: false \(dates Unknown\)/);
  assert.throws(() => run(campus(), [note(), note()]), /Duplicate facility id n1/);
  assert.throws(() => evaluate({ ...campus(), facilities: { id: 'x' } }), /facilities must be an array/);
});

// ---------------------------------------------------------------- warnings
test('warnings: exact texts, per facility and once for the pool', () => {
  const z = run(campus(), [
    note({
      amortization: { type: 'unknown' },
      evidence: { couponPct: { label: 'Executed' }, maturityDate: { label: 'Unknown', factId: 'F0' } },
    }),
    note({ id: 'n2', ...pct10, amortStart: { type: 'afterFirstRent', offsetMonths: 0 } }),
  ]);
  assert.deepEqual(F(z).warnings, [
    'FACILITY n1: amortization unknown — bullet assumed; debt service understated',
    "FACILITY n1: term 'maturityDate' is Unknown, not Executed",
  ]);
  const w = z.summary.creditWarnings;
  assert.equal(w.filter((x) => x === fac.POOL_WARNING).length, 1);
  assert.equal(w.filter((x) => x === fac.ARREARS_WARNING).length, 1);
  assert.ok(
    w.includes(
      'FACILITY n2: amortization start derived from modeled commencement, not contractual confirmation',
    ),
  );
  assert.equal(
    fac.POOL_WARNING,
    'FACILITIES: single project cash pool; facility ring-fencing, cash sweeps and excess-cash-flow offers not modeled',
  );
  assert.deepEqual(F(z).evidence, {
    couponPct: { label: 'Executed' },
    maturityDate: { label: 'Unknown', factId: 'F0' },
  });
});

// ---------------------------------------------------------------- identities across varied scenarios
const scenarios = {
  'single facility, afterFirstRent, nextPeriod': () =>
    run(campus(), [
      note({
        ...pct10,
        amortStart: { type: 'afterFirstRent', offsetMonths: 2 },
        dsra: { type: 'nextPeriod' },
      }),
    ]),
  'shared power tranches, two priorities': () =>
    run(
      campus({
        buildings: [B('A', 1, 12, { itMW: 40 }), B('B', 4, 12, { itMW: 40 }), B('C', 8, 12, { itMW: 40 })],
        powerTranches: [
          { month: 14, mw: 60 },
          { month: 30, mw: 60 },
        ],
      }),
      [
        note({
          id: 'jr',
          priority: 2,
          buildings: ['C'],
          couponPct: 11,
          amortization: { type: 'explicit', amountsM: [5, 5, 10, 10, 20] },
          amortStart: { type: 'afterFinalCommencement', offsetMonths: 1 },
          dsra: { type: 'fixed', amountM: 12 },
        }),
        note({
          id: 'sr',
          priority: 1,
          buildings: ['A', 'B'],
          ...pct10,
          amortStart: { type: 'afterFinalCommencement', offsetMonths: 1 },
          dsra: { type: 'constructionThenNextPeriod', constructionAmountM: 30 },
        }),
      ],
    ),
  'renewal policy with short leases, explicit schedule': () =>
    run(
      campus({
        leaseExpiryPolicy: 'renew',
        renewalProbabilityPct: 60,
        renewalTermMonths: 36,
        buildings: [B('A', 1, 12, { leaseTermMonths: 36 }), B('B', 7, 12, { leaseTermMonths: 48 })],
      }),
      [
        note({
          maturityMonth: 103,
          amortization: { type: 'explicit', amountsM: [40, 40, 40, 40, 40, 40] },
          amortStart: { type: 'fixedMonth', month: 31 },
          dsra: { type: 'nextPeriod' },
        }),
      ],
    ),
  'tenant power pass-through, fixed DSRA, taxes and working capital': () =>
    run(
      campus({
        powerResponsibility: 'reimbursed',
        powerPassThroughPct: 90,
        powerReimbursementLagDays: 30,
        workingCapitalDays: 30,
        cashTaxRatePct: 21,
        maintenanceCapexMWYearM: 0.05,
        buildings: [
          B('A', 1, 12, { powerResponsibility: 'tenant_direct', powerPassThroughPct: 80 }),
          B('B', 7, 12),
        ],
      }),
      [
        note({
          ...pct10,
          amortStart: { type: 'afterFirstRent', offsetMonths: 0 },
          dsra: { type: 'fixed', amountM: 20 },
        }),
      ],
    ),
  'delays, overrun, tenant capex lag, unknown amortization': () =>
    run(
      campus({
        delayMonths: 9,
        overrunPct: 20,
        tenantCapexPct: 30,
        tenantFundingLagMonths: 2,
        rateShockPct: 4,
      }),
      [note({ amortization: { type: 'unknown' }, dsra: { type: 'fixed', amountM: 10 } })],
    ),
  'capped sponsor, funding default and halt, DSRA draws': () =>
    run(
      campus({
        initialCash: 40,
        sponsorCommitmentM: 120,
        buildings: [B('A', 1, 12), B('B', 10, 30, { itMW: 100 })],
      }),
      [
        note({
          faceM: 300,
          issuePricePct: 100,
          ...pct10,
          amortStart: { type: 'afterFirstRent', offsetMonths: 0 },
          dsra: { type: 'constructionThenNextPeriod', constructionAmountM: 15 },
        }),
      ],
    ),
  'gross capacity basis, rent credits, contracted exit, maturity at horizon end': () =>
    run(
      campus({
        months: 97,
        capacityBasis: 'gross',
        exitValuePolicy: 'contracted',
        tenantRentCreditPct: 25,
        tenantCreditMonths: 6,
        buildings: [B('A', 1, 12), B('B', 7, 12, { rentInputMode: 'total', contractedRentM: 1400 })],
      }),
      [
        note({
          maturityMonth: 97,
          ...pct10,
          amortStart: { type: 'afterFinalCommencement', offsetMonths: 0 },
          dsra: { type: 'nextPeriod' },
        }),
        note({
          id: 'n2',
          faceM: 50,
          priority: 3,
          issueMonth: 20,
          firstPaymentMonth: 25,
          maturityMonth: 85,
          buildings: ['B'],
        }),
      ],
    ),
  'halt with shared-tranche re-resolution': () => run(haltCampus(60), haltNotes()),
};
test('identities hold across varied scenarios (closing, accrued and DSRA rolls; sources/uses residual)', () => {
  assert.ok(Object.keys(scenarios).length >= 6);
  const seen = new Set();
  for (const [name, fn] of Object.entries(scenarios)) {
    const z = fn();
    assertIdentities(z, name);
    for (const r of z.rows) {
      if (r.facilityDsraDraw > 0) seen.add('draw');
      if (r.unfundedGapM > 0) seen.add('unfunded');
      if (r.facilityLockup) seen.add('lockup');
    }
    if (z.summary.constructionHaltMonth) seen.add('halt');
  }
  for (const k of ['draw', 'unfunded', 'lockup', 'halt'])
    assert.ok(seen.has(k), 'scenario set exercises ' + k);
});

test('facility runs are deterministic and do not mutate input', () => {
  const input = {
    ...campus(),
    facilities: [note({ ...pct10, amortStart: { type: 'afterFirstRent', offsetMonths: 0 } })],
  };
  const before = JSON.stringify(input);
  assert.equal(JSON.stringify(evaluate(input)), JSON.stringify(evaluate(input)));
  assert.equal(JSON.stringify(input), before);
});

// ---------------------------------------------------------------- compatibility
test('facilities absent or empty: full output byte-identical to the v25.8.4-ca.1 baseline', () => {
  const variants = [
    {},
    { facilities: [] },
    { leaseExpiryPolicy: 'renew' },
    { refinanceTenorPolicy: 'leaseTail', exitValuePolicy: 'contracted' },
    { powerResponsibility: 'reimbursed', powerReimbursementLagDays: 20, workingCapitalDays: 45 },
    { sponsorCommitmentM: 400, fundingDefaultPolicy: 'halt' },
    { loanMaturityMode: 'equity', cashSweepPct: 25, dsraMonths: 6, mezzLtcPct: 10 },
    { tenantCapexPct: 40, tenantFundingLagMonths: 3, tenantRentCreditPct: 20, tenantCreditMonths: 6 },
  ];
  let n = 0;
  const cmp = (input) => {
    const s = JSON.stringify(input);
    let a, b;
    try {
      a = JSON.stringify(evaluate(JSON.parse(s)));
    } catch (e) {
      a = 'ERR ' + e.message;
    }
    try {
      b = JSON.stringify(baseline.evaluate(JSON.parse(s)));
    } catch (e) {
      b = 'ERR ' + e.message;
    }
    assert.equal(a, b, 'output differs for ' + s.slice(0, 200));
    n++;
  };
  for (const v of variants) {
    cmp(v);
    cmp({
      ...v,
      powerTranches: [
        { month: 20, mw: 80 },
        { month: 30, mw: 70, building: 'Building C' },
      ],
    });
  }
  for (const s of specs)
    for (const v of variants.slice(0, 5))
      for (const [delayMonths, overrunPct, rateShockPct] of [
        [0, 0, 0],
        [6, 10, 2],
        [18, 20, 4],
      ])
        cmp({ ...s.assumptions, ...v, delayMonths, overrunPct, rateShockPct });
  assert.ok(n >= 250, 'compared ' + n + ' cases');
});

// ---------------------------------------------------------------- templates, demo, browser build
test('transaction templates: evidence on every term; modelable ones run, unknown-date ones refuse', () => {
  const byId = Object.fromEntries(templates.map((t) => [t.id, t]));
  assert.deepEqual(Object.keys(byId).sort(), [
    'apld_computeco2_2031',
    'apld_computeco3_2031',
    'apld_computeco_2030',
    'core_finance1_2031',
    'galaxy_helios2_2031',
  ]);
  const facts = templates.flatMap((t) => Object.values(t.evidence).map((e) => e.factId)).filter(Boolean);
  for (const id of ['F14', 'F34', 'F37', 'F39', 'F46', 'F47']) assert.ok(facts.includes(id), 'fact ' + id);
  assert.equal(byId.apld_computeco_2030.evidence.dsra.factId, 'F34');
  assert.equal(byId.apld_computeco_2030.evidence.dsra.label, 'Executed');
  assert.equal(byId.galaxy_helios2_2031.evidence.dsra.factId, 'F37');
  assert.equal(byId.core_finance1_2031.evidence.dsra.factId, 'F39');
  assert.equal(byId.core_finance1_2031.evidence.amortization.label, 'Executed');
  assert.equal(byId.galaxy_helios2_2031.evidence.amortization.label, 'Public approximate');
  for (const t of templates) {
    for (const term of [
      'faceM',
      'couponPct',
      'issuePricePct',
      'issueDate',
      'firstPaymentDate',
      'maturityDate',
      'amortization',
      'dsra',
      'buildings',
    ])
      assert.ok(
        fac.EVIDENCE_LABELS.includes(t.evidence[term] && t.evidence[term].label),
        `${t.id} ${term} label`,
      );
    assert.equal(typeof t.modelable, 'boolean');
    if (!t.modelable) {
      assert.ok(t.modelableReason && /Unknown/.test(t.modelableReason));
      assert.equal(t.maturityDate, null);
      assert.equal(t.evidence.maturityDate.label, 'Unknown');
      const c = campus({ buildings: [B(t.buildings[0], 1, 12)] });
      assert.throws(() => run(c, [t]), /modelable: false/);
    }
  }
  assert.deepEqual(
    templates.filter((t) => t.modelable).map((t) => t.id),
    ['apld_computeco_2030', 'galaxy_helios2_2031', 'core_finance1_2031'],
  );
});

test('demo script models only modelable templates on a synthetic campus', () => {
  const { runDemo } = require('../scripts/demo_facilities.cjs');
  const { results, skipped } = runDemo();
  assert.deepEqual(
    results.map((r) => r.id),
    ['apld_computeco_2030', 'galaxy_helios2_2031', 'core_finance1_2031'],
  );
  assert.deepEqual(
    skipped.map((s) => s.id),
    ['apld_computeco3_2031', 'apld_computeco2_2031'],
  );
  for (const r of results) {
    assertIdentities({ rows: r.rows, summary: r.summary }, 'demo ' + r.id);
    assert.ok(r.summary.creditWarnings.includes(fac.POOL_WARNING));
  }
  const apld = results.find((r) => r.id === 'apld_computeco_2030').facility;
  assert.equal(apld.balloonM, 2350, 'unknown amortization -> bullet');
  assert.ok(
    apld.warnings.includes(
      'FACILITY apld_computeco_2030: amortization unknown — bullet assumed; debt service understated',
    ),
  );
  assert.ok(apld.schedule.every((r) => r.dsraBalance === 0 || r.dsraBalance === 177));
});

test('browser bundle exposes the same facility engine', () => {
  const { bundle } = require('../scripts/build_browser.cjs');
  const ctx = {};
  vm.createContext(ctx);
  vm.runInContext(bundle(), ctx);
  const input = scenarios['shared power tranches, two priorities']().assumptions;
  assert.equal(
    JSON.stringify(ctx.PowerPathEngine.evaluate(input).rows),
    JSON.stringify(evaluate(input).rows),
  );
  assert.equal(ctx.PowerPathEngine.ENGINE_VERSION, require(path.join(__dirname, '../package.json')).version);
});
