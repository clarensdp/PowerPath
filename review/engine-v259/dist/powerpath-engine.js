/* @powerpath/engine 25.9.0-risk1 — browser build */
(function(root){'use strict';
const __ppModules={};
const __ppRequire=(p)=>{if(Object.prototype.hasOwnProperty.call(__ppModules,p))return __ppModules[p];throw Error('Module not bundled: '+p);};
__ppModules['./facilities.cjs']=(function(require){const module={exports:{}};const exports=module.exports;
/**
 * PowerPath v25.9 debt facilities (fixed-rate notes) per FACILITY_SPEC_v259.md. Pure helpers used by
 * evaluate() in underwrite.cjs. No transaction terms are hard-coded here: every term is an input.
 * Units: $M, months (model month 1 = calendarStartYear/calendarStartMonth), % as 0-100.
 */
'use strict';

const EVIDENCE_LABELS = ['Executed', 'Public approximate', 'Management expectation', 'Assumption', 'Unknown'];
const AMORT_TYPES = ['none', 'unknown', 'pctOriginalPerYear', 'explicit'];
const AMORT_START_TYPES = ['fixedMonth', 'afterFirstRent', 'afterFinalCommencement'];
const DSRA_TYPES = ['none', 'fixed', 'nextPeriod', 'constructionThenNextPeriod'];
const GENERIC_DEBT_ERROR =
  'Generic construction debt must be disabled (ltc=0, mezzLtcPct=0) when facilities are modeled';
const POOL_WARNING =
  'FACILITIES: single project cash pool; facility ring-fencing, cash sweeps and excess-cash-flow offers not modeled';
const ARREARS_WARNING = 'FACILITIES: payment shortfalls are shown as unfunded cash, not as facility arrears';

const num = (v, label, lo, hi) => {
  if (typeof v !== 'number' || !Number.isFinite(v) || v < lo || v > hi)
    throw Error(label + ' must be a finite number in ' + lo + '..' + hi);
  return v;
};

/** ISO date YYYY-MM-DD -> model month; the day is ignored (spec §1). */
function dateToMonth(iso, calendarStartYear, calendarStartMonth, label) {
  if (typeof iso !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(iso))
    throw Error(label + ' must be an ISO date YYYY-MM-DD');
  const Y = Number(iso.slice(0, 4)),
    M = Number(iso.slice(5, 7)),
    D = Number(iso.slice(8, 10));
  if (M < 1 || M > 12 || D < 1 || D > 31) throw Error(label + ' is not a valid calendar date');
  return (Y - calendarStartYear) * 12 + (M - calendarStartMonth) + 1;
}

/** Integer month field takes precedence over the date field (spec §1). */
function monthOf(obj, monthKey, dateKey, a, label) {
  const mv = obj[monthKey];
  if (mv !== undefined && mv !== null) {
    if (!Number.isInteger(mv)) throw Error(label + ' ' + monthKey + ' must be an integer month');
    return mv;
  }
  const dv = obj[dateKey];
  if (dv !== undefined && dv !== null)
    return dateToMonth(dv, a.calendarStartYear, a.calendarStartMonth, label + ' ' + dateKey);
  throw Error(label + ' requires ' + monthKey + ' or ' + dateKey);
}

/**
 * Validates facility inputs (spec §0-§1) and returns mutable per-facility state objects, in INPUT order.
 * Throws on any violation.
 */
function normalizeFacilities(list, a, months, buildingNames) {
  if (!Array.isArray(list)) throw Error('facilities must be an array');
  if (a.ltc !== 0 || a.mezzLtcPct !== 0) throw Error(GENERIC_DEBT_ERROR);
  const ids = new Set();
  return list.map((f, index) => {
    if (!f || typeof f !== 'object') throw Error('Facility ' + index + ' must be an object');
    if (typeof f.id !== 'string' || !f.id.trim()) throw Error('Facility ' + index + ' requires a string id');
    const L = 'Facility ' + f.id + ':';
    if (ids.has(f.id)) throw Error('Duplicate facility id ' + f.id);
    ids.add(f.id);
    if (f.modelable === false)
      throw Error(
        L +
          ' template is marked modelable: false' +
          (f.modelableReason ? ' (' + f.modelableReason + ')' : ''),
      );
    if (typeof f.name !== 'string') throw Error(L + ' name must be a string');
    if (f.type !== 'fixed_note') throw Error(L + " type must be 'fixed_note'");
    if (typeof f.faceM !== 'number' || !Number.isFinite(f.faceM) || f.faceM <= 0)
      throw Error(L + ' faceM must be finite and > 0');
    const couponPct = num(f.couponPct, L + ' couponPct', 0, 100),
      issuePricePct = num(f.issuePricePct, L + ' issuePricePct', 0, 200),
      feePct = f.feePct === undefined ? 0 : num(f.feePct, L + ' feePct', 0, 100);
    const issueMonth = monthOf(f, 'issueMonth', 'issueDate', a, L),
      firstPaymentMonth = monthOf(f, 'firstPaymentMonth', 'firstPaymentDate', a, L),
      maturityMonth = monthOf(f, 'maturityMonth', 'maturityDate', a, L);
    if (issueMonth < 1) throw Error(L + ' issueMonth must be >= 1 (got ' + issueMonth + ')');
    if (!(issueMonth < firstPaymentMonth)) throw Error(L + ' firstPaymentMonth must be after issueMonth');
    if (!(firstPaymentMonth <= maturityMonth)) throw Error(L + ' maturityMonth must be >= firstPaymentMonth');
    if (!(maturityMonth <= months))
      throw Error(L + ' maturityMonth ' + maturityMonth + ' is beyond the horizon');
    if ((maturityMonth - firstPaymentMonth) % 6 !== 0)
      throw Error(L + ' maturity is not on the semiannual payment cycle');
    if (!Array.isArray(f.buildings) || f.buildings.length === 0)
      throw Error(L + ' buildings must be a non-empty array');
    for (const b of f.buildings) if (!buildingNames.includes(b)) throw Error(L + ' unknown building ' + b);
    if (new Set(f.buildings).size !== f.buildings.length) throw Error(L + ' duplicate collateral building');
    const priority = f.priority === undefined ? 1 : f.priority;
    if (!Number.isInteger(priority)) throw Error(L + ' priority must be an integer');
    const am = f.amortization;
    if (!am || !AMORT_TYPES.includes(am.type)) throw Error(L + ' invalid amortization type');
    let amortization;
    if (am.type === 'pctOriginalPerYear') {
      if (
        typeof am.annualPct !== 'number' ||
        !Number.isFinite(am.annualPct) ||
        am.annualPct < 0 ||
        am.annualPct > 100
      )
        throw Error(L + ' pctOriginalPerYear needs a finite annualPct in 0..100');
      amortization = { type: am.type, annualPct: am.annualPct };
    } else if (am.type === 'explicit') {
      if (
        !Array.isArray(am.amountsM) ||
        am.amountsM.some((x) => typeof x !== 'number' || !Number.isFinite(x) || x < 0)
      )
        throw Error(L + ' explicit amortization amounts must be finite and >= 0');
      amortization = { type: am.type, amountsM: am.amountsM.slice() };
    } else amortization = { type: am.type };
    const as = f.amortStart;
    let amortStart = null,
      A = null;
    if (as === undefined || as === null) {
      if (!['none', 'unknown'].includes(am.type))
        throw Error(L + " amortStart may be omitted only with amortization 'none' or 'unknown'");
    } else {
      if (!AMORT_START_TYPES.includes(as.type)) throw Error(L + ' invalid amortStart type');
      if (as.type === 'fixedMonth') {
        A = monthOf(as, 'month', 'date', a, L + ' amortStart');
        amortStart = { type: as.type, month: A };
      } else {
        if (!Number.isInteger(as.offsetMonths) || as.offsetMonths < 0)
          throw Error(L + ' amortStart offsetMonths must be an integer >= 0');
        amortStart = { type: as.type, offsetMonths: as.offsetMonths };
      }
    }
    const ds = f.dsra === undefined ? { type: 'none' } : f.dsra;
    if (!ds || !DSRA_TYPES.includes(ds.type)) throw Error(L + ' invalid dsra type');
    let dsra = { type: ds.type };
    if (ds.type === 'fixed') dsra.amountM = num(ds.amountM, L + ' dsra amountM', 0, Infinity);
    if (ds.type === 'constructionThenNextPeriod')
      dsra.constructionAmountM = num(ds.constructionAmountM, L + ' dsra constructionAmountM', 0, Infinity);
    const lockupDscr = f.lockupDscr === undefined ? 1.2 : num(f.lockupDscr, L + ' lockupDscr', 0, Infinity);
    const evidence = {};
    if (f.evidence !== undefined && f.evidence !== null) {
      if (typeof f.evidence !== 'object') throw Error(L + ' evidence must be an object');
      for (const [term, e] of Object.entries(f.evidence)) {
        if (!e || !EVIDENCE_LABELS.includes(e.label))
          throw Error(L + " evidence for '" + term + "' has an invalid label");
        evidence[term] = { ...e };
      }
    }
    const P = [];
    for (let p = firstPaymentMonth; p <= maturityMonth; p += 6) P.push(p);
    return {
      index,
      id: f.id,
      name: f.name,
      faceM: f.faceM,
      couponPct,
      issuePricePct,
      feePct,
      issueMonth,
      firstPaymentMonth,
      maturityMonth,
      buildings: f.buildings.slice(),
      priority,
      amortization,
      amortStart,
      dsraSpec: dsra,
      lockupDscr,
      evidence,
      P,
      Pset: new Set(P),
      A,
      // AM1: construction-end event month E (fixedMonth: the given month, known from month 1).
      E: A,
      // AM3: first month every collateral building has gross rent > 0, once it has occurred.
      L: null,
      // AM4: a maturity in the final model month settles in the exit waterfall.
      deferMaturity: maturityMonth === months,
      maturityInstallment: 0,
      // running state
      bal: 0,
      accrued: 0,
      dsra: 0,
      balloonM: 0,
      totalInterestPaidM: 0,
      totalPrincipalPaidM: 0,
      unpaidAtExitM: 0,
      shares: [],
      dscrTests: [],
      lockTest: null,
      lockupMonths: [],
      dsraDeficiencyMonths: [],
      schedule: [],
      cur: null,
    };
  });
}

/** Stable priority order (lower first; ties keep input order). */
const byPriority = (states) => states.slice().sort((x, y) => x.priority - y.priority || x.index - y.index);

/** First month in 1..upTo where `test(physicalByMonth[m])` holds, else null. */
function firstMonth(ctx, upTo, test) {
  for (let m = 1; m <= Math.min(upTo, ctx.months); m++) if (test(ctx.physicalByMonth[m])) return m;
  return null;
}

/**
 * Amendment 1 (AM1, AM3): event-based resolution with NO look-ahead, evaluated at the start of month m on the
 * physical schedule current at month m. An event counts only once it has happened (event month <= m).
 * - L (construction lock-up end): first month every collateral building has gross rent > 0.
 * - E (construction-end event): afterFirstRent R; afterFinalCommencement T = max(C, K); fixedMonth the given month.
 * Once E has occurred, A = smallest p in P with p > R + offset (afterFirstRent) or p >= T + offset
 * (afterFinalCommencement); A may stay null if no such p exists. E, L and A never change once set.
 * ctx: { months, physicalByMonth, cohortsByBuilding, itMW(name), creditMonths(name) }
 */
function updateEvents(f, ctx, m) {
  if (f.L === null)
    f.L = firstMonth(ctx, m, (ph) => f.buildings.every((b) => (ph.grossByBuilding[b] || 0) > 0));
  if (!f.amortStart || f.amortStart.type === 'fixedMonth' || f.E !== null) return;
  const off = f.amortStart.offsetMonths;
  if (f.amortStart.type === 'afterFirstRent') {
    const R = firstMonth(ctx, m, (ph) => f.buildings.some((b) => (ph.grossByBuilding[b] || 0) > 0));
    if (R === null) return;
    f.E = R;
    const p = f.P.find((x) => x > R + off);
    f.A = p === undefined ? null : p;
    return;
  }
  const C = firstMonth(ctx, m, (ph) =>
    f.buildings.every((b) => Math.abs((ph.rentedByBuilding[b] || 0) - ctx.itMW(b)) <= 1e-9),
  );
  if (C === null) return;
  let K = -Infinity;
  for (const b of f.buildings) {
    const cohorts = ctx.cohortsByBuilding.get(b) || [];
    if (!cohorts.length) continue;
    K = Math.max(K, Math.max(...cohorts.map((c) => c.start)) + ctx.creditMonths(b));
  }
  const T = Math.max(C, K);
  if (T > m) return;
  f.E = T;
  const p = f.P.find((x) => x >= T + off);
  f.A = p === undefined ? null : p;
}

/**
 * Scheduled installment at payment month p given opening balance bOpen (spec §4). Defined for every p in P with
 * A set and p >= A, INCLUDING the maturity month (used for balloonM, the maturity DSCR denominator and a
 * nextPeriod DSRA whose next payment is the maturity). Before maturity it is the principal actually paid.
 */
function scheduledInstallment(f, p, bOpen) {
  if (f.A === null || p < f.A || !f.Pset.has(p)) return 0;
  if (f.amortization.type === 'pctOriginalPerYear')
    return Math.min(bOpen, (f.faceM * f.amortization.annualPct) / 200);
  if (f.amortization.type === 'explicit') {
    const j = f.P.filter((x) => x >= f.A).indexOf(p);
    const amt = f.amortization.amountsM[j];
    return Math.min(bOpen, amt === undefined ? 0 : amt);
  }
  return 0;
}

/** Issuance, accrual, interest and principal for month m (spec §2-§4). Sets f.cur. */
function monthFlows(f, m) {
  const r = {
    month: m,
    opening: 0,
    accrual: 0,
    interestPaid: 0,
    principalPaid: 0,
    scheduledPrincipal: 0,
    interestDue: 0,
    closing: 0,
    accruedStart: f.accrued,
    accruedEnd: 0,
    proceeds: 0,
    fees: 0,
    dsraRequired: 0,
    dsraBalance: 0,
    dsraMovement: 0,
    dsraDraw: 0,
    dsraDeficiency: 0,
    cfadsShare: 0,
    exitInterestPaid: 0,
    exitPrincipalPaid: 0,
  };
  f.cur = r;
  if (m < f.issueMonth) return r;
  if (m === f.issueMonth) {
    r.proceeds = (f.faceM * f.issuePricePct) / 100;
    r.fees = (f.faceM * f.feePct) / 100;
    f.bal = f.faceM;
    r.opening = f.bal; // balance after issuance, so closing = opening - principalPaid holds in the issue month
  } else {
    r.opening = f.bal;
    if (m <= f.maturityMonth && f.bal > 0) {
      r.accrual = (f.bal * f.couponPct) / 1200;
      f.accrued += r.accrual;
    }
    if (f.Pset.has(m) && m === f.maturityMonth && f.deferMaturity) {
      // AM4: not paid in step 2; interest and principal are settled in the exit waterfall.
      r.interestDue = f.accrued;
      r.scheduledPrincipal = scheduledInstallment(f, m, f.bal);
      f.maturityInstallment = r.scheduledPrincipal;
    } else if (f.Pset.has(m)) {
      r.interestPaid = f.accrued;
      r.interestDue = f.accrued;
      f.accrued = 0;
      const inst = scheduledInstallment(f, m, f.bal);
      r.scheduledPrincipal = inst;
      r.principalPaid = m === f.maturityMonth ? f.bal : inst;
      if (m === f.maturityMonth) f.balloonM = r.principalPaid - inst;
      f.bal -= r.principalPaid;
    }
  }
  f.totalInterestPaidM += r.interestPaid;
  f.totalPrincipalPaidM += r.principalPaid;
  r.closing = f.bal;
  r.accruedEnd = f.accrued;
  return r;
}

/** DSCR test on payment months (spec §7); records the test and the lock-up window it puts in force. */
function dscrTest(f, m) {
  if (!f.Pset.has(m)) return;
  const r = f.cur;
  let sum = 0;
  for (let k = m - 5; k <= m; k++) if (k >= 1) sum += f.shares[k] || 0;
  const den = r.interestDue + r.scheduledPrincipal;
  const dscr = den > 0 ? sum / den : null;
  f.dscrTests.push({ month: m, dscr });
  const next = f.P.find((x) => x > m);
  f.lockTest = { dscr, until: next === undefined ? m : next - 1 };
}

/** True when this facility's most recent DSCR test is in force in month m and below lockupDscr. */
const dscrLocked = (f, m) =>
  f.lockTest !== null && m <= f.lockTest.until && f.lockTest.dscr !== null && f.lockTest.dscr < f.lockupDscr;

function nextPeriodRequirement(f, m) {
  const q = f.P.find((x) => x > m);
  if (q === undefined) return 0;
  return f.accrued + ((f.bal * f.couponPct) / 1200) * (q - m) + scheduledInstallment(f, q, f.bal);
}

/** DSRA requirement Q(m) at end of month m (spec §6); 0 before issuance and once the balance is 0. */
function dsraRequirement(f, m) {
  if (m < f.issueMonth || !(f.bal > 0)) return 0;
  const s = f.dsraSpec;
  if (s.type === 'fixed') return s.amountM;
  if (s.type === 'nextPeriod') return nextPeriodRequirement(f, m);
  if (s.type === 'constructionThenNextPeriod')
    return f.E === null || m < f.E ? s.constructionAmountM : nextPeriodRequirement(f, m);
  return 0;
}

/**
 * Exit payoff (spec §5.10): pay facilities in priority order, accrued interest first, then principal, from
 * `available` (already including released DSRAs). Mutates states; returns the amount paid.
 */
function exitPayoff(ordered, available) {
  let left = Math.max(0, available),
    paid = 0;
  for (const f of ordered) {
    const pi = Math.min(f.accrued, left);
    left -= pi;
    const pp = Math.min(f.bal, left);
    left -= pp;
    f.accrued -= pi;
    f.bal -= pp;
    if (f.cur) {
      f.cur.exitInterestPaid = pi;
      f.cur.exitPrincipalPaid = pp;
      f.cur.interestPaid += pi;
      f.cur.principalPaid += pp;
      f.cur.closing = f.bal;
      f.cur.accruedEnd = f.accrued;
    }
    if (f.deferMaturity) f.balloonM = Math.max(0, pp - f.maturityInstallment); // AM4: balloon settled at exit
    f.totalInterestPaidM += pi;
    f.totalPrincipalPaidM += pp;
    f.unpaidAtExitM = f.bal + f.accrued;
    paid += pi + pp;
  }
  return paid;
}

function facilityWarnings(f) {
  const w = [];
  if (f.amortStart && ['afterFirstRent', 'afterFinalCommencement'].includes(f.amortStart.type))
    w.push(
      'FACILITY ' +
        f.id +
        ': amortization start derived from modeled commencement, not contractual confirmation',
    );
  if (f.amortization.type === 'unknown')
    w.push('FACILITY ' + f.id + ': amortization unknown — bullet assumed; debt service understated');
  if (f.amortStart && f.A === null)
    w.push('FACILITY ' + f.id + ': amortization start never resolved within horizon');
  for (const [term, e] of Object.entries(f.evidence))
    if (e.label !== 'Executed')
      w.push('FACILITY ' + f.id + ": term '" + term + "' is " + e.label + ', not Executed');
  return w;
}

function facilitySummary(f) {
  const proceedsM = (f.faceM * f.issuePricePct) / 100;
  const finite = f.dscrTests.map((t) => t.dscr).filter((x) => x !== null);
  return {
    id: f.id,
    name: f.name,
    faceM: f.faceM,
    couponPct: f.couponPct,
    issuePricePct: f.issuePricePct,
    proceedsM,
    oidM: f.faceM - proceedsM,
    feesM: (f.faceM * f.feePct) / 100,
    issueMonth: f.issueMonth,
    firstPaymentMonth: f.firstPaymentMonth,
    maturityMonth: f.maturityMonth,
    amortStartMonth: f.A,
    amortStartBasis: f.amortStart ? f.amortStart.type : 'none',
    constructionEndMonth: f.E,
    constructionLockupEndMonth: f.L,
    totalInterestPaidM: f.totalInterestPaidM,
    totalPrincipalPaidM: f.totalPrincipalPaidM,
    balloonM: f.balloonM,
    endingBalanceM: f.bal,
    unpaidAtExitM: f.unpaidAtExitM,
    minDscr: finite.length ? Math.min(...finite) : null,
    dscrTests: f.dscrTests.map((t) => ({ ...t })),
    lockupMonths: f.lockupMonths.slice(),
    dsraDeficiencyMonths: f.dsraDeficiencyMonths.slice(),
    schedule: f.schedule.map((r) => ({
      month: r.month,
      opening: r.opening,
      accrual: r.accrual,
      interestPaid: r.interestPaid,
      principalPaid: r.principalPaid,
      closing: r.closing,
      accruedEnd: r.accruedEnd,
      dsraRequired: r.dsraRequired,
      dsraBalance: r.dsraBalance,
      cfadsShare: r.cfadsShare,
      scheduledPrincipal: r.scheduledPrincipal,
      dsraMovement: r.dsraMovement,
      dsraDraw: r.dsraDraw,
    })),
    evidence: JSON.parse(JSON.stringify(f.evidence)),
    warnings: facilityWarnings(f),
  };
}

module.exports = {
  EVIDENCE_LABELS,
  GENERIC_DEBT_ERROR,
  POOL_WARNING,
  ARREARS_WARNING,
  dateToMonth,
  normalizeFacilities,
  byPriority,
  updateEvents,
  scheduledInstallment,
  monthFlows,
  dscrTest,
  dscrLocked,
  dsraRequirement,
  exitPayoff,
  facilityWarnings,
  facilitySummary,
};

return module.exports;})(__ppRequire);
const engine=(function(require){const module={exports:{}};const exports=module.exports;
/**
 * PowerPath underwriting engine — pure monthly project-finance ledger. Units: $M, MW, months.
 * Extracted from PowerPath v25.8.4-CA (red-team patched). No DOM, no storage, no network:
 * the same module runs in the browser, on a server and in audits.
 */
'use strict';

const fac = require('./facilities.cjs');
const finite = (v, k, min = 0) => {
  v = Number(v);
  if (!Number.isFinite(v) || v < min) throw Error(k + ' must be finite and >= ' + min);
  return v;
};
const defaults = () => ({
  months: 120,
  calendarStartYear: 2026,
  calendarStartMonth: 1,
  discount: 10,
  rate: 8,
  ltc: 65,
  debtFee: 1,
  termMonths: 60,
  amortMonths: 240,
  dscrCovenant: 1.2,
  minLiquidity: 10,
  initialCash: 50,
  reserveTargetM: 10,
  rentPerKwMonth: 170,
  pue: 1.3,
  powerCostMWh: 85,
  powerResponsibility: 'landlord',
  powerPassThroughPct: 100,
  powerReimbursementLagDays: 0,
  otherOpexPct: 12,
  fixedOpexM: 0.4,
  constructionCostMW: 7,
  delayMonths: 0,
  overrunPct: 0,
  rateShockPct: 0,
  energyShockPct: 0,
  refinanceLtvPct: 60,
  refinanceValueM: 1400,
  refinanceRatePct: 7,
  refinanceFeePct: 1,
  exitValueM: 1800,
  exitCostPct: 2,
  loanMaturityMode: 'refinance',
  distributionPolicy: 'excess',
  capacityBasis: 'IT',
  tenantCapexPct: 0,
  tenantFundingLagMonths: 0,
  tenantRentCreditPct: 0,
  tenantCreditMonths: 0,
  debtYieldMinPct: 8,
  refinanceDscrMin: 1.25,
  refinanceAmortMonths: 240,
  mezzLtcPct: 0,
  mezzRatePct: 13,
  mezzFeePct: 2,
  cashSweepPct: 0,
  rateShockAllFacilities: false,
  exitTenantReceivableRecoveryPct: 0,
  exitWorkingCapitalRecoveryPct: 0,
  distributionDscrMin: 1.2,
  lockDistributionsOnBreach: true,
  dsraMonths: 0,
  dsraReleaseAtExit: true,
  sponsorCommitmentM: null,
  cashTaxRatePct: 0,
  maintenanceCapexMWYearM: 0,
  workingCapitalDays: 0,
  fundingDefaultPolicy: 'halt',
  refinanceTenorPolicy: 'fixed',
  leaseTailBufferMonths: 12,
  minRefinanceAmortMonths: 24,
  leaseExpiryPolicy: 'vacate',
  renewalProbabilityPct: 75,
  renewalRentPct: 100,
  renewalTermMonths: 60,
  exitValuePolicy: 'fixed',
  vacantValuePct: 40,
  buildings: [
    {
      name: 'Building A',
      itMW: 50,
      constructionStart: 1,
      constructionMonths: 18,
      powerMonth: 19,
      leaseMonth: 19,
      leaseTermMonths: 180,
      rentEscalatorPct: 2.5,
    },
    {
      name: 'Building B',
      itMW: 50,
      constructionStart: 10,
      constructionMonths: 18,
      powerMonth: 28,
      leaseMonth: 28,
      leaseTermMonths: 180,
      rentEscalatorPct: 2.5,
    },
    {
      name: 'Building C',
      itMW: 50,
      constructionStart: 19,
      constructionMonths: 18,
      powerMonth: 37,
      leaseMonth: 37,
      leaseTermMonths: 180,
      rentEscalatorPct: 2.5,
    },
  ],
  powerTranches: [],
});
function irr(flows) {
  if (!flows.some((x) => x < 0) || !flows.some((x) => x > 0)) return null;
  let npv = (r) => flows.reduce((s, v, i) => s + v / (1 + r) ** (i / 12), 0);
  let low = -0.999,
    high = 5,
    f0 = npv(low),
    f1 = npv(high);
  if (f0 * f1 > 0) return null;
  for (let j = 0; j < 150; j++) {
    let mid = (low + high) / 2,
      f = npv(mid);
    if (f0 * f > 0) {
      low = mid;
      f0 = f;
    } else high = mid;
  }
  return (low + high) / 2;
}
// Rent basis: never interpret a disclosed all-in lease value as a starting annual rent.
function rentSchedule(b, globalRent) {
  const mode = b.rentInputMode || 'starting';
  const term = Math.round(b.leaseTermMonths ?? 180),
    mw = b._itMW;
  const esc = (b.rentEscalatorPct ?? 2.5) / 100;
  if (!['starting', 'total', 'schedule'].includes(mode)) throw Error('Invalid rent input mode');
  if (mode === 'total') {
    const target = finite(b.contractedRentM, 'contractedRentM', 0.000001);
    const factor = Array.from({ length: term }, (_, i) => Math.pow(1 + esc, Math.floor(i / 12))).reduce(
      (x, y) => x + y,
      0,
    );
    return {
      mode,
      monthly: (age) =>
        (mw * 1000 * ((target * 1e6) / (mw * 1000 * factor)) * Math.pow(1 + esc, Math.floor(age / 12))) / 1e6,
      target,
      baseRate: (target * 1e6) / (mw * 1000 * factor),
    };
  }
  if (mode === 'schedule') {
    const years = Array.isArray(b.annualRentM)
      ? b.annualRentM
      : String(b.annualRentM || '')
          .split(',')
          .filter(Boolean)
          .map(Number);
    if (years.length !== Math.ceil(term / 12))
      throw Error('Explicit schedule must have one annual rental value per lease year');
    years.forEach((v, i) => finite(v, 'annualRentM ' + (i + 1)));
    const total = years.reduce((acc, v, i) => acc + (v * Math.min(12, term - i * 12)) / 12, 0);
    return { mode, monthly: (age) => years[Math.floor(age / 12)] / 12, target: total, baseRate: null };
  }
  const rate = b.rentPerKwMonth ?? globalRent;
  finite(rate, 'starting rent');
  const target =
    typeof b.contractedRentM === 'number' && Number.isFinite(b.contractedRentM)
      ? finite(b.contractedRentM, 'contractedRentM')
      : null;
  return {
    mode,
    monthly: (age) => (mw * 1000 * rate * Math.pow(1 + esc, Math.floor(age / 12))) / 1e6,
    target,
    baseRate: rate,
  };
}
function rentAudit(buildings, globalRent, pue, globalBasis) {
  return buildings.map((b) => {
    const it = b.itMW / ((b.capacityBasis || globalBasis) === 'gross' ? pue : 1);
    const t = Math.round(b.leaseTermMonths ?? 180);
    const r = rentSchedule({ ...b, _itMW: it }, globalRent);
    let modeled = 0;
    for (let i = 0; i < t; i++) modeled += r.monthly(i);
    const variance = r.target == null ? null : modeled - r.target,
      variancePct = r.target == null ? null : (100 * variance) / r.target;
    const reconciled = r.target != null && Math.abs(variancePct) <= 0.1;
    return {
      building: b.name,
      mode: r.mode,
      contractedRentM: r.target,
      modeledContractRentM: modeled,
      varianceM: variance,
      variancePct,
      startingRentPerKwMonth: r.baseRate,
      sourceRef: b.leaseSourceRef || '',
      reconciled,
      hasDocumentReference: Boolean(String(b.leaseSourceRef || '').trim()),
      status:
        r.target == null
          ? 'No contracted value for reconciliation'
          : reconciled
            ? 'Arithmetic reconciled; source review required'
            : 'BLOCKED: contracted value mismatch',
    };
  });
}
function evaluate(input = {}) {
  const d = defaults(),
    a = { ...d, ...input };
  a.buildings = (input.buildings || d.buildings).map((b) => ({ ...b }));
  a.powerTranches = (input.powerTranches || []).map((t) => ({ ...t }));
  const months = Math.round(finite(a.months, 'months', 12));
  if (months > 360) throw Error('months > 360');
  const checks = [
    'calendarStartYear',
    'calendarStartMonth',
    'discount',
    'rate',
    'ltc',
    'debtFee',
    'rentPerKwMonth',
    'pue',
    'powerCostMWh',
    'otherOpexPct',
    'fixedOpexM',
    'constructionCostMW',
    'delayMonths',
    'overrunPct',
    'rateShockPct',
    'energyShockPct',
    'initialCash',
    'dscrCovenant',
    'minLiquidity',
    'reserveTargetM',
    'refinanceLtvPct',
    'refinanceValueM',
    'refinanceRatePct',
    'refinanceFeePct',
    'exitValueM',
    'exitCostPct',
    'tenantCapexPct',
    'tenantFundingLagMonths',
    'tenantRentCreditPct',
    'tenantCreditMonths',
    'debtYieldMinPct',
    'refinanceDscrMin',
    'refinanceAmortMonths',
    'mezzLtcPct',
    'mezzRatePct',
    'mezzFeePct',
    'cashSweepPct',
    'distributionDscrMin',
    'dsraMonths',
    'cashTaxRatePct',
    'maintenanceCapexMWYearM',
    'workingCapitalDays',
    'exitTenantReceivableRecoveryPct',
    'exitWorkingCapitalRecoveryPct',
    'powerPassThroughPct',
  ];
  for (const k of checks) finite(a[k], k);
  if (a.sponsorCommitmentM !== null && a.sponsorCommitmentM !== undefined && a.sponsorCommitmentM !== '') {
    a.sponsorCommitmentM = finite(a.sponsorCommitmentM, 'sponsorCommitmentM');
    if (a.sponsorCommitmentM < a.initialCash - 1e-8)
      throw Error('Sponsor commitment cannot be below opening sponsor cash');
  } else a.sponsorCommitmentM = null;
  if (
    !Number.isInteger(a.calendarStartYear) ||
    a.calendarStartYear < 2000 ||
    a.calendarStartYear > 2200 ||
    !Number.isInteger(a.calendarStartMonth) ||
    a.calendarStartMonth < 1 ||
    a.calendarStartMonth > 12
  )
    throw Error('Invalid start calendar year/month');
  if (
    a.dsraMonths > 24 ||
    a.cashSweepPct > 100 ||
    a.ltc + a.mezzLtcPct > 100 ||
    a.ltc > 100 ||
    a.tenantCapexPct > 100 ||
    a.tenantRentCreditPct > 100 ||
    a.otherOpexPct > 100 ||
    a.cashTaxRatePct > 100 ||
    a.exitTenantReceivableRecoveryPct > 100 ||
    a.exitWorkingCapitalRecoveryPct > 100 ||
    a.workingCapitalDays > 365 ||
    a.tenantFundingLagMonths > 36 ||
    !Number.isInteger(a.tenantFundingLagMonths) ||
    a.pue < 1 ||
    a.refinanceLtvPct > 100 ||
    a.exitCostPct > 100 ||
    a.buildings.length < 1 ||
    a.buildings.length > 20 ||
    !['IT', 'gross'].includes(a.capacityBasis)
  )
    throw Error('Invalid financial assumptions');
  finite(a.termMonths, 'termMonths', 1);
  finite(a.amortMonths, 'amortMonths', 1);
  // N2: protect users from settings which formerly appeared to work but were silently ignored.
  // Construction debt is interest-only until retirement/refinancing; a mini-perm policy needs a sourced schedule.
  if (input.strictDebtPolicyValidation === true && a.amortMonths !== d.amortMonths)
    throw Error('amortMonths is not active: construction loan currently interest-only until maturity');
  if (input.strictDebtPolicyValidation === true && a.dsraReleaseAtExit !== true)
    throw Error('dsraReleaseAtExit=false is not supported by the current terminal reserve waterfall');
  if (!['refinance', 'equity', 'default'].includes(a.loanMaturityMode)) throw Error('Invalid maturity mode');
  for (const b of a.buildings) {
    for (const k of ['itMW', 'constructionStart', 'constructionMonths', 'powerMonth', 'leaseMonth'])
      finite(b[k], k, k === 'itMW' ? 0.01 : 1);
    if (b.constructionStart + b.constructionMonths - 1 > months)
      throw Error('Building construction outside horizon');
    if (b.leaseTermMonths !== undefined) {
      finite(b.leaseTermMonths, 'leaseTermMonths', 1);
      if (!Number.isInteger(b.leaseTermMonths)) throw Error('Lease term must be whole months');
    }
    if (b.rentEscalatorPct !== undefined && finite(b.rentEscalatorPct, 'rentEscalatorPct') > 100)
      throw Error('Rent escalator above 100%');
    if (b.rentPerKwMonth !== undefined) finite(b.rentPerKwMonth, 'building rent');
    if (b.tenantCapexPct !== undefined && finite(b.tenantCapexPct, 'building tenant capex') > 100)
      throw Error('Building tenant capex above 100%');
    if (b.tenantRentCreditPct !== undefined && finite(b.tenantRentCreditPct, 'building rent credit') > 100)
      throw Error('Building rent credit above 100%');
    if (b.capacityBasis && !['IT', 'gross'].includes(b.capacityBasis)) throw Error('Unknown capacity basis');
    if (b.contractedRentM !== undefined && b.contractedRentM !== '')
      finite(b.contractedRentM, 'contractedRentM', 0.000001);
  }
  // v25.8-CA P3: tranche MW carries an explicit unit. Default = the campus capacityBasis, so a
  // 'gross' campus treats utility tranches as gross MW and converts them to IT MW with PUE.
  a.trancheCapacityBasis = input.trancheCapacityBasis ?? a.capacityBasis;
  if (!['IT', 'gross'].includes(a.trancheCapacityBasis)) throw Error('Unknown tranche capacity basis');
  if (typeof a.rateShockAllFacilities !== 'boolean') throw Error('rateShockAllFacilities must be boolean');
  if (!['halt', 'continue'].includes(a.fundingDefaultPolicy)) throw Error('Invalid funding default policy');
  // v25.8-CA2 lease-tail policies (placeholders; set from leases / lender terms when available)
  if (
    !['fixed', 'leaseTail'].includes(a.refinanceTenorPolicy) ||
    !['vacate', 'renew'].includes(a.leaseExpiryPolicy) ||
    !['fixed', 'contracted'].includes(a.exitValuePolicy)
  )
    throw Error('Invalid lease-tail policy');
  for (const k of [
    'leaseTailBufferMonths',
    'minRefinanceAmortMonths',
    'renewalProbabilityPct',
    'renewalRentPct',
    'renewalTermMonths',
    'vacantValuePct',
  ])
    finite(a[k], k);
  if (
    a.renewalProbabilityPct > 100 ||
    a.vacantValuePct > 100 ||
    !Number.isInteger(a.renewalTermMonths) ||
    a.minRefinanceAmortMonths < 1
  )
    throw Error('Invalid lease-tail assumptions');
  for (const t of a.powerTranches) {
    finite(t.mw, 'tranche MW', 0.001);
    finite(t.month, 'tranche month', 1);
    if (t.building !== undefined && !a.buildings.some((b) => b.name === t.building))
      throw Error('Unknown tranche building');
    if (t.basis !== undefined && !['IT', 'gross'].includes(t.basis)) throw Error('Unknown tranche basis');
    t._itMW = t.mw / ((t.basis || a.trancheCapacityBasis) === 'gross' ? a.pue : 1);
  }
  if (!['landlord', 'tenant_direct', 'reimbursed'].includes(a.powerResponsibility))
    throw Error('powerResponsibility must be landlord, tenant_direct or reimbursed');
  if (a.powerPassThroughPct > 100) throw Error('powerPassThroughPct cannot exceed 100');
  // v25.8.4-CA1: reimbursement billings carry their OWN collection lag (default 0 = collected in the billing
  // month, as the v25.8.4 audit states); previously they silently took the rent workingCapitalDays.
  finite(a.powerReimbursementLagDays, 'powerReimbursementLagDays');
  if (a.powerReimbursementLagDays > 365) throw Error('powerReimbursementLagDays above 365');
  for (const b of a.buildings) {
    if (
      b.powerResponsibility !== undefined &&
      !['landlord', 'tenant_direct', 'reimbursed'].includes(b.powerResponsibility)
    )
      throw Error('Unknown building power responsibility for ' + b.name);
    if (
      b.powerPassThroughPct !== undefined &&
      finite(b.powerPassThroughPct, 'building powerPassThroughPct') > 100
    )
      throw Error('Building powerPassThroughPct must be <=100 for ' + b.name);
  }
  for (const b of a.buildings) {
    const assigned = a.powerTranches.filter((t) => t.building === b.name).reduce((v, t) => v + t._itMW, 0);
    if (assigned > b.itMW / ((b.capacityBasis || a.capacityBasis) === 'gross' ? a.pue : 1) + 1e-8)
      throw Error('Assigned power tranches exceed ' + b.name + ' IT MW');
  }
  const itMW = (b) => b.itMW / ((b.capacityBasis || a.capacityBasis) === 'gross' ? a.pue : 1);
  // v25.9 debt facilities (FACILITY_SPEC_v259). Absent or empty => every output identical to v25.8.4-ca.1.
  if (input.facilities !== undefined && input.facilities !== null && !Array.isArray(input.facilities))
    throw Error('facilities must be an array');
  const hasFac = Array.isArray(input.facilities) && input.facilities.length > 0;
  const facStates = hasFac
    ? fac.normalizeFacilities(
        input.facilities,
        a,
        months,
        a.buildings.map((b) => b.name),
      )
    : [];
  const facOrdered = fac.byPriority(facStates);
  if (hasFac) a.facilities = input.facilities.map((f) => JSON.parse(JSON.stringify(f)));
  const leaseAudits = rentAudit(a.buildings, a.rentPerKwMonth, a.pue, a.capacityBasis);
  const rentalMethods = new Map(
    a.buildings.map((b) => [b.name, rentSchedule({ ...b, _itMW: itMW(b) }, a.rentPerKwMonth)]),
  );
  const hoursInMonth = (m) => {
    const monthIndex = a.calendarStartMonth - 1 + m - 1;
    const year = a.calendarStartYear + Math.floor(monthIndex / 12);
    const zeroMon = ((monthIndex % 12) + 12) % 12;
    return new Date(Date.UTC(year, zeroMon + 1, 0)).getUTCDate() * 24;
  };
  // Physical commissioning and lease commencement are distinct. Each newly energized
  // portion begins its own contractual payment age when physically ready for service.
  // A shared supply tranche is allocated deterministically in building input order;
  // this policy is a screening assumption, NOT a contractual allocation.
  // v25.8-CA P5: after a funding default the sponsor/lenders cannot pay for unfinished buildings.
  // Under fundingDefaultPolicy 'halt' (default) construction of every building not complete by the
  // default month stops, its later capex is not incurred and it never energizes.
  const abandoned = new Set();
  let haltMonth = Infinity;
  const cohortsByBuilding = new Map(a.buildings.map((b) => [b.name, []]));
  const physicalByMonth = [];
  function computePhysical() {
    physicalByMonth.length = 0;
    for (const b of a.buildings) cohortsByBuilding.set(b.name, []);
    const lastPhysical = new Map(a.buildings.map((b) => [b.name, 0]));
    // v25.8-CA P2: shared supply, once allocated to an energized building, stays allocated (no
    // silent re-allocation that would de-energize a building already in service). Only newly
    // released shared MW is offered to ready buildings, in input order.
    const sharedHeld = new Map(a.buildings.map((b) => [b.name, 0]));
    for (let month = 0; month <= months + 12; month++) {
      const sharedTotal = a.powerTranches
        .filter((t) => !t.building && t.month + a.delayMonths <= month)
        .reduce((v, t) => v + t._itMW, 0);
      for (const b of a.buildings) {
        const ded = a.powerTranches
          .filter((t) => t.building === b.name && t.month + a.delayMonths <= month)
          .reduce((v, t) => v + t._itMW, 0);
        sharedHeld.set(b.name, Math.min(sharedHeld.get(b.name), Math.max(0, itMW(b) - ded)));
      }
      let shared = Math.max(0, sharedTotal - [...sharedHeld.values()].reduce((x, y) => x + y, 0));
      let grossR = 0,
        credits = 0,
        rentedMw = 0,
        physicalMw = 0;
      const rentedByBuilding = {},
        grossByBuilding = {},
        leaseByBuilding = {};
      for (const b of a.buildings) {
        const mw = itMW(b),
          done = b.constructionStart + b.constructionMonths - 1;
        const ready = abandoned.has(b.name)
          ? Infinity
          : Math.max(done + 1, b.leaseMonth + a.delayMonths, b.powerMonth + a.delayMonths);
        let delivered = 0;
        if (month >= ready) {
          if (a.powerTranches.length) {
            const dedicated = a.powerTranches
              .filter((t) => t.building === b.name && t.month + a.delayMonths <= month)
              .reduce((v, t) => v + t._itMW, 0);
            const portion = Math.min(Math.max(0, mw - dedicated - sharedHeld.get(b.name)), shared);
            shared -= portion;
            sharedHeld.set(b.name, sharedHeld.get(b.name) + portion);
            delivered = Math.min(mw, dedicated + sharedHeld.get(b.name));
          } else delivered = mw;
        }
        physicalMw += delivered;
        const previous = lastPhysical.get(b.name);
        if (delivered + 1e-8 < previous)
          throw Error('Physical supply allocation fell for ' + b.name + '; explicit curtailment required');
        if (delivered > previous + 1e-9)
          cohortsByBuilding.get(b.name).push({ mw: delivered - previous, start: month });
        lastPhysical.set(b.name, delivered);
        const term = b.leaseTermMonths ?? 180;
        let buildingRentedMW = 0,
          buildingGross = 0,
          buildingCredits = 0;
        const rentMethod = rentalMethods.get(b.name);
        for (const cohort of cohortsByBuilding.get(b.name)) {
          const age = month - cohort.start;
          if (age < 0) continue;
          if (age >= term) {
            // v25.8-CA2: expected-value renewal. Renewed share keeps paying (last contract rent x renewalRentPct,
            // escalating) for renewalTermMonths; the rest is vacant (no rent, no energy).
            if (a.leaseExpiryPolicy === 'renew' && age < term + a.renewalTermMonths) {
              const p = a.renewalProbabilityPct / 100,
                esc = (b.rentEscalatorPct ?? 2.5) / 100;
              rentedMw += cohort.mw * p;
              buildingRentedMW += cohort.mw * p;
              const renewalRent =
                ((((rentMethod.monthly(term - 1) * cohort.mw) / mw) * a.renewalRentPct) / 100) *
                Math.pow(1 + esc, Math.floor((age - term) / 12)) *
                p;
              grossR += renewalRent;
              buildingGross += renewalRent;
            }
            continue;
          }
          rentedMw += cohort.mw;
          buildingRentedMW += cohort.mw;
          const rental = (rentMethod.monthly(age) * cohort.mw) / mw;
          grossR += rental;
          buildingGross += rental;
          if (age < (b.tenantCreditMonths ?? a.tenantCreditMonths)) {
            const credit = (rental * (b.tenantRentCreditPct ?? a.tenantRentCreditPct)) / 100;
            credits += credit;
            buildingCredits += credit;
          }
        }
        rentedByBuilding[b.name] = buildingRentedMW;
        // v25.9: per-building rent tracking for facility CFADS allocation (spec §7); not emitted in rows.
        grossByBuilding[b.name] = buildingGross;
        leaseByBuilding[b.name] = buildingGross - buildingCredits;
      }
      physicalByMonth.push({
        grossRevenue: grossR,
        rentCredits: credits,
        onlineMW: rentedMw,
        availableMW: physicalMw,
        rentedByBuilding,
        grossByBuilding,
        leaseByBuilding,
      });
    }
  }
  computePhysical();
  // Independent of debt accounting. This also underpins forward CFADS refinancing.
  function operations(m) {
    let capex = 0,
      tenantFundedCapex = 0;
    for (const b of a.buildings) {
      const mw = itMW(b),
        done = b.constructionStart + b.constructionMonths - 1;
      const gross =
        m >= b.constructionStart && m <= done && !(abandoned.has(b.name) && m >= haltMonth)
          ? (mw * a.constructionCostMW * (1 + a.overrunPct / 100)) / b.constructionMonths
          : 0;
      capex += gross;
      tenantFundedCapex += (gross * (b.tenantCapexPct ?? a.tenantCapexPct)) / 100;
    }
    const physical = physicalByMonth[Math.max(0, Math.min(physicalByMonth.length - 1, m))];
    const { grossRevenue, rentCredits, onlineMW, availableMW } = physical;
    // The contracted lease value excludes power reimbursements. Preserve the gross cost
    // for dispatch/economic comparison, but bill it to the correct party in CFADS.
    // 'tenant_direct': tenant pays designated share outside landlord P&L;
    // 'reimbursed': landlord pays utility and invoices the same share at cost, no markup.
    const leaseRevenue = grossRevenue - rentCredits;
    let grossEnergy = 0,
      energy = 0,
      powerReimbursement = 0,
      tenantDirectPower = 0;
    for (const b of a.buildings) {
      const mw = physical.rentedByBuilding[b.name] || 0;
      const cost = (mw * a.pue * hoursInMonth(m) * a.powerCostMWh * (1 + a.energyShockPct / 100)) / 1e6;
      grossEnergy += cost;
      const responsibility = b.powerResponsibility ?? a.powerResponsibility;
      const passThrough = (b.powerPassThroughPct ?? a.powerPassThroughPct) / 100;
      if (responsibility === 'tenant_direct') {
        tenantDirectPower += cost * passThrough;
        energy += cost * (1 - passThrough);
      } else if (responsibility === 'reimbursed') {
        energy += cost;
        powerReimbursement += cost * passThrough;
      } else energy += cost;
    }
    const revenue = leaseRevenue + powerReimbursement;
    // General operating expenses are not a percentage of pass-through energy billings.
    const opex = (leaseRevenue * a.otherOpexPct) / 100 + (onlineMW ? a.fixedOpexM : 0);
    const ebitda = revenue - energy - opex;
    const cashTaxes = (Math.max(0, ebitda) * a.cashTaxRatePct) / 100; // Proxy, not a tax-return calculation.
    const maintenanceCapex = (onlineMW * a.maintenanceCapexMWYearM) / 12;
    const workingCapitalBalance =
      (Math.max(0, leaseRevenue) * a.workingCapitalDays) / 30 +
      (Math.max(0, powerReimbursement) * a.powerReimbursementLagDays) / 30;
    return {
      month: m,
      capex,
      tenantFundedCapex,
      grossRevenue,
      rentCredits,
      leaseRevenue,
      onlineMW,
      availableMW,
      revenue,
      grossEnergy,
      energy,
      powerReimbursement,
      tenantDirectPower,
      netEnergyCost: energy - powerReimbursement,
      opex,
      ebitda,
      cashTaxes,
      maintenanceCapex,
      workingCapitalBalance,
    };
  }
  function cfadsMonth(m) {
    const x = operations(m),
      prior = operations(m - 1);
    return (
      x.ebitda - x.cashTaxes - x.maintenanceCapex - (x.workingCapitalBalance - prior.workingCapitalBalance)
    );
  }
  let exitShareUsed = 1,
    refiAmortN = Math.max(1, Math.round(a.refinanceAmortMonths));
  function waltMonths(m) {
    let w = 0,
      t = 0;
    for (const b of a.buildings) {
      if (abandoned.has(b.name)) continue;
      const ready = Math.max(
        b.constructionStart + b.constructionMonths,
        b.leaseMonth + a.delayMonths,
        b.powerMonth + a.delayMonths,
      );
      const end = ready + (b.leaseTermMonths ?? 180);
      w += itMW(b) * Math.max(0, end - m);
      t += itMW(b);
    }
    return t ? w / t : 0;
  }
  const flows = [-a.initialCash],
    rows = [];
  let cash = a.initialCash,
    reserve = 0,
    debt = 0,
    mezz = 0,
    totalTenantReceivable = 0,
    totalSponsor = a.initialCash,
    draws = 0,
    mezzDraws = 0,
    principalPaid = 0,
    interestTotal = 0,
    feeTotal = 0,
    peakDebt = 0,
    firstDebtMonth = null,
    maturityMonth = null,
    refiOccurred = false,
    constructionFacilityClosed = false,
    defaulted = false,
    liquidityBreaches = [],
    covenantBreaches = [],
    refinanceSizing = null,
    fundingDefault = false,
    unpaidDebtAtExitM = 0;
  const initialDebtRate = (a.rate + a.rateShockPct) / 1200;
  // Optional credit-wide stress: original shocks only construction senior debt.
  // This opt-in extends the same bps shock to mezzanine and refinancing without changing legacy results.
  const effectiveRefinanceRatePct = a.refinanceRatePct + (a.rateShockAllFacilities ? a.rateShockPct : 0);
  const effectiveMezzRatePct = a.mezzRatePct + (a.rateShockAllFacilities ? a.rateShockPct : 0);
  const sponsorRemaining = () =>
    a.sponsorCommitmentM === null ? Infinity : Math.max(0, a.sponsorCommitmentM - totalSponsor);
  const drawSponsor = (needed) => {
    const actual = Math.min(Math.max(0, needed), sponsorRemaining());
    totalSponsor += actual;
    return actual;
  };
  const buildingByName = new Map(a.buildings.map((b) => [b.name, b]));
  const facCtx = {
    months,
    physicalByMonth,
    cohortsByBuilding,
    itMW: (name) => itMW(buildingByName.get(name)),
    creditMonths: (name) => buildingByName.get(name).tenantCreditMonths ?? a.tenantCreditMonths ?? 0,
  };
  const facilityPaymentShortfallMonths = [];
  for (let m = 1; m <= months; m++) {
    const op = operations(m),
      prev = operations(m - 1);
    const {
      capex,
      tenantFundedCapex,
      grossRevenue,
      rentCredits,
      leaseRevenue,
      onlineMW,
      availableMW,
      revenue,
      grossEnergy,
      energy,
      powerReimbursement,
      tenantDirectPower,
      netEnergyCost,
      opex,
      ebitda,
      cashTaxes,
      maintenanceCapex,
    } = op;
    const tenantCashReceipt =
      m > a.tenantFundingLagMonths ? operations(m - a.tenantFundingLagMonths).tenantFundedCapex : 0;
    totalTenantReceivable += tenantFundedCapex - tenantCashReceipt;
    const workingCapitalChange = op.workingCapitalBalance - prev.workingCapitalBalance;
    const cfads = ebitda - cashTaxes - maintenanceCapex - workingCapitalChange;
    // v25.9 facility issuance, accrual, interest and principal (spec §2-§4, §7 allocation and tests).
    let notesProceeds = 0,
      notesFees = 0,
      facilityDebtServiceDue = 0;
    if (hasFac) {
      const physical = physicalByMonth[Math.max(0, Math.min(physicalByMonth.length - 1, m))];
      let leaseAll = 0;
      for (const b of a.buildings) leaseAll += physical.leaseByBuilding[b.name] || 0;
      for (const f of facOrdered) {
        fac.updateEvents(f, facCtx, m);
        const r = fac.monthFlows(f, m);
        let leaseF = 0;
        for (const name of f.buildings) leaseF += physical.leaseByBuilding[name] || 0;
        const share = leaseAll > 0 ? (cfads * leaseF) / leaseAll : 0;
        f.shares[m] = share;
        r.cfadsShare = share;
        fac.dscrTest(f, m);
        notesProceeds += r.proceeds;
        notesFees += r.fees;
        facilityDebtServiceDue += r.interestPaid + r.principalPaid;
      }
    }
    const openingSeniorDebt = debt,
      openingMezzDebt = mezz,
      openingReserve = reserve,
      openingCash = cash;
    const sponsorEligibleCapex = capex - tenantFundedCapex;
    const seniorDraw = constructionFacilityClosed || defaulted ? 0 : (sponsorEligibleCapex * a.ltc) / 100;
    const mezzDraw =
      constructionFacilityClosed || defaulted ? 0 : (sponsorEligibleCapex * a.mezzLtcPct) / 100;
    const fee = (seniorDraw * a.debtFee) / 100 + (mezzDraw * a.mezzFeePct) / 100;
    debt += seniorDraw;
    mezz += mezzDraw;
    draws += seniorDraw;
    mezzDraws += mezzDraw;
    feeTotal += fee;
    if (seniorDraw + mezzDraw > 0 && firstDebtMonth === null) {
      firstDebtMonth = m;
      maturityMonth = firstDebtMonth + Math.round(a.termMonths) - 1;
    }
    const seniorInterest = debt * (refiOccurred ? effectiveRefinanceRatePct / 1200 : initialDebtRate),
      mezzInterest = (mezz * effectiveMezzRatePct) / 1200;
    const interest = seniorInterest + mezzInterest;
    interestTotal += interest;
    const constructing = a.buildings.some(
      (b) =>
        m >= b.constructionStart &&
        m < b.constructionStart + b.constructionMonths &&
        !(abandoned.has(b.name) && m >= haltMonth),
    );
    const capitalizedInterest = !refiOccurred && constructing ? interest : 0,
      cashInterest = interest - capitalizedInterest;
    const capSenior = capitalizedInterest * (interest ? seniorInterest / interest : 1),
      capMezz = capitalizedInterest - capSenior;
    debt += capSenior;
    mezz += capMezz;
    let principal = 0,
      mezzPrincipal = 0,
      refinanceProceeds = 0,
      refinanceFee = 0,
      maturityShortfall = 0,
      sweepPrincipal = 0;
    let forward12CfadsM = null,
      forward12NoiM = null;
    if (maturityMonth !== null && m === maturityMonth && !refiOccurred) {
      const oldDebt = debt,
        oldMezz = mezz;
      if (defaulted) {
        maturityShortfall = oldDebt + oldMezz;
        fundingDefault = true;
      } else if (a.loanMaturityMode === 'refinance') {
        forward12CfadsM = 0;
        forward12NoiM = 0;
        for (let j = 1; j <= 12; j++) {
          const f = operations(m + j);
          forward12CfadsM += cfadsMonth(m + j);
          forward12NoiM += f.ebitda - f.maintenanceCapex;
        }
        const r = effectiveRefinanceRatePct / 1200;
        let n = Math.max(1, Math.round(a.refinanceAmortMonths));
        // v25.8-CA2: lease-tail tenor. Amortize within the MW-weighted remaining contracted lease term
        // (initial terms only, no renewals) less a tail buffer; floor at minRefinanceAmortMonths.
        const walt = waltMonths(m);
        if (a.refinanceTenorPolicy === 'leaseTail')
          n = Math.max(
            Math.round(a.minRefinanceAmortMonths),
            Math.min(n, Math.floor(walt - a.leaseTailBufferMonths)),
          );
        refiAmortN = n;
        const paymentPerDollar = r === 0 ? 1 / n : r / (1 - Math.pow(1 + r, -n));
        const ltvLimit = (a.refinanceValueM * a.refinanceLtvPct) / 100;
        const dscrLimit =
          Math.max(0, forward12CfadsM) / Math.max(0.01, a.refinanceDscrMin) / (12 * paymentPerDollar);
        const yieldLimit =
          a.debtYieldMinPct > 0 ? Math.max(0, forward12NoiM) / (a.debtYieldMinPct / 100) : Infinity;
        const newDebt = Math.max(0, Math.min(ltvLimit, dscrLimit, yieldLimit));
        refinanceSizing = {
          ltvLimit,
          dscrLimit,
          yieldLimit,
          selected: newDebt,
          forward12CfadsM,
          forward12NoiM,
          amortMonths: n,
          remainingLeaseTermMonths: walt,
          binding: newDebt === ltvLimit ? 'LTV' : newDebt === dscrLimit ? 'DSCR' : 'debt yield',
        };
        const requiredFee = (newDebt * a.refinanceFeePct) / 100;
        // Refinance may not close if cash and enforceable sponsor commitment cannot pay the shortfall.
        const beforePayoff =
          cash + cfads + seniorDraw + mezzDraw + tenantCashReceipt - capex - fee - cashInterest;
        const availableForPayoff = Math.max(0, beforePayoff - a.minLiquidity) + sponsorRemaining();
        const gap = Math.max(0, oldDebt + oldMezz + requiredFee - newDebt - availableForPayoff);
        if (gap > 1e-8) {
          defaulted = true;
          maturityShortfall = gap;
          fundingDefault = true;
          refinanceSizing.failed = true;
        } else {
          refinanceProceeds = newDebt;
          refinanceFee = requiredFee;
          feeTotal += refinanceFee;
          principal = oldDebt;
          mezzPrincipal = oldMezz;
          debt = newDebt;
          mezz = 0;
          refiOccurred = true;
          constructionFacilityClosed = true;
        }
      } else if (a.loanMaturityMode === 'equity') {
        const beforePayoff =
          cash + cfads + seniorDraw + mezzDraw + tenantCashReceipt - capex - fee - cashInterest;
        const gap = Math.max(
          0,
          oldDebt + oldMezz - (Math.max(0, beforePayoff - a.minLiquidity) + sponsorRemaining()),
        );
        if (gap > 1e-8) {
          defaulted = true;
          maturityShortfall = gap;
          fundingDefault = true;
        } else {
          principal = oldDebt;
          mezzPrincipal = oldMezz;
          debt = 0;
          mezz = 0;
          constructionFacilityClosed = true;
        }
      } else {
        defaulted = true;
        maturityShortfall = oldDebt + oldMezz;
      }
    } else if (refiOccurred && m > maturityMonth) {
      // v25.8-CA P1: the refinanced loan is SIZED on a level (annuity) payment, so it must be REPAID on
      // that same annuity. v25.8 repaid level principal (balance/remaining), whose first payments are
      // ~29% above the sized payment at 7%/240m, so a DSCR-sized refinancing breached on day one.
      const left = Math.max(1, refiAmortN - (m - maturityMonth - 1)),
        rr = effectiveRefinanceRatePct / 1200;
      const payment = rr === 0 ? debt / left : (debt * rr) / (1 - Math.pow(1 + rr, -left));
      principal = left === 1 ? debt : Math.min(debt, Math.max(0, payment - seniorInterest));
      debt -= principal;
    }
    principalPaid += principal + mezzPrincipal;
    // DSCR excludes mandatory maturity balloon, refinancing transactions and voluntary sweeps.
    const scheduledDebtService = cashInterest + (m === maturityMonth ? 0 : principal + mezzPrincipal);
    const dscr = scheduledDebtService > 0 ? cfads / scheduledDebtService : null;
    const loanSources = seniorDraw + mezzDraw + refinanceProceeds;
    const operatingCash = cfads;
    let uses = capex + fee + refinanceFee + cashInterest + principal + mezzPrincipal;
    if (hasFac) uses = uses + notesFees + facilityDebtServiceDue;
    const preFundingCash = hasFac
      ? cash + operatingCash + loanSources + tenantCashReceipt + notesProceeds - uses
      : cash + operatingCash + loanSources + tenantCashReceipt - uses;
    // v25.9 §5.4: facility DSRAs are drawn (priority order) before sponsor support.
    let facilityDsraDraw = 0;
    if (hasFac && preFundingCash < a.minLiquidity) {
      let remaining = a.minLiquidity - preFundingCash;
      for (const f of facOrdered) {
        const r = f.cur;
        const d = Math.min(f.dsra, r.interestPaid + r.principalPaid, remaining);
        if (d > 0) {
          f.dsra -= d;
          r.dsraDraw += d;
          r.dsraMovement -= d;
          remaining -= d;
          facilityDsraDraw += d;
        }
      }
    }
    let sponsorContribution = hasFac
      ? drawSponsor(Math.max(0, a.minLiquidity - preFundingCash - facilityDsraDraw))
      : drawSponsor(Math.max(0, a.minLiquidity - preFundingCash));
    cash = hasFac
      ? preFundingCash + facilityDsraDraw + sponsorContribution
      : preFundingCash + sponsorContribution;
    const unfundedGapM = Math.max(0, a.minLiquidity - cash);
    if (unfundedGapM > 1e-8) {
      defaulted = true;
      fundingDefault = true;
    }
    // v25.9 §5.6: facility DSRA funding before the base reserve (cash above minLiquidity, then sponsor).
    let facilityDsraDeficient = false;
    if (hasFac) {
      if (unfundedGapM > 1e-8 && facilityDebtServiceDue > 0) facilityPaymentShortfallMonths.push(m);
      for (const f of facOrdered) {
        if (m < f.issueMonth) continue;
        const r = f.cur;
        const Q = fac.dsraRequirement(f, m);
        r.dsraRequired = Q;
        if (f.dsra < Q) {
          const fromCash = Math.min(Q - f.dsra, Math.max(0, cash - a.minLiquidity));
          if (fromCash > 0) {
            cash -= fromCash;
            f.dsra += fromCash;
            r.dsraMovement += fromCash;
          }
          if (Q - f.dsra > 1e-8) {
            const topup = drawSponsor(Q - f.dsra);
            sponsorContribution += topup;
            f.dsra += topup;
            r.dsraMovement += topup;
          }
          r.dsraDeficiency = Math.max(0, Q - f.dsra);
          if (r.dsraDeficiency > 1e-8) {
            f.dsraDeficiencyMonths.push(m);
            facilityDsraDeficient = true;
          }
        } else if (f.dsra > Q) {
          const release = f.dsra - Q;
          f.dsra -= release;
          cash += release;
          r.dsraMovement -= release;
        }
      }
    }
    const projectedRefiPayment =
      refiOccurred && debt > 0
        ? effectiveRefinanceRatePct === 0
          ? debt / Math.max(1, refiAmortN - (m - maturityMonth))
          : (debt * (effectiveRefinanceRatePct / 1200)) /
            (1 -
              Math.pow(1 + effectiveRefinanceRatePct / 1200, -Math.max(1, refiAmortN - (m - maturityMonth))))
        : 0;
    const dsraTarget = refiOccurred ? a.dsraMonths * projectedRefiPayment : 0;
    // Base restricted reserve and DSRA are distinct obligations, not interchangeable.
    const restrictedTarget = a.reserveTargetM + dsraTarget;
    let reserveMovement = 0;
    if (reserve < restrictedTarget) {
      reserveMovement = Math.min(restrictedTarget - reserve, Math.max(0, cash - a.minLiquidity));
      cash -= reserveMovement;
      reserve += reserveMovement;
    } else if (reserve > restrictedTarget) {
      const release = reserve - restrictedTarget;
      reserveMovement = -release;
      reserve -= release;
      cash += release;
    }
    const reserveDeficiency = Math.max(0, restrictedTarget - reserve);
    if (reserveDeficiency > 1e-8) {
      const topup = drawSponsor(reserveDeficiency);
      sponsorContribution += topup;
      cash += topup;
      const credit = Math.min(topup, reserveDeficiency);
      cash -= credit;
      reserve += credit;
      reserveMovement += credit;
    }
    const finalReserveDeficiency = Math.max(0, restrictedTarget - reserve);
    const debtOutstanding = debt + mezz > 1e-9;
    const inBreach = dscr !== null && dscr < a.dscrCovenant;
    // v25.9 §5.8: facility lock-up (DSRA deficiency, DSCR test in force below lockupDscr, unfunded gap).
    let facilityLockup = false,
      facilityConstructionLockup = false;
    if (hasFac) {
      for (const f of facStates) {
        // Amendment 1 AM3: distributions locked until every collateral building has paid rent.
        const construction = f.bal > 0 && f.L === null;
        facilityConstructionLockup = facilityConstructionLockup || construction;
        const own =
          (f.cur.dsraDeficiency > 1e-8 && m >= f.issueMonth) || fac.dscrLocked(f, m) || construction;
        if (own) f.lockupMonths.push(m);
        facilityLockup = facilityLockup || own;
      }
      facilityLockup = facilityLockup || facilityDsraDeficient || unfundedGapM > 1e-8;
    }
    const locked =
      finalReserveDeficiency > 1e-8 ||
      defaulted ||
      (a.lockDistributionsOnBreach !== false && inBreach) ||
      (debtOutstanding && (dscr === null || dscr < a.distributionDscrMin)) ||
      facilityLockup;
    if (debtOutstanding && !defaulted && a.cashSweepPct > 0) {
      const excess = Math.max(0, cash - a.minLiquidity);
      sweepPrincipal = Math.min(debt, (excess * a.cashSweepPct) / 100);
      cash -= sweepPrincipal;
      debt -= sweepPrincipal;
      principal += sweepPrincipal;
      principalPaid += sweepPrincipal;
    }
    let distribution = 0;
    if (!locked && a.distributionPolicy === 'excess' && m < months) {
      distribution = Math.max(0, cash - a.minLiquidity);
      cash -= distribution;
    }
    let facilityExitPayoff = 0,
      facilityUnpaidAtExit = 0;
    let terminalProceeds = 0,
      exitDebtPayoff = 0,
      exitCollections = 0,
      exitTenantReceivableCollection = 0,
      exitWorkingCapitalCollection = 0;
    if (m === months) {
      // v25.8-CA P5: an abandoned campus cannot be sold at the full-campus exit value; scale by completed IT MW.
      const totalIt = a.buildings.reduce((v, b) => v + itMW(b), 0),
        liveIt = a.buildings.filter((b) => !abandoned.has(b.name)).reduce((v, b) => v + itMW(b), 0);
      let exitShare = abandoned.size ? liveIt / totalIt : 1;
      // v25.8-CA2: 'contracted' exit values leased MW at full value and vacant/expired MW at vacantValuePct.
      if (a.exitValuePolicy === 'contracted') {
        const leased = Math.min(liveIt, physicalByMonth[m].onlineMW);
        exitShare = (leased + ((liveIt - leased) * a.vacantValuePct) / 100) / totalIt;
      }
      exitShareUsed = exitShare;
      terminalProceeds = a.exitValueM * (1 - a.exitCostPct / 100) * exitShare;
      // Collections are separate from the assumed property sale; default 0 prevents automatic double-counting.
      // These amounts require confirmation that exitValueM excludes working capital and receivables.
      exitTenantReceivableCollection = (totalTenantReceivable * a.exitTenantReceivableRecoveryPct) / 100;
      exitWorkingCapitalCollection =
        (Math.max(0, op.workingCapitalBalance) * a.exitWorkingCapitalRecoveryPct) / 100;
      exitCollections = exitTenantReceivableCollection + exitWorkingCapitalCollection;
      totalTenantReceivable = Math.max(0, totalTenantReceivable - exitTenantReceivableCollection);
      if (hasFac) {
        // v25.9 §5.10: release every facility DSRA into available cash, then pay facilities in priority order.
        for (const f of facOrdered) {
          if (f.dsra !== 0) {
            const rel = f.dsra;
            f.dsra = 0;
            cash += rel;
            f.cur.dsraMovement -= rel;
          }
        }
        facilityExitPayoff = fac.exitPayoff(facOrdered, cash + terminalProceeds + exitCollections + reserve);
        cash -= facilityExitPayoff;
        for (const f of facStates) facilityUnpaidAtExit += f.bal + f.accrued;
      }
      const availableForDebt = Math.max(0, cash + terminalProceeds + exitCollections + reserve);
      exitDebtPayoff = Math.min(debt + mezz, availableForDebt);
      const paySenior = Math.min(debt, exitDebtPayoff),
        payMezz = exitDebtPayoff - paySenior;
      debt -= paySenior;
      mezz -= payMezz;
      principal += paySenior;
      mezzPrincipal += payMezz;
      principalPaid += exitDebtPayoff;
      unpaidDebtAtExitM = hasFac ? debt + mezz + facilityUnpaidAtExit : debt + mezz;
      if (unpaidDebtAtExitM > 1e-8) defaulted = true;
      cash += terminalProceeds + exitCollections - exitDebtPayoff + reserve;
      reserveMovement -= reserve;
      reserve = 0;
      if (cash > 0 && unpaidDebtAtExitM < 1e-8 && !defaulted) {
        distribution += cash;
        cash = 0;
      }
    }
    const shortfall = preFundingCash < a.minLiquidity,
      covenant = dscr !== null && m !== maturityMonth && dscr < a.dscrCovenant;
    if (shortfall) liquidityBreaches.push(m);
    if (covenant) covenantBreaches.push(m);
    uses += sweepPrincipal;
    if (fundingDefault && a.fundingDefaultPolicy === 'halt' && haltMonth === Infinity) {
      haltMonth = m + 1;
      for (const b of a.buildings)
        if (b.constructionStart + b.constructionMonths - 1 > m) abandoned.add(b.name);
      if (abandoned.size) computePhysical();
    }
    flows.push(distribution - sponsorContribution);
    peakDebt = Math.max(peakDebt, debt + mezz, refinanceProceeds);
    const debtResidual = debt - (openingSeniorDebt + seniorDraw + capSenior + refinanceProceeds - principal);
    const mezzResidual = mezz - (openingMezzDebt + mezzDraw + capMezz - mezzPrincipal);
    const reserveResidual = reserve - openingReserve - reserveMovement;
    const baseSourcesUsesResidual =
      openingCash +
      operatingCash +
      loanSources +
      tenantCashReceipt +
      sponsorContribution +
      terminalProceeds +
      exitCollections -
      reserveMovement -
      uses -
      exitDebtPayoff -
      distribution -
      cash;
    let facilityRow = null;
    if (hasFac) {
      facilityRow = {
        notesProceeds,
        notesFees,
        facilityInterestAccrued: 0,
        facilityInterestPaid: 0,
        facilityPrincipalPaid: 0,
        facilityDebtService: 0,
        facilityBalance: 0,
        facilityAccruedInterest: 0,
        facilityDsra: 0,
        facilityDsraMovement: 0,
        facilityDsraDraw,
        facilityLockup,
        facilityConstructionLockup,
      };
      for (const f of facOrdered) {
        const r = f.cur;
        r.dsraBalance = f.dsra;
        facilityRow.facilityInterestAccrued += r.accrual;
        facilityRow.facilityInterestPaid += r.interestPaid;
        facilityRow.facilityPrincipalPaid += r.principalPaid;
        facilityRow.facilityDebtService += r.interestPaid + r.principalPaid;
        facilityRow.facilityBalance += f.bal;
        facilityRow.facilityAccruedInterest += f.accrued;
        facilityRow.facilityDsra += f.dsra;
        facilityRow.facilityDsraMovement += r.dsraMovement;
        if (m >= f.issueMonth) f.schedule.push(r);
      }
    }
    const sourcesUsesResidual = hasFac
      ? baseSourcesUsesResidual + notesProceeds - facilityRow.facilityDsraMovement - facilityExitPayoff
      : baseSourcesUsesResidual;
    const row = {
      month: m,
      onlineMW,
      availableMW,
      grossRevenue,
      rentCredits,
      leaseRevenue,
      revenue,
      grossEnergy,
      energy,
      powerReimbursement,
      tenantDirectPower,
      netEnergyCost,
      opex,
      ebitda,
      cashTaxes,
      maintenanceCapex,
      workingCapitalBalance: op.workingCapitalBalance,
      workingCapitalChange,
      cfads,
      capex,
      tenantFundedCapex,
      tenantCashReceipt,
      tenantFundingReceivable: totalTenantReceivable,
      draw: seniorDraw,
      mezzDraw,
      fee,
      refinanceFee,
      interest,
      capitalizedInterest,
      cashInterest,
      principal,
      mezzPrincipal,
      debt,
      mezzDebt: mezz,
      debtService: scheduledDebtService,
      scheduledDebtService,
      dscr,
      breach: covenant,
      liquidityBreach: shortfall,
      openingCash,
      loanSources,
      uses,
      operatingCash,
      preFundingCash,
      sponsorContribution,
      equityContribution: sponsorContribution,
      distribution,
      netEquity: distribution - sponsorContribution,
      cash,
      reserve,
      reserveMovement,
      refinanceProceeds,
      sweepPrincipal,
      maturityShortfall,
      terminalProceeds,
      exitCollections,
      exitTenantReceivableCollection,
      exitWorkingCapitalCollection,
      exitDebtPayoff,
      unpaidDebtAtExitM,
      unfundedGapM,
      sourcesUsesResidual,
      debtResidual,
      mezzResidual,
      reserveResidual,
      reserveDeficiency: finalReserveDeficiency,
      restrictedTarget,
      dsraTarget,
      openingSeniorDebt,
      openingMezzDebt,
      openingReserve,
      forward12CfadsM,
      forward12NoiM,
    };
    if (facilityRow) Object.assign(row, facilityRow);
    rows.push(row);
  }
  const npv = flows.reduce((sum, v, i) => sum + v / (1 + a.discount / 100) ** (i / 12), 0),
    equityOut = rows.reduce((sum, x) => sum + x.distribution, 0),
    dscrs = rows.map((r) => r.dscr).filter(Number.isFinite);
  // Independent red-team assurance: an arithmetic answer is NOT a financeable investment case.
  // A lease-tail mismatch, covenant breach or unrestricted sponsor funding must remain visible
  // even when the modeled equity NPV is positive. These do not authenticate legal terms.
  const modelEnd = months;
  const allCohorts = [...cohortsByBuilding.values()].flat();
  const lastLeaseEnd = allCohorts.length
    ? Math.max(
        ...allCohorts.map(
          (x) =>
            x.start -
            1 +
            Math.max(
              1,
              ...a.buildings
                .filter((b) => cohortsByBuilding.get(b.name).includes(x))
                .map((b) => b.leaseTermMonths ?? 180),
            ),
        ),
      )
    : null;
  const creditWarnings = [];
  if (a.amortMonths !== d.amortMonths)
    creditWarnings.push(
      'amortMonths is not implemented for construction debt; this override has no effect (interest-only construction debt)',
    );
  if (a.dsraReleaseAtExit !== true)
    creditWarnings.push(
      'dsraReleaseAtExit=false is unsupported; current terminal waterfall releases restricted reserves',
    );
  if (defaulted)
    creditWarnings.push(
      'Modeled financing default; outputs are downside sensitivities, not performing-project valuations',
    );
  if (covenantBreaches.length)
    creditWarnings.push(
      covenantBreaches.length +
        ' modeled DSCR covenant breach month(s); debt service is not covenant-compliant',
    );
  if (a.sponsorCommitmentM === null)
    creditWarnings.push('Sponsor funding is uncapped and not evidenced; this is a sensitivity assumption');
  if (leaseAudits.some((x) => !x.reconciled))
    creditWarnings.push('Contractual revenue targets are missing or do not reconcile');
  if (leaseAudits.some((x) => !x.hasDocumentReference))
    creditWarnings.push('At least one lease has no source reference');
  if (lastLeaseEnd !== null && lastLeaseEnd < modelEnd && a.exitValueM > 0 && a.exitValuePolicy === 'fixed')
    creditWarnings.push(
      'Lease expiry precedes modeled exit while positive uncontracted asset exit value remains',
    );
  if (rows.at(-1).onlineMW < 1e-7 && a.exitValueM > 0 && a.exitValuePolicy === 'fixed')
    creditWarnings.push(
      'Positive terminal sale proceeds assumed despite zero contracted operating MW at exit',
    );
  if (rows.at(-1).unfundedGapM > 1e-8)
    creditWarnings.push('Unfunded cash or unpaid operating obligations remain at exit');
  if (a.leaseExpiryPolicy === 'renew')
    creditWarnings.push(
      'Renewal probability, renewal rent and renewal duration are synthetic assumptions, not signed extensions',
    );
  if (a.exitValuePolicy === 'contracted')
    creditWarnings.push('Vacant-MW terminal valuation is a scenario assumption, not an appraisal');
  if (
    a.refinanceTenorPolicy === 'leaseTail' &&
    refinanceSizing &&
    refinanceSizing.remainingLeaseTermMonths - a.leaseTailBufferMonths < refinanceSizing.amortMonths
  )
    creditWarnings.push(
      'Minimum refinance tenor exceeds remaining contracted lease term less buffer; cannot treat as lease-tail compliant',
    );
  if (
    a.powerResponsibility !== 'landlord' ||
    a.buildings.some((b) => b.powerResponsibility && b.powerResponsibility !== 'landlord')
  )
    creditWarnings.push(
      'Power cost responsibility is modeled from disclosed arrangement or scenario; pass-through billing and timing require lease verification',
    );
  creditWarnings.push(
    'Fixed-rate transaction notes, utility service rights and lender-specific cash waterfalls are not contract-integrated',
  );
  const facilitySummaries = facStates.map(fac.facilitySummary);
  if (hasFac) {
    for (const f of facilitySummaries) creditWarnings.push(...f.warnings);
    creditWarnings.push(fac.POOL_WARNING, fac.ARREARS_WARNING);
  }
  // v25.9.0-risk1: facility DSCR tests below a facility's lock-up threshold are credit failures. They must
  // block screening readiness exactly like generic covenant breaches (a case that cannot service its
  // notes must never look better than one with generic debt). Facilities-absent output is unchanged.
  const facilityDscrBreachMonths = [];
  if (hasFac) {
    facStates.forEach((f) => {
      const low = f.dscrTests.filter((t) => t.dscr !== null && t.dscr < f.lockupDscr);
      if (low.length) {
        low.forEach((t) => facilityDscrBreachMonths.push(t.month));
        creditWarnings.push(
          'FACILITY ' +
            f.id +
            ': ' +
            low.length +
            ' DSCR test(s) below lock-up ' +
            f.lockupDscr +
            'x (min ' +
            Math.min(...low.map((t) => t.dscr)).toFixed(2) +
            'x); debt service is not covered',
        );
      }
    });
    facilityDscrBreachMonths.sort((x, y) => x - y);
  }
  const screeningReadiness =
    defaulted || covenantBreaches.length > 0 || facilityDscrBreachMonths.length > 0
      ? 'BLOCKED — not a performing credit case'
      : 'CONDITIONAL — scenario screening only';
  const summary = {
    financeabilityStatus: defaulted
      ? fundingDefault
        ? 'FUNDING DEFAULT — sponsor limit or refinance gap'
        : 'DEFAULT — financing assumptions not performing'
      : a.sponsorCommitmentM === null
        ? 'UNVERIFIED SPONSOR FUNDING — assumption-driven'
        : leaseAudits.some((x) => !x.reconciled)
          ? 'UNRECONCILED — not validated'
          : covenantBreaches.length
            ? 'COVENANT BREACH — review required'
            : 'MODELED — not externally validated',
    npvM: npv,
    leveredIRR: irr(flows),
    equityMultiple: totalSponsor ? equityOut / totalSponsor : null,
    peakDebtM: peakDebt,
    interestM: interestTotal,
    feesM: feeTotal,
    principalM: principalPaid,
    debtDrawsM: draws,
    mezzDrawsM: mezzDraws,
    equityInvestedM: totalSponsor,
    equityDistributionsM: equityOut,
    minDSCR: dscrs.length ? Math.min(...dscrs) : null,
    minCashM: Math.min(...rows.map((r) => r.cash)),
    breachMonths: covenantBreaches,
    liquidityBreachMonths: liquidityBreaches,
    maturityMonth,
    refinanced: refiOccurred,
    refinanceSizing,
    defaulted,
    fundingDefault,
    unpaidDebtAtExitM,
    endingDebtM: debt + mezz,
    endingReserveM: reserve,
    sweepPrincipalM: rows.reduce((s, r) => s + r.sweepPrincipal, 0),
    sourcesUsesMaxResidual: Math.max(...rows.map((r) => Math.abs(r.sourcesUsesResidual))),
    debtMaxResidual: Math.max(...rows.flatMap((r) => [Math.abs(r.debtResidual), Math.abs(r.mezzResidual)])),
    reserveMaxResidual: Math.max(...rows.map((r) => Math.abs(r.reserveResidual))),
    dsraDeficiencyMonths: rows.filter((r) => r.reserveDeficiency > 1e-8).map((r) => r.month),
    sponsorCommitmentM: a.sponsorCommitmentM,
    sponsorRemainingM:
      a.sponsorCommitmentM === null ? null : Math.max(0, a.sponsorCommitmentM - totalSponsor),
    unfundedMonths: rows.filter((r) => r.unfundedGapM > 1e-8).map((r) => r.month),
    operatingMWh: rows.reduce((sum, r) => sum + r.onlineMW * a.pue * hoursInMonth(r.month), 0),
    grossPowerCostM: rows.reduce((s, r) => s + r.grossEnergy, 0),
    landlordPowerExpenseM: rows.reduce((s, r) => s + r.energy, 0),
    tenantDirectPowerM: rows.reduce((s, r) => s + r.tenantDirectPower, 0),
    powerReimbursementM: rows.reduce((s, r) => s + r.powerReimbursement, 0),
    netLandlordPowerCostM: rows.reduce((s, r) => s + r.netEnergyCost, 0),
    tenantFundingM: rows.reduce((sum, r) => sum + r.tenantFundedCapex, 0),
    rentCreditsM: rows.reduce((sum, r) => sum + r.rentCredits, 0),
    cumulativeCfadsM: rows.reduce((sum, r) => sum + r.cfads, 0),
    leaseAudits,
    screeningReadiness,
    creditWarnings,
    lastLeaseEndMonth: lastLeaseEnd,
    leaseReconciliationBlocked: leaseAudits.some((x) => !x.reconciled),
    financialValidationStatus: 'NOT INDEPENDENTLY VALIDATED',
    fundingDefaultPolicy: a.fundingDefaultPolicy,
    refinanceTenorPolicy: a.refinanceTenorPolicy,
    leaseTailTenorWarning: !!(
      a.refinanceTenorPolicy === 'leaseTail' &&
      refinanceSizing &&
      refinanceSizing.remainingLeaseTermMonths - a.leaseTailBufferMonths < refinanceSizing.amortMonths
    ),
    leaseExpiryPolicy: a.leaseExpiryPolicy,
    exitValuePolicy: a.exitValuePolicy,
    refinanceAmortMonthsUsed: refiOccurred ? refiAmortN : null,
    exitValueShare: exitShareUsed,
    constructionHaltMonth: Number.isFinite(haltMonth) ? haltMonth : null,
    abandonedBuildings: [...abandoned],
    peakUnfundedGapM: Math.max(0, ...rows.map((r) => r.unfundedGapM)),
    residualCashRetainedAtExitM: rows.at(-1).cash,
    uncollectedTenantReceivableAtExitM: totalTenantReceivable,
    workingCapitalBalanceAtExitM:
      rows.at(-1).workingCapitalBalance - rows.at(-1).exitWorkingCapitalCollection,
    exitCollectionsM: rows.at(-1).exitCollections,
    rateShockAllFacilities: a.rateShockAllFacilities,
  };
  if (hasFac) {
    summary.facilities = facilitySummaries;
    summary.facilityDscrBreachMonths = [...new Set(facilityDscrBreachMonths)];
    summary.facilityPaymentShortfallMonths = facilityPaymentShortfallMonths;
  }
  return { assumptions: a, rows, summary, flows };
}

module.exports = { defaults, evaluate, irr, rentAudit, rentSchedule };

return module.exports;})(__ppRequire);
const notes=(function(require){const module={exports:{}};const exports=module.exports;
/* Publicly documented semiannual senior notes schedule. Standalone audit calculator.
   NOT YET integrated into PowerPath's project loan waterfall. */
'use strict';
function parseDate(x) {
  const d = new Date(x + 'T00:00:00Z');
  if (!/^\d{4}-\d{2}-\d{2}$/.test(x) || Number.isNaN(+d) || d.toISOString().slice(0, 10) !== x)
    throw Error('Invalid ISO date');
  return d;
}
function fmt(d) {
  return d.toISOString().slice(0, 10);
}
function days30360(a, b) {
  const x = parseDate(a),
    y = parseDate(b);
  let d1 = Math.min(30, x.getUTCDate()),
    d2 = y.getUTCDate();
  if (d1 === 30 && d2 === 31) d2 = 30;
  return (
    360 * (y.getUTCFullYear() - x.getUTCFullYear()) + 30 * (y.getUTCMonth() - x.getUTCMonth()) + (d2 - d1)
  );
}
function stepMonths(iso, n) {
  const d = parseDate(iso),
    day = d.getUTCDate(),
    year = d.getUTCFullYear(),
    mon = d.getUTCMonth() + n;
  const first = new Date(Date.UTC(year, mon, 1));
  const last = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
  return fmt(new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), Math.min(day, last))));
}
function schedule(t) {
  for (const k of ['faceM', 'couponPct', 'issuePricePct'])
    if (!Number.isFinite(t[k]) || t[k] < 0) throw Error('Invalid ' + k);
  if (t.faceM <= 0 || t.couponPct > 100 || t.issuePricePct > 200) throw Error('Implausible note terms');
  const issue = parseDate(t.issueDate),
    first = parseDate(t.firstCouponDate),
    maturity = parseDate(t.maturityDate);
  if (first <= issue || maturity < first) throw Error('Payment dates invalid');
  const knownAmort = !!t.firstAmortDate;
  if (knownAmort && parseDate(t.firstAmortDate) < first) throw Error('Amortization starts before coupons');
  if (
    t.originalPrincipalAmortPctYear != null &&
    (!Number.isFinite(t.originalPrincipalAmortPctYear) ||
      t.originalPrincipalAmortPctYear < 0 ||
      t.originalPrincipalAmortPctYear > 100)
  )
    throw Error('Invalid amortization rate');
  const rows = [];
  let remaining = t.faceM,
    date = t.firstCouponDate,
    coupons = 0,
    amortized = 0;
  while (parseDate(date) <= maturity) {
    const opening = remaining;
    // v25.8-CA P6: the first coupon accrues from the accrual start (issue date unless stated) to the first
    // coupon date on 30/360, not a flat half-year. APLD 2025-11-20 -> 2026-06-15 is 205/360, not 180/360.
    const accrualStart = t.accrualStartDate || t.issueDate;
    const coupon =
      rows.length === 0 && t.firstPeriodAccrual !== 'regular'
        ? (((opening * t.couponPct) / 100) * days30360(accrualStart, date)) / 360
        : (opening * t.couponPct) / 200;
    const eligible = knownAmort && date >= t.firstAmortDate && parseDate(date) < maturity;
    const scheduled = eligible
      ? Math.min(remaining, (t.faceM * (t.originalPrincipalAmortPctYear || 0)) / 200)
      : 0;
    let principal = scheduled;
    if (parseDate(date).getTime() === maturity.getTime()) principal = remaining;
    remaining -= principal;
    coupons += coupon;
    amortized += principal;
    rows.push({
      date,
      openingM: opening,
      couponM: coupon,
      scheduledPrincipalM: scheduled,
      maturityBalloonM: parseDate(date).getTime() === maturity.getTime() ? principal : 0,
      principalM: principal,
      closingM: remaining,
    });
    date = stepMonths(date, 6);
  }
  if (rows.length === 0 || rows.at(-1).date !== t.maturityDate)
    throw Error('Maturity not on the semiannual coupon cycle; supply a tailored stub schedule');
  const unknownAmort = !(
    knownAmort &&
    t.originalPrincipalAmortPctYear != null &&
    t.firstAmortDateVerified === true
  );
  return {
    name: t.name,
    netIssueCashBeforeFeesM: (t.faceM * t.issuePricePct) / 100,
    issueDiscountM: t.faceM * (1 - t.issuePricePct / 100),
    rows,
    couponM: coupons,
    principalM: amortized,
    endingM: remaining,
    amortizationTimingConfirmed: knownAmort && t.firstAmortDateVerified === true,
    projectedContractualWaterfall: !unknownAmort,
    warnings: [
      '30/360 first-period stub from ' +
        (t.accrualStartDate ? 'stated accrual start' : 'issue date (accrual start NOT confirmed)') +
        '; later coupons are regular half-years; amendments not modeled',
      ...(unknownAmort
        ? [
            'Amortization amounts and/or first-payment trigger unverified: schedule cannot establish contractual debt waterfall',
          ]
        : []),
    ],
    source: t.source,
  };
}
module.exports = { schedule, stepMonths, days30360 };

return module.exports;})(__ppRequire);
const assurance=(function(require){const module={exports:{}};const exports=module.exports;
'use strict';
/**
 * PowerPath assurance gates (Risk). Decides what a model result may be USED for.
 * Policy: arithmetic, tests and AI review can never unlock transaction valuation or lender
 * certification. Only evidence records (executed documents) plus a signed external review
 * bound to the exact engine version and input hash can.
 */
// Pure-JS SHA-256 (FIPS 180-4) so the module runs unchanged in browsers, Node and audits.
function sha256hex(str) {
  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];
  const bytes = [];
  for (const ch of unescape(encodeURIComponent(str))) bytes.push(ch.charCodeAt(0));
  const bitLen = bytes.length * 8;
  bytes.push(0x80);
  while (bytes.length % 64 !== 56) bytes.push(0);
  for (let i = 7; i >= 0; i--) bytes.push(Math.floor(bitLen / 2 ** (8 * i)) & 0xff);
  const H = [0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19];
  const rotr = (x, n) => (x >>> n) | (x << (32 - n));
  for (let off = 0; off < bytes.length; off += 64) {
    const w = new Array(64);
    for (let t = 0; t < 16; t++)
      w[t] =
        (bytes[off + 4 * t] << 24) |
        (bytes[off + 4 * t + 1] << 16) |
        (bytes[off + 4 * t + 2] << 8) |
        bytes[off + 4 * t + 3];
    for (let t = 16; t < 64; t++) {
      const s0 = rotr(w[t - 15], 7) ^ rotr(w[t - 15], 18) ^ (w[t - 15] >>> 3),
        s1 = rotr(w[t - 2], 17) ^ rotr(w[t - 2], 19) ^ (w[t - 2] >>> 10);
      w[t] = (w[t - 16] + s0 + w[t - 7] + s1) | 0;
    }
    let [a, b, c, d, e, f, g, h] = H;
    for (let t = 0; t < 64; t++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25),
        ch = (e & f) ^ (~e & g),
        t1 = (h + S1 + ch + K[t] + w[t]) | 0;
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22),
        mj = (a & b) ^ (a & c) ^ (b & c),
        t2 = (S0 + mj) | 0;
      h = g;
      g = f;
      f = e;
      e = (d + t1) | 0;
      d = c;
      c = b;
      b = a;
      a = (t1 + t2) | 0;
    }
    H[0] = (H[0] + a) | 0;
    H[1] = (H[1] + b) | 0;
    H[2] = (H[2] + c) | 0;
    H[3] = (H[3] + d) | 0;
    H[4] = (H[4] + e) | 0;
    H[5] = (H[5] + f) | 0;
    H[6] = (H[6] + g) | 0;
    H[7] = (H[7] + h) | 0;
  }
  return H.map((x) => (x >>> 0).toString(16).padStart(8, '0')).join('');
}

