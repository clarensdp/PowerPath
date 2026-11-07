'use strict';
const assert=require('node:assert/strict');
const {evaluate}=require('./underwrite25.js');
function test(name,override,expect,includes){
 const x=evaluate(override||{}),s=x.summary;
 assert.equal(s.screeningReadiness,expect,name);
 for(const term of includes){assert.ok(s.creditWarnings.some(w=>w.includes(term)),name+' missing '+term)}
 assert.equal(s.financialValidationStatus,'NOT INDEPENDENTLY VALIDATED');
 assert.ok(s.creditWarnings.some(x=>x.includes('not contract-integrated')));
 assert.ok(s.sourcesUsesMaxResidual<1e-6 && s.debtMaxResidual<1e-6);
 console.log('PASS '+name)
}
test('Unlimited sponsor baseline is unverified',{},'CONDITIONAL — scenario screening only',['uncapped','Contractual revenue']);
test('Sponsor funding default',{sponsorCommitmentM:50.0001},'BLOCKED — not a performing credit case',['default']);
test('Lease-tail blocked credit',{sponsorCommitmentM:10000,months:240,refinanceValueM:8000},'BLOCKED — not a performing credit case',['Lease expiry','covenant']);
test('Term-level evidence missing even when liquidity high',{sponsorCommitmentM:10000,ltc:0,mezzLtcPct:0,initialCash:1000,months:72,reserveTargetM:0},'CONDITIONAL — scenario screening only',['lease has no source']);
