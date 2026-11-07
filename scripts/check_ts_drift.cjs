// Fails when web/public/{app,geo}.js no longer match a fresh compile of web/src/*.ts.
// Guards against hand-edits to compiled output (found in the Nov 7 audit: app.js had a link missing from app.ts).
const { execSync } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'pp-tsc-'));
execSync(`npx --yes -p typescript@5.6.3 tsc -p tsconfig.json --outDir ${out}`, { stdio: 'inherit' });
let drift = 0;
for (const f of ['app.js', 'geo.js']) {
  const a = fs.readFileSync(path.join(out, f), 'utf8'), b = fs.readFileSync(path.join('web/public', f), 'utf8');
  if (a !== b) { console.error(`DRIFT: web/public/${f} differs from compiled web/src output. Edit the .ts source and run npm run build:ts.`); drift++; }
}
if (drift) process.exit(1);
console.log('TypeScript sources and compiled JS are in sync.');
