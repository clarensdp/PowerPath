/* Verified wholesale historical price activation; opt-in, project-scoped, reversible. */
(function(root){'use strict';
const KEY='powerpath-v20-2-price-activation';
function get(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch{return {}}}
function set(projectId,cfg){const x=get();x[projectId]=cfg;localStorage.setItem(KEY,JSON.stringify(x));return cfg;}
function normalize(o){
 if(!o||o.source!=='pjm_lmp'||!Array.isArray(o.records))throw Error('PJM hourly price snapshot required');
 const data=o.records.map(r=>({t:r.time_utc||r.period_reported,v:Number(r.value),node:String(r.node||o.parameters?.node||'')}));
 if(data.length!==8760)throw Error('Need exactly 8,760 consecutive non-leap UTC hours; received '+data.length);
 const first=Date.parse(data[0].t);if(!Number.isFinite(first)||!data[0].t.endsWith('Z'))throw Error('UTC ISO timestamps with Z required');
 if(new Date(first).getUTCFullYear()!==new Date(first+8759*3600000).getUTCFullYear())throw Error('Use one calendar year');
 if(new Date(first).getUTCMonth()!==0||new Date(first).getUTCDate()!==1||new Date(first).getUTCHours()!==0)throw Error('History must start Jan 1 00:00 UTC');
 if(!data[0].node||!/^[0-9]+$/.test(data[0].node))throw Error('Explicit numeric PJM node required');
 for(let i=0;i<data.length;i++){
  if(!data[i].t.endsWith('Z')||Date.parse(data[i].t)!==first+i*3600000)throw Error('Hourly gap / duplication at index '+i);
  if(!Number.isFinite(data[i].v)||Math.abs(data[i].v)>100000)throw Error('Invalid LMP at index '+i);
  if(data[i].node!==data[0].node)throw Error('Mixed nodes');
 }
 if(o.quality?.status==='synthetic')throw Error('Synthetic dataset cannot activate');
 return {whole:data.map(x=>x.v),node:data[0].node,year:new Date(first).getUTCFullYear(),avg:data.reduce((s,x)=>s+x.v,0)/8760};
}
function select(projectId,region,base,connector){
 const cfg=get()[projectId];if(!cfg?.enabled)return {base,active:false,reason:'Price activation disabled'};
 if(region?.ba!=='PJM')return {base,active:false,reason:'Only PJM-mapped projects supported'};
 const snap=connector?.get()?.pjm_lmp;if(!snap)return {base,active:false,reason:'No PJM snapshot'};
 try{const p=normalize(snap);if(p.node!==String(cfg.node))throw Error('Node mismatch');return {base:{...base,whole:p.whole,adder:Number(cfg.basis)||0},active:true,node:p.node,year:p.year,average:p.avg,basis:Number(cfg.basis)||0,source:snap.source_url,retrieved_at:snap.retrieved_at};}catch(e){return {base,active:false,reason:e.message};}
}
root.PowerMarketData={normalize,get,set,select};
})(typeof globalThis!=='undefined'?globalThis:this);
