'use strict';
const test = require('node:test'),
  assert = require('node:assert/strict');
const { evaluate, ENGINE_VERSION } = require('../src/index.cjs');
const { assess, stableHash, MATERIAL_TERMS } = require('../src/assurance.cjs');
const exec = Object.fromEntries(MATERIAL_TERMS.map((t) => [t, { label: 'Executed', factId: 'X' }]));
const fullDocs = { executedLeases: true, indentureSchedules: true, utilityAgreements: true };
const capped = (o = {}) => evaluate({ sponsorCommitmentM: 5000, ...o });

test('default: screening allowed, valuation and certification blocked', () => {
  const a = assess(evaluate({}), {}, ENGINE_VERSION);
  assert.match(a.uses.screening, /ALLOWED/);
  assert.equal(a.uses.transactionValuation, 'BLOCKED');
  assert.equal(a.uses.lenderCertification, 'BLOCKED');
  assert.equal(a.gates.G5.status, 'NOT STARTED');
  assert.equal(a.display.valuationLabel, 'Screening scenario — not a valuation');
});
test('tests passing + independent reference cannot unlock valuation', () => {
  const a = assess(capped(), { terms: exec, reconciliation: { independentReference: true } }, ENGINE_VERSION);
  assert.equal(a.gates.G2.status, 'PASS');
  assert.equal(a.uses.transactionValuation, 'BLOCKED');
});
test('all documents but one non-executed material term stays blocked', () => {
  const a = assess(
    capped(),
    {
      terms: { ...exec, capex: { label: 'Management expectation' } },
      documents: fullDocs,
      reconciliation: { independentReference: true, contractMatched: true },
    },
    ENGINE_VERSION,
  );
  assert.equal(a.gates.G4.status, 'FAIL');
  assert.deepEqual(a.nonExecutedMaterialTerms, ['capex']);
  assert.equal(a.uses.transactionValuation, 'BLOCKED');
});
test('AI review is never external assurance', () => {
  const r = capped();
  const a = assess(
    r,
    {
      terms: exec,
      documents: fullDocs,
      reconciliation: { independentReference: true, contractMatched: true },
      externalReview: {
        reviewer: 'Claude',
        firm: 'Anthropic',
        date: '2026-10-26',
        scope: 'full',
        signedOff: true,
        engineVersion: ENGINE_VERSION,
        inputHash: stableHash(r.assumptions),
      },
    },
    ENGINE_VERSION,
  );
  assert.equal(a.gates.G5.status, 'FAIL');
  assert.match(a.gates.G5.detail, /AI review/);
  assert.equal(a.uses.transactionValuation, 'BLOCKED');
});
test('review bound to another engine version or other inputs is rejected', () => {
  const r = capped();
  const base = {
    terms: exec,
    documents: fullDocs,
    reconciliation: { independentReference: true, contractMatched: true },
  };
  const rev = {
    reviewer: 'J. Analyst',
    firm: 'Example Model Audit LLP',
    date: '2026-12-01',
    scope: 'Model integrity',
    signedOff: true,
  };
  assert.equal(
    assess(
      r,
      { ...base, externalReview: { ...rev, engineVersion: '25.8.0', inputHash: stableHash(r.assumptions) } },
      ENGINE_VERSION,
    ).gates.G5.status,
    'FAIL',
  );
  assert.equal(
    assess(
      r,
      { ...base, externalReview: { ...rev, engineVersion: ENGINE_VERSION, inputHash: 'deadbeef' } },
      ENGINE_VERSION,
    ).gates.G5.status,
    'FAIL',
  );
});
test('only full evidence + matching signed human review permits valuation; breaches still block certification', () => {
  const r = capped();
  const ev = {
    terms: exec,
    documents: fullDocs,
    reconciliation: { independentReference: true, contractMatched: true },
    externalReview: {
      reviewer: 'J. Analyst',
      firm: 'Example Model Audit LLP',
      date: '2026-12-01',
      scope: 'Model integrity',
      signedOff: true,
      engineVersion: ENGINE_VERSION,
      inputHash: stableHash(r.assumptions),
    },
  };
  const a = assess(r, ev, ENGINE_VERSION);
  assert.equal(a.gates.G5.status, 'PASS');
  assert.match(a.uses.transactionValuation, /PERMITTED/);
  const breached = evaluate({ sponsorCommitmentM: 5000, refinanceValueM: 5000 });
  const b = assess(
    breached,
    { ...ev, externalReview: { ...ev.externalReview, inputHash: stableHash(breached.assumptions) } },
    ENGINE_VERSION,
  );
  assert.ok(breached.summary.breachMonths.length > 0);
  assert.equal(b.uses.lenderCertification, 'BLOCKED');
});
test('modeled default blocks valuation even with full evidence', () => {
  const r = evaluate({ sponsorCommitmentM: 60 });
  const ev = {
    terms: exec,
    documents: fullDocs,
    reconciliation: { independentReference: true, contractMatched: true },
    externalReview: {
      reviewer: 'J. Analyst',
      firm: 'Example Model Audit LLP',
      date: '2026-12-01',
      scope: 'x',
      signedOff: true,
      engineVersion: ENGINE_VERSION,
      inputHash: stableHash(r.assumptions),
    },
  };
  assert.equal(r.summary.defaulted, true);
  assert.equal(assess(r, ev, ENGINE_VERSION).uses.transactionValuation, 'BLOCKED');
});
test('all 16 public cases are blocked for valuation and certification today', () => {
  const specs = require('./fixtures/frozen_inputs_16.json');
  for (const s of specs) {
    const a = assess(evaluate(JSON.parse(JSON.stringify(s.assumptions))), {}, ENGINE_VERSION);
    assert.equal(a.uses.transactionValuation, 'BLOCKED', s.name);
    assert.equal(a.uses.lenderCertification, 'BLOCKED', s.name);
    assert.equal(a.gates.G4.status, 'FAIL');
    assert.equal(a.gates.G5.status, 'NOT STARTED');
  }
});
test('browser bundle exposes the same assurance gates', () => {
  const vm = require('node:vm');
  const { bundle } = require('../scripts/build_browser.cjs');
  const ctx = { console };
  vm.createContext(ctx);
  vm.runInContext(bundle(), ctx);
  const E = ctx.PowerPathEngine;
  const a = E.assurance.assess(E.evaluate({}), {}, E.ENGINE_VERSION);
  assert.equal(a.uses.transactionValuation, 'BLOCKED');
  assert.equal(a.inputHash, assess(evaluate({}), {}, ENGINE_VERSION).inputHash);
});
