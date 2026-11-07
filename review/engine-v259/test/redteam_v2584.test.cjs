'use strict';
// Red-team regression for v25.8.4 (CA1/CA2). Usage: node test_v2584_ca.cjs <underwrite25.js>
const assert = require('node:assert/strict');
const U = require('../src/underwrite.cjs');
const R = [];
const t = (n, f) => {
  try {
    f();
    R.push([n, 'PASS']);
  } catch (e) {
    R.push([n, 'FAIL', e.message.split('\n')[0]]);
  }
};
const near = (a, b, tol, m) => assert.ok(Math.abs(a - b) <= tol, `${m}: ${a} vs ${b}`);
t(
  'CA1a reimbursed 100% equals tenant_direct 100% when rent has a WC lag (reimbursements collected in billing month)',
  () => {
    const d = U.evaluate({ powerResponsibility: 'tenant_direct', workingCapitalDays: 45 }).summary.npvM,
      r = U.evaluate({ powerResponsibility: 'reimbursed', workingCapitalDays: 45 }).summary.npvM;
    near(r, d, 1e-9, 'NPV');
  },
);
t('CA1b explicit reimbursement lag reproduces a lagged receivable', () => {
  const z = U.evaluate({
    powerResponsibility: 'reimbursed',
    workingCapitalDays: 0,
    powerReimbursementLagDays: 30,
  });
  const r = z.rows[40];
  near(r.workingCapitalBalance, r.powerReimbursement, 1e-9, 'one month of reimbursements outstanding');
});
t('CA1c identities hold with both lags', () => {
  const s = U.evaluate({
    powerResponsibility: 'reimbursed',
    workingCapitalDays: 45,
    powerReimbursementLagDays: 20,
    powerPassThroughPct: 70,
  }).summary;
  assert.ok(Math.max(s.sourcesUsesMaxResidual, s.debtMaxResidual, s.reserveMaxResidual) < 1e-6);
});
t('CA2 lease-expiry warning fires when the last horizon month is vacant', () => {
  const z = U.evaluate({
    months: 120,
    buildings: [
      {
        name: 'A',
        itMW: 50,
        constructionStart: 1,
        constructionMonths: 12,
        powerMonth: 13,
        leaseMonth: 13,
        leaseTermMonths: 107,
      },
    ],
  });
  assert.equal(z.rows.at(-1).onlineMW, 0);
  assert.ok(
    z.summary.creditWarnings.some((w) => w.startsWith('Lease expiry precedes')),
    'warning missing',
  );
});
t('CA2b no warning when the lease runs to the final month', () => {
  const z = U.evaluate({
    months: 120,
    buildings: [
      {
        name: 'A',
        itMW: 50,
        constructionStart: 1,
        constructionMonths: 12,
        powerMonth: 13,
        leaseMonth: 13,
        leaseTermMonths: 108,
      },
    ],
  });
  assert.ok(!z.summary.creditWarnings.some((w) => w.startsWith('Lease expiry precedes')));
});
t('INV landlord default unchanged', () =>
  near(U.evaluate({}).summary.npvM, 438.78920905153547, 1e-9, 'base NPV'),
);
for (const r of R) console.log(r.join('  '));
const f = R.filter((r) => r[1] === 'FAIL').length;
console.log(`${R.length - f}/${R.length} passed`);
if (f) process.exit(1);
