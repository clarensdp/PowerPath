const E=require('./engine2.js'),base=require('./hourly.json');E.setRegions(require('./regions.json'));let pass=0,fail=0;
const ok=(n,c,msg)=>{if(c){pass++;console.log('PASS',n,msg||'');}else{fail++;console.log('FAIL',n,msg||'');}};
// 1. calibration against the checker-validated hackathon benchmark (same dispatch rules: $100/t carbon shadow)
const CAL=[['Balanced',{solar:70,wind:155,turbine:25},18,53.18,65.0,100,true],['N-1 reliability',{solar:65,wind:150,turbine:50},18,57.20,73.8,100,true],['Carbon cap (cost-first)',{solar:65,wind:130,turbine:25},18,51.17,null,0,true],
 ['Earlier opening (info)',{solar:45,wind:120,engine:15,fuelcell:30},14,76.33,120.6,100,false],['Lead-time aware (info)',{solar:70,wind:160,battery:4,engine:10},22,55.10,48.7,100,false]];
const calib=[];
for(const [name,mix,open,usd,kg,cs,strict] of CAL){const sp=E.calibSpec(mix,open);sp.carbonShadow=cs;const sim=E.simulate(sp,base),c=E.calibCost(sim),err=c.usd/usd-1;calib.push({name,model:+c.usd.toFixed(2),official:usd,err:+(100*err).toFixed(1),kg:+c.kg.toFixed(1),kgOfficial:kg,strict});
 if(strict)ok('calib '+name,Math.abs(err)<0.015&&(kg==null||Math.abs(c.kg-kg)/kg<0.02),`model ${c.usd.toFixed(2)} vs official ${usd} $/MWh (${(100*err).toFixed(1)}%), ${c.kg.toFixed(1)} vs ${kg} kg`);
 else console.log('INFO calib',name,`model ${c.usd.toFixed(2)} vs official ${usd} (${(100*err).toFixed(1)}%): heuristic dispatch vs optimal LP during a constrained ramp / plan-specific availability`);}
