'use strict';
const fs=require('node:fs'),path=require('node:path');
const {defaults,evaluate}=require('../workspace/underwrite25');
const baseline=require('./underwrite_v2583_baseline.js');
const catalog=require('./case_catalog_v2584.json');
const out=path.join(__dirname,'v2584_results');fs.mkdirSync(out,{recursive:true});
const index=d=>{const [y,m]=d.split('-').map(Number);return (y-2025)*12+m};
const round=(n,d=6)=>Number.isFinite(n)?Number(n.toFixed(d)):null;
const csv=(rows,name)=>{const keys=Object.keys(rows[0]);fs.writeFileSync(path.join(out,name),[keys.join(','),...rows.map(r=>keys.map(k=>JSON.stringify(r[k]??'')).join(','))].join('\n'));};
const summary=[],stresses=[],specs=[],failures=[];
for(const c of catalog){
 const mw=c.modeledItMW,start=Math.max(3,index(c.first)),finish=Math.max(start,index(c.last));
 const count=c.project==='Polaris Forge 1'?3:(c.project==='Abilene Lancium Stargate'?8:Math.min(3,Math.max(1,Math.ceil(mw/100))));
 const portions=c.project==='Polaris Forge 1'?[.25,.375,.375]:Array(count).fill(1/count);
 const buildings=portions.map((f,i)=>{const m=start+Math.floor(i*(finish-start)/Math.max(count-1,1));const b={name:'Phase '+(i+1),itMW:mw*f,constructionStart:Math.max(1,m-18),constructionMonths:Math.max(6,Math.min(18,m-1)),powerMonth:m,leaseMonth:m,leaseTermMonths:Math.round((c.leaseYears||15)*12),rentEscalatorPct:c.rentEscalatorPctFromFiling??2.5,leaseSourceRef:c.source};
  if(c.evidenceTier==='APPROX_DISCLOSED_CONTRACT_TOTAL'){
    b.rentInputMode='total';b.contractedRentM=c.buildingLeaseValueM_provisional?.[i]??c.reportedLeaseM*f;
  }else if(c.rentPerKwMonthFromFiling){b.rentInputMode='starting';b.rentPerKwMonth=c.rentPerKwMonthFromFiling;}
  return b;
 });
 const horizon=Math.min(360,Math.max(144,index(c.last)+Math.round((c.leaseYears||15)*12)+12));
 const s={...defaults(),calendarStartYear:2025,calendarStartMonth:1,months:horizon,buildings,constructionCostMW:(c.screeningCapexMPerItMW??7),exitValueM:mw*12,refinanceValueM:mw*8,termMonths:60,initialCash:Math.max(50,mw*.4),minLiquidity:Math.max(10,mw*.05),reserveTargetM:Math.max(10,mw*.05),powerResponsibility:c.powerCostResponsibility,powerPassThroughPct:100};
 specs.push({name:c.project,source:c.source,evidenceTier:c.evidenceTier,powerEvidenceTier:c.powerCostEvidenceTier,scenario:s});
 try{
 const prev=baseline.evaluate(s),next=evaluate(s);
 const item={organization:c.organization,project:c.project,reportedCapacityMW:c.capacityMW,reportedCapacityBasis:c.capacityUnit,modeledItMWProxy:mw,powerMode:c.powerCostResponsibility,powerEvidenceTier:c.powerCostEvidenceTier,leaseTier:c.evidenceTier,modeledLeaseTotalM:c.reportedLeaseM,
 npvBeforeM:round(prev.summary.npvM,3),npvAfterM:round(next.summary.npvM,3),deltaNPVM:round(next.summary.npvM-prev.summary.npvM,3),grossPowerCostM:round(next.summary.grossPowerCostM,3),tenantBilledM:round(next.summary.powerReimbursementM,3),netLandlordPowerM:round(next.summary.netLandlordPowerCostM,3),breachMonths:next.summary.breachMonths.length,defaulted:next.summary.defaulted,contractVerified:false,scopeCaution:c.leaseScope||c.energyAccountingCaveat||c.notes};
 summary.push(item);
 for(const delay of [0,3,6,12,18])for(const overrun of [0,10,20])for(const shock of [0,200,400]){
   const a=evaluate({...s,delayMonths:delay,overrunPct:overrun,rateShockPct:shock/100});
   if(a.summary.sourcesUsesMaxResidual>1e-6||a.summary.debtMaxResidual>1e-6||a.summary.reserveMaxResidual>1e-6)throw Error('Accounting residual');
   stresses.push({project:c.project,delay,overrun,rateShockBps:shock,npvM:round(a.summary.npvM,3),breachMonths:a.summary.breachMonths.length,defaulted:a.summary.defaulted,netLandlordPowerM:round(a.summary.netLandlordPowerCostM,3),maxResidualM:round(a.summary.sourcesUsesMaxResidual,9)});
 }
 }catch(e){failures.push({project:c.project,error:e.stack})}
}
if(summary.length){csv(summary,'power_cost_16_cases.csv');csv(stresses,'stress_720_scenarios.csv')}
fs.writeFileSync(path.join(out,'frozen_inputs_16.json'),JSON.stringify(specs,null,2));
const result={cases:summary.length,stress:stresses.length,errors:failures,scenarioOnly:true,verifiedTransactions:0,modeledPowerPassThroughCases:summary.filter(x=>x.powerMode!=='landlord').length,maxAbsNpvDeltaM:Math.max(0,...summary.map(x=>Math.abs(x.deltaNPVM)))};
fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));
if(result.cases!==16||result.stress!==720||failures.length)process.exit(1);
