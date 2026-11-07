/* Valuation layer on top of the unchanged PowerFinance engine (finance.js and its tests are untouched).
   Adds: campus size and phasing, rent convention (power included vs passed through), exit value,
   income tax with straight-line depreciation and loss carry-forward, equipment sales-tax exemption,
   and an energy investment tax credit on eligible onsite storage and fuel cells.
   All figures stay real 2023 USD, monthly, over the same 120-month horizon. Screening, not tax advice. */
(function(){
 const F=PowerFinance,orig=F.evaluate.bind(F);
 const VX_DEFAULTS={size:75,phase2Share:0,phase2Lag:12,rentBasis:'incl',exitMult:12,taxRate:25,depLife:15,salesTaxExempt:0,itc:0};
 let vx={...VX_DEFAULTS};try{const s=JSON.parse(localStorage.getItem('pp_vx')||'null');if(s)vx={...vx,...s};}catch{}
 const ECACHE=new Map();
 const ROWK=['revenue','energy','overhead','consequence','ebitda','capex','terminal','cf'];
 function clean(input){const o={...input};for(const k of Object.keys(VX_DEFAULTS))delete o[k];return o;}
 function phaseRows(p,inp,dcCapex,scale){
  const r=orig(p,{...inp,dcCapex,terminal:0});
  const ek=p.id+'|'+inp.delay+'|'+inp.overrun;let e=ECACHE.get(ek);if(!e){e=orig(p,{...inp,dcCapex:0,terminal:0});ECACHE.set(ek,e);if(ECACHE.size>400)ECACHE.clear();}
  return r.rows.map((row,m)=>{const pass=vx.rentBasis==='pass'?row.energy:0;
   return {month:m,revenue:(row.revenue+pass)*scale,energy:row.energy*scale,overhead:row.overhead*scale,consequence:row.consequence*scale,
    ebitda:(row.ebitda+pass)*scale,capex:row.capex*scale,energyCapex:e.rows[m].capex*scale,terminal:0,cf:(row.cf+pass)*scale,billable:row.billable*scale};});
 }
 function combined(p,input){
  const a={...F.defaults,...clean(input)};F.validate(a);
  const k=Math.max(0.01,vx.size/75),f2=Math.min(1,Math.max(0,vx.phase2Share/100)),f1=1-f2;
  const dc=a.dcCapex*(1-Math.min(100,Math.max(0,vx.salesTaxExempt))/100);
  let rows=phaseRows(p,a,dc,k*f1);
  if(f2>0){const r2=phaseRows(p,{...a,delay:a.delay+Math.round(vx.phase2Lag)},dc,k*f2);rows=rows.map((x,m)=>{const y=r2[m],o={month:m};for(const key of [...ROWK,'energyCapex','billable'])o[key]=x[key]+y[key];return o;});}
  return {a,rows};
 }
 function finish(p,a,rows,withExit=true){
  const last=rows.slice(108).reduce((s,r)=>s+r.ebitda,0),exit=withExit?Math.max(0,last*vx.exitMult):0,userTerm=Math.max(0,a.terminal)*1e6;
  const caps=p.caps||{},onsite=['battery_4h','fuel_cell','gas_turbine','gas_engine'].reduce((s,x)=>s+(caps[x]||0),0),elig=onsite?((caps.battery_4h||0)+(caps.fuel_cell||0))/onsite:0;
  const life=Math.max(1,vx.depLife)*12,rate=Math.max(0,Math.min(60,vx.taxRate))/100,itcPct=Math.max(0,Math.min(50,vx.itc))/100;
  const dep=new Array(120).fill(0);rows.forEach((r,m)=>{if(r.capex>0)for(let j=m;j<Math.min(120,m+life);j++)dep[j]+=r.capex/life;});
  let nol=0,cash=0,npv=0,taxes=0,credits=0;const out=[];
  rows.forEach((r,m)=>{let taxable=r.ebitda-dep[m]+(m===119?exit+userTerm:0);
   if(taxable<0){nol+=-taxable;taxable=0;}else{const use=Math.min(nol,taxable);nol-=use;taxable-=use;}
   const tax=taxable*rate,credit=r.energyCapex*elig*itcPct,terminal=m===119?exit+userTerm:0;
   const cf=r.cf+terminal-tax+credit,df=(1+a.discount/100)**((m+1)/12);taxes+=tax;credits+=credit;cash+=cf;npv+=cf/df;
   out.push({...r,terminal,tax,credit,cf,cumulative:cash,npv:cf/df});});
  return {rows:out,npv,cash,exit,taxes,credits};
 }
 function core(p,input){const {a,rows}=combined(p,input);return finish(p,a,rows).npv;}
 F.evaluate=function(p,input={}){
  const {a,rows}=combined(p,input),res=finish(p,a,rows),noExit=finish(p,a,rows,false);
  const payIdx=res.rows.findIndex((r,i)=>r.cumulative>=0&&res.rows.slice(i).every(x=>x.cumulative>=0));
  const at=r=>core(p,{...input,rent:r});let r0=a.rent,n0=res.npv,r1=a.rent+60,n1=at(r1),breakRent=null;
  for(let i=0;i<8&&Math.abs(n1-n0)>1;i++){const r2=Math.max(0,r1-n1*(r1-r0)/(n1-n0));r0=r1;n0=n1;r1=r2;n1=at(r1);if(Math.abs(n1)<5e4)break;}
  if(Number.isFinite(r1)&&Math.abs(n1)<5e5)breakRent=r1;
  const total=k=>res.rows.reduce((s,r)=>s+r[k],0);
  return {profile:p,assumptions:a,rows:res.rows,npv:res.npv,npvNoExit:noExit.npv,exitValue:res.exit,taxes:res.taxes,credits:res.credits,cash:res.cash,
   opProfit:total('ebitda'),payback:payIdx<0?null:payIdx+1,opening:p.open+a.delay,revenue:total('revenue'),energy:total('energy'),capex:total('capex'),breakRent,
   annual:Array.from({length:10},(_,i)=>{const rr=res.rows.slice(i*12,(i+1)*12),sum=k=>rr.reduce((s,r)=>s+r[k],0);return {year:i+1,revenue:sum('revenue'),energy:sum('energy'),ebitda:sum('ebitda'),capex:sum('capex'),cash:sum('cf'),cumulative:rr[11].cumulative};})};
 };
 F.vx=()=>({...vx});F.setVx=o=>{vx={...vx,...o};try{localStorage.setItem('pp_vx',JSON.stringify(vx));}catch{}};F.vxDefaults=VX_DEFAULTS;F.evaluateEngine=orig;
})();
