'use strict';
// Independently specified adversarial checks for the v25.8.5 underwriting engine (engine/underwrite25.js).
// Each check is derived from a rule stated in the release documentation or standard project-finance
// arithmetic, NOT from the engine's own source equations. The engine's internal residual fields are
// deliberately NOT trusted; identities are recomputed from row fields.
// Usage: node finance_adversarial.cjs <path/to/underwrite25.js>   (exit 1 on any failure)
const path = require('node:path');
const u = require(path.resolve(process.argv[2]));
const D = u.defaults();
const results = [];
const T = 1e-6;
function check(name, fn) {
  try { const msg = fn(); results.push({ name, pass: true, msg: msg || '' }); }
  catch (e) { results.push({ name, pass: false, msg: String(e.message || e).slice(0, 300) }); }
}
function eq(a, b, tol, label) { if (!(Math.abs(a - b) <= tol)) throw Error(`${label}: ${a} vs ${b} (tol ${tol})`); }
function ok(c, label) { if (!c) throw Error(label); }
const run = (over) => u.evaluate(JSON.parse(JSON.stringify({ ...D, ...over })));
const annuity = (P, rPctAnnual, n) => { const r = rPctAnnual / 1200; return r === 0 ? P / n : P * r / (1 - Math.pow(1 + r, -n)); };

// 1. Refinancing: the scheduled post-refi debt service equals the annuity on the sized balance.
check('A01 refi repaid on the same annuity it was sized on (DSCR-binding case)', () => {
  const r = run({ sponsorCommitmentM: null, refinanceLtvPct: 100, refinanceValueM: 99999, debtYieldMinPct: 0.01, refinanceDscrMin: 1.25 });
  const s = r.summary; ok(s.refinanced, 'expected refinancing'); ok(s.refinanceSizing.binding === 'DSCR', 'expected DSCR binding, got ' + s.refinanceSizing.binding);
  const m = s.maturityMonth, P = s.refinanceSizing.selected, n = s.refinanceSizing.amortMonths;
  const pay = annuity(P, D.refinanceRatePct, n);
  const first = r.rows[m]; // month m+1 (rows are 0-indexed by month-1)
  eq(first.cashInterest + first.principal - first.sweepPrincipal, pay, 1e-6, 'first refi payment');
  // DSCR sizing: forward-12 CFADS / (12*payment) == refinanceDscrMin
  eq(s.refinanceSizing.forward12CfadsM / (12 * pay), 1.25, 1e-6, 'sized DSCR');
  return `payment ${pay.toFixed(4)} $M/mo`;
});

// 2. Funding default halt: unfinished buildings stop, never energize; no negative cash; debt not shown repaid.
check('A02 sponsor-cap funding default halts unfinished buildings and leaves debt unpaid', () => {
  const r = run({ sponsorCommitmentM: 60, initialCash: 50 });
  const s = r.summary; ok(s.fundingDefault, 'expected a funding default with a $60M sponsor cap');
  const halt = s.constructionHaltMonth; ok(Number.isFinite(halt), 'halt month missing');
  ok(s.abandonedBuildings && s.abandonedBuildings.length > 0, 'expected abandoned buildings');
  const after = r.rows.filter(x => x.month >= halt);
  // after the halt only completed buildings may still incur capex (none should)
  const capexAfter = after.reduce((v, x) => v + x.capex, 0);
  ok(capexAfter < 1e-9, `capex after halt ${capexAfter}`);
  ok(Math.min(...r.rows.map(x => x.cash)) > -1e-6, 'cash went negative (phantom financing)');
  ok(s.unpaidDebtAtExitM > 0 || s.endingDebtM > 0 || s.defaulted, 'debt shown as fully repaid after default');
  ok(/BLOCKED/.test(s.screeningReadiness), 'defaulted case not BLOCKED');
  return `halt month ${halt}, abandoned ${s.abandonedBuildings.join('/')}`;
});