const LABELS = ['Executed', 'Public approximate', 'Management expectation', 'Assumption', 'Unknown'];
// Terms that must be Executed before a transaction valuation is permitted.
const MATERIAL_TERMS = [
  'rent',
  'leaseTerm',
  'commencement',
  'powerResponsibility',
  'capex',
  'debtTerms',
  'amortization',
  'utilityService',
];

function stableHash(obj) {
  const canon = (v) =>
    Array.isArray(v)
      ? v.map(canon)
      : v && typeof v === 'object'
        ? Object.fromEntries(
            Object.keys(v)
              .sort()
              .map((k) => [k, canon(v[k])]),
          )
        : v;
  return sha256hex(JSON.stringify(canon(obj)));
}

/**
 * @param {object} result   evaluate() output ({assumptions, summary})
 * @param {object} evidence { terms: {term: {label, factId?, source?}}, documents: {executedLeases, indentureSchedules, utilityAgreements}: boolean,
 *                            reconciliation: {independentReference: boolean, contractMatched: boolean},
 *                            externalReview?: {reviewer, firm, date, scope, signedOff, engineVersion, inputHash} }
 * @param {string} engineVersion
 */
function assess(result, evidence = {}, engineVersion) {
  const s = result.summary || {};
  const terms = evidence.terms || {};
  const docs = evidence.documents || {};
  const rec = evidence.reconciliation || {};
  const review = evidence.externalReview || null;
  const inputHash = stableHash(result.assumptions || {});
  const blocking = [];
  for (const [k, v] of Object.entries(terms))
    if (!LABELS.includes(v && v.label)) blocking.push(`Term '${k}' has invalid evidence label`);

  const nonExecuted = MATERIAL_TERMS.filter((t) => !terms[t] || terms[t].label !== 'Executed');
  const arithmeticOk =
    Math.max(
      s.sourcesUsesMaxResidual ?? Infinity,
      s.debtMaxResidual ?? Infinity,
      s.reserveMaxResidual ?? Infinity,
    ) < 1e-6;

  const gates = {
    G0: {
      name: 'Input provenance',
      status: Object.keys(terms).length ? (nonExecuted.length ? 'QUALIFIED' : 'PASS') : 'FAIL',
      detail: nonExecuted.length ? `Not executed: ${nonExecuted.join(', ')}` : 'All material terms executed',
    },
    G1: {
      name: 'Public headline normalization',
      status: (s.leaseAudits || []).some((x) => x.mode === 'total') ? 'QUALIFIED' : 'NOT APPLICABLE',
      detail: 'Total-rent calibration is an identity by construction, not contract verification',
    },
    G2: {
      name: 'Engine arithmetic & independent reference',
      status: arithmeticOk && rec.independentReference ? 'PASS' : arithmeticOk ? 'QUALIFIED' : 'FAIL',
      detail: arithmeticOk ? 'Monthly identities hold' : 'Accounting identity residual above tolerance',
    },
    G3: {
      name: 'Adverse / stress tests',
      status: arithmeticOk ? 'QUALIFIED' : 'FAIL',
      detail: 'Tested error classes only',
    },
    G4: {
      name: 'Real transaction reconciliation',
      status:
        docs.executedLeases &&
        docs.indentureSchedules &&
        docs.utilityAgreements &&
        rec.contractMatched &&
        !nonExecuted.length
          ? 'PASS'
          : 'FAIL',
      detail:
        [
          !docs.executedLeases && 'executed leases',
          !docs.indentureSchedules && 'indenture schedules',
          !docs.utilityAgreements && 'utility agreements',
          !rec.contractMatched && 'model-to-contract match',
        ]
          .filter(Boolean)
          .join(', ') || 'Reconciled',
    },
    G5: { name: 'Independent external review', status: 'NOT STARTED', detail: 'No signed review' },
  };
  if (review) {
    const problems = [];
    for (const f of ['reviewer', 'firm', 'date', 'scope']) if (!review[f]) problems.push(`missing ${f}`);
    if (review.signedOff !== true) problems.push('not signed off');
    if (review.engineVersion !== engineVersion)
      problems.push(`review covers engine ${review.engineVersion || '?'}, not ${engineVersion}`);
    if (review.inputHash !== inputHash) problems.push('review covers different inputs');
    if (/\b(ai|claude|gpt|codex|llm|automated)\b/i.test(`${review.reviewer} ${review.firm}`))
      problems.push('automated/AI review is not external assurance');
    gates.G5 = problems.length
      ? { name: gates.G5.name, status: 'FAIL', detail: problems.join('; ') }
      : { name: gates.G5.name, status: 'PASS', detail: `${review.firm}, ${review.date}: ${review.scope}` };
  }

  if (gates.G2.status === 'FAIL') blocking.push('Arithmetic identities fail');
  if (s.defaulted) blocking.push('Modeled default — downside sensitivity only');
  if ((s.breachMonths || []).length) blocking.push(`${s.breachMonths.length} covenant breach month(s)`);
  const facBreaches = s.facilityDscrBreachMonths || [];
  if (facBreaches.length) blocking.push(`${facBreaches.length} facility DSCR test(s) below lock-up`);
  if (s.sponsorCommitmentM == null) blocking.push('Sponsor funding uncapped / unevidenced');
  if (gates.G4.status !== 'PASS') blocking.push(`G4 not passed: ${gates.G4.detail}`);
  if (gates.G5.status !== 'PASS') blocking.push(`G5 not passed: ${gates.G5.detail}`);

  const valuationOk = gates.G4.status === 'PASS' && gates.G2.status === 'PASS' && !s.defaulted;
  const uses = {
    screening: gates.G2.status === 'FAIL' ? 'BLOCKED' : 'ALLOWED — scenario screening only',
    transactionValuation:
      valuationOk && gates.G5.status === 'PASS' ? 'PERMITTED — within reviewer scope' : 'BLOCKED',
    lenderCertification:
      valuationOk && gates.G5.status === 'PASS' && !(s.breachMonths || []).length && !facBreaches.length
        ? 'PERMITTED — within reviewer scope'
        : 'BLOCKED',
  };
  return {
    engineVersion,
    inputHash,
    gates,
    uses,
    blockingReasons: blocking,
    nonExecutedMaterialTerms: nonExecuted,
    display: {
      valuationLabel:
        uses.transactionValuation === 'BLOCKED'
          ? 'Screening scenario — not a valuation'
          : 'Reviewed valuation (see scope)',
      showCreditWarnings: true,
      creditWarnings: s.creditWarnings || [],
    },
  };
}
module.exports = { assess, stableHash, sha256hex, LABELS, MATERIAL_TERMS };

return module.exports;})(__ppRequire);
root.PowerPathEngine=Object.freeze({...engine,notes,assurance,ENGINE_VERSION:"25.9.0-risk1"});
})(typeof window!=='undefined'?window:globalThis);
