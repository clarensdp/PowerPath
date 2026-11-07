'use strict';
const assert=require('node:assert/strict');
const {evaluate,defaults}=require('./underwrite25.js');
let count=0;
const test=(name,fn)=>{fn();count++;console.log('PASS',name)};
const eq=(a,b,eps=1e-7)=>assert.ok(Math.abs(a-b)<eps,`${a} versus ${b}`);
const caseBase=()=>({...defaults(),months:120});
const checked=(x)=>{for(const r of x.rows){eq(r.sourcesUsesResidual,0,1e-6);eq(r.debtResidual,0,1e-6);eq(r.mezzResidual,0,1e-6);eq(r.reserveResidual,0,1e-6);assert.ok(r.reserve>=-1e-8);assert.ok(r.debt>=-1e-8);assert.ok(r.mezzDebt>=-1e-8)}return x};
test('CFADS bridges EBITDA, taxes, sustaining capex, change in working capital',()=>{
 const z=checked(evaluate({...caseBase(),cashTaxRatePct:23,maintenanceCapexMWYearM:.15,workingCapitalDays:37}));
 for(const r of z.rows)eq(r.cfads,r.ebitda-r.cashTaxes-r.maintenanceCapex-r.workingCapitalChange);
 assert.ok(z.rows.some(r=>r.cfads<r.ebitda-1e-5));
});
test('zero CFADS adjustments preserves the legacy EBITDA numerator',()=>{
 const z=checked(evaluate(caseBase()));for(const r of z.rows)eq(r.cfads,r.ebitda);
});
test('income taxes and maintenance decrease forward CFADS and refinance debt capacity',()=>{
 const base=checked(evaluate({...caseBase(),refinanceDscrMin:20,refinanceLtvPct:100,debtYieldMinPct:0}));
 const hit=checked(evaluate({...caseBase(),refinanceDscrMin:20,refinanceLtvPct:100,debtYieldMinPct:0,cashTaxRatePct:25,maintenanceCapexMWYearM:.2}));
 assert.ok(hit.summary.refinanceSizing.forward12CfadsM<base.summary.refinanceSizing.forward12CfadsM);
 assert.ok(hit.summary.refinanceSizing.selected<base.summary.refinanceSizing.selected);
});
test('forward twelve-month CFADS agrees with realized subsequent forecast',()=>{
 const z=checked(evaluate({...caseBase(),termMonths:24,workingCapitalDays:20,cashTaxRatePct:11})),m=z.summary.maturityMonth;
 const predicted=z.summary.refinanceSizing.forward12CfadsM;
 eq(predicted,z.rows.slice(m,m+12).reduce((sum,r)=>sum+r.cfads,0),1e-6);
});
test('cashflow-based DSCR differs from EBITDA when cash expenditures exist',()=>{
 const z=checked(evaluate({...caseBase(),cashTaxRatePct:20,maintenanceCapexMWYearM:.12}));
 assert.ok(z.rows.some(r=>r.dscr!==null&&r.debtService>0&&Math.abs(r.dscr-r.ebitda/r.debtService)>1e-3));
});
test('sponsor contributions never exceed explicit sponsor commitment',()=>{
 const cap=75,z=checked(evaluate({...caseBase(),sponsorCommitmentM:cap}));
 assert.ok(z.summary.equityInvestedM<=cap+1e-8);assert.ok(z.summary.fundingDefault);
 assert.ok(z.summary.unfundedMonths.length>0||z.rows.some(r=>r.maturityShortfall>0));
 assert.ok(z.rows.every(r=>r.distribution<=1e-8));
});
test('missing sponsor commitment remains unverified, not a funded endorsement',()=>{
 const z=checked(evaluate(caseBase()));assert.equal(z.summary.sponsorCommitmentM,null);
 assert.match(z.summary.financeabilityStatus,/UNVERIFIED SPONSOR FUNDING/);
});
test('underfunded refinance fails to close instead of retiring debt',()=>{
 const z=checked(evaluate({...caseBase(),sponsorCommitmentM:80,termMonths:24}));
 assert.ok(z.summary.fundingDefault);assert.equal(z.summary.refinanced,false);
 assert.ok(z.rows[z.summary.maturityMonth-1].debt>0);
 assert.ok(z.rows[z.summary.maturityMonth-1].maturityShortfall>0);
});
test('high explicit sponsor commitment permits refinance',()=>{
 const z=checked(evaluate({...caseBase(),sponsorCommitmentM:3000,termMonths:24}));
 assert.equal(z.summary.refinanced,true);assert.equal(z.summary.fundingDefault,false);
 assert.ok(z.summary.sponsorRemainingM>=0);
});
test('no synthetic sponsor cure if equity paydown cannot be funded',()=>{
 const z=checked(evaluate({...caseBase(),loanMaturityMode:'equity',termMonths:24,sponsorCommitmentM:70}));
 assert.equal(z.summary.defaulted,true);assert.ok(z.rows[z.summary.maturityMonth-1].debt>0);
 assert.ok(z.summary.equityInvestedM<=70+1e-8);
});
test('exit asset proceeds cannot repay more debt than cash available',()=>{
 const z=checked(evaluate({...caseBase(),loanMaturityMode:'default',exitValueM:0,sponsorCommitmentM:75,rentPerKwMonth:0}));
 assert.ok(z.summary.unpaidDebtAtExitM>0);assert.ok(z.summary.endingDebtM>0);
 assert.equal(z.summary.defaulted,true);assert.equal(z.rows.at(-1).distribution,0);
});
test('adverse sponsor caps retain reconciled accounting despite negative liquidity',()=>{
 for(let c=50;c<=300;c+=10){const z=checked(evaluate({...caseBase(),sponsorCommitmentM:c,cashTaxRatePct:16,workingCapitalDays:20,mezzLtcPct:15,ltc:55,dsraMonths:6}));assert.ok(z.summary.equityInvestedM<=c+1e-7)}
});
test('reject inconsistent sponsor commitment',()=>{
 assert.throws(()=>evaluate({...caseBase(),sponsorCommitmentM:20}),/Sponsor commitment/);
 assert.throws(()=>evaluate({...caseBase(),sponsorCommitmentM:-2}),/sponsorCommitmentM/);
 assert.throws(()=>evaluate({...caseBase(),cashTaxRatePct:150}),/Invalid financial/);
});
test('sponsor limiting is monotonic on total equity cash injections',()=>{
 const a=checked(evaluate({...caseBase(),sponsorCommitmentM:60}));
 const b=checked(evaluate({...caseBase(),sponsorCommitmentM:200}));
 assert.ok(a.summary.equityInvestedM<=b.summary.equityInvestedM+1e-8);
});
test('stress cross product: delays, senior rates, sponsor funding, annual taxes',()=>{
 let total=0;
 for(const delay of [0,6,12])for(const rate of [6,10])for(const cap of [100,400,1500])for(const taxes of [0,22]){
  const z=checked(evaluate({...caseBase(),delayMonths:delay,rate,termMonths:24,sponsorCommitmentM:cap,cashTaxRatePct:taxes,maintenanceCapexMWYearM:.1,workingCapitalDays:25,mezzLtcPct:10,ltc:50}));
  assert.ok(z.summary.equityInvestedM<=cap+1e-6);
  total++;
 }
 assert.equal(total,36);
});
console.log(`TOTAL ${count} v25.7 independent targeted groups (including 36 cross stresses)`);
