const path=process.argv[2];const U=require(path);
const r=(o)=>{try{return U.evaluate(o)}catch(e){return {err:e.message}}};
// H1 annuity vs level principal
let x=r({});const s=x.summary;const mm=s.maturityMonth;
const rr=x.rows.filter(z=>z.month>mm&&z.month<=mm+3);
const ppd=(0.07/12)/(1-Math.pow(1+0.07/12,-240));
console.log('H1 refi debt',s.refinanceSizing&&s.refinanceSizing.selected.toFixed(2),'binding',s.refinanceSizing&&s.refinanceSizing.binding,'mat',mm);
rr.forEach(z=>console.log('  m',z.month,'DS',z.scheduledDebtService.toFixed(3),'annuity',(s.refinanceSizing.selected*ppd).toFixed(3),'dscr',z.dscr&&z.dscr.toFixed(3)));
console.log('  minDSCR',s.minDSCR,'breaches',s.breachMonths.length,'npv',s.npvM.toFixed(2));
// DSCR-binding case
x=r({refinanceValueM:5000});console.log('H1b DSCR-binding sizing',x.summary.refinanceSizing.binding,x.summary.refinanceSizing.selected.toFixed(1),'dscr m+1',x.rows[x.summary.maturityMonth].dscr.toFixed(3),'target',1.25,'breaches',x.summary.breachMonths.length);
// H2 shared tranche reverse readiness
const B=[{name:'A',itMW:50,constructionStart:10,constructionMonths:18,powerMonth:28,leaseMonth:28,leaseTermMonths:180},{name:'B',itMW:50,constructionStart:1,constructionMonths:18,powerMonth:19,leaseMonth:19,leaseTermMonths:180}];
x=r({buildings:B,powerTranches:[{month:19,mw:50}]});console.log('H2 shared tranche reverse order:',x.err||('ok online m30 '+x.rows[29].onlineMW));
// H3 gross basis + tranches
x=r({capacityBasis:'gross',pue:1.3,buildings:[{name:'A',itMW:130,constructionStart:1,constructionMonths:18,powerMonth:19,leaseMonth:19,leaseTermMonths:180}],powerTranches:[{month:19,mw:100,building:'A'}]});
console.log('H3 gross 130MW bldg (100 IT), 100MW gross utility tranche ->',x.err||('online IT MW '+x.rows[20].onlineMW+' (gross-consistent would be '+(100/1.3).toFixed(1)+')'));
// H4
x=r({});const mwh=x.rows.reduce((t,z,i)=>t+z.onlineMW*1.3*(z.energy>0?z.energy*1e6/(z.onlineMW*1.3*85):0),0);
console.log('H4 operatingMWh summary',s.operatingMWh.toFixed(0),'calendar',mwh.toFixed(0));
// H5 tenant receivable at horizon
x=r({tenantCapexPct:50,tenantFundingLagMonths:6,months:42,buildings:[{name:'A',itMW:50,constructionStart:25,constructionMonths:18,powerMonth:43,leaseMonth:43}]});
console.log('H5 receivable at exit',x.err||x.rows.at(-1).tenantFundingReceivable.toFixed(2),'WC bal end', r({workingCapitalDays:45}).rows.at(-1).workingCapitalBalance.toFixed(2));
// H6 stranded residual
x=r({sponsorCommitmentM:50+0.0001,minLiquidity:10});
const L=x.rows.at(-1);console.log('H6 defaulted',x.summary.defaulted,'unpaid',x.summary.unpaidDebtAtExitM.toFixed(2),'end cash',L.cash.toFixed(2),'dist last',L.distribution.toFixed(2));
