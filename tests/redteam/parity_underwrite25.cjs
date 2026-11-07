'use strict';
// Red-team: run the bundled Python reference against engine/underwrite25.js (the engine the v26 server actually uses
// for underwrite mode / previews / sensitivities), not only against the v25.9 notes engine.
const { execFileSync } = require('node:child_process'), fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const ROOT = process.argv[2];
const eng = require(path.join(ROOT, process.argv[3] || 'engine/underwrite25.js'));
const dir = path.join(ROOT, 'review/engine-v259/reference'), tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pp-ref-'));
let checks = 0, worst = 0, failures = [], perCase = {};
for (const f of ['cases.json', 'cases_v2583.json', 'cases_v2584.json']) {
  const out = path.join(tmp, f);
  execFileSync('python3', ['-I', path.join(dir, 'powerpath_reference.py'), path.join(dir, f), out]);
  const ref = JSON.parse(fs.readFileSync(out, 'utf8')), cases = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
  for (const [k, spec] of Object.entries(cases)) {
    let js;
    try { js = eng.evaluate(JSON.parse(JSON.stringify(spec))).rows; } catch (e) { failures.push(`${f}:${k} THROW ${e.message}`); continue; }
    let gap = 0, worstField = '';
    ref[k].rows.forEach((r, i) => { for (const [field, y] of Object.entries(r)) { if (field === 'month') continue; const x = js[i] ? js[i][field] : undefined; checks++;
      const g = x == null && y == null ? 0 : x == null || y == null ? Infinity : Math.abs(x - y); if (g > gap) { gap = g; worstField = field + '@m' + r.month; } } });
    perCase[f + ':' + k] = { gap, worstField }; worst = Math.max(worst, gap);
    if (gap > 1e-6) failures.push(`${f}:${k} gap ${gap} at ${worstField}`);
  }
}
console.log(JSON.stringify({ engine: process.argv[3] || 'engine/underwrite25.js', checks, maxGapM: worst, failures }, null, 1));
if (failures.length) process.exit(1);
