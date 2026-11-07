'use strict';
// Risk fix v25.9.0-risk1: facility DSCR failures must block screening readiness and certification.
const test = require('node:test'),
  assert = require('node:assert/strict');
const cur = require('../src/underwrite.cjs');
const pre = require('./fixtures/underwrite_v2590_pre_risk/underwrite.cjs');
const { assess, stableHash, MATERIAL_TERMS } = require('../src/assurance.cjs');
const B = [
  {
    name: 'A',
    itMW: 100,
    constructionStart: 1,
    constructionMonths: 12,
    powerMonth: 13,
    leaseMonth: 13,
    leaseTermMonths: 180,
  },
];
const heavy = {
  months: 120,
  ltc: 0,
  mezzLtcPct: 0,
  sponsorCommitmentM: 5000,
  buildings: B,
  facilities: [
    {
      id: 'heavy',
      name: 'Over-levered notes',
      type: 'fixed_note',
      faceM: 2500,
      couponPct: 10,
      issuePricePct: 100,
      issueMonth: 1,
      firstPaymentMonth: 7,
      maturityMonth: 115,
      buildings: ['A'],
      amortization: { type: 'pctOriginalPerYear', annualPct: 5 },
      amortStart: { type: 'afterFirstRent', offsetMonths: 0 },
      dsra: { type: 'none' },
    },
  ],
};
test('facility DSCR below lock-up blocks screening readiness (fails on pre-fix engine)', () => {
  const z = cur.evaluate(JSON.parse(JSON.stringify(heavy)));
  const low = z.summary.facilities[0].dscrTests.filter((t) => t.dscr !== null && t.dscr < 1.2);
  assert.ok(low.length > 0, 'scenario must have weak facility DSCR');
  assert.equal(z.summary.breachMonths.length, 0, 'no generic covenant exists');
  assert.equal(z.summary.screeningReadiness, 'BLOCKED — not a performing credit case');
  assert.deepEqual(
    z.summary.facilityDscrBreachMonths,
    low.map((t) => t.month),
  );
  assert.ok(
    z.summary.creditWarnings.some((w) => w.startsWith('FACILITY heavy: ') && w.includes('below lock-up')),
  );
  const old = pre.evaluate(JSON.parse(JSON.stringify(heavy)));
  assert.equal(
    old.summary.screeningReadiness,
    'CONDITIONAL — scenario screening only',
    'demonstrates the pre-fix defect',
  );
});
test('assurance blocks certification on facility DSCR failures even with full evidence', () => {
  const z = cur.evaluate(JSON.parse(JSON.stringify(heavy)));
  const ev = {
    terms: Object.fromEntries(MATERIAL_TERMS.map((t) => [t, { label: 'Executed' }])),
    documents: { executedLeases: true, indentureSchedules: true, utilityAgreements: true },
    reconciliation: { independentReference: true, contractMatched: true },
    externalReview: {
      reviewer: 'J. Analyst',
      firm: 'Example Model Audit LLP',
      date: '2026-12-01',
      scope: 'x',
      signedOff: true,
      engineVersion: 'v',
      inputHash: stableHash(z.assumptions),
    },
  };
  const a = assess(z, ev, 'v');
  assert.equal(a.uses.lenderCertification, 'BLOCKED');
  assert.ok(a.blockingReasons.some((r) => r.includes('facility DSCR')));
});
test('facilities absent: summary has no facilityDscrBreachMonths key (byte-identical contract)', () => {
  assert.ok(!('facilityDscrBreachMonths' in cur.evaluate({}).summary));
});
