'use strict';
const fs=require('node:fs'),path=require('node:path');
const {evaluate,defaults}=require('../workspace/underwrite25.js');
const legacyFile=path.resolve(__dirname,'../../PowerPath_v25_7/workspace/underwrite25.js');
const legacy=require(fs.existsSync(legacyFile)?legacyFile:path.join(__dirname,'../red_team/baseline_v25_7/underwrite25.js'));
const catalog=require('./case_catalog_v258.json');
const out=path.join(__dirname,'v258_results');fs.mkdirSync(out,{recursive:true});
const index=d=>{const [y,m]=d.split('-').map(Number);return (y-2025)*12+m};
const round=(x,n=6)=>Number.isFinite(x)?Number(x.toFixed(n)):null;
const csv=(rows,name)=>{const h=Object.keys(rows[0]);const cells=rows.map(r=>h.map(k=>JSON.stringify(r[k]??'')).join(','));fs.writeFileSync(path.join(out,name),[h.join(','),...cells].join('\n'));};
const cases=[],scenarios=[],specs=[];
let failures=[];
for(const c of catalog){
 const mw=c.modeledItMW, start=Math.max(3,index(c.first)),finish=Math.max(start,index(c.last));
 const n=c.project==='Polaris Forge 1'?3:(c.project==='Abilene Lancium Stargate'?8:Math.min(3,Math.max(1,Math.ceil(mw/100))));
 const weights=c.project==='Polaris Forge 1'?[100,150,150].map(x=>x/400):Array(n).fill(1/n);
 const totalMonths=12*(c.leaseYears??15);
 const buildings=weights.map((fraction,i)=>{
  const month=start+Math.floor(i*(finish-start)/Math.max(n-1,1));
  const b={name:'Phase '+(i+1),itMW:mw*fraction,constructionStart:Math.max(1,month-18),constructionMonths:Math.max(6,Math.min(18,month-1)),powerMonth:month,leaseMonth:month,leaseTermMonths:totalMonths,rentEscalatorPct:2.5};
  if(c.evidenceTier==='APPROX_DISCLOSED_CONTRACT_TOTAL'){
    b.rentInputMode='total';b.contractedRentM=c.reportedLeaseM*fraction;b.leaseSourceRef=c.source;
  }
  return b;
 });
 const horizon=Math.min(360,Math.max(144,index(c.last)+totalMonths+12));
 const spec={...defaults(),calendarStartYear:2025,calendarStartMonth:1,months:horizon,buildings,constructionCostMW:7,exitValueM:mw*12,refinanceValueM:mw*8,termMonths:60,initialCash:Math.max(50,mw*.4),minLiquidity:Math.max(10,mw*.05),reserveTargetM:Math.max(10,mw*.05)};
 specs.push({name:c.project,evidenceTier:c.evidenceTier,source:c.source,assumptions:spec});
 try{
  const next=evaluate(spec),old=legacy.evaluate(spec);
  for(const r of next.rows){if(!Number.isFinite(r.sourcesUsesResidual)||Math.abs(r.sourcesUsesResidual)>1e-6)throw Error('Monthly sources/uses residual '+r.month);}
  let contractVariance=null;
  if(c.evidenceTier==='APPROX_DISCLOSED_CONTRACT_TOTAL'){
    const total=next.summary.leaseAudits.reduce((v,b)=>v+b.modeledContractRentM,0);
    contractVariance=total-c.reportedLeaseM;
    if(Math.abs(contractVariance)>1e-6)throw Error('Contract normalization residual '+contractVariance);
  }
  cases.push({project:c.project,organization:c.organization,capacityReported:c.capacityMW,capacityBasis:c.capacityUnit,modeledItMW:mw,
   evidenceTier:c.evidenceTier,reportedRentTotalM:c.reportedLeaseM,contractTotalVarianceM:round(contractVariance,9),
   isContractVerified:false,requiresTransactionDocs:true,
   modeledNPVM:round(next.summary.npvM,3),priorVersionNPVM:round(old.summary.npvM,3),versionDeltaM:round(next.summary.npvM-old.summary.npvM,6),
   modelDefault:next.summary.defaulted,leaseMismatch:next.summary.leaseReconciliationBlocked,source:c.source,
   caveat:c.evidenceTier==='APPROX_DISCLOSED_CONTRACT_TOTAL'?'Aggregate public contract value approximate; allocation, timing, debt, capex and terms assumed':'Contract value not site/phase specific or not disclosed; valuation illustrative only'});
  for(const delay of [0,3,6,12,18])for(const overrun of [0,10,20])for(const shock of [0,200,400]){
   const scenario={...spec,delayMonths:delay,overrunPct:overrun,rateShockPct:shock/100};
   const r=evaluate(scenario),prev=legacy.evaluate(scenario);
   scenarios.push({project:c.project,evidenceTier:c.evidenceTier,delay,overrun,rateShockBps:shock,
    npvM:round(r.summary.npvM,5),deltaVsOldM:round(r.summary.npvM-prev.summary.npvM,7),
    peakDebtM:round(r.summary.peakDebtM,4),defaulted:r.summary.defaulted,
    sourceUsesResidualM:round(r.summary.sourcesUsesMaxResidual,9),debtResidualM:round(r.summary.debtMaxResidual,9),
    reserveResidualM:round(r.summary.reserveMaxResidual,9)});
  }
 }catch(e){failures.push({project:c.project,error:e.message})}
}
if(cases.length){csv(cases,'transaction_calibration_16.csv');csv(scenarios,'stress_comparison_720.csv')}
fs.writeFileSync(path.join(out,'frozen_inputs_16.json'),JSON.stringify(specs,null,2));
const summary={projects:cases.length,stressCases:scenarios.length,errors:failures.length,disclosedApproxTotalsReconciled:cases.filter(x=>x.evidenceTier==='APPROX_DISCLOSED_CONTRACT_TOTAL'&&Math.abs(x.contractTotalVarianceM)<1e-6).length,
 contractVerified:0,example:cases.slice(0,5),maxModelResidual:Math.max(...scenarios.map(s=>Math.max(Math.abs(s.sourceUsesResidualM||0),Math.abs(s.debtResidualM||0),Math.abs(s.reserveResidualM||0)))),
 maxVersionDelta:Math.max(...scenarios.map(s=>Math.abs(s.deltaVsOldM||0))),failures};
fs.writeFileSync(path.join(out,'summary.json'),JSON.stringify(summary,null,2));
console.log(JSON.stringify({...summary,example:undefined},null,2));
if(failures.length||cases.length!==16||scenarios.length!==720)process.exit(1);
