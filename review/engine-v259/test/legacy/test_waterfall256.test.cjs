const assert=require('node:assert/strict');
const {evaluate,defaults}=require('../../src/underwrite.cjs');
const cases=[{}, {dsraMonths:6},{dsraMonths:12,termMonths:24,cashSweepPct:30},{dsraMonths:6,loanMaturityMode:'equity'}, {dsraMonths:6,loanMaturityMode:'default'}, {mezzLtcPct:15,ltc:55,dsraMonths:9,tenantCapexPct:30,cashSweepPct:40}];
for(let i=0;i<cases.length;i++){
 const z=evaluate({...defaults(),...cases[i]});const S=z.summary;
 assert.ok(S.sourcesUsesMaxResidual<1e-7,`cash ${i}`);
 assert.ok(S.debtMaxResidual<1e-7,`debt ${i}`);
 assert.ok(S.reserveMaxResidual<1e-7,`reserve ${i}`);
 assert.ok(z.rows.every(r=>r.debt>=-1e-9&&r.mezzDebt>=-1e-9&&r.reserve>=-1e-9),`balance ${i}`);
 assert.ok(z.rows.every(r=>r.reserveDeficiency<1e-8||r.distribution===0),`blocked ${i}`);
 assert.ok(z.rows.every(r=>Math.abs(r.reserve-r.openingReserve-r.reserveMovement)<1e-7),`reserve ledger ${i}`);
}
assert.throws(()=>evaluate({dsraMonths:25}),/Invalid financial/);
const withReserve=evaluate({...defaults(),dsraMonths:6}),noReserve=evaluate(defaults());
assert.ok(withReserve.rows.some(r=>r.dsraTarget>0));
assert.ok(noReserve.rows.every(r=>r.dsraTarget===0));
console.log('v25.6 waterfall: 6 financing cases, 8 control assertions passed');
