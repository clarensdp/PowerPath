/* PowerPath v25.9-alpha — separate opt-in transaction-facilities underwriting pathway.
   Reuses v25.8.5 physical/lease/CFADS operations; DOES NOT rewrite the frozen legacy debt engine.
   Contract terms supplied below are illustrative unless backed by original executed documents.
   All amounts USD millions. Timing is monthly; actual indenture day count/schedules must be verified. */
(function(root){'use strict';
const n=(x,k,min=0)=>{const v=Number(x);if(!Number.isFinite(v)||v<min)throw Error(k+' must be finite and >= '+min);return v};
const round=x=>Math.round(x*1e10)/1e10;
function sample(){return {project:{...root.PowerPathUnderwrite25.defaults(),months:120,initialCash:50,sponsorCommitmentM:800,distributionPolicy:'none',powerResponsibility:'tenant_direct'},facilities:[{id:'senior-construction',type:'construction',buildingNames:['Building A','Building B','Building C'],advancePct:55,annualRatePct:8.5,issueMonth:1,maturityMonth:60,interestPolicy:'cash',priority:1,sourceId:'ASSUMPTION: SAMPLE'},{id:'fixed-rate-note',type:'note',buildingNames:['Building B','Building C'],faceM:180,issuePricePct:98,couponPct:9.25,issueMonth:13,firstCouponMonth:19,couponIntervalMonths:6,amortStartMonth:37,amortAnnualPct:4,maturityMonth:96,dsraFixedM:8,priority:1,sourceId:'ASSUMPTION: SAMPLE'}]};}
function validate(project,facilities){
 if(!project||!Array.isArray(project.buildings)||!project.buildings.length)throw Error('A project with buildings is required');
 if(!Array.isArray(facilities)||!facilities.length||facilities.length>12)throw Error('Provide 1-12 facilities');
 const names=new Set(project.buildings.map(b=>b.name)),ids=new Set(),term=Math.round(n(project.months,'months',12));
 for(const f of facilities){
  if(!f.id||ids.has(f.id))throw Error('Facility IDs must be unique');ids.add(f.id);
  if(!['note','construction'].includes(f.type))throw Error('Unsupported facility type '+f.type);
  if(!Array.isArray(f.buildingNames)||!f.buildingNames.length||f.buildingNames.some(x=>!names.has(x)))throw Error(f.id+': explicit, valid building scope is required');
  f.issueMonth=Math.round(n(f.issueMonth,'issueMonth',1));f.maturityMonth=Math.round(n(f.maturityMonth,'maturityMonth',f.issueMonth));
  if(f.issueMonth>term||f.maturityMonth>term)throw Error(f.id+': issue and maturity must be within model horizon');
  f.priority=Math.round(n(f.priority??1,'priority',1));
  if(f.type==='note'){
   for(const k of ['faceM','issuePricePct','couponPct','amortAnnualPct'])n(f[k]??(k==='issuePricePct'?100:0),k,k==='faceM'?0.00001:0);
   if(f.issuePricePct>100||f.amortAnnualPct>100||f.couponPct>100)throw Error(f.id+': invalid rate');
   f.couponIntervalMonths=Math.round(n(f.couponIntervalMonths??6,'couponIntervalMonths',1));
   if(![1,3,6,12].includes(f.couponIntervalMonths))throw Error(f.id+': coupon interval must be 1,3,6,12 months');
   f.firstCouponMonth=Math.round(n(f.firstCouponMonth??f.issueMonth+f.couponIntervalMonths,'firstCouponMonth',f.issueMonth+1));
   if(f.amortStartMonth!==undefined&&f.amortStartMonth!==null)f.amortStartMonth=Math.round(n(f.amortStartMonth,'amortStartMonth',f.issueMonth));
   if(f.amortTrigger!==undefined&&!['month','first_rent_plus'].includes(f.amortTrigger))throw Error('Unsupported amortization trigger');
   if(f.amortTrigger==='first_rent_plus')f.monthsAfterFirstRent=Math.round(n(f.monthsAfterFirstRent??0,'monthsAfterFirstRent'));
   n(f.dsraFixedM??0,'dsraFixedM');
  }else {n(f.advancePct,'advancePct');n(f.annualRatePct,'annualRatePct');if(f.advancePct>100||f.annualRatePct>100)throw Error('Invalid construction advance or rate');}
 }
 // Explicit scopes are not a substitute for legal recourse. Mark overlaps, never silently net them.
 return {term,names};
}
function evaluate(data){
 const raw=JSON.parse(JSON.stringify(data)),a=raw.project,facilities=raw.facilities;
 const {term}=validate(a,facilities);
 // Operation-only reference. No debt or terminal valuation in this reference result.
 // It provides *the same* physical and lease economics as PowerPath v25.8.5.
 const opConfig={...a,months:term,ltc:0,mezzLtcPct:0,loanMaturityMode:'equity',termMonths:term+10,initialCash:0,minLiquidity:0,reserveTargetM:0,dsraMonths:0,exitValueM:0,distributionPolicy:'none',sponsorCommitmentM:null};
 const ref=root.PowerPathUnderwrite25.evaluate(opConfig);
 const sc=new Map(facilities.map(f=>[f.id,{...f,balance:0,reserve:0,firstRentMonth:null,amortTriggerMonth:null,paidPrincipal:0,paidInterest:0,issued:0}]));
 const it=b=>b.itMW/((b.capacityBasis||a.capacityBasis||'IT')==='gross'?(a.pue||1.3):1);
 const rentStart=b=>Math.max(b.constructionStart+b.constructionMonths,b.powerMonth+(a.delayMonths||0),b.leaseMonth+(a.delayMonths||0));
 for(const f of sc.values())if(f.type==='note'){
   const starts=a.buildings.filter(b=>f.buildingNames.includes(b.name)).map(rentStart);
   f.firstRentMonth=Math.min(...starts);
   f.amortTriggerMonth=f.amortTrigger==='first_rent_plus'?f.firstRentMonth+(f.monthsAfterFirstRent||0):(f.amortStartMonth??Infinity);
 }
 const commitment=a.sponsorCommitmentM==null?Infinity:n(a.sponsorCommitmentM,'sponsorCommitmentM');
 let cash=n(a.initialCash??0,'initialCash'),totalSponsor=cash,defaulted=false,defaultMonth=null,endingReserve=0;
 if(totalSponsor>commitment)throw Error('Opening cash exceeds capped sponsor commitment');
 let equityFlows=[-cash],rows=[],unpaidAtExit=0;
 const notesSorted=[...sc.values()].sort((x,y)=>x.priority-y.priority||x.id.localeCompare(y.id));
 for(let m=1;m<=term;m++){
   const op=ref.rows[m-1],openingCash=cash,openingTotalDebt=notesSorted.reduce((s,f)=>s+f.balance,0),openingReserve=endingReserve;
   const activities=[];let draws=0,oid=0,interestDue=0,principalDue=0,paidInterest=0,paidPrincipal=0,issueCash=0;
   // Monthly per-building eligible sponsor capex: can finance only within defined scope.
   for(const f of notesSorted){
     let draw=0,nominalIssue=0,coupon=0,scheduledPrincipal=0;
     if(f.type==='construction'&&m>=f.issueMonth&&m<f.maturityMonth&&!defaulted){
       for(const b of a.buildings.filter(b=>f.buildingNames.includes(b.name))){
         const end=b.constructionStart+b.constructionMonths-1;
         if(m>=b.constructionStart&&m<=end){const cap=it(b)*(a.constructionCostMW??7)*(1+(a.overrunPct??0)/100)/b.constructionMonths;
           draw+=cap*(1-(b.tenantCapexPct??a.tenantCapexPct??0)/100)*(f.advancePct/100);}
       }
       f.balance+=draw;draws+=draw;
     }
     if(f.type==='note'&&m===f.issueMonth&&!defaulted){
       nominalIssue=f.faceM;f.balance+=nominalIssue;f.issued+=nominalIssue;
       issueCash=nominalIssue*(f.issuePricePct??100)/100;draws+=issueCash;oid+=nominalIssue-issueCash;
     }
     if(f.type==='construction'&&f.balance>0){coupon=f.balance*f.annualRatePct/1200;}
     if(f.type==='note'&&f.balance>0){
       if(m>=f.firstCouponMonth&&(m-f.firstCouponMonth)%f.couponIntervalMonths===0){
         let factor=f.couponIntervalMonths/12;
         // Optional, explicit first-stub day fraction (30/360). Do not infer day precision from month.
         if(m===f.firstCouponMonth&&f.firstCouponDayCount30_360!==undefined)factor=n(f.firstCouponDayCount30_360,'firstCouponDayCount30_360')/360;
         coupon=f.balance*f.couponPct/100*factor;
         if(m>=f.amortTriggerMonth){scheduledPrincipal=Math.min(f.balance,f.faceM*(f.amortAnnualPct??0)/100*f.couponIntervalMonths/12);}
       }
     }
     if(m===f.maturityMonth)scheduledPrincipal=f.balance;
     interestDue+=coupon;principalDue+=scheduledPrincipal;
     activities.push({id:f.id,type:f.type,scope:f.buildingNames.join('; '),draw,nominalIssue,issuedCash:f.type==='note'&&nominalIssue>0?issueCash:0,couponDue:coupon,principalDue:scheduledPrincipal,priority:f.priority,openingBalance:f.balance-draw-nominalIssue,closingBalance:0,interestPaid:0,principalPaid:0,reserve:f.reserve,triggerMonth:f.amortTriggerMonth||null});
   }
   cash+=op.cfads+op.tenantCashReceipt-op.capex+draws;
   // Paying contractual debt BEFORE any equity distribution; never disguise an unfunded obligation.
   // Source docs must establish actual cross-facility priority and permitted use of each DSRA.
   const totalDue=interestDue+principalDue;
   const availableSponsor=Math.max(0,commitment-totalSponsor);
   const sponsorNeed=Math.max(0,totalDue+Math.max(0,a.minLiquidity||0)-cash);
   const sponsorContribution=Math.min(sponsorNeed,availableSponsor);
   totalSponsor+=sponsorContribution;cash+=sponsorContribution;
   for(let i=0;i<notesSorted.length;i++){
     const f=notesSorted[i],ac=activities[i];
     const payI=Math.min(ac.couponDue,Math.max(0,cash));cash-=payI;paidInterest+=payI;f.paidInterest+=payI;ac.interestPaid=payI;
     const payP=Math.min(ac.principalDue,Math.max(0,cash));cash-=payP;paidPrincipal+=payP;f.balance-=payP;f.paidPrincipal+=payP;ac.principalPaid=payP;
     ac.closingBalance=f.balance;
     if(ac.couponDue-payI>1e-8||ac.principalDue-payP>1e-8){defaulted=true;if(defaultMonth===null)defaultMonth=m;}
   }
   // Reserve targets are additive by facility. Deficiency blocks distribution. Reserve cash
   // is restricted, so cannot be used to silently pay debt absent documented draw rights.
   let reserveFunding=0,reserveShortfall=0;
   for(const f of notesSorted){const target=f.type==='note'&&f.balance>0?n(f.dsraFixedM??0,'dsraFixedM'):0;
     if(f.reserve>target){cash+=f.reserve-target;reserveFunding-=f.reserve-target;f.reserve=target;}
     if(f.reserve<target){const add=Math.min(target-f.reserve,Math.max(0,cash-(a.minLiquidity||0)));f.reserve+=add;cash-=add;reserveFunding+=add;}
     reserveShortfall+=Math.max(0,target-f.reserve);
   }
   endingReserve=notesSorted.reduce((s,f)=>s+f.reserve,0);
   const unfundedLiquidity=Math.max(0,(a.minLiquidity||0)-cash);
   if(unfundedLiquidity>1e-8){const extra=Math.min(unfundedLiquidity,Math.max(0,commitment-totalSponsor));totalSponsor+=extra;cash+=extra;}
   if(cash<(a.minLiquidity||0)-1e-8){defaulted=true;if(defaultMonth===null)defaultMonth=m;}
   const debtOutstanding=notesSorted.some(f=>f.balance>1e-8);
   const dscr=totalDue>0?op.cfads/totalDue:null;
   const inBreach=dscr!==null&&op.leaseRevenue>0&&dscr<(a.dscrCovenant??1.2); // no pre-revenue maintenance DSCR test without contractual definition
   const locked=defaulted||reserveShortfall>1e-8||inBreach||debtOutstanding&&(dscr===null||dscr<(a.distributionDscrMin??1.2));
   let distribution=0;
   if(!locked&&m<term){distribution=Math.max(0,cash-(a.minLiquidity||0));cash-=distribution;}
   let terminalProceeds=0,terminalDebtPayoff=0;
   if(m===term){
      // Terminal enterprise value and recovery are synthetic sensitivity inputs, not lender appraisals.
      terminalProceeds=(a.exitValueM??0)*(1-(a.exitCostPct??0)/100);
      cash+=terminalProceeds;
      for(const f of notesSorted){const pay=Math.min(f.balance,Math.max(0,cash));f.balance-=pay;cash-=pay;terminalDebtPayoff+=pay;}
      unpaidAtExit=notesSorted.reduce((s,f)=>s+f.balance,0);
      if(unpaidAtExit>1e-8){defaulted=true;if(defaultMonth===null)defaultMonth=m;}
      cash+=endingReserve;endingReserve=0;for(const f of notesSorted)f.reserve=0;
      if(!defaulted){distribution+=Math.max(0,cash);cash-=distribution;}
   }
   equityFlows.push(distribution-sponsorContribution);
   const closingDebt=notesSorted.reduce((s,f)=>s+f.balance,0);
   const debtResidual=round(closingDebt-(openingTotalDebt+activities.reduce((s,t)=>s+t.nominalIssue+t.draw,0)-paidPrincipal-terminalDebtPayoff));
   const cashResidual=round(cash-(openingCash+op.cfads+op.tenantCashReceipt-op.capex+draws+sponsorContribution-paidInterest-paidPrincipal-reserveFunding-distribution+terminalProceeds-terminalDebtPayoff+(m===term?openingReserve+reserveFunding:0)));
   rows.push({month:m,cfads:op.cfads,leaseRevenue:op.leaseRevenue,capex:op.capex,tenantCashReceipt:op.tenantCashReceipt,draws,oid,interestDue,principalDue,paidInterest,paidPrincipal,debtService:paidInterest+paidPrincipal,dscr,breach:inBreach,defaulted,reserveShortfall,reserve:endingReserve,reserveFunding,sponsorContribution,totalSponsor,distribution,terminalProceeds,terminalDebtPayoff,cash,openingCash,closingDebt,unpaidAtExit,debtResidual,cashResidual,facilities:activities});
   // Conservative halt: do not simulate financed construction, operating revenue, distributions,
   // debt repayment or asset recovery after funding/payment default. These require a sourced workout.
   if(defaulted&&m<term)break;
 }
 const npv=defaulted?null:equityFlows.reduce((s,v,i)=>s+v/Math.pow(1+(a.discount??10)/100,i/12),0);
 const issueWarn=facilities.some(f=>!f.sourceId||f.sourceId.startsWith('ASSUMPTION'));
 return {summary:{npvM:npv,finalCashM:cash,unpaidDebtAtExitM:defaulted&&defaultMonth<term?null:unpaidAtExit,defaulted,defaultMonth,modeledMonths:rows.length,endingDebtM:rows.at(-1).closingDebt,breachMonths:rows.filter(r=>r.breach).map(r=>r.month),maxCashResidual:Math.max(...rows.map(r=>Math.abs(r.cashResidual))),maxDebtResidual:Math.max(...rows.map(r=>Math.abs(r.debtResidual))),facilityCount:facilities.length,assurance:'UNVERIFIED SCENARIO — NOT LENDER GRADE',warnings:['Financing waterfalls are screening conventions; legal priority/collateral and note covenants are NOT verified.',...(issueWarn?['One or more facility assumptions have no executed document source.']:[]),...(a.sponsorCommitmentM==null?['Unlimited sponsor capital assumed.']:[]),...(defaulted?['Cash shortfall/default: simulation stops; no terminal recovery or post-default project NPV is calculated.']:[])]},rows,facilities:[...sc.values()].map(f=>({id:f.id,type:f.type,scope:f.buildingNames,balance:f.balance,issued:f.issued,paidInterest:f.paidInterest,paidPrincipal:f.paidPrincipal,sourceId:f.sourceId||null})),underlyingOperationsSource:'PowerPathUnderwrite25.evaluate v25.8.5',assumptions:raw};
}
function render(){const box=document.getElementById('finance259Content');if(!box)return;
 let current=sample(),result=null;
 box.innerHTML=`<div class="finhero"><div><div class="fin-label">CONTROLLED FINANCIAL SANDBOX</div><h2>Build a financing structure, not just a single loan.</h2><p>Use the same project operations as Economics. Each facility has a defined borrower asset scope, issuance timing, rate, principal schedule and reserve. No public transaction is validated by this example.</p></div><div class="finwarning"><strong>Not lender certified</strong><span>Contract-specific cash waterfalls and recovery rights must be independently documented and reviewed.</span></div></div>
 <div class="finlayout"><div class="fin-editor"><div class="fin-row"><h3>Facility configuration</h3><button id="finReset">Reset example</button></div><p class="small">Start with a simple fixed-note scenario, or import your active project's saved underwriting assumptions. All terms remain hypothetical until sourced.</p><div class="fin-quick"><label>Notes issued ($M)<input id="finFace" type="number" step="1" min="0" value="180"></label><label>Coupon rate (%)<input id="finCoupon" type="number" step="0.1" min="0" max="100" value="9.25"></label><label>Final maturity (month)<input id="finMaturity" type="number" step="1" min="1" value="96"></label></div><div class="fin-actions"><button id="finApply" class="primary">Apply &amp; calculate</button><button id="finImport">Use saved project model</button></div><details class="fin-details"><summary>Advanced: facility and project JSON</summary><p class="small">Edit building scope, payment dates, reserves and principal triggers. Inputs must be confirmed separately against the relevant agreements.</p><textarea id="finInput" aria-label="Edit project and financing facility JSON" spellcheck="false"></textarea></details><div class="fin-actions"><button id="finRun" class="primary">Run facility waterfall</button><button id="finCSV">Export monthly ledger</button></div><div id="finError" role="alert"></div></div><div class="fin-results"><div id="finStats"></div><h3>Facility ledger</h3><div id="finFacilities"></div><h3>Monthly obligations</h3><div id="finMonthly" class="table-wrap"></div></div></div>`;
 const input=box.querySelector('#finInput'),warning=box.querySelector('#finError');
 const load=()=>{input.value=JSON.stringify(sample(),null,2);box.querySelector('#finFace').value=180;box.querySelector('#finCoupon').value=9.25;box.querySelector('#finMaturity').value=96;box.querySelector('#finRun').click()};
 box.querySelector('#finApply').onclick=()=>{try{const v=JSON.parse(input.value);const f=v.facilities.find(x=>x.type==='note');if(!f)throw Error('No fixed note facility in this scenario');f.faceM=n(box.querySelector('#finFace').value,'faceM');f.couponPct=n(box.querySelector('#finCoupon').value,'couponPct');f.maturityMonth=Math.round(n(box.querySelector('#finMaturity').value,'maturityMonth',1));input.value=JSON.stringify(v,null,2);run()}catch(err){warning.textContent=err.message}};
 box.querySelector('#finImport').onclick=()=>{try{const id=typeof dev!=='undefined'?dev.projectId:null;if(!id)throw Error('Select a project from Project overview first');const stored=localStorage.getItem('powerpath-v251-'+id);if(!stored)throw Error('Run and save Underwrite from the selected project first');const data=JSON.parse(stored);if(!Array.isArray(data.buildings)||!data.buildings.length)throw Error('Saved underwriting project has no buildings');const cfg=JSON.parse(input.value);cfg.project={...root.PowerPathUnderwrite25.defaults(),...data};const names=data.buildings.map(b=>b.name);for(const f of cfg.facilities){f.buildingNames=f.type==='note'?names.slice(0,Math.max(1,Math.min(2,names.length))):names;f.sourceId='ASSUMPTION: imported local project; financing terms NOT verified';}input.value=JSON.stringify(cfg,null,2);warning.textContent='Imported saved project operating assumptions; note facilities remain illustrative and must be reviewed.';run();}catch(err){warning.textContent=err.message}};
 function run(){try{current=JSON.parse(input.value);result=evaluate(current);warning.textContent='';const s=result.summary;
   box.querySelector('#finFace').value=current.facilities.find(f=>f.type==='note')?.faceM??0;box.querySelector('#finCoupon').value=current.facilities.find(f=>f.type==='note')?.couponPct??0;box.querySelector('#finMaturity').value=current.facilities.find(f=>f.type==='note')?.maturityMonth??0;box.querySelector('#finStats').innerHTML=`<div class="fin-security"><b>UNVERIFIED SCENARIO</b><span>${s.warnings.map(escape).join(' · ')}</span></div><div class="fin-kpis">${[['Modeled equity NPV',s.npvM===null?'N/A — default':'$'+s.npvM.toFixed(1)+'M'],['Ending debt','$'+s.endingDebtM.toFixed(1)+'M'],['Covenant breach months',String(s.breachMonths.length)],['Funding default',s.defaulted?'YES':'Not modeled'],['Reconciliation','Cash '+s.maxCashResidual.toExponential(1)+'M']].map(([k,v])=>`<div><small>${escape(k)}</small><b>${escape(v)}</b></div>`).join('')}</div>`;
   box.querySelector('#finFacilities').innerHTML=`<div class="fin-facs">${result.facilities.map(f=>`<div><strong>${escape(f.id)}</strong><small>${escape(f.type)} · ${escape(f.scope.join(', '))}</small><span>Ending $${f.balance.toFixed(2)}M · ${escape(f.sourceId||'NO SOURCE')}</span></div>`).join('')}</div>`;
   box.querySelector('#finMonthly').innerHTML=`<table><thead><tr>${['Month','CFADS','Debt drawn','Interest due','Principal due','Debt paid','Debt balance','Sponsor cash','DSCR','Default'].map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${result.rows.map(r=>`<tr><td>${r.month}</td>${[r.cfads,r.draws,r.interestDue,r.principalDue,r.debtService,r.closingDebt,r.sponsorContribution].map(x=>`<td>${x.toFixed(2)}</td>`).join('')}<td>${r.dscr==null?'—':r.dscr.toFixed(2)+'x'}</td><td>${r.defaulted?'⚠':'—'}</td></tr>`).join('')}</tbody></table>`;
 }catch(err){warning.textContent='Unable to calculate: '+err.message;result=null;}}
 function escape(x){return String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
 box.querySelector('#finRun').onclick=run;box.querySelector('#finReset').onclick=load;
 box.querySelector('#finCSV').onclick=()=>{if(!result)return;const k=['month','cfads','capex','draws','oid','interestDue','principalDue','paidInterest','paidPrincipal','cash','closingDebt','reserve','sponsorContribution','distribution','debtResidual','cashResidual'];const body=[['ASSURANCE','UNVERIFIED SCREENING - NOT LENDER GRADE'].join(','),k.join(','),...result.rows.map(r=>k.map(t=>r[t]??'').join(','))].join('\n');const url=URL.createObjectURL(new Blob([body],{type:'text/csv'}));const a=document.createElement('a');a.href=url;a.download='PowerPath_v259_Facility_Waterfall_UNVERIFIED.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};load();
}
root.PowerPathFacilities259={evaluate,sample,render,validate};
if(typeof module!=='undefined'&&module.exports)module.exports={evaluate,sample,validate};

})(typeof window!=='undefined'?window:globalThis);
