const assert=require('assert');const {evaluate}=require('./workspace/underwrite25');const cc=require('./benchmarks/v258_results/frozen_inputs_16.json');let n=0,maxR=0,defaults=0,breaches=0,fail=0;
for(const c of cc)for(const delay of [0,3,6,12,18])for(const overrun of [0,10,20])for(const bps of [0,200,400]){
 try{const s=evaluate({...c.assumptions,delayMonths:delay,overrunPct:overrun,rateShockPct:bps/100,refinanceTenorPolicy:'leaseTail',leaseExpiryPolicy:'renew',exitValuePolicy:'contracted'}).summary;n++;maxR=Math.max(maxR,s.sourcesUsesMaxResidual,s.debtMaxResidual,s.reserveMaxResidual);if(s.defaulted)defaults++;if(s.breachMonths.length)breaches++;assert(s.financialValidationStatus==='NOT INDEPENDENTLY VALIDATED');}catch(e){fail++;console.log(c.name,delay,overrun,bps,e.message)}
}
console.log(JSON.stringify({runs:n,errors:fail,maxFinancialResidualM:maxR,defaultedCases:defaults,breachCases:breaches,contractVerified:0}));if(fail||n!==720||maxR>1e-6)process.exit(1);