// 3. Power reimbursement lag: receivable = billings of the last L months; EBITDA unaffected; NPV lower with lag.
for (const L of [0, 1, 3]) check(`A03 reimbursement receivable equals last ${L} month(s) of billings`, () => {
  const r = run({ sponsorCommitmentM: null, powerResponsibility: 'reimbursed', powerPassThroughPct: 100, powerReimbursementLagMonths: L });
  for (let i = 0; i < r.rows.length; i++) {
    let expect = 0; for (let k = 0; k < L; k++) if (i - k >= 0) expect += r.rows[i - k].powerReimbursement;
    eq(r.rows[i].powerReimbursementReceivable, expect, 1e-9, `month ${i + 1}`);
  }
});
check('A04 reimbursed@100% has identical EBITDA to tenant_direct and lag only lowers NPV', () => {
  const a = run({ sponsorCommitmentM: null, powerResponsibility: 'tenant_direct' });
  const b = run({ sponsorCommitmentM: null, powerResponsibility: 'reimbursed', powerPassThroughPct: 100, powerReimbursementLagMonths: 0 });
  const c = run({ sponsorCommitmentM: null, powerResponsibility: 'reimbursed', powerPassThroughPct: 100, powerReimbursementLagMonths: 2 });
  a.rows.forEach((x, i) => { eq(x.ebitda, b.rows[i].ebitda, 1e-9, 'ebitda m' + x.month); eq(x.ebitda, c.rows[i].ebitda, 1e-9, 'ebitda lag m' + x.month); });
  eq(a.summary.npvM, b.summary.npvM, 1e-6, 'npv direct vs reimbursed lag0');
  ok(c.summary.npvM < b.summary.npvM - 1e-6, 'lag did not reduce NPV');
});

// 4. Gross vs IT: a gross-basis campus with itMW*PUE must equal an IT-basis campus; gross tranches convert by PUE.
check('A05 gross-basis campus equals IT-basis campus scaled by PUE (incl. gross tranches)', () => {
  const pue = D.pue;
  const itB = D.buildings.map(b => ({ ...b }));
  const grB = D.buildings.map(b => ({ ...b, itMW: b.itMW * pue }));
  const a = run({ sponsorCommitmentM: null, capacityBasis: 'IT', buildings: itB, powerTranches: [{ month: 19, mw: 50 }, { month: 40, mw: 100 }] });
  const b = run({ sponsorCommitmentM: null, capacityBasis: 'gross', buildings: grB, powerTranches: [{ month: 19, mw: 50 * pue }, { month: 40, mw: 100 * pue }] });
  a.rows.forEach((x, i) => { eq(x.onlineMW, b.rows[i].onlineMW, 1e-9, 'onlineMW m' + x.month); eq(x.leaseRevenue, b.rows[i].leaseRevenue, 1e-9, 'rent m' + x.month); });
  eq(a.summary.npvM, b.summary.npvM, 1e-6, 'npv');
});

// 5. Phased lease rent and escalator; 6. lease expiry under 'vacate'.
check('A06 single-building rent: escalator applied exactly at 12-month anniversaries; zero after expiry (vacate)', () => {
  const b = { name: 'Solo', itMW: 40, constructionStart: 1, constructionMonths: 6, powerMonth: 7, leaseMonth: 7, leaseTermMonths: 30, rentEscalatorPct: 3 };
  const r = run({ sponsorCommitmentM: null, months: 60, buildings: [b], ltc: 0, mezzLtcPct: 0, leaseExpiryPolicy: 'vacate', loanMaturityMode: 'equity', exitValueM: 0, refinanceValueM: 0 });
  const rent = m => r.rows[m - 1].leaseRevenue;
  const base = 40 * 1000 * D.rentPerKwMonth / 1e6; // $M per month, IT basis
  eq(rent(7), base, 1e-9, 'first rent');
  eq(rent(18), base, 1e-9, 'month 12 of lease, before escalation');
  eq(rent(19), base * 1.03, 1e-9, 'first anniversary');
  eq(rent(36), base * 1.03 * 1.03, 1e-9, 'last month of 30-month term');
  eq(rent(37), 0, 1e-12, 'first month after expiry');
  ok(r.rows.slice(36).every(x => Math.abs(x.energy) < 1e-12), 'energy cost after lease expiry under vacate');
});

// 7. DSRA funded to dsraMonths x scheduled refi payment (uncapped sponsor).
check('A07 DSRA balance after refi = base reserve + dsraMonths x next scheduled refi payment', () => {
  const r = run({ sponsorCommitmentM: null, dsraMonths: 6 });
  const s = r.summary; ok(s.refinanced, 'no refi');
  const m = s.maturityMonth, row = r.rows[m - 1];
  const left = s.refinanceSizing.amortMonths, pay = annuity(s.refinanceSizing.selected, D.refinanceRatePct, left);
  eq(row.reserve, D.reserveTargetM + 6 * pay, 1e-6, 'reserve at refi month');
});

