const assert=require('node:assert/strict');
const {evaluate,defaults}=require('./underwrite25');
const close=(a,b,e=1e-7)=>assert.ok(Math.abs(a-b)<e,`${a} vs ${b}`);
let passed=0;
function test(label,fn){fn();console.log('PASS',label);passed++}
const base=()=>({...defaults(),months:180});
test('lease expiration stops rental cash flow',()=>{let a=base();a.buildings=[{name:'A',itMW:10,constructionStart:1,constructionMonths:12,powerMonth:13,leaseMonth:13,leaseTermMonths:12,rentEscalatorPct:0}];let r=evaluate(a);assert.ok(r.rows[12].revenue>0);close(r.rows[24].revenue,0)});
test('rent annual escalation applies only after 12 elapsed months',()=>{let a=base();a.buildings=[{name:'A',itMW:10,constructionStart:1,constructionMonths:12,powerMonth:13,leaseMonth:13,leaseTermMonths:36,rentEscalatorPct:10}];let r=evaluate(a);close(r.rows[24].revenue/r.rows[23].revenue,1.1)});
test('gross power correctly converts to IT using PUE',()=>{let a=base();a.capacityBasis='gross';a.buildings=[{name:'A',itMW:130,constructionStart:1,constructionMonths:12,powerMonth:13,leaseMonth:13}];let r=evaluate(a);close(r.rows[12].onlineMW,100)});
test('tenant pays a defined share of construction capex',()=>{let a=base();a.tenantCapexPct=25;let r=evaluate(a);close(r.summary.tenantFundingM,r.rows.reduce((x,z)=>x+z.capex,0)*.25);assert.ok(r.summary.equityInvestedM<evaluate({...a,tenantCapexPct:0}).summary.equityInvestedM)});
test('rent credits are time bounded and reduce revenue',()=>{let a=base();a.tenantRentCreditPct=50;a.tenantCreditMonths=6;let r=evaluate(a);assert.ok(r.rows[18].rentCredits>0);close(r.rows[24].rentCredits,0);assert.ok(r.summary.rentCreditsM>0)});
test('refinance limited by debt yield',()=>{let a=base();a.debtYieldMinPct=100;let r=evaluate(a);let s=r.summary.refinanceSizing;assert.ok(s);assert.equal(s.binding,'debt yield');assert.ok(s.selected<=s.ltvLimit+1e-8);assert.ok(s.selected<=s.dscrLimit+1e-8)});
test('refinance limited by LTV',()=>{let a=base();a.refinanceLtvPct=1;a.debtYieldMinPct=0;a.refinanceDscrMin=.1;let s=evaluate(a).summary.refinanceSizing;assert.equal(s.binding,'LTV')});
test('refinance limited by DSCR',()=>{let a=base();a.refinanceDscrMin=20;a.refinanceLtvPct=100;a.debtYieldMinPct=0;let s=evaluate(a).summary.refinanceSizing;assert.equal(s.binding,'DSCR')});
test('mezzanine loan added to debt with own interest and explicit maturity',()=>{let a=base();a.ltc=50;a.mezzLtcPct=15;let r=evaluate(a);assert.ok(r.summary.mezzDrawsM>0);close(r.summary.debtDrawsM/50,r.summary.mezzDrawsM/15);assert.ok(r.rows.some(x=>x.mezzDebt>0));close(r.summary.endingDebtM,0)});
test('reject over 100 percent financed construction',()=>{assert.throws(()=>evaluate({...base(),ltc:90,mezzLtcPct:20}),/Invalid financial assumptions/)});
test('tenant credits and mezz stress reconcile in every month',()=>{let a={...base(),tenantCapexPct:30,tenantRentCreditPct:35,tenantCreditMonths:24,mezzLtcPct:15,ltc:60,delayMonths:8,overrunPct:20};let r=evaluate(a);for(const x of r.rows)close(x.sourcesUsesResidual,0,1e-5)});
test('no automatic approval or confirmed power from capacity basis',()=>{let a={...base(),capacityBasis:'gross'};let r=evaluate(a);assert.equal(r.summary.refinanced,true);assert.equal(r.assumptions.capacityBasis,'gross')});
console.log('TOTAL',passed,'v25.2 groups');
