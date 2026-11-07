'use strict';
// Independent red-team regression tests (v25.8-CA). Each case FAILS on unpatched v25.8 and PASSES after.
// Usage: node test_claude_audit.cjs [path/to/underwrite25.js] [path/to/contract_notes258.js]
const assert = require('node:assert/strict');
const path = require('node:path');
const U = require(path.resolve(path.join(__dirname, '../src/underwrite.cjs')));
const N = require(path.resolve(path.join(__dirname, '../src/notes.cjs')));
const results = [];
const test = (id, fn) => {
  try {
    fn();
    results.push([id, 'PASS']);
  } catch (e) {
    results.push([id, 'FAIL', e.message.split('\n')[0]]);
  }
};
const near = (a, b, tol, msg) => assert.ok(Math.abs(a - b) <= tol, `${msg}: ${a} vs ${b}`);

// P1 — refinanced debt is repaid on the same annuity it was sized on.
test('P1a refi payment equals sizing annuity', () => {
  const z = U.evaluate({});
  const s = z.summary,
    r = 0.07 / 12,
    n = 240;
  const pmt = (s.refinanceSizing.selected * r) / (1 - Math.pow(1 + r, -n));
  const first = z.rows[s.maturityMonth]; // month maturity+1
  near(first.principal + first.cashInterest, pmt, 1e-6, 'first post-refi senior debt service');
});
test('P1b DSCR-sized refinancing does not open below 1.0x', () => {
  const z = U.evaluate({ refinanceValueM: 5000 });
  assert.equal(z.summary.refinanceSizing.binding, 'DSCR');
  const dscr = z.rows[z.summary.maturityMonth].dscr;
  assert.ok(dscr > 1.15, 'first post-refi DSCR ' + dscr + ' (sized at 1.25x)');
});

// P2 — shared supply already energizing a building is not silently re-allocated.
test('P2 shared tranche with reverse readiness order does not throw and stays allocated', () => {
  const B = [
    {
      name: 'A',
      itMW: 50,
      constructionStart: 10,
      constructionMonths: 18,
      powerMonth: 28,
      leaseMonth: 28,
      leaseTermMonths: 180,
    },
    {
      name: 'B',
      itMW: 50,
      constructionStart: 1,
      constructionMonths: 18,
      powerMonth: 19,
      leaseMonth: 19,
      leaseTermMonths: 180,
    },
  ];
  const z = U.evaluate({ buildings: B, powerTranches: [{ month: 19, mw: 50 }] });
  assert.equal(z.rows[29].onlineMW, 50, 'B keeps the 50 MW shared tranche; A waits for more supply');
});

// P3 — tranche MW on a gross-basis campus is gross and must be converted with PUE.
test('P3 gross utility tranche converted to IT MW', () => {
  const z = U.evaluate({
    capacityBasis: 'gross',
    pue: 1.3,
    buildings: [
      {
        name: 'A',
        itMW: 130,
        constructionStart: 1,
        constructionMonths: 18,
        powerMonth: 19,
        leaseMonth: 19,
        leaseTermMonths: 180,
      },
    ],
    powerTranches: [{ month: 19, mw: 100, building: 'A' }],
  });
  near(z.rows[20].onlineMW, 100 / 1.3, 1e-9, 'IT MW energized by 100 gross MW');
});

// P4 — reported operating MWh must use the same calendar hours as the energy cost.
test('P4 operatingMWh uses calendar hours', () => {
  const z = U.evaluate({});
  const fromCost = z.rows.reduce((t, r) => t + (r.energy * 1e6) / 85, 0);
  near(z.summary.operatingMWh, fromCost, 1e-3, 'MWh');
});

// P5 — after a funding default, unfunded construction is not financed by negative cash.
test('P5 funding default halts unfunded construction (no phantom financing)', () => {
  const z = U.evaluate({ sponsorCommitmentM: 50.0001 });
  assert.equal(z.summary.fundingDefault, true);
  assert.ok(z.summary.minCashM > -100, 'min cash ' + z.summary.minCashM + ' (v25.8: about -861)');
  assert.ok(
    z.summary.unpaidDebtAtExitM > 0,
    'senior debt cannot be fully repaid by a campus that was never funded',
  );
  assert.ok(Array.isArray(z.summary.abandonedBuildings) && z.summary.abandonedBuildings.length === 3);
});
test('P5b terminal leakage is reported', () => {
  const z = U.evaluate({
    tenantCapexPct: 50,
    tenantFundingLagMonths: 6,
    months: 42,
    buildings: [
      { name: 'A', itMW: 50, constructionStart: 25, constructionMonths: 18, powerMonth: 43, leaseMonth: 43 },
    ],
  });
  near(
    z.summary.uncollectedTenantReceivableAtExitM,
    z.rows.at(-1).tenantFundingReceivable,
    1e-9,
    'receivable at exit',
  );
});

