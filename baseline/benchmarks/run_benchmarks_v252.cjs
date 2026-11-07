const fs=require('fs'); const path=require('path');
const {evaluate,defaults}=require('/mnt/data/powerpath_v25_2/workspace/underwrite25.js');
const out='/mnt/data/powerpath_v25_2/benchmarks';
// Source-driven public facts; financial inputs not disclosed by issuers are explicit scenario assumptions.
const projects=[
['Applied Digital','Polaris Forge 1',400,11000,15,'IT','2025-10','2027-06','https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm','100+150+150 IT MW; 15-year contracted value'],
['Applied Digital','Polaris Forge 2',200,5000,15,'IT','2026-09','2027-03','https://ir.applieddigital.com/sec-filings/all-sec-filings/content/0001144879-26-000048/apld-20260531.htm','200 IT MW, first 2H26, full early 2027'],
['Applied Digital','Polaris Forge 3',300,7500,15,'IT','2027-09','2028-06','https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm','300 IT MW, 2H27–2H28 delivery'],
['Applied Digital','Delta Forge 1',300,7500,15,'IT','2027-03','2028-06','https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm','300 IT MW, 1H27–1H28 delivery'],
['Applied Digital','Delta Forge 2',210,5200,15,'IT','2028-03','2028-06','https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm','210 IT MW, 1H28 delivery'],
['Galaxy','Helios CoreWeave phases I–III',526,18000,15,'IT','2026-06','2028-06','https://www.sec.gov/Archives/edgar/data/1859392/000185939226000084/glxy-20260630xpressrelease.htm','$1.2B+ average annual revenue; $18B/15y is MINIMUM proxy; 526 IT MW, 800 gross MW; 133 IT MW Phase I'],
['Cipher','Barber Lake',168,9000,20,'IT','2026-10','2027-01','https://investors.cipherdigital.com/news-releases/news-release-details/cipher-digital-expands-barber-lake-lease-term-20-years/','168 IT MW disclosed first phase vs 300 gross MW campus; $9B+ over 20 years minimum proxy'],
['Cipher','Black Pearl AWS',null,5500,15,'gross','2026-08','2026-12','https://www.sec.gov/Archives/edgar/data/1819989/000181998925000110/ciphermining_businessupd.htm','300 gross MW, not IT MW; assumed PUE 1.30 converts to IT MW'],
['Core Scientific','Denton',260,null,12,'leased','2026-06','2026-09','https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm','~260 MW customer leased power; revenue only group disclosed'],
['Core Scientific','Dalton',175,null,12,'leased','2026-06','2027-03','https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm','~175 MW customer leased power; phase 1 30 MW delivered'],
['Core Scientific','Muskogee',70,null,12,'leased','2026-06','2026-09','https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm','~70 MW leased power; no per-site revenue disclosed'],
['Core Scientific','Marble',65,null,12,'leased','2025-12','2026-01','https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm','~65 MW leased power, handed over; no per-site revenue disclosed'],
['Core Scientific','Austin',20,null,7,'leased','2025-12','2026-01','https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm','~20 MW leased power, delivered, 7-year contract rather than 12'],
['Crusoe','Abilene Lancium Stargate',null,null,null,'gross','2025-06','2026-07','https://www.crusoe.ai/resources/newsroom/crusoe-expands-ai-data-center-campus-in-abilene-to-1-2-gigawatts','1200 total gross MW; phase 1 200+ MW; no public lease terms in cited release'],
['IREN','Sweetwater 1 initial construction',null,null,null,'gross','2027-10','2027-12','https://iren.gcs-web.com/news-releases/news-release-details/irens-2gw-sweetwater-hub-included-base-load-ercot-batch-zero','300 gross MW under construction, initial 1400 MW planned; conditional ERCOT process'],
['IREN','Sweetwater 2 planned',null,null,null,'gross','2028-06','2029-06','https://iren.gcs-web.com/news-releases/news-release-details/irens-2gw-sweetwater-hub-included-base-load-ercot-batch-zero','600 gross MW planned; date is MODEL ASSUMPTION, not disclosed target']
];
const grossOverrides={'Black Pearl AWS':300,'Abilene Lancium Stargate':1200,'Sweetwater 1 initial construction':300,'Sweetwater 2 planned':600};
const index=date=>{const [y,m]=date.split('-').map(Number);return (y-2025)*12+m};
const round=(n,k=4)=>Number.isFinite(n)?Number(n.toFixed(k)):null;
let cases=[],stresses=[],errors=[];
for (let [sponsor,name,mw,value,years,unit,first,last,url,note] of projects){
let itmw=mw??(grossOverrides[name]/1.3); // Gross-to-IT conversion scenario only
const disclosed=unit==='IT' && value!==null && years!==null;
const proxyRevenue=value!==null&&years!==null?value/years:null;
const rent=proxyRevenue!==null?proxyRevenue*1e6/12/(itmw*1000):170;
const start=Math.max(2,index(first)); const finish=Math.max(start,index(last));
let count= name==='Polaris Forge 1'?3:(name==='Abilene Lancium Stargate'?8:Math.min(3, Math.max(1,Math.ceil(itmw/100))));
let buildings=Array.from({length:count},(_,i)=>({name:`Phase ${i+1}`,itMW:itmw/count,constructionStart:Math.max(1,start-18+Math.floor(i*(finish-start)/Math.max(count-1,1))),constructionMonths:Math.max(6,Math.min(18,start-1)),powerMonth:start+Math.floor(i*(finish-start)/Math.max(count-1,1)),leaseMonth:start+Math.floor(i*(finish-start)/Math.max(count-1,1)),leaseTermMonths:12*(years||15),rentEscalatorPct:2.5}));
// 10 year term with 2025 reference; 20 year lease benchmark uses 25y horizon.
let horizon=Math.min(360,Math.max(144, (index(last)+12*(years||15)+12)));
let base={...defaults(),months:horizon,buildings,rentPerKwMonth:rent, constructionCostMW:7,exitValueM:itmw*12,refinanceValueM:itmw*8,termMonths:60,initialCash:Math.max(50,itmw*.4),minLiquidity:Math.max(10,itmw*.05),reserveTargetM:Math.max(10,itmw*.05)};
try{
const b=evaluate(base); const r=b.summary;
const rec={sponsor,project:name,public_capacity_mw:mw??grossOverrides[name],capacity_unit:unit,modeled_it_mw:round(itmw,2),reported_lease_value_m:value,reported_term_years:years,annual_lease_m_proxy:round(proxyRevenue,2),modeled_rent_kw_month:round(rent,2),benchmark_strength:disclosed?'lease_economics':(proxyRevenue!==null?'mixed_units_proxy':'physical_schedule_only'),reported_first:first,reported_last:last,modeled_npv_m:round(r.npvM,2),modeled_irr_pct:round(r.leveredIRR*100,3),peak_debt_m:round(r.peakDebtM,2),min_dscr:round(r.minDSCR,3),sources_uses_max_residual:round(r.sourcesUsesMaxResidual,9),source_url:url,source_notes:note,assumptions_not_public:'Capex $7M/IT MW, LTC 65%, debt 8%, PUE 1.3, power $85/MWh, discount 10%, exit $12M/MW, refi $8M/MW; gross converted at scenario PUE 1.3'};cases.push(rec);
for(const delay of [0,3,6,12,18])for(const overrun of [0,10,20])for(const bps of [0,200,400]){
const z=evaluate({...base,delayMonths:delay,overrunPct:overrun,rateShockPct:bps/100}).summary;
stresses.push({project:name,delay_months:delay,capex_overrun_pct:overrun,rate_shock_bps:bps,npv_m:round(z.npvM,2),irr_pct:round(z.leveredIRR*100,3),peak_debt_m:round(z.peakDebtM,2),min_dscr:round(z.minDSCR,3),covenant_breach_months:z.breachMonths.length,liquidity_breach_months:z.liquidityBreachMonths.length,reconciliation_error:round(z.sourcesUsesMaxResidual,8)});
}
}catch(e){errors.push({name,error:e.message})}
}
const csv=(data,file)=>{let keys=Object.keys(data[0]);fs.writeFileSync(path.join(out,file),[keys.join(','),...data.map(r=>keys.map(k=>JSON.stringify(r[k]??'')).join(','))].join('\n'))};
csv(cases,'public_project_benchmarks.csv');csv(stresses,'stress_results_720_scenarios.csv');fs.writeFileSync(path.join(out,'all_results.json'),JSON.stringify({cases,stresses,errors},null,2));
const maxReconciliation=Math.max(...stresses.map(x=>x.reconciliation_error||0));let report=`# PowerPath v25.1 — Public Project Benchmark and Stress Test\n\nRun generated 2026-10-25. ${cases.length} distinct campus/site benchmarks; ${stresses.length} synthetic stress cases (45 per project). ${errors.length} errors. Max monthly sources/uses residual in resulting stress cases: ${maxReconciliation}.\n\n## Limitations (read before interpreting)\n\n**These are not independent comparisons of actual project levered returns.** Public projects rarely disclose the debt, opex, capex, delivery tranches, equity waterfall, refinancing valuation, and lease details needed. The disclosed figures calibrate capacity and, where available, contractual revenue. All other financial inputs are deliberately common illustrative assumptions. Gross MW and leased customer power are not automatically critical IT MW; conversion is hypothetical and tagged. The model's exit value is a scenario assumption, not observed market valuation. All stress results are therefore sensitivity testing, not forecast accuracy.\n\n## Dataset summary\n\n| Public case | MW input | Evidence quality | Proxy annual revenue ($M) | Modeled equity NPV ($M) | Maximum residual |\n|---|---:|---|---:|---:|---:|\n`;
for(const c of cases)report+=`| ${c.project} | ${c.public_capacity_mw} ${c.capacity_unit} | ${c.benchmark_strength} | ${c.annual_lease_m_proxy??'n/d'} | ${c.modeled_npv_m} | ${c.sources_uses_max_residual} |\n`;
report+=`\n## Key model weaknesses surfaced\n- Uniform cost, exit, and refinancing assumptions drive outputs more than the limited public facts; do not rank projects by synthetic NPV.\n- The engine has no lease-expiry cessation for shorter leases, so late-horizon rents remain modeled even after reported base terms end.\n- The engine uses shared global construction loan/exit assumptions; it cannot represent some disclosed tenant-funded capex structures, 15-20 year contractual escalators, power pass-through arrangements, or multiple debt facilities.\n- Refinance debt sizing uses assumed property value and LTV, not lender DSCR and debt yield checks.\n- A historical quote is not a signed grid capacity agreement and benchmark construction dates are often target rather than actual.\n\n## Disclosures and traceability\n`;
for(const c of cases)report+=`- **${c.project}**: ${c.source_notes}. ${c.source_url}\n`;
report+=`\n## Recommended model changes\n1. Fix lease term, escalators, and revenue recognition by phase; explicitly distinguish site gross, IT and leased customer power.\n2. Connect real capex and financing disclosures as dated versions rather than scenario assumptions.\n3. Debt sizing should constrain the minimum of LTV, DSCR, debt yield, and LTC.\n4. Add a true backtest mode with forecast as-of dates and realized actuals; this dataset does not justify accuracy statistics.\n5. Report cases with incomplete information as stress-only, not calibrated.\n`;
fs.writeFileSync(path.join(out,'STRESS_TEST_REPORT.md'),report);
console.log(JSON.stringify({projects:cases.length,stress_cases:stresses.length,errors,maxReconciliation,negativeNPV:stresses.filter(x=>x.npv_m<0).length,positiveNPV:stresses.filter(x=>x.npv_m>=0).length},null,2));
