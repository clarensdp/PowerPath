'use strict';
const assert = require('node:assert/strict');
const {evaluate,defaults}=require('./underwrite25.js');
const near=(x,y,e=1e-7)=>assert.ok(Math.abs(x-y)<e,`Expected ${x} = ${y}`);
const base=()=>({...defaults(),months:72,initialCash:1000,minLiquidity:0,reserveTargetM:0,ltc:0,mezzLtcPct:0,refinanceLtvPct:0,exitValueM:0,buildings:[{name:'A',itMW:100,constructionStart:1,constructionMonths:2,powerMonth:3,leaseMonth:3,leaseTermMonths:24,rentEscalatorPct:12}]});
let n=0;
function run(name,f){f();console.log('PASS',name);n++}
run('partial power cohorts begin at actual energized dates, not original nominal first date',()=>{
 const z=evaluate({...base(),rentPerKwMonth:100,powerTranches:[{building:'A',mw:50,month:3},{building:'A',mw:50,month:15}]});
 near(z.rows[2].grossRevenue,5);
 near(z.rows[13].grossRevenue,5);
 near(z.rows[14].grossRevenue,10.6); // first half escalated, new half at initial rate
 near(z.rows[26].grossRevenue,5.6); // first 50 MW expired; second cohort first escalator
 near(z.rows[38].grossRevenue,0); // all tranches now expired
 z.rows.forEach(r=>{near(r.sourcesUsesResidual,0,1e-6);near(r.debtResidual,0,1e-6)})
});
run('scheduled power tranche cannot bypass construction, nominal power date, or lease gate',()=>{
 const b=base();b.rentPerKwMonth=100;b.buildings[0].powerMonth=10;
 const z=evaluate({...b,powerTranches:[{building:'A',mw:100,month:3}]});
 for(let m=1;m<10;m++)near(z.rows[m-1].grossRevenue,0);
 near(z.rows[9].grossRevenue,10);
});
run('equity-funded loan retirement prohibits future draws on retired construction facility',()=>{
 const b=base();b.ltc=65;b.mezzLtcPct=5;b.initialCash=4000;
 b.loanMaturityMode='equity';b.termMonths=10;b.months=70;b.buildings=[
 {name:'A',itMW:20,constructionStart:1,constructionMonths:5,powerMonth:6,leaseMonth:6,leaseTermMonths:24},
 {name:'B',itMW:30,constructionStart:20,constructionMonths:6,powerMonth:26,leaseMonth:26,leaseTermMonths:24}];
 const z=evaluate(b);
 assert.ok(z.summary.maturityMonth<20);
 assert.ok(z.rows[z.summary.maturityMonth-1].principal>0);
 assert.ok(z.rows.slice(19,25).every(r=>r.draw===0&&r.mezzDraw===0));
 assert.equal(z.summary.defaulted,false);
 z.rows.forEach(r=>near(r.sourcesUsesResidual,0,1e-6));
});
run('base reserve plus DSRA are additive; reserve reconciles monthly',()=>{
 const z=evaluate({...defaults(),months:120,initialCash:3000,termMonths:24,dsraMonths:6,reserveTargetM:12});
 assert.equal(z.summary.refinanced,true);
 const post=z.rows.filter(r=>r.dsraTarget>1e-5);
 assert.ok(post.length>0);
 post.forEach(r=>{near(r.restrictedTarget,12+r.dsraTarget);near(r.reserveResidual,0,1e-7)});
});
run('full-year funded contractual rent equals specified total with staggered delivery, not double escalated',()=>{
 const b=base();b.months=80;b.buildings[0].rentInputMode='total';b.buildings[0].contractedRentM=240;
 b.powerTranches=[{building:'A',mw:50,month:3},{building:'A',mw:50,month:15}];
 const z=evaluate(b);
 near(z.rows.reduce((v,r)=>v+r.grossRevenue,0),240,1e-6);
 assert.equal(z.summary.leaseReconciliationBlocked,false);
});
run('impossible building-level tenant funding / credit percentages rejected',()=>{
 const b=base();b.buildings[0].tenantCapexPct=150;
 assert.throws(()=>evaluate(b),/above 100%/);
 b.buildings[0].tenantCapexPct=0;b.buildings[0].tenantRentCreditPct=150;
 assert.throws(()=>evaluate(b),/above 100%/);
});
run('dedicated MW above physical IT capacity rejected',()=>{
 const b=base();b.powerTranches=[{building:'A',mw:200,month:3}];
 assert.throws(()=>evaluate(b),/exceed/)
});

run('delayed tenant reimbursements create actual receivable and can exhaust committed liquidity',()=>{
 const b={...base(),tenantCapexPct:100,initialCash:50,sponsorCommitmentM:50,constructionCostMW:7};
 const same=evaluate({...b,tenantFundingLagMonths:0});
 const late=evaluate({...b,tenantFundingLagMonths:3});
 assert.equal(same.summary.fundingDefault,false);
 assert.equal(late.summary.fundingDefault,true);
 near(late.rows[0].tenantFundingReceivable,350);
 near(late.rows[3].tenantCashReceipt,350);
 late.rows.forEach(r=>near(r.sourcesUsesResidual,0,1e-6));
});

run('calendar-month electric energy reflects actual days and leap-year February',()=>{
 const b=base();b.calendarStartYear=2028;b.calendarStartMonth=1;b.pue=1;
 b.buildings[0].constructionMonths=1;b.buildings[0].powerMonth=2;b.buildings[0].leaseMonth=2;
 b.powerCostMWh=100;b.rentPerKwMonth=100;
 const z=evaluate(b);
 near(z.rows[1].energy,100*696*100/1e6); // February 2028, leap year
 near(z.rows[2].energy,100*744*100/1e6); // March 2028
});
console.log('TOTAL',n,'transaction v25.8 tests');
