'use strict';
const test = require('node:test'),
  assert = require('node:assert/strict'),
  fs = require('node:fs'),
  path = require('node:path');
test('engine source has no DOM, storage, network or clock dependencies', () => {
  for (const file of ['../src/underwrite.cjs', '../src/facilities.cjs', '../src/assurance.cjs']) {
    const src = fs.readFileSync(path.join(__dirname, file), 'utf8');
    for (const banned of [
      'document.',
      'window.',
      'localStorage',
      'fetch(',
      'XMLHttpRequest',
      'Date.now',
      'Math.random',
    ])
      assert.ok(!src.includes(banned), 'engine must stay pure: found ' + banned + ' in ' + file);
  }
});
test('evaluate is deterministic and does not mutate its input', () => {
  const { evaluate } = require('../src/underwrite.cjs');
  const input = {
    buildings: [
      { name: 'A', itMW: 40, constructionStart: 1, constructionMonths: 12, powerMonth: 13, leaseMonth: 13 },
    ],
    powerTranches: [{ month: 13, mw: 40 }],
  };
  const before = JSON.stringify(input);
  assert.equal(JSON.stringify(evaluate(input).rows), JSON.stringify(evaluate(input).rows));
  assert.equal(JSON.stringify(input), before);
});