require('fs').writeFileSync(__dirname+'/calibration.json',JSON.stringify(calib));
// 2. unconstrained behaviour
const D=E.defaults();const r=E.evaluate({},base,{breakEven:true});
ok('base runs',Number.isFinite(r.fin.npv)&&r.fin.cost>0,`NPV ${(r.fin.npv/1e6).toFixed(1)}M cost ${r.fin.cost.toFixed(2)} kg ${r.fin.kg.toFixed(0)} powerOn M${r.fin.powerOn} breakRent ${r.fin.breakRent&&r.fin.breakRent.toFixed(0)}`);
const big=E.evaluate({itMW:400,mix:{solar:400,wind:800,turbine:200,battery:100,batteryHours:4}},base);
ok('scales to 500 MW',big.sim.peak===500&&big.fin.served>r.fin.served*5,`served ${(big.fin.served/1e6).toFixed(2)} TWh`);
const noB=E.evaluate({mix:{...D.mix,battery:0}},base),withB=E.evaluate({mix:{...D.mix,battery:40,batteryHours:4}},base),noGrid=E.evaluate({mix:{...D.mix,battery:40,batteryHours:4},gridCharging:false},base);
ok('battery charges from grid',withB.fin.totals.gridCharge>0&&noGrid.fin.totals.gridCharge===0,`grid charge ${(withB.fin.totals.gridCharge/1e3).toFixed(0)} MWh`);
ok('battery reduces merchant cost',withB.sim.years.reduce((t,A)=>t+A.merchant,0)<noB.sim.years.reduce((t,A)=>t+A.merchant,0),'arbitrage lowers grid purchases cost');
const early=E.evaluate({openMonth:12,mix:{...D.mix,turbine:0}},base),bridged=E.evaluate({openMonth:12,mix:{...D.mix,turbine:50,engine:30},lead:{turbine:12,engine:12}},base);
ok('pre-grid opening needs onsite power',early.fin.unserved>bridged.fin.unserved,`unserved ${(early.fin.unserved/1e3).toFixed(0)} vs ${(bridged.fin.unserved/1e3).toFixed(0)} MWh`);
const reg=E.regionFromSite({name:'Iowa',grid:'MISO',price_c:9.34,co2_grid:285.9,solar_cf:0.2,wind_cf:0.38});ok('regional scaling',reg.wind>1&&reg.solar<1&&reg.ppaSolar>1,JSON.stringify(reg));
const S=require('./sites.json').sites,rs=ab=>E.evaluate({region:E.regionFromSite(S.find(x=>x.ab===ab)),mix:{solar:0,wind:0,turbine:0,engine:0,fuelcell:0}},base,{stride:3}).fin;
const va=rs('VA'),wa=rs('WA');ok('EIA-930 regions: hydro grid cleaner than PJM',E.regionFromSite(S.find(x=>x.ab==='VA')).ba==='PJM'&&wa.kg<va.kg*0.3,`VA ${va.kg.toFixed(0)} vs WA ${wa.kg.toFixed(0)} kg/MWh`);
const rb=E.regionalBase(base,'CISO'),noon=[...Array(365).keys()].reduce((t,d)=>t+rb.solar[d*24+12],0),night=[...Array(365).keys()].reduce((t,d)=>t+rb.solar[d*24+2],0);ok('regional solar peaks midday',noon>50&&night===0,`noon ${noon.toFixed(0)} night ${night}`);
// ---- accounting audit regressions (v18)
{const g=E.evaluate({mix:{solar:0,wind:0,nuclear:0,battery:40,batteryHours:4,turbine:0,engine:0,fuelcell:0},gridCharging:true,arbitrage:true},base).fin;
 ok('grid-charged battery is not clean',g.totals.dischargeGrid>0&&g.totals.dischargeClean===0&&g.clean<0.001,`discharge from grid ${(g.totals.dischargeGrid/1e3).toFixed(0)} MWh, clean share ${(100*g.clean).toFixed(2)}%`);
 const c=E.evaluate({mix:{solar:200,wind:0,nuclear:0,battery:40,batteryHours:4,turbine:0,engine:0,fuelcell:0},gridCharging:false},base).fin;
 ok('solar-charged battery is clean',c.totals.dischargeClean>0&&c.totals.dischargeGrid<1e-6,`clean discharge ${(c.totals.dischargeClean/1e3).toFixed(0)} MWh`);
 const e=E.evaluate({mix:{solar:100,wind:50,nuclear:0,battery:30,batteryHours:4,turbine:10,engine:10,fuelcell:10}},base);let bad=0;
 e.sim.years.forEach(A=>{const src=A.solar+A.wind+A.nuclear+A.grid+A.turbine+A.engine+A.fuelcell+A.discharge;if(A.req>0&&Math.abs(src-A.served)>1e-6*A.req+1)bad++;if(A.discharge>(A.cleanCharge+A.gridCharge)*0.85+40*4*1.01)bad++;});
 ok('energy balance: sources = served, discharge <= charge x RTE',bad===0,`${bad} bad years`);}
{const sp={openMonth:24,rampMonths:12,fin:{rentEsc:0}},r=E.evaluate(sp,base).fin,y3=r.rows[2],y5=r.rows[4];
 ok('rent ramps with the lease-up',y3.rent<y5.rent*0.75,`year 3 rent ${(y3.rent/1e6).toFixed(1)}M vs year 5 ${(y5.rent/1e6).toFixed(1)}M`);
 const full=175*12*60000*0.9;ok('stabilized rent = rent x IT kW x occupancy',Math.abs(y5.rent-full*(r.served?y5.served/y5.req:1))/full<0.02,`${(y5.rent/1e6).toFixed(2)}M vs ${(full/1e6).toFixed(2)}M`);
 const esc=E.evaluate({fin:{rentEsc:2.5}},base).fin;ok('rent escalates',esc.rows[15].rent>esc.rows[5].rent*1.2);}
{const r=E.evaluate({openMonth:30,mix:{solar:0,wind:0,nuclear:0,battery:0,batteryHours:4,turbine:0,engine:0,fuelcell:20},conn:{firstMonth:30,fullMonth:36}},base).fin;
 ok('no equipment O&M before opening',r.rows[0].energy===0&&r.rows[1].energy===0,`year1 ${r.rows[0].energy} year2 ${r.rows[1].energy}`);
 const b=E.evaluate({mix:{battery:40,batteryHours:4}},base).fin;ok('battery replaced at end of life inside hold',(b.replace.battery||0)>0&&b.rows[16].capex>0,`replacement ${((b.replace.battery||0)/1e6).toFixed(1)}M in year ${b.rows.findIndex((x,i)=>i>3&&x.capex>0)+1}`);
 const last=b.rows[b.rows.length-1];ok('exit taxed on gain over remaining basis',last.tax<(last.taxable+b.exit)*0.25,`exit tax ${(last.tax/1e6).toFixed(1)}M on exit ${(b.exit/1e6).toFixed(0)}M, basis ${(b.remBasis/1e6).toFixed(0)}M`);}
const incl=E.evaluate({fin:{rentBasis:'incl'}},base),pass2=E.evaluate({fin:{rentBasis:'pass'}},base);ok('pass-through raises NPV',pass2.fin.npv>incl.fin.npv);
(async()=>{const t0=Date.now();const o=await E.optimize({},base,{passes:4});const e=E.evaluate({mix:o.mix},base);ok('optimizer improves NPV',e.fin.npv>=r.fin.npv-1,`${JSON.stringify(o.mix)} NPV ${(e.fin.npv/1e6).toFixed(1)}M after ${o.evals} evals in ${Date.now()-t0} ms`);
console.log(`${pass} passed, ${fail} failed`);process.exit(fail?1:0);})();