// 8. Maturity balloon excluded from DSCR in the maturity month.
check('A08 maturity-month DSCR excludes the balloon and refinancing principal', () => {
  const r = run({ sponsorCommitmentM: null });
  const m = r.summary.maturityMonth, row = r.rows[m - 1];
  ok(row.principal > 100, 'expected balloon principal at maturity');
  eq(row.dscr, row.cfads / row.cashInterest, 1e-9, 'maturity DSCR');
});

// 9. Cash roll-forward recomputed from row flows (not engine residual fields).
for (const [label, over] of [['base', {}], ['capped sponsor default', { sponsorCommitmentM: 60 }], ['sweep+dsra+mezz', { sponsorCommitmentM: null, cashSweepPct: 50, dsraMonths: 3, mezzLtcPct: 10 }]])
check(`A09 independent cash roll-forward closes every month (${label})`, () => {
  const r = run({ sponsorCommitmentM: null, ...over });
  let cash = D.initialCash, worst = 0;
  for (const x of r.rows) {
    const inflow = x.cfads + x.draw + x.mezzDraw + x.refinanceProceeds + x.tenantCashReceipt + x.sponsorContribution + x.terminalProceeds + x.exitCollections;
    const outflow = x.capex + x.fee + x.refinanceFee + x.cashInterest + x.principal + x.mezzPrincipal + x.reserveMovement + x.distribution;
    // exit debt payoff is already inside principal/mezzPrincipal at exit
    cash = cash + inflow - outflow;
    worst = Math.max(worst, Math.abs(cash - x.cash)); cash = x.cash;
  }
  ok(worst < 1e-6, 'max cash roll residual ' + worst);
});

// 10. Uncapped sponsor funding is flagged; 11. no false institutional sign-off anywhere.
check('A10 uncapped sponsor flagged and never reported as financeable', () => {
  const s = run({ sponsorCommitmentM: null }).summary;
  ok(s.creditWarnings.some(w => /uncapped/i.test(w)), 'missing uncapped warning');
  ok(/UNVERIFIED SPONSOR/.test(s.financeabilityStatus), 'status ' + s.financeabilityStatus);
});
check('A11 no output claims lender approval, certification or verified valuation', () => {
  for (const over of [{}, { sponsorCommitmentM: 3000 }, { sponsorCommitmentM: null, dscrCovenant: 0.5 }]) {
    const s = run(over).summary, txt = JSON.stringify({ a: s.financeabilityStatus, b: s.screeningReadiness, c: s.financialValidationStatus });
    ok(!/(lender[- ]?(grade|approved|certified)|APPROVED|CERTIFIED|VERIFIED VALUATION|\bPASS\b)/i.test(txt.replace(/not (externally )?validated|NOT .*VERIFIED|UNVERIFIED/gi, '')), 'claim found: ' + txt);
  }
});

// 12. NPV recomputed from independently reconstructed equity flows.
check('A12 NPV = monthly-discounted (distributions - sponsor contributions), t0 = -initialCash', () => {
  const r = run({ sponsorCommitmentM: null });
  const flows = [-D.initialCash, ...r.rows.map(x => x.distribution - x.sponsorContribution)];
  const npv = flows.reduce((s, v, i) => s + v / Math.pow(1 + D.discount / 100, i / 12), 0);
  eq(r.summary.npvM, npv, 1e-6, 'npv');
});

// 13. Exit proceeds and 14. capex totals from first principles.
check('A13 terminal proceeds = exitValue x (1 - exit cost) for a fully built campus', () => {
  const r = run({ sponsorCommitmentM: null });
  eq(r.rows.at(-1).terminalProceeds, D.exitValueM * (1 - D.exitCostPct / 100), 1e-9, 'terminal');
});
check('A14 total capex = sum(IT MW) x $/MW x (1+overrun) when nothing is abandoned', () => {
  const r = run({ sponsorCommitmentM: null, overrunPct: 15 });
  const mw = D.buildings.reduce((v, b) => v + b.itMW, 0);
  eq(r.rows.reduce((v, x) => v + x.capex, 0), mw * D.constructionCostMW * 1.15, 1e-6, 'capex');
});

