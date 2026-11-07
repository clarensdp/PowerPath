'use strict';
const assert = require('node:assert/strict');
const {defaults,evaluate}=require('./underwrite25');
const close=(a,b,tol=1e-7)=>assert.ok(Math.abs(a-b)<tol,`Expected ${a} ≈ ${b}`);
let checks=0;const test=(name,fn)=>{fn();checks++;console.log(`PASS ${name}`)};
const base=()=>({...defaults(),months:180,termMonths:48,ltc:50,mezzLtcPct:15,rateShockPct:2,exitValueM:3000,refinanceValueM:3000});
test('legacy rate shock policy unchanged when opt-in false',()=>{
 const a=base(); const x=evaluate(a),y=evaluate({...a,rateShockAllFacilities:false});
 close(x.summary.npvM,y.summary.npvM); close(x.summary.interestM,y.summary.interestM);
 assert.equal(x.rows[4].interest,y.rows[4].interest);
});
test('opt-in shock flows through mezzanine coupon, refinance sizing and amortization',()=>{
 const a=base(),no=evaluate(a),yes=evaluate({...a,rateShockAllFacilities:true});
 assert.equal(no.summary.refinanced,true); assert.equal(yes.summary.refinanced,true);
 assert.ok(yes.rows[4].interest>no.rows[4].interest);
 assert.ok(yes.summary.refinanceSizing.selected<no.summary.refinanceSizing.selected);
 assert.ok(yes.rows[50].interest>no.rows[50].interest);
 assert.ok(yes.summary.npvM<no.summary.npvM);
 assert.ok(yes.summary.sourcesUsesMaxResidual<1e-7);
});
test('default exit policies do not manufacture receivable or WC collections',()=>{
 const a={...base(),workingCapitalDays:15,tenantCapexPct:25,tenantFundingLagMonths:4};
 const x=evaluate(a);assert.equal(x.rows.at(-1).exitCollections,0);
 assert.ok(x.summary.sourcesUsesMaxResidual<1e-7);
});
test('explicit working capital collection appears only at exit and reconciles cash',()=>{
 const a={...base(),workingCapitalDays:15,exitWorkingCapitalRecoveryPct:100};
 const zero=evaluate({...a,exitWorkingCapitalRecoveryPct:0}),full=evaluate(a);
 const r=full.rows.at(-1),z=zero.rows.at(-1);
 assert.ok(r.exitWorkingCapitalCollection>0);
 close(r.exitWorkingCapitalCollection,r.workingCapitalBalance);
 close(r.exitCollections,r.exitWorkingCapitalCollection);
 close(r.terminalProceeds,z.terminalProceeds);
 assert.equal(full.rows.at(-2).exitCollections,0);
 assert.ok(full.summary.sourcesUsesMaxResidual<1e-7);
});
test('tenant funding lag creates receivable recoverable at exit only once',()=>{
 const a={...defaults(),months:36,termMonths:60,buildings:[{name:'Final',itMW:12,constructionStart:31,constructionMonths:6,powerMonth:37,leaseMonth:37,leaseTermMonths:120,rentEscalatorPct:0}],ltc:0,mezzLtcPct:0,tenantCapexPct:50,tenantFundingLagMonths:12,exitValueM:1000,initialCash:1000,refinanceValueM:1000};
 const x=evaluate({...a,exitTenantReceivableRecoveryPct:0}),y=evaluate({...a,exitTenantReceivableRecoveryPct:100});
 const rec=x.summary.uncollectedTenantReceivableAtExitM;
 assert.ok(rec>0);close(y.rows.at(-1).exitTenantReceivableCollection,rec);close(y.summary.uncollectedTenantReceivableAtExitM,0);
 assert.ok(y.summary.sourcesUsesMaxResidual<1e-7);close(x.rows.at(-1).terminalProceeds,y.rows.at(-1).terminalProceeds);
});
test('debt payoff cannot exceed resources and no reserve identity is broken by collections',()=>{
 const a={...base(),exitWorkingCapitalRecoveryPct:80,workingCapitalDays:60,exitValueM:10,initialCash:30};
 const x=evaluate(a),r=x.rows.at(-1);assert.ok(x.summary.sourcesUsesMaxResidual<1e-6);assert.ok(x.summary.debtMaxResidual<1e-6);assert.ok(x.summary.reserveMaxResidual<1e-6);
 assert.ok(r.exitDebtPayoff<=r.terminalProceeds+r.exitCollections+r.openingCash+r.reserve-r.reserveMovement+100); // conservative upper envelope
});
test('reject unbounded exit collections or nonboolean rate policy',()=>{
 assert.throws(()=>evaluate({...defaults(),exitTenantReceivableRecoveryPct:101}),/Invalid financial assumptions/);
 assert.throws(()=>evaluate({...defaults(),exitWorkingCapitalRecoveryPct:101}),/Invalid financial assumptions/);
 assert.throws(()=>evaluate({...defaults(),rateShockAllFacilities:'true'}),/boolean/);
});
test('previously ignored debt-tenor and DSRA switches cannot mislead users',()=>{
 assert.throws(()=>evaluate({...defaults(),amortMonths:120,strictDebtPolicyValidation:true}),/not active/);
 assert.match(evaluate({...defaults(),amortMonths:120}).summary.creditWarnings.join(' '),/amortMonths is not implemented/);
 assert.throws(()=>evaluate({...defaults(),dsraReleaseAtExit:false,strictDebtPolicyValidation:true}),/not supported/);
 assert.match(evaluate({...defaults(),dsraReleaseAtExit:false}).summary.creditWarnings.join(' '),/unsupported/);
});
console.log(`\n${checks} Phase 1A financial tests passed`);
