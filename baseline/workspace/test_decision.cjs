/* Source-level and engine integration smoke test; DOM behavior requires real browser. */
const assert=require('node:assert/strict'),fs=require('fs');
const E=require('./engine2.js'),F=require('./feasibility.js'),D=require('./development.js');
const H=require('./hourly.json');E.setRegions(require('./regions.json'));
const src=fs.readFileSync(__dirname+'/decision-ui.js','utf8');
let n=0;const ok=(yes,name)=>{assert.ok(yes,name);console.log('PASS',name);n++};
ok(src.includes("powerpath-v19-2-project-evidence"),'project-scoped evidence store');
ok(src.includes("e.date<='2026-10-25'"),'dated evidence requirement');
ok(src.includes("v.bridge.sync"),'explicit schedule linkage');
ok(src.includes("Blocking")===false&&src.includes("'Blocked'"),'hard blocked gate');
ok(src.includes('stride=1')&&src.includes('exportBrief()'),'full-stride decision export');
ok(src.includes('Unverified')&&src.includes('not independently authenticated'),'evidence limitation text');
const p=D.freshProject();const s=D.schedule(p);ok(!!s.firstDate&&!!s.fullDate,'schedule survives integration');
const spec=E.defaults();spec.horizonYears=3;
const scenarios=F.compare(E,H,spec,{grid:'Unverified',air:'Unverified',gas:'Unverified',equipment:'Unverified'},{carbonCap:900,maxUnservedMWh:1e9,maxDelayMonths:36},{stride:6});
ok(scenarios.length===3,'three scenarios run through original engine');
ok(scenarios.every(x=>x.gate.status!=='Feasible'),'unverified inputs never approved');
console.log(n+' decision checks passed');
