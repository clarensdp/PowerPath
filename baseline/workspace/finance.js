/* Pure, auditable financial overlay. All dollars real 2023 USD. */
(function(root){
const defaults={rent:190,occupancy:90,pue:1.25,dcCapex:450,otherOpex:20,fixedOpex:0.25,discount:8,terminal:0,energyShock:0,delay:0,overrun:0};
function validate(a){for(const [k,v] of Object.entries(a))if(!Number.isFinite(v))throw Error(`Invalid ${k}`);if(a.pue<1||a.occupancy<0||a.occupancy>100||a.discount<0||a.discount>100||a.rent<0||a.dcCapex<0||a.otherOpex<0||a.otherOpex>=100||a.fixedOpex<0||a.terminal<0||a.energyShock< -100||a.delay<0||!Number.isInteger(a.delay)||a.overrun<0)throw Error('Assumptions outside supported range');}
function evaluate(p,input={}){
 const a={...defaults,...input};validate(a);const rows=[];let cash=0,npv=0,revenuePV=0,costPV=0,opProfit=0;
 const opening=p.open+a.delay,scale=a.occupancy/100,dc=a.dcCapex*1e6*(1+a.overrun/100);
 for(let m=0;m<120;m++){
  const j=m-a.delay,at=k=>j>=0&&j<120?p.monthly[k][j]:0;
  // Billable MWh includes relocated workload; interrupted work earns no revenue.
  const billable=at('billable')*scale,kwmonth=billable/730/a.pue*1000;
  const revenue=kwmonth*a.rent;
  // Utilization changes revenue only: contracted dispatch/cost remains reserved.
  const energy=at('variable')*(1+a.energyShock/100)+at('fixed')+at('relocation');
  const consequence=at('consequence');
  const overhead=revenue*a.otherOpex/100+(m>=opening?a.fixedOpex*1e6:0);
  const ebitda=revenue-energy-overhead-consequence;
  // DC construction spend stays on original schedule when opening is delayed.
  const capex=(m<p.open?dc/p.open:0)+at('capex')*(1+a.overrun/100);
  const terminal=m===119?Math.max(0,a.terminal*1e6):0;
  const cf=ebitda-capex+terminal,df=(1+a.discount/100)**((m+1)/12);
  cash+=cf;npv+=cf/df;revenuePV+=kwmonth*(1-a.otherOpex/100)/df;costPV+=(energy+overhead-revenue*a.otherOpex/100+consequence+capex-terminal)/df;opProfit+=ebitda;
  rows.push({month:m,revenue,energy,overhead,consequence,ebitda,capex,terminal,cf,cumulative:cash,npv:cf/df,billable});
 }
 const payback=rows.find((r,i)=>r.cumulative>=0&&rows.slice(i).every(x=>x.cumulative>=0))?.month;
 const total=k=>rows.reduce((s,r)=>s+r[k],0);
 const breakRent=revenuePV>0?costPV/revenuePV:null;
 return {profile:p,assumptions:a,rows,npv,cash,opProfit,payback:payback===undefined?null:payback+1,opening,revenue:total('revenue'),energy:total('energy'),capex:total('capex'),breakRent,annual:Array.from({length:10},(_,i)=>{const rr=rows.slice(i*12,(i+1)*12),sum=k=>rr.reduce((s,r)=>s+r[k],0);return {year:i+1,revenue:sum('revenue'),energy:sum('energy'),ebitda:sum('ebitda'),capex:sum('capex'),cash:sum('cf'),cumulative:rr[11].cumulative};})};
}
const api={defaults,evaluate,validate};if(typeof module!=='undefined')module.exports=api;root.PowerFinance=api;
})(typeof globalThis!=='undefined'?globalThis:this);
