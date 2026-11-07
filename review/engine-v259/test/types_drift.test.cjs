'use strict';
const test = require('node:test'),
  assert = require('node:assert/strict'),
  fs = require('node:fs'),
  path = require('node:path');
const { evaluate } = require('../src/underwrite.cjs');
const d = fs.readFileSync(path.join(__dirname, '../src/index.d.ts'), 'utf8');
const body = (n) =>
  d
    .split('export interface ' + n + ' {')[1]
    .split('\n}')[0]
    .split('\n')
    .map((l) => l.trim())
    .filter((l) => l && !l.startsWith('/') && !l.startsWith('*'));
// Required fields: `name: type`. Optional fields (`name?: type`) are the v25.9 facility outputs, which are
// emitted only when facilities are modeled.
const declared = (n) => new Set(body(n).map((l) => l.split(/[?:]/)[0]));
const optional = (n) =>
  new Set(
    body(n)
      .filter((l) => /^\w+\?:/.test(l))
      .map((l) => l.split('?')[0]),
  );
const facilityCase = () => ({
  powerResponsibility: 'reimbursed',
  ltc: 0,
  facilities: [
    {
      id: 'drift',
      name: 'Synthetic drift note',
      type: 'fixed_note',
      faceM: 300,
      couponPct: 8,
      issuePricePct: 99,
      issueMonth: 2,
      firstPaymentMonth: 6,
      maturityMonth: 60,
      buildings: ['Building A'],
      amortization: { type: 'pctOriginalPerYear', annualPct: 10 },
      amortStart: { type: 'afterFirstRent', offsetMonths: 0 },
      dsra: { type: 'nextPeriod' },
    },
  ],
});
test('declared MonthRow and Summary fields match runtime output exactly', () => {
  const z = evaluate({ powerResponsibility: 'reimbursed' });
  for (const [n, obj] of [
    ['MonthRow', z.rows[5]],
    ['Summary', z.summary],
  ]) {
    const decl = declared(n),
      opt = optional(n),
      rt = Object.keys(obj);
    assert.deepEqual(
      rt.filter((k) => !decl.has(k)),
      [],
      n + ' fields missing from index.d.ts',
    );
    assert.deepEqual(
      [...decl].filter((k) => !opt.has(k) && !rt.includes(k)),
      [],
      n + ' declared fields absent at runtime',
    );
    assert.deepEqual(
      [...opt].filter((k) => rt.includes(k)),
      [],
      n + ' facility-only fields emitted without facilities',
    );
  }
});
test('facilities present: every declared MonthRow/Summary/FacilitySummary field is emitted, and nothing else', () => {
  const z = evaluate(facilityCase());
  for (const [n, obj] of [
    ['MonthRow', z.rows[5]],
    ['Summary', z.summary],
    ['FacilitySummary', z.summary.facilities[0]],
    ['FacilityScheduleRow', z.summary.facilities[0].schedule[0]],
    ['FacilityDscrTest', z.summary.facilities[0].dscrTests[0]],
  ]) {
    const decl = declared(n),
      rt = Object.keys(obj);
    assert.deepEqual(
      rt.filter((k) => !decl.has(k)),
      [],
      n + ' fields missing from index.d.ts',
    );
    assert.deepEqual(
      [...decl].filter((k) => !rt.includes(k)),
      [],
      n + ' declared fields absent at runtime',
    );
  }
  for (const r of z.rows) assert.equal(Object.keys(r).length, Object.keys(z.rows[0]).length);
});
