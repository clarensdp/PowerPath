'use strict';
// Golden snapshot of the 16 public cases x 45 stresses (720 runs). Any change to engine outputs
// must be deliberate: run `npm run golden:update` and review the diff in review.
const fs = require('node:fs'),
  path = require('node:path'),
  crypto = require('node:crypto');
const { evaluate } = require('../src/underwrite.cjs');
const specs = require('../test/fixtures/frozen_inputs_16.json');
const FILE = path.join(__dirname, '../test/golden/stress720.json');
function compute() {
  const out = [];
  for (const s of specs)
    for (const delay of [0, 3, 6, 12, 18])
      for (const overrun of [0, 10, 20])
        for (const shock of [0, 200, 400]) {
          const z = evaluate({
            ...JSON.parse(JSON.stringify(s.assumptions)),
            delayMonths: delay,
            overrunPct: overrun,
            rateShockPct: shock / 100,
          });
          const S = z.summary;
          out.push({
            project: s.name,
            delay,
            overrun,
            shock,
            npvM: S.npvM,
            minDSCR: S.minDSCR,
            breaches: S.breachMonths.length,
            defaulted: S.defaulted,
            maxResidual: Math.max(S.sourcesUsesMaxResidual, S.debtMaxResidual, S.reserveMaxResidual),
            rowsSha256: crypto.createHash('sha256').update(JSON.stringify(z.rows)).digest('hex'),
          });
        }
  return out;
}
module.exports = { compute, FILE };
if (require.main === module && process.argv.includes('--update')) {
  fs.mkdirSync(path.dirname(FILE), { recursive: true });
  fs.writeFileSync(FILE, JSON.stringify(compute(), null, 1));
  console.log('golden updated:', FILE);
}
