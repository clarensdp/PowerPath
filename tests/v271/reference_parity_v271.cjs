'use strict';
// v27.1 parity against the bundled Python reference (review/engine-v259/reference/powerpath_reference.py), which ports
// the v25.8.5 equations. Rules:
//  (1) cases with no cash shortfall and no matured default: v27.1 must match the reference on every monthly field;
//  (2) cases with a shortfall/matured default: the LEGACY engine must match the reference (so the reference is intact),
//      and v27.1 must match the reference exactly up to the first month whose treatment changed. Every surviving
//      difference is therefore located at a changed-treatment month, not elsewhere.
const { execFileSync } = require('node:child_process'), fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const ROOT = path.resolve(__dirname, '../..');
const v27 = require(path.join(ROOT, 'engine/underwrite27.js')), v25 = require(path.join(ROOT, 'engine/underwrite25.js'));
const dir = path.join(ROOT, 'review/engine-v259/reference'), tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pp-ref271-'));
const gapOf = (rowsA, refRows, upto = Infinity) => { let g = 0, at = ''; refRows.forEach((r, i) => { if (r.month >= upto) return; for (const [k, y] of Object.entries(r)) { if (k === 'month' || k === 'sourcesUsesResidual') continue; const x = rowsA[i][k]; const d = x == null && y == null ? 0 : x == null || y == null ? Infinity : Math.abs(x - y); if (d > g) { g = d; at = k + '@m' + r.month } } }); return { g, at } };
const report = { identical: [], changedTreatment: [], failures: [], checks: 0 };
for (const f of ['cases.json', 'cases_v2583.json', 'cases_v2584.json']) {
  const out = path.join(tmp, f);
  execFileSync('python3', ['-I', path.join(dir, 'powerpath_reference.py'), path.join(dir, f), out]);
  const ref = JSON.parse(fs.readFileSync(out, 'utf8')), cases = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
  for (const [k, spec] of Object.entries(cases)) {
    const a = v27.evaluate(JSON.parse(JSON.stringify(spec))), b = v25.evaluate(JSON.parse(JSON.stringify(spec)));
    report.checks += ref[k].rows.length * (Object.keys(ref[k].rows[0]).length - 1);
    const changeMonth = (a.rows.find(r => r.paymentDefault || r.maturedUnpaid || r.arrearsPrincipalPaid > 0 || r.pastDuePrincipalClosing > 0 || r.unpaidInterestClosing > 0) || {}).month;
    const legacyGap = gapOf(b.rows, ref[k].rows);
    if (legacyGap.g > 1e-6) { report.failures.push(`${f}:${k} legacy engine no longer matches reference (${legacyGap.g} at ${legacyGap.at})`); continue }
    if (changeMonth === undefined) {
      const g = gapOf(a.rows, ref[k].rows);
      if (g.g > 1e-6) report.failures.push(`${f}:${k} no changed treatment but gap ${g.g} at ${g.at}`); else report.identical.push(`${f}:${k}`);
    } else {
      const pre = gapOf(a.rows, ref[k].rows, changeMonth), full = gapOf(a.rows, ref[k].rows);
      if (pre.g > 1e-6) report.failures.push(`${f}:${k} differs BEFORE changed-treatment month ${changeMonth}: ${pre.g} at ${pre.at}`);
      else report.changedTreatment.push({ case: `${f}:${k}`, firstChangedMonth: changeMonth, maxGapAfterM: full.g, at: full.at, legacyMinCashM: Math.min(...b.rows.map(r => r.cash)), v271MinCashM: a.summary.minCashM, legacyUnpaidPrincipalAtExitM: b.summary.unpaidDebtAtExitM, v271UnpaidClaimsAtExitM: a.summary.unpaidLenderClaimsAtExitM, npvDeltaM: a.summary.npvM - b.summary.npvM });
    }
  }
}
console.log(JSON.stringify(report, null, 1));
if (report.failures.length) process.exit(1);
