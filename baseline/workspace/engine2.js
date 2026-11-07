/* PowerPath engine v2: unconstrained sizing, hourly dispatch and project finance for a data-center campus.
   Pure functions (browser + Node). Hourly shapes: EIA-930 regional carbon, solar and wind (regions.json) where available; otherwise the 2023 ERCOT reference year scaled to
   each state's price, carbon intensity and solar / wind resource. Costs default to cited public sources and
   are all editable. The hackathon benchmark is reproduced in calibration mode (see test_engine2.cjs). */
(function(root){
const SOURCES={
 eia:'EIA, Capital Cost and Performance Characteristics (AEO2023, 2022$)',
 aero26:'2026 market: EIA AEO2025 aeroderivative $1,606/kW (2023$) escalated for the turbine backlog (Wood Mackenzie: equipment prices +195% since 2019; GridLab: ~$2,000/kW for 2030-31 projects); lead time ~40 months (Enverus via Reuters Events, Sep 2026)',
 recip26:'2026 market: EIA AEO2023 reciprocating engine $2,240/kW (2022$) escalated ~7%; INNIO-VoltaGrid data-center fleet delivered from Dec 2025 with first units operating Apr 2026, so 18 months order-to-power is a screening value',
 fc26:'2026 market: industry analysis puts Bloom SOFC at ~$2,500-3,000/kW installed (unverified, low confidence; EIA AEO2023 reference $6,771/kW); Oracle system delivered in 55 days, so 9 months covers procurement and permits',
 eia930:'EIA-930 hourly grid operations Oct 2025-Sep 2026 with EPA eGRID2023 factors, via Cleanest Hour (MIT license)',
 atb:'NREL Annual Technology Baseline 2024, utility-scale battery storage',
 lvl:'LevelTen North American PPA Price Index, Q2 2026 (P25)',
 steo:'EIA Short-Term Energy Outlook, July 2026 (Henry Hub 2027)',
 jll:'JLL 2026 forecast via Datacentres.com ($11.3M per MW)',
 egrid:'EPA eGRID 2023 state output rates',
 eia_price:'EIA 2024 average retail price by state',
 usda:'USDA NASS 2025 land values'};
const CATALOG={
 solar:{name:'Solar PPA',kind:'contract',price:52.65,lead:24,src:'lvl'},
 wind:{name:'Wind PPA',kind:'contract',price:61.19,lead:30,src:'lvl'},
 nuclear:{name:'Nuclear PPA',kind:'firm',price:95,lead:72,src:'assumption'},
 battery:{name:'Battery storage',kind:'storage',capex:1270,fomPct:2.5,rte:0.85,life:15,lead:18,acresPerMW:0.15,src:'eia+atb'},
 turbine:{name:'Gas turbine (aeroderivative)',kind:'thermal',capex:2000,fom:18.35,vom:5.29,hr:9.124,life:25,lead:40,acresPerMW:0.1,src:'aero26'},
 engine:{name:'Reciprocating engines',kind:'thermal',capex:2400,fom:39.57,vom:6.40,hr:8.295,life:20,lead:18,acresPerMW:0.05,src:'recip26'},
 fuelcell:{name:'Fuel cells',kind:'thermal',capex:3000,fom:34.65,vom:0.66,hr:6.469,life:15,lead:9,acresPerMW:0.05,src:'fc26'}};
const THERMAL=['fuelcell','engine','turbine'];
const GAS_T_PER_MMBTU=0.05306;
const NAT_CF={solar:0.245,wind:0.35},TX_REF={price_c:9.79,co2:348.495,solar_cf:0.25,wind_cf:0.37};
function defaults(){return {
 itMW:60,pue:1.25,openMonth:20,horizonYears:20,rampMonths:10,rampStart:1/3,
 conn:{mw:null,firstMonth:18,fullMonth:30,firstShare:1/3,stressFrac:0.6},
 mix:{solar:70,wind:155,nuclear:0,battery:0,batteryHours:4,turbine:25,engine:0,fuelcell:0},
 lead:{},gridCharging:true,arbitrage:true,flexShare:0.10,voll:1000,carbonShadow:0,
 market:{hh:3.49,gasAdder:0.75,gasEsc:0.02,powerEsc:0.03,co2Esc:-0.03,demandCharge:0,gridServices:0},
 fin:{rent:175,rentBasis:'pass',occupancy:90,campusCapexPerMW:11.3,otherOpexPct:30,fixedOpexPerMWyr:0.04,upgradePerKW:60,landPerAcre:2970,acresPerMW:1.5,
  taxRate:25,campusLife:20,energyLife:7,exitMult:10,discount:8,slaPenalty:500,rentEsc:2.5,depositPct:30},
 region:{price:1,co2:1,solar:1,wind:1,label:'Texas · ERCOT'},
 goals:{carbonValue:0,maxKg:null,minClean:null,voll:10000}};}
let REG=null;const RBCACHE=new Map();
function setRegions(r){REG=r;RBCACHE.clear();}
function dec(s,bytes){const bin=typeof atob==='function'?atob(s):Buffer.from(s,'base64').toString('binary');const u=new Uint8Array(bin.length);for(let i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);return bytes===2?new Uint16Array(u.buffer):u;}
function regionalBase(base,ba){const key=ba;if(RBCACHE.has(key)&&RBCACHE.get(key).src===base)return RBCACHE.get(key).b;const o=REG.ba[ba];
 const mean=a=>{let t=0;for(const v of a)t+=v;return t/a.length;};const sol=dec(o.solar,1),win=dec(o.wind,1),co=dec(o.co2,2);
 const ks=mean(base.solar)/Math.max(1e-9,mean(sol)),kw=mean(base.wind)/Math.max(1e-9,mean(win));
 const b={...base,solar:Array.from(sol,v=>Math.min(1,v*ks)),wind:Array.from(win,v=>Math.min(1,v*kw)),co2:Array.from(co,v=>v/1000)};RBCACHE.set(key,{src:base,b});return b;}
function regionFromSite(s){const ba=REG&&REG.stateBA&&REG.stateBA[s.ab]&&REG.ba[REG.stateBA[s.ab]]?REG.stateBA[s.ab]:null;return {ba,baName:ba?REG.ba[ba].name:null,price:(s.price_c||TX_REF.price_c)/TX_REF.price_c,co2:ba?1:(s.co2_grid||TX_REF.co2)/TX_REF.co2,solar:(s.solar_cf||TX_REF.solar_cf)/TX_REF.solar_cf,wind:(s.wind_cf||TX_REF.wind_cf)/TX_REF.wind_cf,label:s.name+' · '+s.grid,
 ppaSolar:Math.min(1.5,Math.max(0.75,NAT_CF.solar/(s.solar_cf||NAT_CF.solar))),ppaWind:Math.min(1.5,Math.max(0.75,NAT_CF.wind/(s.wind_cf||NAT_CF.wind)))};}
function merge(a,b){const o=Array.isArray(a)?a.slice():{...a};for(const k in b){if(b[k]&&typeof b[k]==='object'&&!Array.isArray(b[k])&&a&&typeof a[k]==='object')o[k]=merge(a[k],b[k]);else if(b[k]!==undefined)o[k]=b[k];}return o;}
function crf(r,n){return r/(1-Math.pow(1+r,-n));}
/* daily price ranks for storage arbitrage, from the reference price shape */
const RANKCACHE=new Map();
function dayRanks(base){if(RANKCACHE.has(base))return RANKCACHE.get(base);const out=[];for(let d=0;d<365;d++){const hs=[...Array(24).keys()].map(i=>d*24+i).sort((x,y)=>base.whole[x]-base.whole[y]);const rank=new Int8Array(24);hs.forEach((h,i)=>rank[h-d*24]=i);out.push(rank);}RANKCACHE.set(base,out);return out;}
/* hourly dispatch over the development horizon (730-hour months, reference hour = h mod 8760) */
function simulate(spec,base,opt={}){
 const s=merge(defaults(),spec);if(s.region&&s.region.ba&&REG&&REG.ba[s.region.ba]&&!s.calib)base=regionalBase(base,s.region.ba);const mix=s.mix,M=s.market,R=s.region,H=Math.round(s.horizonYears)*12;
 const peak=s.itMW*s.pue,connMW=s.conn.mw==null?peak:s.conn.mw,maxLoad=Math.max(...base.load);
 const lead=k=>s.lead[k]!=null?s.lead[k]:CATALOG[k].lead;
 const avail=k=>(mix[k]||0)>0?Math.max(lead(k),0):Infinity;
 const ppa={solar:CATALOG.solar.price*(R.ppaSolar||1),wind:CATALOG.wind.price*(R.ppaWind||1),nuclear:CATALOG.nuclear.price};
 if(s.calib){ppa.solar=s.calib.ppa.solar;ppa.wind=s.calib.ppa.wind;ppa.nuclear=s.calib.ppa.nuclear;}
 const B=CATALOG.battery,Pb=mix.battery||0,hrs=mix.batteryHours||4,Eb=Pb*hrs,eta=Math.sqrt(s.calib?s.calib.rte:B.rte);
 const ranks=dayRanks(base),stride=opt.stride||1;
 const Y=[...Array(Math.ceil(H/12))].map(()=>({req:0,served:0,curtail:0,unserved:0,unservedH:0,solar:0,wind:0,nuclear:0,grid:0,gridCharge:0,cleanCharge:0,discharge:0,dischargeClean:0,dischargeGrid:0,turbine:0,engine:0,fuelcell:0,contract:0,merchant:0,fuel:0,vom:0,co2:0,clean:0,peakImport:0,spill:0}));
 const MR=new Float64Array(H),MS=new Float64Array(H),ML=new Float64Array(H);let soc=0,socC=0;const occ=s.calib?1:Math.max(0,Math.min(100,s.fin.occupancy))/100;const trace=[];const tr=opt.trace;const audit=opt.audit?{hours:0,failures:0,maxSocResidual:0,maxCleanResidual:0,maxBoundsViolation:0,violations:[]}:null;
 for(let m=0;m<H;m++){
  const k=m-s.openMonth,rs0=s.calib?1/3:Math.max(0.01,Math.min(1,s.rampStart)),frac=(k<0?0:Math.min(1,rs0+k*(1-rs0)/s.rampMonths))*occ,y=Math.floor(m/12),A=Y[y];ML[m]=frac;
  let gcap=m>=s.conn.fullMonth?connMW:m>=s.conn.firstMonth?connMW*s.conn.firstShare:0;if(s.conn.steps){gcap=0;for(const [m0,mw] of s.conn.steps)if(m>=m0)gcap=mw;}
  for(let j=0;j<730;j+=1){
   const h=m*730+j,r=h%8760;const previousSOC=soc,previousCleanSOC=socC;if(stride>1&&(Math.floor(r/24)+Math.floor(h/8760))%stride!==0)continue;const w=stride;
   const yr=h/8760,L=peak*base.load[r]/maxLoad*frac;
   const price=(base.whole[r]*R.price*Math.pow(1+M.powerEsc,yr)+base.adder);
   const gas=(s.calib?base.hh[r]*Math.pow(1+M.gasEsc,yr)+base.gadd[r]:M.hh*Math.pow(1+M.gasEsc,yr)+M.gasAdder);
   const gco2=base.co2[r]*R.co2*Math.pow(1+M.co2Esc,yr);
   const stress=base.stress[r],G=gcap*(stress?(s.calib?base.sfrac[r]:s.conn.stressFrac):1);
   const on=x=>m>=Math.max(s.openMonth,avail(x));
   const sol=on('solar')?(mix.solar||0)*Math.min(1,base.solar[r]*R.solar):0,win=on('wind')?(mix.wind||0)*Math.min(1,base.wind[r]*R.wind):0,nuc=on('nuclear')?(mix.nuclear||0)*base.firm[r]:0;
   if(L<=0){continue;}
   A.req+=L*w;MR[m]+=L*w;
   A.contract+=(sol*ppa.solar+win*ppa.wind+nuc*ppa.nuclear)*w;
   const off=sol+win+nuc,del=Math.min(off,G);let c=Math.min(del,L),D=L-c,spare=del-c,head=G-del;
   const fromS=off>0?sol/off:0,fromW=off>0?win/off:0;A.solar+=c*fromS*w;A.wind+=c*fromW*w;A.nuclear+=(c-c*fromS-c*fromW)*w;
   const bOn=Pb>0&&m>=Math.max(s.openMonth,avail('battery'));let ch=0,gch=0,dis=0,disC=0;
   if(bOn&&spare>0){ch=Math.min(spare,Pb,(Eb-soc)/eta);soc+=ch*eta;socC+=ch*eta;spare-=ch;}
   const rk=ranks[Math.floor(r/24)%365][r%24];
   if(bOn&&s.gridCharging&&s.arbitrage&&!stress&&rk<hrs&&head>0&&soc<Eb){gch=Math.min(Pb-ch,(Eb-soc)/eta,head);if(gch>0){soc+=gch*eta;head-=gch;}}
   A.spill+=(Math.max(0,off-del)+spare)*w;
   if(bOn&&D>0&&soc>1e-9){const want=stress||D>head||(s.arbitrage&&rk>=24-hrs)||(!s.gridCharging&&price>60);if(want){dis=Math.min(D,Pb,soc*eta);const cf=soc>1e-9?Math.min(1,socC/soc):0;disC=dis*cf;soc-=dis/eta;socC=Math.max(0,socC-dis/eta*cf);D-=dis;}}
   A.cleanCharge+=ch*w;A.gridCharge+=gch*w;A.discharge+=dis*w;A.dischargeClean+=disC*w;A.dischargeGrid+=(dis-disC)*w;
   A.clean+=(c+disC)*w;
   // merit order: onsite thermal vs grid, carbon shadow for dispatch only
   const offers=[];for(const t of THERMAL)if((mix[t]||0)>0&&on(t)){const C=s.calib&&s.calib.thermal[t]?s.calib.thermal[t]:CATALOG[t];offers.push({t,mw:mix[t],cost:gas*C.hr+C.vom,sc:gas*C.hr+C.vom+s.carbonShadow*C.hr*GAS_T_PER_MMBTU,co2:C.hr*GAS_T_PER_MMBTU});}
   offers.push({t:'grid',mw:head,cost:price,sc:price+s.carbonShadow*gco2,co2:gco2});offers.sort((a,b)=>a.sc-b.sc);
   let imp=gch+del;
   for(const o of offers){if(D<=1e-9)break;const q=Math.min(D,o.mw);if(q<=0)continue;D-=q;
    if(o.t==='grid'){A.grid+=q*w;A.merchant+=q*price*w;A.co2+=q*o.co2*w;imp+=q;}else{A[o.t]+=q*w;A.fuel+=q*(o.cost-(s.calib&&s.calib.thermal[o.t]?s.calib.thermal[o.t].vom:CATALOG[o.t].vom))*w;A.vom+=q*(s.calib&&s.calib.thermal[o.t]?s.calib.thermal[o.t].vom:CATALOG[o.t].vom)*w;A.co2+=q*o.co2*w;}}
   A.merchant+=gch*price*w;A.co2+=gch*gco2*w;
   if(imp>A.peakImport)A.peakImport=imp;
   let cur=0;if(D>1e-6){if(s.calib){if(stress){const r1=Math.min(D,s.calib.reloc,base.t1[r]*frac);D-=r1;A.merchant+=r1*s.calib.relocUsd*w;A.co2+=r1*1.05*gco2*w;A.curtail+=0;const r2=Math.min(D,base.t2[r]*frac);D-=r2;A.unserved+=r2*w;}}
    else{cur=Math.min(D,L*s.flexShare);D-=cur;A.curtail+=cur*w;}
    if(D>1e-6){A.unserved+=D*w;A.unservedH+=w;}}
   const served=L-cur-Math.max(0,D>1e-6?D:0);A.served+=served*w;MS[m]+=served*w;
   if(audit){const expected=previousSOC+(ch+gch)*eta-dis/eta;const expectedClean=previousCleanSOC+ch*eta-disC/eta;const er=Math.abs(soc-expected),ec=Math.abs(socC-expectedClean),bounds=Math.max(0,-soc,soc-Eb,-socC,socC-soc);audit.hours++;audit.maxSocResidual=Math.max(audit.maxSocResidual,er);audit.maxCleanResidual=Math.max(audit.maxCleanResidual,ec);audit.maxBoundsViolation=Math.max(audit.maxBoundsViolation,bounds);if(er>1e-7||ec>1e-7||bounds>1e-7||Math.abs(disC+(dis-disC)-dis)>1e-7){audit.failures++;if(audit.violations.length<10)audit.violations.push({h,er,ec,bounds});}}
    if(tr&&y===tr.year&&r>=tr.start&&r<tr.start+168&&j%stride===0)trace.push({r,L,sol:c*fromS,win:c*fromW,nuc:c-c*fromS-c*fromW,dis,ch:ch+gch,grid:imp-del-gch,th:L-c-dis-(imp-del-gch)-cur-Math.max(0,D),cur,uns:Math.max(0,D),price,G});
  }}
 return {spec:s,years:Y,monthReq:MR,monthServed:MS,monthLease:ML,trace,audit,peak,connMW,avail:Object.fromEntries(Object.keys(CATALOG).map(k=>[k,avail(k)])),ppa};}
/* project finance on top of the dispatch (annual, real dollars) */
function finance(sim,finIn={}){
 const s=sim.spec,f={...s.fin,...finIn},mix=s.mix,H=sim.monthReq.length,Yn=Math.ceil(H/12),itKW=s.itMW*1000,dr=f.discount/100;
 const capexItem=k=>{const C=CATALOG[k];if(k==='battery'){const h=mix.batteryHours||4;return (mix.battery||0)*1000*C.capex*(0.35+0.65*h/4);}return (mix[k]||0)*1000*(C.capex||0);};
 const fomItem=k=>{const C=CATALOG[k];if(k==='battery')return capexItem(k)*C.fomPct/100;return (mix[k]||0)*1000*(C.fom||0);};
 const rows=[];let nol=0;const campus=s.itMW*f.campusCapexPerMW*1e6,cStart=Math.max(0,s.openMonth-24);
 const dep=new Float64Array(Yn);const addDep=(amt,y0,life)=>{for(let y=y0;y<Math.min(Yn,y0+life);y++)dep[y]+=amt/life;};
 const capexY=new Float64Array(Yn);let basis=campus;const inSvc=k=>Math.max(s.openMonth,sim.avail[k]);
 for(let m=cStart;m<s.openMonth;m++)capexY[Math.floor(m/12)]+=campus/Math.max(1,s.openMonth-cStart);
 addDep(campus,Math.floor(s.openMonth/12),f.campusLife);
 const energyCapex={},replace={};for(const k of ['battery','turbine','engine','fuelcell']){const c=capexItem(k);if(c>0){
   const dep0=Math.min(Yn-1,Math.floor(sim.avail[k]/12)),pay0=0;capexY[pay0]+=c*f.depositPct/100;capexY[dep0]+=c*(1-f.depositPct/100);energyCapex[k]=c;basis+=c;
   const sv=inSvc(k);addDep(c,Math.min(Yn-1,Math.floor(sv/12)),f.energyLife);
   const life=CATALOG[k].life*12;for(let r=sv+life;r<H;r+=life){const yr=Math.floor(r/12);capexY[yr]+=c;addDep(c,yr,f.energyLife);basis+=c;replace[k]=(replace[k]||0)+c;}}}
 const upgrade=f.upgradePerKW*sim.peak*1000,land=f.landPerAcre*f.acresPerMW*sim.peak;capexY[0]+=land;basis+=upgrade;capexY[Math.min(Yn-1,Math.floor(s.conn.firstMonth/12))]+=upgrade;addDep(upgrade,Math.floor(s.conn.firstMonth/12),f.campusLife);
 for(let y=0;y<Yn;y++){const A=sim.years[y];let rev=0;for(let m=y*12;m<Math.min(H,y*12+12);m++){if(m<s.openMonth||sim.monthReq[m]<=0)continue;const fr=sim.monthServed[m]/sim.monthReq[m],lease=sim.monthLease?sim.monthLease[m]:f.occupancy/100;rev+=f.rent*Math.pow(1+(f.rentEsc||0)/100,(m-s.openMonth)/12)*itKW*lease*fr;}
  const fom=Object.keys(CATALOG).reduce((t,k)=>t+((mix[k]||0)>0&&y*12+12>inSvc(k)?fomItem(k)*Math.min(1,(y*12+12-Math.max(y*12,inSvc(k)))/12):0),0);
  const energy=A.contract+A.merchant+A.fuel+A.vom+fom+s.market.demandCharge*1000*A.peakImport*12*(A.req>0?1:0)-s.market.gridServices*1000*(mix.battery||0)*(A.req>0?1:0);
  const pass=f.rentBasis==='pass'?energy:0,revenue=rev+pass;
  const esc=Math.pow(1+(f.rentEsc||0)/100,Math.max(0,y-s.openMonth/12)),opex=rev*f.otherOpexPct/100+(A.req>0?f.fixedOpexPerMWyr*1e6*s.itMW*esc:0)+A.unserved*f.slaPenalty;
  const ebitda=revenue-energy-opex;let taxable=ebitda-dep[y];if(taxable<0){nol-=taxable;taxable=0;}else{const u=Math.min(nol,taxable);nol-=u;taxable-=u;}
  rows.push({year:y+1,revenue,rent:rev,energy,opex,ebitda,capex:capexY[y],dep:dep[y],tax:0,taxable,cf:0,co2:A.co2,served:A.served,req:A.req});}
 const exit=Math.max(0,rows[Yn-1].ebitda*f.exitMult),depSum=dep.reduce((a,b)=>a+b,0),remBasis=Math.max(0,basis-depSum)+land,exitGain=exit-remBasis;
 let npv=0,cum=0,payback=null;const cfs=[];
 rows.forEach((r,i)=>{let taxable=r.taxable+(i===Yn-1?exitGain:0);if(taxable<0)taxable=0;r.tax=taxable*f.taxRate/100;r.exit=i===Yn-1?exit:0;r.cf=r.ebitda-r.capex-r.tax+r.exit;cfs.push(r.cf);npv+=r.cf/Math.pow(1+dr,i+0.5);cum+=r.cf;r.cumulative=cum;if(payback==null&&cum>=0&&i>0&&rows.slice(0,i).some(x=>x.cumulative<0))payback=i+1;});
 const irr=(()=>{const v=t=>cfs.reduce((a,c,i)=>a+c/Math.pow(1+t,i+0.5),0);let lo=-0.9,hi=2;if(v(lo)*v(hi)>0)return null;for(let i=0;i<80;i++){const md=(lo+hi)/2;if(v(lo)*v(md)<=0)hi=md;else lo=md;}return (lo+hi)/2;})();
 // levelized cost of power: PV(energy costs + annualized energy capex + upgrade) / PV(served MWh)
 let pvC=0,pvE=0;sim.years.forEach((A,y)=>{const ann=Object.entries(energyCapex).reduce((t,[k,c])=>t+(y*12+12>inSvc(k)?c*crf(dr||0.08,CATALOG[k].life):0),0)+(y*12+12>s.conn.firstMonth?upgrade*crf(dr||0.08,25):0);pvC+=(rows[y].energy+ann)/Math.pow(1+dr,y+0.5);pvE+=A.served/Math.pow(1+dr,y+0.5);});
 const T=k=>sim.years.reduce((t,A)=>t+A[k],0),served=T('served'),req=T('req');
 let powerOn=null;for(let m=s.openMonth;m<H;m++){if(sim.monthReq[m]>0&&sim.monthServed[m]/sim.monthReq[m]>=0.99){powerOn=m;break;}}
 return {rows,npv,irr,payback,exit,cost:pvE>0?pvC/pvE:null,kg:served>0?1000*T('co2')/served:null,clean:served>0?T('clean')/served:0,served,req,unserved:T('unserved'),unservedH:T('unservedH'),curtail:T('curtail'),
  energyCapex,replace,remBasis,campus,upgrade,land,powerOn,acres:Object.keys(CATALOG).reduce((t,k)=>t+(mix[k]||0)*(CATALOG[k].acresPerMW||0),0),totals:Object.fromEntries(['solar','wind','nuclear','grid','discharge','dischargeClean','dischargeGrid','gridCharge','cleanCharge','turbine','engine','fuelcell','spill'].map(k=>[k,T(k)]))};}
function evaluate(spec,base,opt={}){const sim=simulate(spec,base,opt);const f=finance(sim,opt.fin||{});
 if(opt.breakEven){const at=r=>finance(sim,{...opt.fin,rent:r}).npv;let r0=sim.spec.fin.rent,n0=f.npv,r1=r0+40,n1=at(r1);for(let i=0;i<8&&Math.abs(n1-n0)>1;i++){const r2=Math.max(0,r1-n1*(r1-r0)/(n1-n0));r0=r1;n0=n1;r1=r2;n1=at(r1);if(Math.abs(n1)<1e5)break;}f.breakRent=Math.abs(n1)<1e6?r1:null;}
 return {sim,fin:f};}
/* coordinate-descent sizing: maximize NPV minus any internal carbon value, subject to optional limits */
async function optimize(spec,base,o={}){
 const allow=o.allow||{solar:true,wind:true,nuclear:false,battery:true,turbine:true,engine:true,fuelcell:true};
 const s=merge(defaults(),spec),peak=s.itMW*s.pue,step=Math.max(5,Math.round(peak*0.05/5)*5);
 let mix={...s.mix};for(const k of Object.keys(allow))if(!allow[k])mix[k]=0;
 const score=m=>{const e=evaluate({...spec,mix:m},base,{stride:o.stride||3});const f=e.fin;let v=f.npv-(o.carbonValue||0)*(f.kg||0)/1000*f.served*0.5-(o.voll!=null?o.voll:10000)*f.unserved;
  if(o.maxKg!=null&&f.kg>o.maxKg)v-=1e9*(f.kg-o.maxKg)/100;if(o.minClean!=null&&f.clean<o.minClean)v-=1e9*(o.minClean-f.clean);if(o.maxAcres!=null&&f.acres>o.maxAcres)v-=1e9*(f.acres-o.maxAcres);return v;};
 let best=score(mix),evals=1;const keys=Object.keys(allow).filter(k=>allow[k]);
 for(let pass=0;pass<(o.passes||6);pass++){let moved=false;
  for(const k of keys){for(const dir of [1,-1]){let improved=true;while(improved){improved=false;const cand={...mix,[k]:Math.max(0,(mix[k]||0)+dir*step)};if(cand[k]===mix[k])break;const v=score(cand);evals++;if(v>best+1){best=v;mix=cand;improved=true;moved=true;}if(o.onProgress)await o.onProgress(evals,mix);}}}
  if(mix.battery>0){for(const hh of [2,4,8]){if(hh===mix.batteryHours)continue;const cand={...mix,batteryHours:hh};const v=score(cand);evals++;if(v>best+1){best=v;mix=cand;moved=true;}}}
  if(!moved)break;}
 return {mix,evals};}
/* calibration: the hackathon packet's cost accounting ($ per requested MWh), for the benchmark test only */
const PACKET={turbine:{capex:1606,fom:9.56,life:25,hr:9.447,vom:5.7},engine:{capex:2400,fom:25,life:20,hr:8.454,vom:12},fuelcell:{capex:4000,fom:150,life:15,hr:6.5,vom:5},battery:{capex:1744,fom:40,life:15}};
function calibSpec(mix,open){return {itMW:60,pue:1.25,openMonth:open,horizonYears:10,rampMonths:10,mix:{batteryHours:4,...mix},gridCharging:false,arbitrage:false,flexShare:0,carbonShadow:100,
 conn:{mw:75,steps:[[18,25],[24,50],[30,75]],firstMonth:18,fullMonth:30,stressFrac:0.6},market:{powerEsc:0.05,gasEsc:0.03,co2Esc:-0.03},
 lead:{solar:24,wind:12,battery:14,turbine:18,engine:16,fuelcell:14,nuclear:60},
 calib:{ppa:{solar:40,wind:35,nuclear:95},rte:0.85,reloc:12/1.05,relocUsd:70*1.05+50,thermal:{turbine:PACKET.turbine,engine:PACKET.engine,fuelcell:PACKET.fuelcell}},region:{price:1,co2:1,solar:1,wind:1}};}
function calibCost(sim){const s=sim.spec,mix=s.mix,H=sim.monthReq.length;let fixed=0;
 for(const k of ['turbine','engine','fuelcell','battery']){const mw=mix[k]||0;if(!mw)continue;const P=PACKET[k],start=Math.max(s.openMonth,sim.avail[k]),hours=Math.max(0,H-start)*730;fixed+=mw*1000*(P.capex*crf(0.08,P.life)+P.fom)/8760*hours;}
 const T=k=>sim.years.reduce((t,A)=>t+A[k],0),req=T('req');
 const total=fixed+T('contract')+T('merchant')+T('fuel')+T('vom')+T('unserved')*1000;return {usd:total/req,kg:1000*T('co2')/req,req};}
const api={setRegions,regionalBase,CATALOG,calibSpec,calibCost,SOURCES,defaults,regionFromSite,simulate,finance,evaluate,optimize,merge};
if(typeof module!=='undefined')module.exports=api;root.PowerEngine=api;
})(typeof globalThis!=='undefined'?globalThis:this);
