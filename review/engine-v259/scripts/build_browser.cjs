'use strict';
// Builds dist/powerpath-engine.js: the engine + notes as one browser script exposing window.PowerPathEngine,
// and dist/underwrite-panel.js (UI). The engine source is wrapped, never rewritten. v25.9: underwrite.cjs
// requires ./facilities.cjs, which is wrapped the same way and served through a one-entry require shim.
const fs = require('node:fs'),
  path = require('node:path'),
  crypto = require('node:crypto');
const root = path.join(__dirname, '..'),
  dist = path.join(root, 'dist');
const wrap = (file) =>
  `(function(require){const module={exports:{}};const exports=module.exports;\n${fs.readFileSync(path.join(root, file), 'utf8')}\nreturn module.exports;})(__ppRequire)`;
function bundle() {
  const version = require('../package.json').version;
  return `/* @powerpath/engine ${version} — browser build */\n(function(root){'use strict';\nconst __ppModules={};\nconst __ppRequire=(p)=>{if(Object.prototype.hasOwnProperty.call(__ppModules,p))return __ppModules[p];throw Error('Module not bundled: '+p);};\n__ppModules['./facilities.cjs']=${wrap('src/facilities.cjs')};\nconst engine=${wrap('src/underwrite.cjs')};\nconst notes=${wrap('src/notes.cjs')};\nconst assurance=${wrap('src/assurance.cjs')};\nroot.PowerPathEngine=Object.freeze({...engine,notes,assurance,ENGINE_VERSION:${JSON.stringify(version)}});\n})(typeof window!=='undefined'?window:globalThis);\n`;
}
module.exports = { bundle };
if (require.main === module) {
  fs.mkdirSync(dist, { recursive: true });
  fs.writeFileSync(path.join(dist, 'powerpath-engine.js'), bundle());
  fs.copyFileSync(path.join(root, 'ui/underwrite-panel.js'), path.join(dist, 'underwrite-panel.js'));
  const sha = (f) =>
    crypto
      .createHash('sha256')
      .update(fs.readFileSync(path.join(dist, f)))
      .digest('hex');
  fs.writeFileSync(
    path.join(dist, 'SHA256SUMS'),
    ['powerpath-engine.js', 'underwrite-panel.js'].map((f) => `${sha(f)}  ${f}`).join('\n') + '\n',
  );
  console.log(fs.readFileSync(path.join(dist, 'SHA256SUMS'), 'utf8').trim());
}
