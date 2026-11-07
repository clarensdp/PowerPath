'use strict';
// Runs the separately written Python reference (reference/powerpath_reference.py) on every case file and
// compares all monthly fields it computes with the engine. The reference reads only assumptions.
const { execFileSync } = require('node:child_process'),
  fs = require('node:fs'),
  os = require('node:os'),
  path = require('node:path');
const { evaluate } = require('../src/underwrite.cjs');
const dir = path.join(__dirname, '../reference'),
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pp-ref-'));
let checks = 0,
  worst = 0,
  failures = [];
for (const f of ['cases.json', 'cases_v2583.json', 'cases_v2584.json']) {
  const out = path.join(tmp, f);
  execFileSync('python3', ['-I', path.join(dir, 'powerpath_reference.py'), path.join(dir, f), out]);
  const ref = JSON.parse(fs.readFileSync(out, 'utf8')),
    cases = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
  for (const [k, spec] of Object.entries(cases)) {
    const js = evaluate(JSON.parse(JSON.stringify(spec))).rows;
    let gap = 0;
    ref[k].rows.forEach((r, i) => {
      for (const [field, y] of Object.entries(r)) {
        if (field === 'month') continue;
        const x = js[i][field];
        checks++;
        const g = x == null && y == null ? 0 : x == null || y == null ? Infinity : Math.abs(x - y);
        gap = Math.max(gap, g);
      }
    });
    worst = Math.max(worst, gap);
    if (gap > 1e-6) failures.push(`${f}:${k} gap ${gap}`);
  }
}
console.log(JSON.stringify({ checks, maxGapM: worst, failures }, null, 1));
if (failures.length) process.exit(1);