// 15. Covenant breach list recomputed; 16. no distributions while locked.
for (const cov of [1.2, 1.8, 2.5]) check(`A15 breach months = {dscr < ${cov}} excluding maturity month`, () => {
  const r = run({ sponsorCommitmentM: null, dscrCovenant: cov, distributionDscrMin: cov });
  const m = r.summary.maturityMonth;
  const expect = r.rows.filter(x => x.dscr !== null && Number.isFinite(x.dscr) && x.month !== m && x.dscr < cov).map(x => x.month);
  ok(JSON.stringify(expect) === JSON.stringify(r.summary.breachMonths), `expected ${expect.length} got ${r.summary.breachMonths.length}`);
  const leak = r.rows.filter(x => x.month < D.months && x.debt + x.mezzDebt > 1e-9 && x.dscr !== null && x.dscr < cov && x.distribution > 1e-9);
  ok(!leak.length, 'distribution paid in breach month ' + (leak[0] && leak[0].month));
});

// 17. Sweep never takes cash below minimum liquidity.
check('A16 cash sweep respects minimum liquidity', () => {
  const r = run({ sponsorCommitmentM: null, cashSweepPct: 100 });
  const bad = r.rows.filter(x => x.sweepPrincipal > 1e-9 && x.cash < D.minLiquidity - 1e-6);
  ok(!bad.length, 'cash below minLiquidity after sweep in month ' + (bad[0] && bad[0].month));
});

// 18. Refinancing that cannot be funded must default rather than close.
check('A17 unfundable refinancing gap defaults instead of closing', () => {
  const r = run({ sponsorCommitmentM: 50, initialCash: 50, refinanceValueM: 100, ltc: 65 });
  const s = r.summary;
  ok(s.defaulted && s.fundingDefault, 'expected funding default');
  ok(!(s.refinanced && s.refinanceSizing && s.refinanceSizing.selected < 100 && !s.refinanceSizing.failed && s.unpaidDebtAtExitM === 0), 'refi closed despite gap');
});

// 19. Renewal escalation: first renewal year at renewalRentPct of final-month rent, escalating from year 2 of renewal.
check('A18 renewal rent: first renewal year flat, then escalates', () => {
  const b = { name: 'Solo', itMW: 40, constructionStart: 1, constructionMonths: 6, powerMonth: 7, leaseMonth: 7, leaseTermMonths: 24, rentEscalatorPct: 3 };
  const r = run({ sponsorCommitmentM: null, months: 72, buildings: [b], ltc: 0, mezzLtcPct: 0, leaseExpiryPolicy: 'renew', renewalProbabilityPct: 100, renewalRentPct: 100, renewalTermMonths: 36, loanMaturityMode: 'equity', exitValueM: 0, refinanceValueM: 0 });
  const rent = m => r.rows[m - 1].leaseRevenue;
  eq(rent(31), rent(30), 1e-9, 'first renewal month = last contract month');
  eq(rent(42), rent(31), 1e-9, 'flat through renewal year 1');
  eq(rent(43), rent(31) * 1.03, 1e-9, 'escalates at renewal year 2');
  eq(rent(66), rent(31) * 1.03 * 1.03, 1e-9, 'last renewal month');
  eq(rent(67), 0, 1e-12, 'after renewal term');
});

// 20. Abandoned campus exit scales with completed IT MW.
check('A19 halted campus terminal value scales with completed IT MW', () => {
  const r = run({ sponsorCommitmentM: 60, initialCash: 50 });
  const s = r.summary, done = D.buildings.filter(b => !s.abandonedBuildings.includes(b.name)).reduce((v, b) => v + b.itMW, 0);
  const total = D.buildings.reduce((v, b) => v + b.itMW, 0);
  eq(r.rows.at(-1).terminalProceeds, D.exitValueM * (1 - D.exitCostPct / 100) * done / total, 1e-9, 'terminal');
});

// KNOWN OPEN (RT-A02, frozen engine): after a total-halt funding default, construction interest keeps being paid
// from negative cash; reported here, excluded from the exit status, and re-flagged if it ever starts passing.
// RT-A02 is fixed in engine/underwrite27.js (v27.1); it stays a documented defect of the frozen legacy engine only.
const KNOWN_OPEN = /underwrite25\.js$/.test(process.argv[2]) ? ['A02'] : [];
for (const r of results) if (KNOWN_OPEN.some(k => r.name.startsWith(k))) r.knownOpen = true;
const unexpectedPass = results.filter(r => r.knownOpen && r.pass);
const failed = results.filter(r => !r.pass && !r.knownOpen).concat(unexpectedPass.map(r => ({ ...r, msg: 'KNOWN-OPEN item now passes: update KNOWN_OPEN' })));
console.log(JSON.stringify({ engine: process.argv[2], passed: results.length - failed.length, failed: failed.length, results }, null, 1));
process.exit(failed.length ? 1 : 0);
