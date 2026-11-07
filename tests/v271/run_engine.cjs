'use strict';
// Test helper: evaluate a scenario with a named engine file. stdin: {"engine": "engine/underwrite27.js", "input": {...}}
const path = require('node:path'), fs = require('node:fs');
const req = JSON.parse(fs.readFileSync(0, 'utf8'));
const eng = require(path.resolve(__dirname, '../..', req.engine));
try {
  const out = eng.evaluate({ ...eng.defaults(), ...req.input });
  process.stdout.write(JSON.stringify({ rows: out.rows, summary: out.summary, assumptions: out.assumptions }, (k, v) => typeof v === 'number' && !Number.isFinite(v) ? null : v));
} catch (e) { process.stdout.write(JSON.stringify({ error: e.message })); }