// P6 — first coupon stub accrues 30/360 from issue date.
test('P6 APLD first coupon 205/360', () => {
  const s = N.schedule({
    name: 'apld',
    faceM: 2350,
    issuePricePct: 97,
    couponPct: 9.25,
    issueDate: '2025-11-20',
    firstCouponDate: '2026-06-15',
    maturityDate: '2030-12-15',
    originalPrincipalAmortPctYear: null,
  });
  near(s.rows[0].couponM, (2350 * 0.0925 * 205) / 360, 1e-9, 'first coupon');
});

// Invariants that must still hold after the patches.
test('INV identities reconcile in patched edge cases', () => {
  for (const o of [
    {},
    { sponsorCommitmentM: 50.0001 },
    { refinanceValueM: 5000, cashSweepPct: 50, dsraMonths: 6 },
    { loanMaturityMode: 'equity' },
    { tenantCapexPct: 40, tenantFundingLagMonths: 3 },
  ]) {
    const s = U.evaluate(o).summary;
    assert.ok(
      s.sourcesUsesMaxResidual < 1e-6 && s.debtMaxResidual < 1e-6 && s.reserveMaxResidual < 1e-6,
      JSON.stringify(o),
    );
  }
});

// P8 (v25.8-CA2) — lease-tail policies. Legacy defaults must be unchanged; new policies must behave as documented.
const LT_B = [
  {
    name: 'A',
    itMW: 60,
    constructionStart: 1,
    constructionMonths: 12,
    powerMonth: 13,
    leaseMonth: 13,
    leaseTermMonths: 84,
    rentEscalatorPct: 3,
  },
];
test('P8a legacy defaults unchanged (base NPV)', () => {
  const s = U.evaluate({}).summary;
  assert.equal(s.refinanceTenorPolicy, 'fixed');
  near(s.npvM, 438.78920905153547, 1e-9, 'base NPV');
});
test('P8b leaseTail tenor amortizes within remaining lease less buffer', () => {
  const s = U.evaluate({ months: 120, buildings: LT_B, refinanceTenorPolicy: 'leaseTail' }).summary;
  // ready m13, term 84 -> lease ends after m96; maturity m60 -> 37 months left, minus 12 buffer = 25
  assert.equal(s.refinanceAmortMonthsUsed, 25);
  assert.ok(s.refinanceSizing.amortMonths === 25 && s.endingDebtM < 1e-9);
});
test('P8c renewal: expected-value rent after expiry', () => {
  const o = {
    months: 120,
    buildings: LT_B,
    leaseExpiryPolicy: 'renew',
    renewalProbabilityPct: 60,
    renewalRentPct: 90,
  };
  const z = U.evaluate(o),
    v = U.evaluate({ months: 120, buildings: LT_B });
  const last = v.rows[95].grossRevenue; // m96 = final contract month
  near(z.rows[96].grossRevenue, last * 0.9 * 0.6, 1e-9, 'm97 renewal rent');
  near(z.rows[96].onlineMW, 36, 1e-9, 'renewed MW');
  assert.equal(v.rows[96].grossRevenue, 0);
});
test('P8d contracted exit values vacant MW at vacantValuePct', () => {
  const s = U.evaluate({
    months: 120,
    buildings: LT_B,
    exitValuePolicy: 'contracted',
    vacantValuePct: 40,
  }).summary;
  near(s.exitValueShare, 0.4, 1e-12, 'fully vacant at m120');
});
test('P8e invalid lease-tail policy rejected', () => {
  assert.throws(() => U.evaluate({ leaseExpiryPolicy: 'magic' }), /lease-tail/);
  assert.throws(() => U.evaluate({ renewalProbabilityPct: 120 }), /lease-tail/);
});

for (const r of results) console.log(r.join('  '));
const failed = results.filter((r) => r[1] === 'FAIL').length;
console.log(`${results.length - failed}/${results.length} passed`);
if (failed) process.exit(1);
