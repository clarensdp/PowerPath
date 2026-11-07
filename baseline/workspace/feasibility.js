/* PowerPath v19 — evidence-gated feasibility and comparable power paths. Browser + Node. */
(function(root){
'use strict';
const choices=['Confirmed','Unverified','Denied'];
const basis={grid:'Unverified',air:'Unverified',gas:'Unverified',equipment:'Unverified',carbonCap:400,maxUnservedMWh:0,maxDelayMonths:36};
function classify({scenario,fin,sim,evidence={},limits={}}){
 const e={...basis,...evidence},l={...basis,...limits};const blocking=[],conditional=[];
 const needsGas=scenario==='onsite'||scenario==='hybrid',needsGrid=scenario==='grid'||scenario==='hybrid';
 const gate=(which,label)=>{if(e[which]==='Denied')blocking.push(label+' denied');else if(e[which]!=='Confirmed')conditional.push(label+' not confirmed');};
 if(needsGrid)gate('grid','Grid service / interconnection');
 if(needsGas){gate('air','Air permit');gate('gas','Firm gas supply');gate('equipment','Equipment delivery');}
 if(fin.kg!=null&&Number.isFinite(l.carbonCap)&&fin.kg>l.carbonCap)blocking.push('Carbon '+fin.kg.toFixed(0)+' kg/MWh exceeds '+l.carbonCap+' kg/MWh cap');
 if(fin.unserved>l.maxUnservedMWh+1e-6)blocking.push((fin.unserved/1000).toFixed(1)+' GWh unserved exceeds '+(l.maxUnservedMWh/1000).toFixed(1)+' GWh allowance');
 if(fin.powerOn==null||fin.powerOn>l.maxDelayMonths)blocking.push('Fully served power not reached within deadline M'+l.maxDelayMonths);
 const status=blocking.length?'Blocked':conditional.length?'Conditional':'Feasible';
 return {status,blocking,conditional,reason:[...blocking,...conditional],kg:fin.kg,unserved:fin.unserved,powerOn:fin.powerOn};
}
function createMix(spec,kind){const peak=spec.itMW*spec.pue;const zero={solar:0,wind:0,nuclear:0,battery:0,batteryHours:4,turbine:0,engine:0,fuelcell:0};
 if(kind==='grid')return {...spec,mix:zero,conn:{...spec.conn,mw:peak}};
 if(kind==='onsite')return {...spec,mix:{...zero,engine:Math.ceil(peak/5)*5},conn:{...spec.conn,mw:0,firstMonth:999,fullMonth:999}};
 return {...spec,mix:{...zero,engine:Math.ceil(peak*.6/5)*5,battery:Math.ceil(peak*.2/5)*5},conn:{...spec.conn,mw:peak}};
}
function compare(engine,base,spec,evidence,limits,opts={}){return ['grid','onsite','hybrid'].map(kind=>{
 const s=createMix(spec,kind),r=engine.evaluate(s,base,{stride:opts.stride||3}),f=r.fin,gate=classify({scenario:kind,fin:f,sim:r.sim,evidence,limits});
 return {kind,fin:f,gate,meta:{peak:r.sim.peak,years:s.horizonYears,sampling:opts.stride||3}};
 });}
function winners(results){const ok=results.filter(x=>x.gate.status==='Feasible');const min=(k)=>ok.length?ok.reduce((a,b)=>a.fin[k]<b.fin[k]?a:b).kind:null;
 return {cost:min('cost'),speed:min('powerOn'),carbon:min('kg'),npv:ok.length?ok.reduce((a,b)=>a.fin.npv>b.fin.npv?a:b).kind:null, eligible:ok.length};}
const api={basis,classify,createMix,compare,winners};if(typeof module!=='undefined')module.exports=api;root.PowerFeasibility=api;
})(typeof globalThis!=='undefined'?globalThis:this);
