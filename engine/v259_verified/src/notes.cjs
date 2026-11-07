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
