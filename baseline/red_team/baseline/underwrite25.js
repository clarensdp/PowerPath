/* PowerPath v25.8 — transaction-audit fixes: tranche-rent cohorts, closed debt facilities, reserve integrity. $M. */
(function(root){'use strict';
const finite=(v,k,min=0)=>{v=Number(v);if(!Number.isFinite(v)||v<min)throw Error(k+' must be finite and >= '+min);return v};
const defaults=()=>({months:120,calendarStartYear:2026,calendarStartMonth:1,discount:10,rate:8,ltc:65,debtFee:1,termMonths:60,amortMonths:240,dscrCovenant:1.20,minLiquidity:10,initialCash:50,reserveTargetM:10,rentPerKwMonth:170,pue:1.3,powerCostMWh:85,otherOpexPct:12,fixedOpexM:0.4,constructionCostMW:7,delayMonths:0,overrunPct:0,rateShockPct:0,energyShockPct:0,refinanceLtvPct:60,refinanceValueM:1400,refinanceRatePct:7,refinanceFeePct:1,exitValueM:1800,exitCostPct:2,loanMaturityMode:'refinance',distributionPolicy:'excess',capacityBasis:'IT',tenantCapexPct:0,tenantFundingLagMonths:0,tenantRentCreditPct:0,tenantCreditMonths:0,debtYieldMinPct:8,refinanceDscrMin:1.25,refinanceAmortMonths:240,mezzLtcPct:0,mezzRatePct:13,mezzFeePct:2,cashSweepPct:0,distributionDscrMin:1.20,lockDistributionsOnBreach:true,dsraMonths:0,dsraReleaseAtExit:true,sponsorCommitmentM:null,cashTaxRatePct:0,maintenanceCapexMWYearM:0,workingCapitalDays:0,buildings:[{name:'Building A',itMW:50,constructionStart:1,constructionMonths:18,powerMonth:19,leaseMonth:19,leaseTermMonths:180,rentEscalatorPct:2.5},{name:'Building B',itMW:50,constructionStart:10,constructionMonths:18,powerMonth:28,leaseMonth:28,leaseTermMonths:180,rentEscalatorPct:2.5},{name:'Building C',itMW:50,constructionStart:19,constructionMonths:18,powerMonth:37,leaseMonth:37,leaseTermMonths:180,rentEscalatorPct:2.5}],powerTranches:[]});
function irr(flows){if(!flows.some(x=>x<0)||!flows.some(x=>x>0))return null;let npv=r=>flows.reduce((s,v,i)=>s+v/((1+r)**(i/12)),0);let low=-.999,high=5,f0=npv(low),f1=npv(high);if(f0*f1>0)return null;for(let j=0;j<150;j++){let mid=(low+high)/2,f=npv(mid);if(f0*f>0){low=mid;f0=f}else high=mid}return (low+high)/2}
// Rent basis: never interpret a disclosed all-in lease value as a starting annual rent.
function rentSchedule(b,globalRent){
 const mode=b.rentInputMode||'starting';const term=Math.round(b.leaseTermMonths??180),mw=b._itMW;
 const esc=(b.rentEscalatorPct??2.5)/100;
 if(!['starting','total','schedule'].includes(mode))throw Error('Invalid rent input mode');
 if(mode==='total'){
  const target=finite(b.contractedRentM,'contractedRentM',.000001);
  const factor=Array.from({length:term},(_,i)=>Math.pow(1+esc,Math.floor(i/12))).reduce((x,y)=>x+y,0);
  return {mode,monthly:age=>mw*1000*(target*1e6/(mw*1000*factor))*Math.pow(1+esc,Math.floor(age/12))/1e6,target,baseRate:target*1e6/(mw*1000*factor)};
 }
 if(mode==='schedule'){
  const years=Array.isArray(b.annualRentM)?b.annualRentM: String(b.annualRentM||'').split(',').filter(Boolean).map(Number);
  if(years.length!==Math.ceil(term/12))throw Error('Explicit schedule must have one annual rental value per lease year');
  years.forEach((v,i)=>finite(v,'annualRentM '+(i+1)));
  const total=years.reduce((acc,v,i)=>acc+v*Math.min(12,term-i*12)/12,0);
  return {mode,monthly:age=>years[Math.floor(age/12)]/12,target:total,baseRate:null};
 }
 const rate=b.rentPerKwMonth??globalRent;finite(rate,'starting rent');
 const target=typeof b.contractedRentM==='number'&&Number.isFinite(b.contractedRentM)?finite(b.contractedRentM,'contractedRentM'):null;
 return {mode,monthly:age=>mw*1000*rate*Math.pow(1+esc,Math.floor(age/12))/1e6,target,baseRate:rate};
}
function rentAudit(buildings,globalRent,pue,globalBasis){return buildings.map(b=>{
 const it=b.itMW/((b.capacityBasis||globalBasis)==='gross'?pue:1);const t=Math.round(b.leaseTermMonths??180);
 const r=rentSchedule({...b,_itMW:it},globalRent);let modeled=0;
 for(let i=0;i<t;i++)modeled+=r.monthly(i);
 const variance=r.target==null?null:modeled-r.target,variancePct=r.target==null?null:100*variance/r.target;
 const reconciled=r.target!=null&&Math.abs(variancePct)<=.1;
 return {building:b.name,mode:r.mode,contractedRentM:r.target,modeledContractRentM:modeled,varianceM:variance,variancePct,startingRentPerKwMonth:r.baseRate,sourceRef:b.leaseSourceRef||'',reconciled,hasDocumentReference:Boolean(String(b.leaseSourceRef||'').trim()),status:r.target==null?'No contracted value for reconciliation':reconciled?'Arithmetic reconciled; source review required':'BLOCKED: contracted value mismatch'};
})}
function evaluate(input={}){
 const d=defaults(), a={...d,...input};
 a.buildings=(input.buildings||d.buildings).map(b=>({...b}));
 a.powerTranches=(input.powerTranches||[]).map(t=>({...t}));
 const months=Math.round(finite(a.months,'months',12));if(months>360)throw Error('months > 360');
 const checks=['calendarStartYear','calendarStartMonth','discount','rate','ltc','debtFee','rentPerKwMonth','pue','powerCostMWh','otherOpexPct','fixedOpexM','constructionCostMW','delayMonths','overrunPct','rateShockPct','energyShockPct','initialCash','dscrCovenant','minLiquidity','reserveTargetM','refinanceLtvPct','refinanceValueM','refinanceRatePct','refinanceFeePct','exitValueM','exitCostPct','tenantCapexPct','tenantFundingLagMonths','tenantRentCreditPct','tenantCreditMonths','debtYieldMinPct','refinanceDscrMin','refinanceAmortMonths','mezzLtcPct','mezzRatePct','mezzFeePct','cashSweepPct','distributionDscrMin','dsraMonths','cashTaxRatePct','maintenanceCapexMWYearM','workingCapitalDays'];
 for(const k of checks) finite(a[k],k);
 if(a.sponsorCommitmentM!==null&&a.sponsorCommitmentM!==undefined&&a.sponsorCommitmentM!==''){
  a.sponsorCommitmentM=finite(a.sponsorCommitmentM,'sponsorCommitmentM');
  if(a.sponsorCommitmentM<a.initialCash-1e-8)throw Error('Sponsor commitment cannot be below opening sponsor cash');
 }else a.sponsorCommitmentM=null;
 if(!Number.isInteger(a.calendarStartYear)||a.calendarStartYear<2000||a.calendarStartYear>2200||!Number.isInteger(a.calendarStartMonth)||a.calendarStartMonth<1||a.calendarStartMonth>12)throw Error('Invalid start calendar year/month');
 if(a.dsraMonths>24||a.cashSweepPct>100||a.ltc+a.mezzLtcPct>100||a.ltc>100||a.tenantCapexPct>100||a.tenantRentCreditPct>100||a.otherOpexPct>100||a.cashTaxRatePct>100||a.workingCapitalDays>365||a.tenantFundingLagMonths>36||!Number.isInteger(a.tenantFundingLagMonths)||a.pue<1||a.refinanceLtvPct>100||a.exitCostPct>100||a.buildings.length<1||a.buildings.length>20||!['IT','gross'].includes(a.capacityBasis))throw Error('Invalid financial assumptions');
 finite(a.termMonths,'termMonths',1);finite(a.amortMonths,'amortMonths',1);
 if(!['refinance','equity','default'].includes(a.loanMaturityMode))throw Error('Invalid maturity mode');
 for(const b of a.buildings){
  for(const k of ['itMW','constructionStart','constructionMonths','powerMonth','leaseMonth'])finite(b[k],k,k==='itMW'?.01:1);
  if(b.constructionStart+b.constructionMonths-1>months)throw Error('Building construction outside horizon');
  if(b.leaseTermMonths!==undefined){finite(b.leaseTermMonths,'leaseTermMonths',1);if(!Number.isInteger(b.leaseTermMonths))throw Error('Lease term must be whole months')}
  if(b.rentEscalatorPct!==undefined&&finite(b.rentEscalatorPct,'rentEscalatorPct')>100)throw Error('Rent escalator above 100%');
  if(b.rentPerKwMonth!==undefined)finite(b.rentPerKwMonth,'building rent');
  if(b.tenantCapexPct!==undefined&&finite(b.tenantCapexPct,'building tenant capex')>100)throw Error('Building tenant capex above 100%');
  if(b.tenantRentCreditPct!==undefined&&finite(b.tenantRentCreditPct,'building rent credit')>100)throw Error('Building rent credit above 100%');
  if(b.capacityBasis&&!['IT','gross'].includes(b.capacityBasis))throw Error('Unknown capacity basis');
  if(b.contractedRentM!==undefined&&b.contractedRentM!=='')finite(b.contractedRentM,'contractedRentM',.000001);
 }
 for(const t of a.powerTranches){finite(t.mw,'tranche MW',.001);finite(t.month,'tranche month',1);if(t.building!==undefined&&!a.buildings.some(b=>b.name===t.building))throw Error('Unknown tranche building')}
 for(const b of a.buildings){const assigned=a.powerTranches.filter(t=>t.building===b.name).reduce((v,t)=>v+t.mw,0);if(assigned> b.itMW/((b.capacityBasis||a.capacityBasis)==='gross'?a.pue:1)+1e-8)throw Error('Assigned power tranches exceed '+b.name+' IT MW')}
 const itMW=b=>b.itMW/((b.capacityBasis||a.capacityBasis)==='gross'?a.pue:1);
 const leaseAudits=rentAudit(a.buildings,a.rentPerKwMonth,a.pue,a.capacityBasis);
 const rentalMethods=new Map(a.buildings.map(b=>[b.name,rentSchedule({...b,_itMW:itMW(b)},a.rentPerKwMonth)]));
 const hoursInMonth=(m)=>{const monthIndex=a.calendarStartMonth-1+m-1;const year=a.calendarStartYear+Math.floor(monthIndex/12);const zeroMon=((monthIndex%12)+12)%12;return new Date(Date.UTC(year,zeroMon+1,0)).getUTCDate()*24};
 // Physical commissioning and lease commencement are distinct. Each newly energized
 // portion begins its own contractual payment age when physically ready for service.
 // A shared supply tranche is allocated deterministically in building input order;
 // this policy is a screening assumption, NOT a contractual allocation.
 const cohortsByBuilding=new Map(a.buildings.map(b=>[b.name,[]]));
 const physicalByMonth=[];
 const lastPhysical=new Map(a.buildings.map(b=>[b.name,0]));
 for(let month=0;month<=months+12;month++){
  let shared=a.powerTranches.filter(t=>!t.building&&t.month+a.delayMonths<=month).reduce((v,t)=>v+t.mw,0);
  let grossR=0,credits=0,rentedMw=0,physicalMw=0;
  for(const b of a.buildings){
   const mw=itMW(b),done=b.constructionStart+b.constructionMonths-1;
   const ready=Math.max(done+1,b.leaseMonth+a.delayMonths,b.powerMonth+a.delayMonths);
   let delivered=0;
   if(month>=ready){
    if(a.powerTranches.length){
     const dedicated=a.powerTranches.filter(t=>t.building===b.name&&t.month+a.delayMonths<=month).reduce((v,t)=>v+t.mw,0);
     const portion=Math.min(Math.max(0,mw-dedicated),shared);
     shared-=portion;
     delivered=Math.min(mw,dedicated+portion);
    }else delivered=mw;
   }
   physicalMw+=delivered;
   const previous=lastPhysical.get(b.name);
   if(delivered+1e-8<previous)throw Error('Physical supply allocation fell for '+b.name+'; explicit curtailment required');
   if(delivered>previous+1e-9)cohortsByBuilding.get(b.name).push({mw:delivered-previous,start:month});
   lastPhysical.set(b.name,delivered);
   const term=b.leaseTermMonths??180;
   const rentMethod=rentalMethods.get(b.name);
   for(const cohort of cohortsByBuilding.get(b.name)){
    const age=month-cohort.start;
    if(age<0||age>=term)continue;
    rentedMw+=cohort.mw;
    const rental=rentMethod.monthly(age)*cohort.mw/mw;
    grossR+=rental;
    if(age<(b.tenantCreditMonths??a.tenantCreditMonths))credits+=rental*(b.tenantRentCreditPct??a.tenantRentCreditPct)/100;
   }
  }
  physicalByMonth.push({grossRevenue:grossR,rentCredits:credits,onlineMW:rentedMw,availableMW:physicalMw});
 }
 // Independent of debt accounting. This also underpins forward CFADS refinancing.
 function operations(m){
  let capex=0,tenantFundedCapex=0;
  for(const b of a.buildings){
   const mw=itMW(b),done=b.constructionStart+b.constructionMonths-1;
   const gross=m>=b.constructionStart&&m<=done?mw*a.constructionCostMW*(1+a.overrunPct/100)/b.constructionMonths:0;
   capex+=gross;
   tenantFundedCapex+=gross*(b.tenantCapexPct??a.tenantCapexPct)/100;
  }
  const physical=physicalByMonth[Math.max(0,Math.min(physicalByMonth.length-1,m))];
  const {grossRevenue,rentCredits,onlineMW,availableMW}=physical;
  const revenue=grossRevenue-rentCredits;
  const energy=onlineMW*a.pue*hoursInMonth(m)*a.powerCostMWh*(1+a.energyShockPct/100)/1e6;
  const opex=revenue*a.otherOpexPct/100+(onlineMW?a.fixedOpexM:0);
  const ebitda=revenue-energy-opex;
  const cashTaxes=Math.max(0,ebitda)*a.cashTaxRatePct/100; // Proxy, not a tax-return calculation.
  const maintenanceCapex=onlineMW*a.maintenanceCapexMWYearM/12;
  const workingCapitalBalance=Math.max(0,revenue)*a.workingCapitalDays/30;
  return {month:m,capex,tenantFundedCapex,grossRevenue,rentCredits,onlineMW,availableMW,revenue,energy,opex,ebitda,cashTaxes,maintenanceCapex,workingCapitalBalance};
 }
 function cfadsMonth(m){const x=operations(m),prior=operations(m-1);return x.ebitda-x.cashTaxes-x.maintenanceCapex-(x.workingCapitalBalance-prior.workingCapitalBalance)}
 const flows=[-a.initialCash],rows=[];let cash=a.initialCash,reserve=0,debt=0,mezz=0,totalTenantReceivable=0,totalSponsor=a.initialCash,draws=0,mezzDraws=0,principalPaid=0,interestTotal=0,feeTotal=0,peakDebt=0,firstDebtMonth=null,maturityMonth=null,refiOccurred=false,constructionFacilityClosed=false,defaulted=false,liquidityBreaches=[],covenantBreaches=[],refinanceSizing=null,fundingDefault=false,unpaidDebtAtExitM=0;
 const initialDebtRate=(a.rate+a.rateShockPct)/1200;
 const sponsorRemaining=()=>a.sponsorCommitmentM===null?Infinity:Math.max(0,a.sponsorCommitmentM-totalSponsor);
 const drawSponsor=needed=>{const actual=Math.min(Math.max(0,needed),sponsorRemaining());totalSponsor+=actual;return actual};
 for(let m=1;m<=months;m++){
  const op=operations(m),prev=operations(m-1);
  const {capex,tenantFundedCapex,grossRevenue,rentCredits,onlineMW,availableMW,revenue,energy,opex,ebitda,cashTaxes,maintenanceCapex}=op;
  const tenantCashReceipt=m>a.tenantFundingLagMonths?operations(m-a.tenantFundingLagMonths).tenantFundedCapex:0;
  totalTenantReceivable+=tenantFundedCapex-tenantCashReceipt;
  const workingCapitalChange=op.workingCapitalBalance-prev.workingCapitalBalance;
  const cfads=ebitda-cashTaxes-maintenanceCapex-workingCapitalChange;
  const openingSeniorDebt=debt,openingMezzDebt=mezz,openingReserve=reserve,openingCash=cash;
  const sponsorEligibleCapex=capex-tenantFundedCapex;
  const seniorDraw=constructionFacilityClosed||defaulted?0:sponsorEligibleCapex*a.ltc/100;
  const mezzDraw=constructionFacilityClosed||defaulted?0:sponsorEligibleCapex*a.mezzLtcPct/100;
  const fee=seniorDraw*a.debtFee/100+mezzDraw*a.mezzFeePct/100;
  debt+=seniorDraw;mezz+=mezzDraw;draws+=seniorDraw;mezzDraws+=mezzDraw;feeTotal+=fee;
  if((seniorDraw+mezzDraw)>0&&firstDebtMonth===null){firstDebtMonth=m;maturityMonth=firstDebtMonth+Math.round(a.termMonths)-1}
  const seniorInterest=debt*(refiOccurred?a.refinanceRatePct/1200:initialDebtRate),mezzInterest=mezz*a.mezzRatePct/1200;
  const interest=seniorInterest+mezzInterest;interestTotal+=interest;
  const constructing=a.buildings.some(b=>m>=b.constructionStart&&m<b.constructionStart+b.constructionMonths);
  const capitalizedInterest=!refiOccurred&&constructing?interest:0,cashInterest=interest-capitalizedInterest;
  const capSenior=capitalizedInterest*(interest?seniorInterest/interest:1),capMezz=capitalizedInterest-capSenior;
  debt+=capSenior;mezz+=capMezz;
  let principal=0,mezzPrincipal=0,refinanceProceeds=0,refinanceFee=0,maturityShortfall=0,sweepPrincipal=0;
  let forward12CfadsM=null,forward12NoiM=null;
  if(maturityMonth!==null&&m===maturityMonth&&!refiOccurred){
   const oldDebt=debt,oldMezz=mezz;
   if(defaulted){maturityShortfall=oldDebt+oldMezz;fundingDefault=true}
   else if(a.loanMaturityMode==='refinance'){
    forward12CfadsM=0;forward12NoiM=0;
    for(let j=1;j<=12;j++){const f=operations(m+j);forward12CfadsM+=cfadsMonth(m+j);forward12NoiM+=f.ebitda-f.maintenanceCapex}
    const r=a.refinanceRatePct/1200,n=Math.max(1,Math.round(a.refinanceAmortMonths));
    const paymentPerDollar=r===0?1/n:r/(1-Math.pow(1+r,-n));
    const ltvLimit=a.refinanceValueM*a.refinanceLtvPct/100;
    const dscrLimit=Math.max(0,forward12CfadsM)/Math.max(.01,a.refinanceDscrMin)/(12*paymentPerDollar);
    const yieldLimit=a.debtYieldMinPct>0?Math.max(0,forward12NoiM)/(a.debtYieldMinPct/100):Infinity;
    const newDebt=Math.max(0,Math.min(ltvLimit,dscrLimit,yieldLimit));
    refinanceSizing={ltvLimit,dscrLimit,yieldLimit,selected:newDebt,forward12CfadsM,forward12NoiM,binding:newDebt===ltvLimit?'LTV':newDebt===dscrLimit?'DSCR':'debt yield'};
    const requiredFee=newDebt*a.refinanceFeePct/100;
    // Refinance may not close if cash and enforceable sponsor commitment cannot pay the shortfall.
    const beforePayoff=cash+cfads+seniorDraw+mezzDraw+tenantCashReceipt-capex-fee-cashInterest;
    const availableForPayoff=Math.max(0,beforePayoff-a.minLiquidity)+sponsorRemaining();
    const gap=Math.max(0,oldDebt+oldMezz+requiredFee-newDebt-availableForPayoff);
    if(gap>1e-8){defaulted=true;maturityShortfall=gap;fundingDefault=true;refinanceSizing.failed=true}
    else{refinanceProceeds=newDebt;refinanceFee=requiredFee;feeTotal+=refinanceFee;principal=oldDebt;mezzPrincipal=oldMezz;debt=newDebt;mezz=0;refiOccurred=true;constructionFacilityClosed=true}
   }else if(a.loanMaturityMode==='equity'){
    const beforePayoff=cash+cfads+seniorDraw+mezzDraw+tenantCashReceipt-capex-fee-cashInterest;
    const gap=Math.max(0,oldDebt+oldMezz-(Math.max(0,beforePayoff-a.minLiquidity)+sponsorRemaining()));
    if(gap>1e-8){defaulted=true;maturityShortfall=gap;fundingDefault=true}
    else{principal=oldDebt;mezzPrincipal=oldMezz;debt=0;mezz=0;constructionFacilityClosed=true}
   }else{defaulted=true;maturityShortfall=oldDebt+oldMezz}
  }else if(refiOccurred&&m>maturityMonth){principal=Math.min(debt,debt/Math.max(1,a.refinanceAmortMonths-(m-maturityMonth-1)));debt-=principal}
  principalPaid+=principal+mezzPrincipal;
  // DSCR excludes mandatory maturity balloon, refinancing transactions and voluntary sweeps.
  const scheduledDebtService=cashInterest+(m===maturityMonth?0:principal+mezzPrincipal);
  const dscr=scheduledDebtService>0?cfads/scheduledDebtService:null;
  const loanSources=seniorDraw+mezzDraw+refinanceProceeds;
  const operatingCash=cfads;
  let uses=capex+fee+refinanceFee+cashInterest+principal+mezzPrincipal;
  const preFundingCash=cash+operatingCash+loanSources+tenantCashReceipt-uses;
  let sponsorContribution=drawSponsor(Math.max(0,a.minLiquidity-preFundingCash));
  cash=preFundingCash+sponsorContribution;
  const unfundedGapM=Math.max(0,a.minLiquidity-cash);
  if(unfundedGapM>1e-8){defaulted=true;fundingDefault=true}
  const projectedRefiPayment=(refiOccurred&&debt>0)?(a.refinanceRatePct===0?debt/Math.max(1,a.refinanceAmortMonths-(m-maturityMonth)):debt*(a.refinanceRatePct/1200)/(1-Math.pow(1+a.refinanceRatePct/1200,-Math.max(1,a.refinanceAmortMonths-(m-maturityMonth))))):0;
  const dsraTarget=refiOccurred?a.dsraMonths*projectedRefiPayment:0;
  // Base restricted reserve and DSRA are distinct obligations, not interchangeable.
  const restrictedTarget=a.reserveTargetM+dsraTarget;
  let reserveMovement=0;
  if(reserve<restrictedTarget){reserveMovement=Math.min(restrictedTarget-reserve,Math.max(0,cash-a.minLiquidity));cash-=reserveMovement;reserve+=reserveMovement}
  else if(reserve>restrictedTarget){const release=reserve-restrictedTarget;reserveMovement=-release;reserve-=release;cash+=release}
  const reserveDeficiency=Math.max(0,restrictedTarget-reserve);
  if(reserveDeficiency>1e-8){const topup=drawSponsor(reserveDeficiency);sponsorContribution+=topup;cash+=topup;const credit=Math.min(topup,reserveDeficiency);cash-=credit;reserve+=credit;reserveMovement+=credit}
  const finalReserveDeficiency=Math.max(0,restrictedTarget-reserve);
  const debtOutstanding=debt+mezz>1e-9;
  const inBreach=dscr!==null&&dscr<a.dscrCovenant;
  const locked=finalReserveDeficiency>1e-8||defaulted||(a.lockDistributionsOnBreach!==false&&inBreach)||(debtOutstanding&&(dscr===null||dscr<a.distributionDscrMin));
  if(debtOutstanding&&!defaulted&&a.cashSweepPct>0){const excess=Math.max(0,cash-a.minLiquidity);sweepPrincipal=Math.min(debt,excess*a.cashSweepPct/100);cash-=sweepPrincipal;debt-=sweepPrincipal;principal+=sweepPrincipal;principalPaid+=sweepPrincipal}
  let distribution=0;
  if(!locked&&a.distributionPolicy==='excess'&&m<months){distribution=Math.max(0,cash-a.minLiquidity);cash-=distribution}
  let terminalProceeds=0,exitDebtPayoff=0;
  if(m===months){
   terminalProceeds=a.exitValueM*(1-a.exitCostPct/100);
   const availableForDebt=Math.max(0,cash+terminalProceeds+reserve);
   exitDebtPayoff=Math.min(debt+mezz,availableForDebt);
   const paySenior=Math.min(debt,exitDebtPayoff),payMezz=exitDebtPayoff-paySenior;
   debt-=paySenior;mezz-=payMezz;principal+=paySenior;mezzPrincipal+=payMezz;principalPaid+=exitDebtPayoff;
   unpaidDebtAtExitM=debt+mezz;
   if(unpaidDebtAtExitM>1e-8)defaulted=true;
   cash+=terminalProceeds-exitDebtPayoff+reserve;reserveMovement-=reserve;reserve=0;
   if(cash>0&&unpaidDebtAtExitM<1e-8&&!defaulted){distribution+=cash;cash=0}
  }
  const shortfall=preFundingCash<a.minLiquidity,covenant=dscr!==null&&m!==maturityMonth&&dscr<a.dscrCovenant;
  if(shortfall)liquidityBreaches.push(m);if(covenant)covenantBreaches.push(m);
  uses+=sweepPrincipal;
  flows.push(distribution-sponsorContribution);
  peakDebt=Math.max(peakDebt,debt+mezz,refinanceProceeds);
  const debtResidual=debt-(openingSeniorDebt+seniorDraw+capSenior+refinanceProceeds-principal);
  const mezzResidual=mezz-(openingMezzDebt+mezzDraw+capMezz-mezzPrincipal);
  const reserveResidual=reserve-openingReserve-reserveMovement;
  const sourcesUsesResidual=openingCash+operatingCash+loanSources+tenantCashReceipt+sponsorContribution+terminalProceeds-reserveMovement-uses-exitDebtPayoff-distribution-cash;
  rows.push({month:m,onlineMW,availableMW,grossRevenue,rentCredits,revenue,energy,opex,ebitda,cashTaxes,maintenanceCapex,workingCapitalBalance:op.workingCapitalBalance,workingCapitalChange,cfads,capex,tenantFundedCapex,tenantCashReceipt,tenantFundingReceivable:totalTenantReceivable,draw:seniorDraw,mezzDraw,fee,refinanceFee,interest,capitalizedInterest,cashInterest,principal,mezzPrincipal,debt,mezzDebt:mezz,debtService:scheduledDebtService,scheduledDebtService,dscr,breach:covenant,liquidityBreach:shortfall,openingCash,loanSources,uses,operatingCash,preFundingCash,sponsorContribution,equityContribution:sponsorContribution,distribution,netEquity:distribution-sponsorContribution,cash,reserve,reserveMovement,refinanceProceeds,sweepPrincipal,maturityShortfall,terminalProceeds,exitDebtPayoff,unpaidDebtAtExitM,unfundedGapM,sourcesUsesResidual,debtResidual,mezzResidual,reserveResidual,reserveDeficiency:finalReserveDeficiency,restrictedTarget,dsraTarget,openingSeniorDebt,openingMezzDebt,openingReserve,forward12CfadsM,forward12NoiM});
 }
 const npv=flows.reduce((sum,v,i)=>sum+v/(1+a.discount/100)**(i/12),0),equityOut=rows.reduce((sum,x)=>sum+x.distribution,0),dscrs=rows.map(r=>r.dscr).filter(Number.isFinite);
 const summary={financeabilityStatus:defaulted?(fundingDefault?'FUNDING DEFAULT — sponsor limit or refinance gap':'DEFAULT — financing assumptions not performing'):a.sponsorCommitmentM===null?'UNVERIFIED SPONSOR FUNDING — assumption-driven':leaseAudits.some(x=>!x.reconciled)?'UNRECONCILED — not validated':covenantBreaches.length?'COVENANT BREACH — review required':'MODELED — not externally validated',npvM:npv,leveredIRR:irr(flows),equityMultiple:totalSponsor?equityOut/totalSponsor:null,peakDebtM:peakDebt,interestM:interestTotal,feesM:feeTotal,principalM:principalPaid,debtDrawsM:draws,mezzDrawsM:mezzDraws,equityInvestedM:totalSponsor,equityDistributionsM:equityOut,minDSCR:dscrs.length?Math.min(...dscrs):null,minCashM:Math.min(...rows.map(r=>r.cash)),breachMonths:covenantBreaches,liquidityBreachMonths:liquidityBreaches,maturityMonth,refinanced:refiOccurred,refinanceSizing,defaulted,fundingDefault,unpaidDebtAtExitM,endingDebtM:debt+mezz,endingReserveM:reserve,sweepPrincipalM:rows.reduce((s,r)=>s+r.sweepPrincipal,0),sourcesUsesMaxResidual:Math.max(...rows.map(r=>Math.abs(r.sourcesUsesResidual))),debtMaxResidual:Math.max(...rows.flatMap(r=>[Math.abs(r.debtResidual),Math.abs(r.mezzResidual)])),reserveMaxResidual:Math.max(...rows.map(r=>Math.abs(r.reserveResidual))),dsraDeficiencyMonths:rows.filter(r=>r.reserveDeficiency>1e-8).map(r=>r.month),sponsorCommitmentM:a.sponsorCommitmentM,sponsorRemainingM:a.sponsorCommitmentM===null?null:Math.max(0,a.sponsorCommitmentM-totalSponsor),unfundedMonths:rows.filter(r=>r.unfundedGapM>1e-8).map(r=>r.month),operatingMWh:rows.reduce((sum,r)=>sum+r.onlineMW*a.pue*730,0),tenantFundingM:rows.reduce((sum,r)=>sum+r.tenantFundedCapex,0),rentCreditsM:rows.reduce((sum,r)=>sum+r.rentCredits,0),cumulativeCfadsM:rows.reduce((sum,r)=>sum+r.cfads,0),leaseAudits,leaseReconciliationBlocked:leaseAudits.some(x=>!x.reconciled),financialValidationStatus:'NOT INDEPENDENTLY VALIDATED'};
 return {assumptions:a,rows,summary,flows};
}

const escapeHtml=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(node,project){const key='powerpath-v251-'+project.id;let state;try{state=JSON.parse(localStorage.getItem(key)||'null')}catch{}state=state||defaults();let last=null;const numeric=[['calendarStartYear','Calendar year of model M1'],['calendarStartMonth','Calendar month of model M1 (1–12)'],['rentPerKwMonth','Rent ($/kW-mo)'],['constructionCostMW','Construction ($M/IT MW)'],['ltc','Construction LTC (%)'],['rate','Construction rate (%)'],['termMonths','Construction maturity (months)'],['refinanceLtvPct','Refinance LTV (%)'],['refinanceValueM','Refinance value ($M)'],['refinanceRatePct','Refinance rate (%)'],['exitValueM','Exit value ($M)'],['initialCash','Opening sponsor cash ($M)'],['minLiquidity','Minimum liquidity ($M)'],['reserveTargetM','Restricted reserve ($M)'],['delayMonths','Power delay (months)'],['overrunPct','Capex overrun (%)'],['dscrCovenant','DSCR covenant'],['powerCostMWh','Power ($/MWh)'],['tenantCapexPct','Tenant-funded capex (%)'],['tenantFundingLagMonths','Tenant reimbursement delay (months)'],['tenantRentCreditPct','Tenant rent credits (%)'],['tenantCreditMonths','Credit duration (months)'],['debtYieldMinPct','Refinance minimum debt yield (%)'],['refinanceDscrMin','Refinance minimum DSCR'],['refinanceAmortMonths','Refinance amortization (months)'],['cashSweepPct','Optional senior cash sweep (%)'],['dsraMonths','DSRA months of term-loan debt service'],['cashTaxRatePct','Cash tax proxy (%)'],['maintenanceCapexMWYearM','Maintenance capex ($M/IT MW/yr)'],['workingCapitalDays','Working capital days'],['distributionDscrMin','Distribution DSCR threshold'],['mezzLtcPct','Mezzanine LTC (%)'],['mezzRatePct','Mezzanine rate (%)'],['pue','PUE (gross-to-IT conversion)']];
node.innerHTML=`<h3>Staged campus and levered financing · v25.8</h3><p class="v21-muted">Monthly sources-and-uses reconciliation, separately funded sponsor equity and reserves, explicit construction maturity, refinance or equity payoff, exit proceeds, and power-tranche capacity. $M unless indicated. Screening assumptions, not lender commitments.</p><div class="v21-grid">${numeric.map(([k,label])=>`<label>${label}<input data-v25="${k}" type="number" step="any" value="${escapeHtml(state[k])}"></label>`).join('')}<label>Maturity outcome<select id="v251Mode"><option value="refinance">Refinance</option><option value="equity">Sponsor-funded payoff</option><option value="default">Unfunded / flag default</option></select></label></div><label>Sponsor commitment ($M, total incl. opening cash; blank = not verified/unlimited for sensitivity only)<input id="v257Sponsor" type="number" min="0" step="any" placeholder="Not verified" value="${escapeHtml(state.sponsorCommitmentM??'')}"></label><label>Capacity entered as <select id="v252Capacity"><option value="IT">Critical IT MW</option><option value="gross">Gross facility MW</option></select></label><h3>Building-level schedule</h3><div class="table-wrap"><table><thead><tr><th>Building</th><th>IT MW</th><th>Construction start</th><th>Build months</th><th>Power month</th><th>Lease month</th><th>Lease term (months)</th><th>Rent escalator %</th><th>Rent method</th><th>Contracted total ($M)</th><th>Annual schedule ($M/yr CSV)</th><th>Source reference</th></tr></thead><tbody>${state.buildings.map((b,i)=>`<tr data-b="${i}">${[['name','text'],['itMW','number'],['constructionStart','number'],['constructionMonths','number'],['powerMonth','number'],['leaseMonth','number'],['leaseTermMonths','number'],['rentEscalatorPct','number']].map(([k,t])=>`<td><input data-f="${k}" type="${t}" style="min-width:75px;width:95px" value="${escapeHtml(b[k]??(k==='leaseTermMonths'?180:k==='rentEscalatorPct'?2.5:''))}"></td>`).join('')}<td><select data-f="rentInputMode"><option value="starting" ${(!b.rentInputMode||b.rentInputMode==='starting')?'selected':''}>Starting rent</option><option value="total" ${b.rentInputMode==='total'?'selected':''}>Contract total</option><option value="schedule" ${b.rentInputMode==='schedule'?'selected':''}>Annual schedule</option></select></td><td><input data-f="contractedRentM" type="number" step="any" style="width:95px" value="${escapeHtml(b.contractedRentM??'')}"></td><td><input data-f="annualRentM" type="text" style="width:170px" value="${escapeHtml((b.annualRentM||[]).join?.(',')||b.annualRentM||'')}"></td><td><input data-f="leaseSourceRef" type="text" style="width:150px" value="${escapeHtml(b.leaseSourceRef||'')}"></td></tr>`).join('')}</tbody></table></div><p class="v21-muted">Optional physical power tranches: month,MW,building (one per line; building blank = shared). If blank, each building uses its Power month.</p><textarea id="v251Tranches" rows="3" placeholder="20,50,Building A&#10;30,50,Building B">${escapeHtml((state.powerTranches||[]).map(t=>[t.month,t.mw,t.building||''].join(',')).join('\n'))}</textarea><div class="v21-actions"><button id="v251Run" class="primary">Underwrite project</button><button id="v251Stress">Run stress grid</button><button id="v251Export">Export financial schedule CSV</button></div><div id="v251Output"></div>`;
node.querySelector('#v251Mode').value=state.loanMaturityMode;node.querySelector('#v252Capacity').value=state.capacityBasis||'IT';
function get(){const a={...state};node.querySelectorAll('[data-v25]').forEach(el=>a[el.dataset.v25]=Number(el.value));a.loanMaturityMode=node.querySelector('#v251Mode').value;a.capacityBasis=node.querySelector('#v252Capacity').value;const sponsorText=node.querySelector('#v257Sponsor').value.trim();a.sponsorCommitmentM=sponsorText===''?null:Number(sponsorText);a.buildings=[...node.querySelectorAll('[data-b]')].map(tr=>Object.fromEntries([...tr.querySelectorAll('[data-f]')].map(el=>[el.dataset.f,['name','rentInputMode','annualRentM','leaseSourceRef'].includes(el.dataset.f)?el.value:(el.value===''?undefined:Number(el.value))])));a.powerTranches=node.querySelector('#v251Tranches').value.trim().split('\n').filter(x=>x.trim()).map(line=>{const [m,mw,b]=line.split(',');return {month:Number(m),mw:Number(mw),...(b&&b.trim()?{building:b.trim()}:{})}});return a}
const fmt=x=>Number.isFinite(x)?Number(x).toFixed(2):'N/A';function run(){try{state=get();last=evaluate(state);localStorage.setItem(key,JSON.stringify(state));const s=last.summary;node.querySelector('#v251Output').innerHTML=`<h3>Contract-value reconciliation</h3><p class="v21-muted">Status: <strong>${s.leaseReconciliationBlocked?'BLOCKED — missing or mismatched contracted rent':'Arithmetically reconciled, NOT independently validated'}</strong>. Recorded source references are not authenticated; no case is financially validated without independent documentation review.</p><div class="table-wrap"><table><thead><tr><th>Building</th><th>Mode</th><th>Disclosed ($M)</th><th>Modeled ($M)</th><th>Variance</th><th>Status</th></tr></thead><tbody>${s.leaseAudits.map(x=>`<tr><td>${escapeHtml(x.building)}</td><td>${escapeHtml(x.mode)}</td><td>${fmt(x.contractedRentM)}</td><td>${fmt(x.modeledContractRentM)}</td><td>${fmt(x.variancePct)}%</td><td>${escapeHtml(x.status)}</td></tr>`).join('')}</tbody></table></div><div class="v21-grid">${[['Levered NPV','$'+fmt(s.npvM)+'M'],['Levered IRR',s.leveredIRR===null?'N/A':fmt(s.leveredIRR*100)+'%'],['Equity multiple',fmt(s.equityMultiple)+'x'],['Sponsor funded','$'+fmt(s.equityInvestedM)+'M'],['Peak debt','$'+fmt(s.peakDebtM)+'M'],['Minimum DSCR',fmt(s.minDSCR)+'x'],['Maturity month',s.maturityMonth||'N/A'],['Refinanced',s.refinanced?'Yes':'No'],['DSCR breaches',s.breachMonths.length],['Funding gap events',s.liquidityBreachMonths.length],['Sources/uses residual',fmt(s.sourcesUsesMaxResidual)],['Debt identity residual',fmt(s.debtMaxResidual)],['Reserve identity residual',fmt(s.reserveMaxResidual)],['DSRA shortfall months',s.dsraDeficiencyMonths.length],['Cumulative CFADS','$'+fmt(s.cumulativeCfadsM)+'M'],['Sponsor commitment',s.sponsorCommitmentM===null?'Unverified':'$'+fmt(s.sponsorCommitmentM)+'M'],['Sponsor headroom',s.sponsorRemainingM===null?'Unverified':'$'+fmt(s.sponsorRemainingM)+'M'],['Funding default',s.fundingDefault?'Yes':'No'],['Unpaid exit debt','$'+fmt(s.unpaidDebtAtExitM)+'M'],['Unfunded months',s.unfundedMonths.length],['Ending debt','$'+fmt(s.endingDebtM)+'M'],['Tenant contributions','$'+fmt(s.tenantFundingM)+'M'],['Tenant rent credits','$'+fmt(s.rentCreditsM)+'M'],['Refinance constraint',s.refinanceSizing?.binding||'N/A'],['Financeability',s.financeabilityStatus]].map(([k,v])=>`<div class="v21-tile">${k}<b>${v}</b></div>`).join('')}</div><p class="v21-muted">Unverified sponsor funding implies an unlimited sensitivity assumption; a specified commitment caps funding, and deficits trigger a financing default. Exit value and refinance valuation are user assumptions; no appraisal or credit underwriting has been performed.</p>`;return last}catch(e){node.querySelector('#v251Output').textContent='Cannot underwrite: '+e.message;return null}}
node.querySelector('#v251Run').onclick=run;node.querySelector('#v251Stress').onclick=()=>{if(!run())return;const a=state,rs=[];for(const delay of [0,3,6,12,18])for(const overrun of [0,10,20])for(const shock of [0,200,400]){const z=evaluate({...a,delayMonths:a.delayMonths+delay,overrunPct:a.overrunPct+overrun,rateShockPct:shock/100});rs.push({delay,overrun,shock,npv:z.summary.npvM,irr:z.summary.leveredIRR,breaches:z.summary.breachMonths.length})}const worst=rs.reduce((x,y)=>x.npv<y.npv?x:y);node.querySelector('#v251Output').innerHTML+=`<h3>45-case financial stress grid</h3><p>Worst NPV: $${fmt(worst.npv)}M at ${worst.delay} month delay, ${worst.overrun}% capex overrun, +${worst.shock} bps</p><div class="table-wrap" style="max-height:320px;overflow:auto"><table><thead><tr><th>Delay</th><th>Overrun</th><th>Rate</th><th>NPV ($M)</th><th>IRR</th><th>DSCR issues</th></tr></thead><tbody>${rs.map(r=>`<tr><td>+${r.delay}m</td><td>+${r.overrun}%</td><td>+${r.shock} bps</td><td>${fmt(r.npv)}</td><td>${r.irr===null?'N/A':fmt(r.irr*100)+'%'}</td><td>${r.breaches}</td></tr>`).join('')}</tbody></table></div>`};node.querySelector('#v251Export').onclick=()=>{if(!run())return;const columns=Object.keys(last.rows[0]),csv=[columns.join(','),...last.rows.map(r=>columns.map(k=>r[k]??'').join(','))].join('\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv'})),a=document.createElement('a');a.href=url;a.download='PowerPath_v251_'+project.id+'.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};run();}
root.PowerPathUnderwrite25={defaults,evaluate,irr,render,rentAudit};if(typeof module!=='undefined'&&module.exports)module.exports={defaults,evaluate,irr,rentAudit};
})(typeof window!=='undefined'?window:globalThis);
