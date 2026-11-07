const U=require(process.argv[2]);
const x=U.evaluate({sponsorCommitmentM:50.0001});
const s=x.summary;console.log('minCash',s.minCashM.toFixed(1),'unfundedMonths',s.unfundedMonths.length,'first',s.unfundedMonths[0],'status',s.financeabilityStatus);
for(const m of [1,2,5,10,20,30,40,60,61,80,119,120]){const r=x.rows[m-1];console.log(m,'cash',r.cash.toFixed(1),'capex',r.capex.toFixed(1),'draw',r.draw.toFixed(1),'debt',r.debt.toFixed(1),'cfads',r.cfads.toFixed(1),'unfunded',r.unfundedGapM.toFixed(1),'dist',r.distribution.toFixed(1),'term',r.terminalProceeds.toFixed(0))}
