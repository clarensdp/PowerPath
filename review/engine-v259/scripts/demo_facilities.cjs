'use strict';
// v25.9 facilities demo. Runs every template in data/transactions_v259.json marked "modelable": true on a
// SYNTHETIC campus and prints a per-facility summary. The campus (MW, timing, rent, costs, exit value) is
// invented for illustration only: it is NOT the issuer's project, NOT a forecast and NOT lender-validated.
// Templates marked "modelable": false are listed and skipped, never modeled as if their dates were known.
const path = require('node:path');
const { evaluate } = require('../src/underwrite.cjs');
const data = require(path.join(__dirname, '../data/transactions_v259.json'));

const SYNTHETIC_START = { calendarStartYear: 2025, calendarStartMonth: 1 };

/** Synthetic campus: the template's collateral buildings plus one non-collateral building. */
function syntheticCampus(t) {
  const issueMonth = (Number(t.issueDate.slice(0, 4)) - 2025) * 12 + Number(t.issueDate.slice(5, 7));
  const collateralMW = Math.round(t.faceM / 7 / t.buildings.length);
  const buildings = t.buildings.map((name, i) => ({
    name,
    itMW: collateralMW,
    constructionStart: Math.max(1, issueMonth - 6 + 3 * i),
    constructionMonths: 18,
    powerMonth: Math.max(1, issueMonth - 6 + 3 * i) + 18,
    leaseMonth: Math.max(1, issueMonth - 6 + 3 * i) + 18,
    leaseTermMonths: 180,
    rentEscalatorPct: 2.5,
    leaseSourceRef: 'SYNTHETIC — no lease reviewed',
  }));
  buildings.push({
    name: 'Synthetic non-collateral building',
    itMW: 50,
    constructionStart: 1,
    constructionMonths: 12,
    powerMonth: 13,
    leaseMonth: 13,
    leaseTermMonths: 180,
    rentEscalatorPct: 2.5,
    leaseSourceRef: 'SYNTHETIC — no lease reviewed',
  });
  const totalMW = buildings.reduce((s, b) => s + b.itMW, 0);
  return {
    ...SYNTHETIC_START,
    months: 120,
    ltc: 0,
    mezzLtcPct: 0,
    initialCash: 250,
    minLiquidity: 25,
    reserveTargetM: 25,
    rentPerKwMonth: 170,
    constructionCostMW: 7,
    exitValueM: totalMW * 10,
    buildings,
  };
}

function toFacility(t) {
  const f = JSON.parse(JSON.stringify(t));
  delete f.modelableNote;
  return f;
}

function runDemo() {
  const results = [],
    skipped = [];
  for (const t of data.templates) {
    if (t.modelable !== true) {
      skipped.push({ id: t.id, reason: t.modelableReason });
      continue;
    }
    const z = evaluate({ ...syntheticCampus(t), facilities: [toFacility(t)] });
    results.push({ id: t.id, summary: z.summary, facility: z.summary.facilities[0], rows: z.rows });
  }
  return { results, skipped };
}

module.exports = { runDemo, syntheticCampus };

if (require.main === module) {
  const fmt = (x, d = 1) => (x === null || x === undefined ? 'n/a' : Number(x).toFixed(d));
  const { results, skipped } = runDemo();
  console.log(
    '=== PowerPath v25.9 facilities demo — SYNTHETIC CAMPUS, illustrative only, not lender-validated ===',
  );
  console.log(
    'Calendar start 2025-01, 120 months; campus sizing, timing, rent and exit value are invented.\n',
  );
  for (const { id, summary: s, facility: f } of results) {
    console.log(`[${id}] ${f.name}`);
    console.log(
      `  face ${fmt(f.faceM)}  coupon ${f.couponPct}%  price ${f.issuePricePct}  proceeds ${fmt(f.proceedsM)}  OID ${fmt(f.oidM)}  fees ${fmt(f.feesM)}`,
    );
    console.log(
      `  months: issue ${f.issueMonth}, first payment ${f.firstPaymentMonth}, maturity ${f.maturityMonth}; amort start ${f.amortStartMonth ?? 'unresolved'} (${f.amortStartBasis}); construction end E ${f.constructionEndMonth ?? 'n/a'}; construction lock-up end L ${f.constructionLockupEndMonth ?? 'not reached'}`,
    );
    console.log(
      `  interest paid ${fmt(f.totalInterestPaidM)}  principal paid ${fmt(f.totalPrincipalPaidM)}  balloon ${fmt(f.balloonM)}  ending ${fmt(f.endingBalanceM)}  unpaid at exit ${fmt(f.unpaidAtExitM)}`,
    );
    console.log(
      `  min DSCR ${fmt(f.minDscr, 2)} over ${f.dscrTests.length} tests; lock-up months ${f.lockupMonths.length}; DSRA deficiency months ${f.dsraDeficiencyMonths.length}; peak DSRA ${fmt(Math.max(...f.schedule.map((r) => r.dsraBalance)))}`,
    );
    console.log(
      `  campus (synthetic): NPV ${fmt(s.npvM)}  sponsor in ${fmt(s.equityInvestedM)}  unfunded months ${s.unfundedMonths.length}  payment-shortfall months ${s.facilityPaymentShortfallMonths.length}`,
    );
    console.log(`  warnings (${f.warnings.length}):`);
    for (const w of f.warnings) console.log('    - ' + w);
    console.log('');
  }
  for (const k of skipped) console.log(`[${k.id}] SKIPPED (modelable: false): ${k.reason}`);
}
