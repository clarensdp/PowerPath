"""Build engine/underwrite27.js from the frozen engine/underwrite25.js.

Every change is an exact-match splice (asserted to match once), so the diff between the two engines is
limited to the documented v27.1 cash-constrained waterfall. underwrite25.js itself is never modified.
Usage: python tools/build_underwrite27.py <app_root> [--check]   (--check: verify engine/underwrite27.js is exactly reproducible)
"""
import sys, hashlib
from pathlib import Path
ROOT = Path(sys.argv[1])
src = (ROOT / 'engine/underwrite25.js').read_text()
assert hashlib.sha256(src.encode()).hexdigest() == 'c4e2a090698411e492f5399a52fddbf233539dc3c1871d0877e53fcfb2d9ce29', 'frozen engine changed'
lines = src.split('\n')
assert lines[342] == ' }' and lines[341].startswith('  rows.push(') and lines[229].startswith('  const mezzDraw=')

def rep(s, old, new, count=1):
    n = s.count(old)
    assert n == count, f'expected {count} match, found {n}: {old[:80]!r}'
    return s.replace(old, new)

head = '\n'.join(lines[:236])          # through '  const constructing=...'
tail = '\n'.join(lines[343:])          # from ' const npv=' onward
assert lines[236].startswith('  const capitalizedInterest=') and tail.startswith(' const npv=')

# ---- 1. header / defaults / validation / state ----
head = rep(head, '/* PowerPath v25.8.4', '/* PowerPath engine 27.1.0 — v25.8.5 underwriting with a cash-constrained debt-service waterfall (v27.1). Built from underwrite25.js by\n   build_underwrite27.py; every change is marked "v27.1". Legacy engine: underwrite25.js (unchanged).\n   Original header follows. PowerPath v25.8.4')
head = rep(head, "exitValuePolicy:'fixed',vacantValuePct:40,", "exitValuePolicy:'fixed',vacantValuePct:40,unpaidInterestPolicy:'accrue',pikPermittedByInstrument:false,defaultInterestRatePct:0,debtServicePriority:['seniorInterest','seniorPrincipal','mezzInterest','mezzPrincipal'],reserveDebtServicePolicy:'dsra_only',")
head = rep(head, " if(!['halt','continue'].includes(a.fundingDefaultPolicy))throw Error('Invalid funding default policy');",
 " if(!['halt','continue'].includes(a.fundingDefaultPolicy))throw Error('Invalid funding default policy');\n"
 " // v27.1: explicit treatment of unpaid amounts. Screening default = accrue unpaid interest separately (no compounding,\n"
 " // no default rate). PIK capitalisation is refused unless the instrument expressly permits it.\n"
 " if(!['accrue','pik'].includes(a.unpaidInterestPolicy))throw Error('unpaidInterestPolicy must be accrue or pik');\n"
 " if(a.unpaidInterestPolicy==='pik'&&a.pikPermittedByInstrument!==true)throw Error('PIK capitalisation requires pikPermittedByInstrument=true (documented instrument term)');\n"
 " finite(a.defaultInterestRatePct,'defaultInterestRatePct');if(a.defaultInterestRatePct>20)throw Error('defaultInterestRatePct above 20');\n"
 " {const req=['seniorInterest','seniorPrincipal','mezzInterest','mezzPrincipal'];if(!Array.isArray(a.debtServicePriority)||a.debtServicePriority.length!==4||!req.every(k=>a.debtServicePriority.includes(k)))throw Error('debtServicePriority must order exactly: '+req.join(', '))}\n"
 " if(!['dsra_only','all','none'].includes(a.reserveDebtServicePolicy))throw Error('reserveDebtServicePolicy must be dsra_only, all or none');")
head = rep(head, "refinanceSizing=null,fundingDefault=false,unpaidDebtAtExitM=0;",
 "refinanceSizing=null,fundingDefault=false,unpaidDebtAtExitM=0;\n"
 " // v27.1 waterfall state: unpaid interest (by tranche), past-due principal (part of debt/mezz), unpaid payables, totals.\n"
 " let uiS=0,uiM=0,pdS=0,pdM=0,uOps=0,uCap=0,pikTotal=0,defaultInterestTotal=0,cashInterestPaidTotal=0,reserveDrawTotal=0,paymentDefault=false,firstPaymentDefaultMonth=null;\n"
 " let unpaidInterestAtExitM=0,unpaidPayablesAtExitM=0,lenderClaimAtExitBeforeM=0,lenderRecoveryAtExitM=0;const paymentDefaultMonths=[];")

