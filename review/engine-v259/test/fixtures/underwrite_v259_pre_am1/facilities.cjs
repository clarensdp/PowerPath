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

/**
 * Amortization start resolution (spec §4), evaluated on the CURRENT modeled physical schedule over the whole
 * horizon (months 1..months). Once A is set it never changes.
 * ctx: { months, physicalByMonth, cohortsByBuilding, itMW(name), creditMonths(name) }
 */
function tryResolveAmortStart(f, ctx) {
  if (f.A !== null || !f.amortStart || f.amortStart.type === 'fixedMonth') return;
  const off = f.amortStart.offsetMonths;
  if (f.amortStart.type === 'afterFirstRent') {
    let R = null;
    for (let m = 1; m <= ctx.months && R === null; m++) {
      const ph = ctx.physicalByMonth[m];
      if (f.buildings.some((b) => (ph.grossByBuilding[b] || 0) > 0)) R = m;
    }
    if (R === null) return;
    const p = f.P.find((x) => x > R + off);
    if (p !== undefined) f.A = p;
    return;
  }
  let C = null;
  for (let m = 1; m <= ctx.months && C === null; m++) {
    const ph = ctx.physicalByMonth[m];
    if (f.buildings.every((b) => Math.abs((ph.rentedByBuilding[b] || 0) - ctx.itMW(b)) <= 1e-9)) C = m;
  }
  if (C === null) return;
  let K = -Infinity;
  for (const b of f.buildings) {
    const cohorts = ctx.cohortsByBuilding.get(b) || [];
    if (!cohorts.length) continue;
    K = Math.max(K, Math.max(...cohorts.map((c) => c.start)) + ctx.creditMonths(b));
  }
  const T = Math.max(C, K);
  const p = f.P.find((x) => x >= T + off);
  if (p !== undefined) f.A = p;
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
    if (f.Pset.has(m)) {
      r.interestPaid = f.accrued;
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
  const den = r.interestPaid + r.scheduledPrincipal;
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
    return f.A === null ? s.constructionAmountM : nextPeriodRequirement(f, m);
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
  tryResolveAmortStart,
  scheduledInstallment,
  monthFlows,
  dscrTest,
  dscrLocked,
  dsraRequirement,
  exitPayoff,
  facilityWarnings,
  facilitySummary,
};
