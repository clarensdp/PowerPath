'use strict';
const fs=require('node:fs');const newM=require('../workspace/underwrite25.js');const oldPath=require('node:path').resolve(__dirname,'../../PowerPath_v25_7/workspace/underwrite25.js');const oldM=require(require('node:fs').existsSync(oldPath)?oldPath:'/mnt/data/PowerPath_Claude_Independent_Audit_v258/PowerPath_v25_7/workspace/underwrite25.js');
const one=[{name:'A',itMW:100,constructionStart:1,constructionMonths:2,powerMonth:3,leaseMonth:3,leaseTermMonths:24,rentEscalatorPct:12}];
const late=[{name:'A',itMW:20,constructionStart:1,constructionMonths:5,powerMonth:6,leaseMonth:6,leaseTermMonths:24},{name:'B',itMW:30,constructionStart:20,constructionMonths:6,powerMonth:26,leaseMonth:26,leaseTermMonths:24}];
const base={...newM.defaults(),months:72,initialCash:1000,ltc:0,mezzLtcPct:0,minLiquidity:0,reserveTargetM:0,exitValueM:0,buildings:one,rentPerKwMonth:100};
const part={...base,powerTranches:[{building:'A',mw:50,month:3},{building:'A',mw:50,month:15}]};
const p=newM.evaluate(part),old=oldM.evaluate(part);
const equity={...base,initialCash:4000,ltc:65,mezzLtcPct:5,loanMaturityMode:'equity',termMonths:10,months:70,buildings:late};
const eNew=newM.evaluate(equity),eOld=oldM.evaluate(equity);
const ra={...newM.defaults(),months:120,initialCash:3000,termMonths:24,dsraMonths:6,reserveTargetM:12};
const nNew=newM.evaluate(ra),nOld=oldM.evaluate(ra);
const tenant={...base,tenantCapexPct:100,initialCash:50,sponsorCommitmentM:50,constructionCostMW:7};
const t0=newM.evaluate({...tenant,tenantFundingLagMonths:0});const t3=newM.evaluate({...tenant,tenantFundingLagMonths:3});
const impact={partialTranche:{month15_oldGrossRentM:old.rows[14].grossRevenue,month15_newGrossRentM:p.rows[14].grossRevenue,month27_oldRentM:old.rows[26].grossRevenue,month27_newRentM:p.rows[26].grossRevenue,oldNpvM:old.summary.npvM,newNpvM:p.summary.npvM},
closedConstructionDebt:{oldDrawAfterMaturityM:eOld.rows.slice(19,25).reduce((s,r)=>s+r.draw+r.mezzDraw,0),newDrawAfterMaturityM:eNew.rows.slice(19,25).reduce((s,r)=>s+r.draw+r.mezzDraw,0),oldNpvM:eOld.summary.npvM,newNpvM:eNew.summary.npvM},
additiveReserve:{oldPostRefiReserveM:nOld.rows[25].reserve,newPostRefiReserveM:nNew.rows[25].reserve,oldNpvM:nOld.summary.npvM,newNpvM:nNew.summary.npvM},
tenantCollections:{sameMonthFundingDefault:t0.summary.fundingDefault,lag3FundingDefault:t3.summary.fundingDefault,month1ReceivableM:t3.rows[0].tenantFundingReceivable,month4ReceiptM:t3.rows[3].tenantCashReceipt}};
fs.writeFileSync(require('node:path').join(__dirname,'change_impact258.json'),JSON.stringify(impact,null,2));console.log(JSON.stringify(impact,null,2));