# ---- 2. new loop body from capitalisation to end of month ----
body = r"""  // v27.1: default interest accrues only on overdue amounts and only if a rate is supplied (default 0).
  const dRate=a.defaultInterestRatePct/1200;
  const defaultIntSenior=(uiS+pdS)*dRate,defaultIntMezz=(uiM+pdM)*dRate,defaultInterest=defaultIntSenior+defaultIntMezz;defaultInterestTotal+=defaultInterest;
  const openingUnpaidInterest=uiS+uiM,openingPastDue=pdS+pdM,openingPayables=uOps+uCap;
  const capitalizedInterest=!refiOccurred&&constructing?interest:0;
  const capSenior=capitalizedInterest*(interest?seniorInterest/interest:1),capMezz=capitalizedInterest-capSenior;
  debt+=capSenior;mezz+=capMezz;
  // Contractual cash interest due this period, by tranche (construction IDC is capitalised per the legacy convention).
  // Capitalisation is all-or-nothing, so branch to keep exact zeros (DSCR null) identical to v25.8.5.
  const seniorCashIntDue=(capitalizedInterest>0?0:seniorInterest)+defaultIntSenior,mezzCashIntDue=(capitalizedInterest>0?0:mezzInterest)+defaultIntMezz;
  const cashInterestDue=interest-capitalizedInterest+defaultInterest;
  // principal/mezzPrincipal = funded refinancing or equity payoff transactions; sched* = amortisation due (may go unpaid).
  let principal=0,mezzPrincipal=0,refinanceProceeds=0,refinanceFee=0,maturityShortfall=0,sweepPrincipal=0,schedSenior=0,schedMezz=0,maturedNow=false;
  let forward12CfadsM=null,forward12NoiM=null;
  if(maturityMonth!==null&&m===maturityMonth&&!refiOccurred){
   const oldDebt=debt,oldMezz=mezz;
   if(defaulted){maturityShortfall=oldDebt+oldMezz;fundingDefault=true;maturedNow=true}
   else if(a.loanMaturityMode==='refinance'){
    forward12CfadsM=0;forward12NoiM=0;
    for(let j=1;j<=12;j++){const f=operations(m+j);forward12CfadsM+=cfadsMonth(m+j);forward12NoiM+=f.ebitda-f.maintenanceCapex}
    const r=effectiveRefinanceRatePct/1200;let n=Math.max(1,Math.round(a.refinanceAmortMonths));
    const walt=waltMonths(m);
    if(a.refinanceTenorPolicy==='leaseTail')n=Math.max(Math.round(a.minRefinanceAmortMonths),Math.min(n,Math.floor(walt-a.leaseTailBufferMonths)));
    refiAmortN=n;
    const paymentPerDollar=r===0?1/n:r/(1-Math.pow(1+r,-n));
    const ltvLimit=a.refinanceValueM*a.refinanceLtvPct/100;
    const dscrLimit=Math.max(0,forward12CfadsM)/Math.max(.01,a.refinanceDscrMin)/(12*paymentPerDollar);
    const yieldLimit=a.debtYieldMinPct>0?Math.max(0,forward12NoiM)/(a.debtYieldMinPct/100):Infinity;
    const newDebt=Math.max(0,Math.min(ltvLimit,dscrLimit,yieldLimit));
    refinanceSizing={ltvLimit,dscrLimit,yieldLimit,selected:newDebt,forward12CfadsM,forward12NoiM,amortMonths:n,remainingLeaseTermMonths:walt,binding:newDebt===ltvLimit?'LTV':newDebt===dscrLimit?'DSCR':'debt yield'};
    const requiredFee=newDebt*a.refinanceFeePct/100;
    const beforePayoff=cash+cfads+seniorDraw+mezzDraw+tenantCashReceipt-capex-fee-cashInterestDue;
    const availableForPayoff=Math.max(0,beforePayoff-a.minLiquidity)+sponsorRemaining();
    const gap=Math.max(0,oldDebt+oldMezz+requiredFee-newDebt-availableForPayoff);
    if(gap>1e-8){defaulted=true;maturityShortfall=gap;fundingDefault=true;refinanceSizing.failed=true;maturedNow=true}
    else{refinanceProceeds=newDebt;refinanceFee=requiredFee;feeTotal+=refinanceFee;principal=oldDebt;mezzPrincipal=oldMezz;debt=newDebt;mezz=0;refiOccurred=true;constructionFacilityClosed=true}
   }else if(a.loanMaturityMode==='equity'){
    const beforePayoff=cash+cfads+seniorDraw+mezzDraw+tenantCashReceipt-capex-fee-cashInterestDue;
    const gap=Math.max(0,oldDebt+oldMezz-(Math.max(0,beforePayoff-a.minLiquidity)+sponsorRemaining()));
    if(gap>1e-8){defaulted=true;maturityShortfall=gap;fundingDefault=true;maturedNow=true}
    else{principal=oldDebt;mezzPrincipal=oldMezz;debt=0;mezz=0;constructionFacilityClosed=true}
   }else{defaulted=true;maturityShortfall=oldDebt+oldMezz;maturedNow=true}
   // v27.1: an unrefinanced, unrepaid loan matures; all outstanding principal becomes past due (not erased, not "paid").
   if(maturedNow){pdS=debt;pdM=mezz}
  }else if(refiOccurred&&m>maturityMonth){
   // v25.8-CA P1 annuity, applied to the balance not already past due (v27.1), so arrears are not re-amortised.
   const notDue=Math.max(0,debt-pdS);
   const left=Math.max(1,refiAmortN-(m-maturityMonth-1)),rr=effectiveRefinanceRatePct/1200;
   const payment=rr===0?notDue/left:notDue*rr/(1-Math.pow(1+rr,-left));
   schedSenior=left===1?notDue:Math.min(notDue,Math.max(0,payment-notDue*rr))}
  // DSCR uses contractual current-period debt service (due, not paid); excludes maturity balloon and refinancing.
  const scheduledDebtService=cashInterestDue+(m===maturityMonth?0:principal+mezzPrincipal+schedSenior+schedMezz);
  const dscr=scheduledDebtService>0?cfads/scheduledDebtService:null;
  const loanSources=seniorDraw+mezzDraw+refinanceProceeds;
  const operatingCash=cfads;
  // Sponsor support is sized exactly as in v25.8.5 (current obligations + minimum liquidity), within the enforceable cap.
  const currentDue=capex+fee+refinanceFee+cashInterestDue+principal+mezzPrincipal+schedSenior+schedMezz;
  const preFundingCash=cash+operatingCash+loanSources+tenantCashReceipt-currentDue;
  let sponsorContribution=drawSponsor(Math.max(0,a.minLiquidity-preFundingCash));
  // ---- v27.1 cash-constrained allocation. Cash pays obligations in priority order and never goes below zero. ----
  let pool=cash+Math.max(0,cfads)+loanSources+tenantCashReceipt+sponsorContribution;
  const pay=due=>{const p=Math.min(Math.max(0,due),Math.max(0,pool));pool-=p;return p};
  const opsDue=Math.max(0,-cfads),opsPaid=pay(opsDue);
  const refiTxnDue=principal+mezzPrincipal+refinanceFee,refiTxnPaid=pay(refiTxnDue);
  if(refiTxnDue-refiTxnPaid>1e-7)throw Error('Internal invariant: refinancing/payoff closed without funding');
  const constructionDue=capex+fee,constructionPaid=pay(constructionDue);
  const reserveUsable=used=>a.reserveDebtServicePolicy==='none'?0:a.reserveDebtServicePolicy==='all'?Math.max(0,reserve-used):Math.max(0,reserve-used-a.reserveTargetM);
  const dsDue={seniorInterest:seniorCashIntDue,seniorPrincipal:schedSenior,mezzInterest:mezzCashIntDue,mezzPrincipal:schedMezz};
  const dsPaid={seniorInterest:0,seniorPrincipal:0,mezzInterest:0,mezzPrincipal:0};
  let reserveDraw=0;
  for(const k of a.debtServicePriority){let p=pay(dsDue[k]);const rem=dsDue[k]-p;if(rem>1e-12){const r=Math.min(rem,reserveUsable(reserveDraw));reserveDraw+=r;p+=r}dsPaid[k]=p}
  reserve-=reserveDraw;reserveDrawTotal+=reserveDraw;
  cash=pool;
  const currentShortfall=(opsDue-opsPaid)+(constructionDue-constructionPaid)+Object.keys(dsDue).reduce((v,k)=>v+dsDue[k]-dsPaid[k],0);
  if(currentShortfall>1e-9){paymentDefault=true;defaulted=true;fundingDefault=true;paymentDefaultMonths.push(m);if(firstPaymentDefaultMonth===null)firstPaymentDefaultMonth=m}
  uOps+=opsDue-opsPaid;uCap+=constructionDue-constructionPaid;
  debt-=dsPaid.seniorPrincipal;mezz-=dsPaid.mezzPrincipal;
  pdS+=schedSenior-dsPaid.seniorPrincipal;pdM+=schedMezz-dsPaid.mezzPrincipal;
  const seniorIntUnpaid=dsDue.seniorInterest-dsPaid.seniorInterest,mezzIntUnpaid=dsDue.mezzInterest-dsPaid.mezzInterest;
  let pikInterest=0;
  if(a.unpaidInterestPolicy==='pik'){debt+=seniorIntUnpaid;mezz+=mezzIntUnpaid;pikInterest=seniorIntUnpaid+mezzIntUnpaid;pikTotal+=pikInterest}
  else{uiS+=seniorIntUnpaid;uiM+=mezzIntUnpaid}
  const interestPaidCurrent=dsPaid.seniorInterest+dsPaid.mezzInterest;
  const unfundedGapM=Math.max(0,a.minLiquidity-cash);
  if(unfundedGapM>1e-8){defaulted=true;fundingDefault=true}
  // v27.1: arrears (earlier unpaid amounts) are paid only from cash ABOVE minimum liquidity, in the same priority order,
  // so sponsor liquidity support is never silently converted into lender recoveries.
  let avail=Math.max(0,cash-a.minLiquidity);
  const payA=due=>{const p=Math.min(Math.max(0,due),avail);avail-=p;cash-=p;return p};
  const arrOps=payA(uOps);uOps-=arrOps;const arrCap=payA(uCap);uCap-=arrCap;
  let arrIntS=0,arrIntM=0,arrPrinS=0,arrPrinM=0;
  for(const k of a.debtServicePriority){
   if(k==='seniorInterest'){arrIntS=payA(uiS);uiS-=arrIntS}
   else if(k==='mezzInterest'){arrIntM=payA(uiM);uiM-=arrIntM}
   else if(k==='seniorPrincipal'){arrPrinS=payA(pdS);pdS-=arrPrinS;debt-=arrPrinS}
   else{arrPrinM=payA(pdM);pdM-=arrPrinM;mezz-=arrPrinM}}
  const arrearsPaid=arrOps+arrCap+arrIntS+arrIntM+arrPrinS+arrPrinM;
  const notDueDebt=Math.max(0,debt-pdS);
  const projectedRefiPayment=(refiOccurred&&notDueDebt>0)?(effectiveRefinanceRatePct===0?notDueDebt/Math.max(1,refiAmortN-(m-maturityMonth)):notDueDebt*(effectiveRefinanceRatePct/1200)/(1-Math.pow(1+effectiveRefinanceRatePct/1200,-Math.max(1,refiAmortN-(m-maturityMonth))))):0;
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
  const arrearsOutstanding=uiS+uiM+pdS+pdM+uOps+uCap>1e-9;
  const locked=finalReserveDeficiency>1e-8||defaulted||arrearsOutstanding||(a.lockDistributionsOnBreach!==false&&inBreach)||(debtOutstanding&&(dscr===null||dscr<a.distributionDscrMin));
  if(debtOutstanding&&!defaulted&&a.cashSweepPct>0){const excess=Math.max(0,cash-a.minLiquidity);sweepPrincipal=Math.min(Math.max(0,debt-pdS),excess*a.cashSweepPct/100);cash-=sweepPrincipal;debt-=sweepPrincipal}
  let distribution=0;
  if(!locked&&a.distributionPolicy==='excess'&&m<months){distribution=Math.max(0,cash-a.minLiquidity);cash-=distribution}
  let terminalProceeds=0,exitDebtPayoff=0,exitInterestPaid=0,exitPayablesPaid=0,exitCollections=0,exitTenantReceivableCollection=0,exitWorkingCapitalCollection=0,exitPaySenior=0,exitPayMezz=0;
  if(m===months){
   const totalIt=a.buildings.reduce((v,b)=>v+itMW(b),0),liveIt=a.buildings.filter(b=>!abandoned.has(b.name)).reduce((v,b)=>v+itMW(b),0);
   let exitShare=abandoned.size?liveIt/totalIt:1;
   if(a.exitValuePolicy==='contracted'){const leased=Math.min(liveIt,physicalByMonth[m].onlineMW);exitShare=(leased+(liveIt-leased)*a.vacantValuePct/100)/totalIt}
   exitShareUsed=exitShare;
   terminalProceeds=a.exitValueM*(1-a.exitCostPct/100)*exitShare;
   exitTenantReceivableCollection=totalTenantReceivable*a.exitTenantReceivableRecoveryPct/100;
   exitWorkingCapitalCollection=Math.max(0,op.workingCapitalBalance)*a.exitWorkingCapitalRecoveryPct/100;
   exitCollections=exitTenantReceivableCollection+exitWorkingCapitalCollection;
   totalTenantReceivable=Math.max(0,totalTenantReceivable-exitTenantReceivableCollection);
   // v27.1 terminal waterfall: cash, reserves and proceeds go to lender claims (unpaid interest before principal, in the
   // configured tranche priority), then to unpaid construction and operating payables, then to equity.
   let pot=Math.max(0,cash+terminalProceeds+exitCollections+reserve);
   lenderClaimAtExitBeforeM=debt+mezz+uiS+uiM;
   const take=due=>{const p=Math.min(Math.max(0,due),pot);pot-=p;return p};
   for(const k of a.debtServicePriority){
    if(k==='seniorInterest'){const p=take(uiS);uiS-=p;exitInterestPaid+=p}
    else if(k==='mezzInterest'){const p=take(uiM);uiM-=p;exitInterestPaid+=p}
    else if(k==='seniorPrincipal'){exitPaySenior=take(debt);debt-=exitPaySenior;pdS=Math.min(pdS,debt)}
    else{exitPayMezz=take(mezz);mezz-=exitPayMezz;pdM=Math.min(pdM,mezz)}}
   exitDebtPayoff=exitPaySenior+exitPayMezz;lenderRecoveryAtExitM=exitDebtPayoff+exitInterestPaid;
   const pc=take(uCap);uCap-=pc;const po=take(uOps);uOps-=po;exitPayablesPaid=pc+po;
   unpaidDebtAtExitM=debt+mezz;unpaidInterestAtExitM=uiS+uiM;unpaidPayablesAtExitM=uOps+uCap;
   if(unpaidDebtAtExitM+unpaidInterestAtExitM>1e-8)defaulted=true;
   cash+=terminalProceeds+exitCollections+reserve-exitDebtPayoff-exitInterestPaid-exitPayablesPaid;reserveMovement-=reserve;reserve=0;
   if(cash>0&&unpaidDebtAtExitM+unpaidInterestAtExitM+unpaidPayablesAtExitM<1e-8&&!defaulted){distribution+=cash;cash=0}
  }
  const shortfall=preFundingCash<a.minLiquidity,covenant=dscr!==null&&m!==maturityMonth&&dscr<a.dscrCovenant;
  if(shortfall)liquidityBreaches.push(m);if(covenant)covenantBreaches.push(m);
  if(fundingDefault&&a.fundingDefaultPolicy==='halt'&&haltMonth===Infinity){haltMonth=m+1;for(const b of a.buildings)if(b.constructionStart+b.constructionMonths-1>m)abandoned.add(b.name);if(abandoned.size)computePhysical()}
  flows.push(distribution-sponsorContribution);
  peakDebt=Math.max(peakDebt,debt+mezz,refinanceProceeds);
  // Row fields keep legacy names: principal/mezzPrincipal/cashInterest are amounts ACTUALLY PAID (any source).
  const seniorPrincipalPaid=principal+dsPaid.seniorPrincipal+arrPrinS+sweepPrincipal+exitPaySenior;
  const mezzPrincipalPaid=mezzPrincipal+dsPaid.mezzPrincipal+arrPrinM+exitPayMezz;
  principalPaid+=seniorPrincipalPaid+mezzPrincipalPaid;
  const interestPaidAll=interestPaidCurrent+arrIntS+arrIntM+exitInterestPaid;cashInterestPaidTotal+=interestPaidAll;
  const cashOutDebtService=interestPaidCurrent+dsPaid.seniorPrincipal+dsPaid.mezzPrincipal-reserveDraw;
  const uses=opsPaid+refiTxnPaid+constructionPaid+cashOutDebtService+arrearsPaid+sweepPrincipal;
  const cashInflowsM=Math.max(0,cfads)+loanSources+tenantCashReceipt+sponsorContribution+terminalProceeds+exitCollections+Math.max(0,-reserveMovement);
  const cashOutflowsM=uses+exitDebtPayoff+exitInterestPaid+exitPayablesPaid+distribution+Math.max(0,reserveMovement);
  // Mandatory monthly identities (independently re-checked by tests/v271/oracle_waterfall.py).
  const cashIdentityResidual=openingCash+cashInflowsM-cashOutflowsM-cash;
  const interestIdentityResidual=openingUnpaidInterest+interest+defaultInterest-capitalizedInterest-interestPaidAll-pikInterest-(uiS+uiM);
  const debtResidual=debt-(openingSeniorDebt+seniorDraw+capSenior+refinanceProceeds+(a.unpaidInterestPolicy==='pik'?seniorIntUnpaid:0)-seniorPrincipalPaid);
  const mezzResidual=mezz-(openingMezzDebt+mezzDraw+capMezz+(a.unpaidInterestPolicy==='pik'?mezzIntUnpaid:0)-mezzPrincipalPaid);
  const reserveResidual=reserve-openingReserve-reserveMovement+reserveDraw;
  const payablesResidual=(uOps+uCap)-(openingPayables+(opsDue-opsPaid)+(constructionDue-constructionPaid)-arrOps-arrCap-exitPayablesPaid);
  const sourcesUsesResidual=cashIdentityResidual;
  rows.push({month:m,onlineMW,availableMW,grossRevenue,rentCredits,leaseRevenue,revenue,grossEnergy,energy,powerReimbursement,tenantDirectPower,netEnergyCost,opex,ebitda,cashTaxes,maintenanceCapex,workingCapitalBalance:op.workingCapitalBalance,powerReimbursementReceivable:op.powerReimbursementReceivable,leaseWorkingCapital:op.leaseWorkingCapital,workingCapitalChange,cfads,capex,tenantFundedCapex,tenantCashReceipt,tenantFundingReceivable:totalTenantReceivable,draw:seniorDraw,mezzDraw,fee,refinanceFee,interest,capitalizedInterest,cashInterest:interestPaidAll,principal:seniorPrincipalPaid,mezzPrincipal:mezzPrincipalPaid,debt,mezzDebt:mezz,debtService:scheduledDebtService,scheduledDebtService,dscr,breach:covenant,liquidityBreach:shortfall,openingCash,loanSources,uses,operatingCash,preFundingCash,sponsorContribution,equityContribution:sponsorContribution,distribution,netEquity:distribution-sponsorContribution,cash,reserve,reserveMovement,refinanceProceeds,sweepPrincipal,maturityShortfall,terminalProceeds,exitCollections,exitTenantReceivableCollection,exitWorkingCapitalCollection,exitDebtPayoff,unpaidDebtAtExitM,unfundedGapM,sourcesUsesResidual,debtResidual,mezzResidual,reserveResidual,reserveDeficiency:finalReserveDeficiency,restrictedTarget,dsraTarget,openingSeniorDebt,openingMezzDebt,openingReserve,forward12CfadsM,forward12NoiM,
   engineVersion:'27.1.0',cashInterestDue,cashInterestPaidCurrent:interestPaidCurrent,interestPaidArrears:arrIntS+arrIntM,exitInterestPaid,defaultInterest,pikInterest,unpaidInterestCurrent:seniorIntUnpaid+mezzIntUnpaid,unpaidInterestOpening:openingUnpaidInterest,unpaidInterestClosing:uiS+uiM,unpaidInterestSenior:uiS,unpaidInterestMezz:uiM,
   scheduledPrincipalDue:schedSenior+schedMezz,scheduledPrincipalPaid:dsPaid.seniorPrincipal+dsPaid.mezzPrincipal,refinancingRepayment:principal+mezzPrincipal,arrearsPrincipalPaid:arrPrinS+arrPrinM,pastDuePrincipalOpening:openingPastDue,pastDuePrincipalClosing:pdS+pdM,maturedUnpaid:maturedNow,
   operatingShortfallDue:opsDue,operatingPaid:opsPaid,constructionDue,constructionPaid,unpaidPayablesOpening:openingPayables,unpaidOperatingClosing:uOps,unpaidConstructionClosing:uCap,arrearsPayablesPaid:arrOps+arrCap,exitPayablesPaid,
   reserveDrawForDebtService:reserveDraw,currentShortfallM:currentShortfall,paymentDefault:currentShortfall>1e-9,lenderClaimM:debt+mezz+uiS+uiM,cashInflowsM,cashOutflowsM,cashIdentityResidual,interestIdentityResidual,payablesResidual});
 }"""
