'use strict';
const test = require('node:test'),
  assert = require('node:assert/strict');
const { compute, FILE } = require('../scripts/golden.cjs');
test('720 public-case stresses match the golden snapshot exactly', () => {
  const golden = require(FILE),
    now = compute();
  assert.equal(now.length, 720);
  for (let i = 0; i < now.length; i++) {
    const a = now[i],
      b = golden[i],
      id = `${a.project} d${a.delay} o${a.overrun} s${a.shock}`;
    assert.equal(a.rowsSha256, b.rowsSha256, 'monthly rows changed: ' + id);
    assert.ok(a.maxResidual < 1e-6, 'accounting identity broken: ' + id);
  }
});
