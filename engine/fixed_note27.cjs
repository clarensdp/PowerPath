'use strict';
/* PowerPath fixed_note27 1.0.0 — instrument-level schedule for a fixed-rate, semiannual-pay secured note with contingent
   amortisation. Layer 2 (reconstructed financing cash flows) only: it computes what the stated terms imply under the
   supplied assumptions. It does NOT value a project, size debt, or verify any term. All amounts in $M.

   Conventions (each is an input, never hard-coded to a transaction):
   - Interest accrues from issueDate on the principal outstanding during each accrual period; the first period is a stub.
   - dayCount: '30/360' (US bond basis), 'ACT/360' or 'ACT/365'.
   - Installments (annualPctOfOriginal / installmentsPerYear of ORIGINAL principal) fall on payment dates on or after
     firstInstallmentDate and strictly before maturity; null firstInstallmentDate = no installment before maturity.
   - All remaining principal is due at maturity. The maturity payment is split into the scheduled installment that
     would fall on that date (if amortising) and the true balloon.
   - Effective interest (amortised cost): yield y (semiannual compounding) equates net proceeds with all contractual
     cash flows, measured in 30/360-or-actual year fractions per dayCount. Carrying value at a date = PV of remaining
     cash flows at y.
*/
const D = s => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s)); if (!m) throw Error('Invalid date ' + s); const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])); if (d.getUTCMonth() !== +m[2] - 1) throw Error('Invalid date ' + s); return d };
const iso = d => d.toISOString().slice(0, 10);
const finite = (v, k, min = -Infinity, max = Infinity) => { v = Number(v); if (!Number.isFinite(v) || v < min || v > max) throw Error(k + ' out of range'); return v };
function yearFrac(a, b, dc) {
  if (dc === 'ACT/360') return (b - a) / 864e5 / 360;
  if (dc === 'ACT/365') return (b - a) / 864e5 / 365;
  if (dc !== '30/360') throw Error('Unsupported dayCount ' + dc);
  let d1 = a.getUTCDate(), d2 = b.getUTCDate();
  if (d1 === 31) d1 = 30; if (d2 === 31 && d1 >= 30) d2 = 30;
  return ((b.getUTCFullYear() - a.getUTCFullYear()) * 360 + (b.getUTCMonth() - a.getUTCMonth()) * 30 + (d2 - d1)) / 360;
}
function paymentDates(first, maturity, monthDays) {
  const out = []; const f = D(first), mat = D(maturity);
  for (let y = f.getUTCFullYear(); y <= mat.getUTCFullYear(); y++) for (const [mo, day] of monthDays) { const d = new Date(Date.UTC(y, mo - 1, day)); if (d >= f && d <= mat) out.push(d) }
  out.sort((a, b) => a - b); if (!out.length || +out[out.length - 1] !== +mat) throw Error('Maturity must fall on a payment date');
  if (+out[0] !== +f) throw Error('firstInterestDate must fall on a payment date');
  return out;
}
function evaluate(x) {
  const P = finite(x.principalM, 'principalM', 0.000001), c = finite(x.couponPct, 'couponPct', 0, 30) / 100;
  const price = finite(x.issuePricePct ?? 100, 'issuePricePct', 50, 110), costs = finite(x.issuanceCostsM ?? 0, 'issuanceCostsM', 0);
  const dc = x.dayCount || '30/360'; const issue = D(x.issueDate), mat = D(x.maturityDate);
  const am = x.amortization || {}; const pct = finite(am.annualPctOfOriginal ?? 0, 'annualPctOfOriginal', 0, 100), per = Math.round(finite(am.installmentsPerYear ?? 2, 'installmentsPerYear', 1, 12));
  const firstInst = am.firstInstallmentDate ? D(am.firstInstallmentDate) : null;
  const dates = paymentDates(x.firstInterestDate, x.maturityDate, x.paymentMonthDays || [[5, 15], [11, 15]]);
  if (D(x.firstInterestDate) <= issue) throw Error('First interest date must follow issue date');
  if (firstInst && !dates.some(d => +d === +firstInst)) throw Error('firstInstallmentDate must be a scheduled payment date');
  const dsra = x.dsra || {}; const dsraBal = finite(dsra.balanceM ?? 0, 'dsra.balanceM', 0); const dsraPolicy = dsra.policy || 'hold';
  if (!['hold', 'release_at_maturity'].includes(dsraPolicy)) throw Error('dsra.policy must be hold or release_at_maturity');
  const targets = (x.dscrTargets || [1.0, 1.2, 1.35]).map(t => finite(t, 'dscrTarget', 0.5, 5));
  const inst = P * pct / 100 / per;
  let out = P, prev = issue; const periods = [];
  for (const d of dates) {
    const frac = yearFrac(prev, d, dc), interest = out * c * frac, isMat = +d === +mat;
    const amortising = firstInst !== null && d >= firstInst;
    const scheduled = amortising ? Math.min(out, inst) : 0;
    const balloon = isMat ? out - scheduled : 0;
    const principal = scheduled + balloon;
    const dsraRelease = isMat && dsraPolicy === 'release_at_maturity' ? Math.min(dsraBal, interest + principal) : 0;
    const ds = interest + principal;
    const p = { date: iso(d), accrualStart: iso(prev), yearFraction: frac, openingPrincipalM: out, interestM: interest, scheduledPrincipalM: scheduled, balloonM: balloon, principalM: principal, debtServiceM: ds, closingPrincipalM: out - principal, dsraBalanceM: isMat && dsraPolicy === 'release_at_maturity' ? dsraBal - dsraRelease : dsraBal, dsraReleaseM: dsraRelease, amortising, requiredCfadsM: {} };
    // Illustrative coverage only: CFADS that would be needed to cover this period's scheduled debt service (balloon excluded).
    for (const t of targets) p.requiredCfadsM[t.toFixed(2)] = (interest + scheduled) * t;
    periods.push(p); out -= principal; prev = d;
  }
  const netProceeds = P * price / 100 - costs, oid = P * (1 - price / 100);
  // Effective yield: semiannual compounding over cumulative year fractions (day count as specified).
  const T = []; let acc = 0, p0 = issue; for (const p of periods) { acc += yearFrac(p0, D(p.date), dc); T.push(acc); p0 = D(p.date) }
  const pv = y => periods.reduce((s, p, i) => s + p.debtServiceM / Math.pow(1 + y / 2, 2 * T[i]), 0);
  let lo = 0, hi = 1; for (let i = 0; i < 200; i++) { const mid = (lo + hi) / 2; if (pv(mid) > netProceeds) lo = mid; else hi = mid }
  const y = (lo + hi) / 2;
  const carryingAt = dateStr => { const t = D(dateStr); if (t < issue) return null; const tt = yearFrac(issue, t, dc); let s = 0; periods.forEach((p, i) => { if (D(p.date) > t) s += p.debtServiceM / Math.pow(1 + y / 2, 2 * (T[i] - tt)) }); const outP = periods.filter(p => D(p.date) <= t).reduce((v, p) => v - p.principalM, P); const paidInt = periods.filter(p => D(p.date) <= t).reduce((v, p) => v + p.interestM, 0); const lastDate = periods.filter(p => D(p.date) <= t).map(p => D(p.date)).pop() || issue; const accrued = outP * c * yearFrac(lastDate, t, dc); return { date: dateStr, principalOutstandingM: outP, carryingAmountM: s - accrued, accruedCouponM: accrued, unamortizedDiscountAndCostsM: outP - (s - accrued), couponPaidToDateM: paidInt, interestExpenseToDateM: (s - accrued) - netProceeds + paidInt + (P - outP) + accrued } };
  const byYear = {}; for (const p of periods) { const yr = p.date.slice(0, 4); byYear[yr] = (byYear[yr] || 0) + p.principalM }
  const sum = k => periods.reduce((v, p) => v + p[k], 0);
  const finalP = periods[periods.length - 1];
  return {
    engine: 'fixed_note27', engineVersion: '1.0.0', periods,
    summary: {
      instrumentId: x.instrumentId || null, principalM: P, couponPct: c * 100, dayCount: dc, issueDate: iso(issue), maturityDate: iso(mat),
      firstInstallmentDate: firstInst ? iso(firstInst) : null, installmentAmountM: inst, installmentsBeforeMaturity: periods.filter(p => p.scheduledPrincipalM > 0 && p.date !== iso(mat)).length,
      totalInterestM: sum('interestM'), totalScheduledPrincipalM: sum('scheduledPrincipalM'), balloonM: finalP.balloonM, finalMaturityPaymentPrincipalM: finalP.principalM,
      firstCouponM: periods[0].interestM, firstPeriodYearFraction: periods[0].yearFraction, grossProceedsM: P * price / 100, originalIssueDiscountM: oid, issuanceCostsM: costs, netProceedsM: netProceeds,
      effectiveYieldBondEquivalentPct: y * 100, effectiveAnnualRatePct: (Math.pow(1 + y / 2, 2) - 1) * 100,
      principalByCalendarYearM: byYear, dsraPolicy, dsraBalanceM: dsraBal,
      carrying: (x.reportingDates || []).map(carryingAt),
      layer: 'LAYER_2_RECONSTRUCTED_FINANCING_CASH_FLOWS', valuation: 'NOT_A_PROJECT_VALUATION'
    }
  };
}
module.exports = { evaluate, yearFrac: (a, b, dc) => yearFrac(D(a), D(b), dc), ENGINE_VERSION: '1.0.0' };
