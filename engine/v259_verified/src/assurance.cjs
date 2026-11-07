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