new_loop = head + '\n' + body + '\n' + tail

# ---- 3. summary additions and warnings ----
new_loop = rep(new_loop, " return {assumptions:a,rows,summary,flows};",
 " // v27.1 summary: lender claims and unpaid amounts never disappear at exit.\n"
 " Object.assign(summary,{engineVersion:'27.1.0',unpaidInterestPolicy:a.unpaidInterestPolicy,debtServicePriority:a.debtServicePriority.slice(),reserveDebtServicePolicy:a.reserveDebtServicePolicy,defaultInterestRatePct:a.defaultInterestRatePct,\n"
 "  paymentDefault,firstPaymentDefaultMonth,paymentDefaultMonths,cashInterestPaidM:cashInterestPaidTotal,pikInterestM:pikTotal,defaultInterestM:defaultInterestTotal,reserveDrawsForDebtServiceM:reserveDrawTotal,\n"
 "  unpaidInterestAtExitM,unpaidPayablesAtExitM,unpaidLenderClaimsAtExitM:unpaidDebtAtExitM+unpaidInterestAtExitM,lenderClaimAtExitBeforeM,lenderRecoveryAtExitM,\n"
 "  lenderRecoveryPct:lenderClaimAtExitBeforeM>1e-9?lenderRecoveryAtExitM/lenderClaimAtExitBeforeM*100:null,minCashM:Math.min(...rows.map(r=>r.cash)),\n"
 "  maxIdentityResidual:Math.max(...rows.map(r=>Math.max(Math.abs(r.cashIdentityResidual),Math.abs(r.interestIdentityResidual),Math.abs(r.debtResidual),Math.abs(r.mezzResidual),Math.abs(r.reserveResidual),Math.abs(r.payablesResidual))))});\n"
 " if(paymentDefault)summary.creditWarnings.push('Contractual payments went unpaid (first in month '+firstPaymentDefaultMonth+'); unpaid interest and past-due principal are carried as lender claims, not paid with negative cash');\n"
 " if(a.unpaidInterestPolicy==='accrue'&&(uiS+uiM+unpaidInterestAtExitM+cashInterestPaidTotal)>0&&paymentDefault)summary.creditWarnings.push('Unpaid interest is accrued without compounding or default rate (screening convention; instrument terms not verified)');\n"
 " if(a.unpaidInterestPolicy==='pik')summary.creditWarnings.push('PIK capitalisation of unpaid interest assumed permitted by the instrument; verify against executed terms');\n"
 " if(a.defaultInterestRatePct>0)summary.creditWarnings.push('Default interest rate applied is an assumption unless sourced from executed terms');\n"
 " return {assumptions:a,rows,summary,flows};")
new_loop = rep(new_loop, "root.PowerPathUnderwrite25={defaults,evaluate,irr,render,rentAudit};", "root.PowerPathUnderwrite27={defaults,evaluate,irr,render,rentAudit,ENGINE_VERSION:'27.1.0'};")
new_loop = rep(new_loop, "module.exports={defaults,evaluate,irr,rentAudit}", "module.exports={defaults,evaluate,irr,rentAudit,ENGINE_VERSION:'27.1.0'}")
new_loop = rep(new_loop, "const key='powerpath-v251-'+project.id", "const key='powerpath-v271-'+project.id")
target = ROOT / 'engine/underwrite27.js'
if '--check' in sys.argv:
    ok = target.read_text() == new_loop
    print('underwrite27.js reproducible from frozen underwrite25.js:', ok); sys.exit(0 if ok else 1)
target.write_text(new_loop)
print('wrote engine/underwrite27.js', hashlib.sha256(new_loop.encode()).hexdigest())
