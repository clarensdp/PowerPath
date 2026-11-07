const fs=require('fs');
const A=require('/home/claude/pkg/PowerPath_v25_8/workspace/underwrite25.js');
const B=require('/home/claude/pkg/PowerPath_v25_8_claude/workspace/underwrite25.js');
const specs=require('/home/claude/pkg/PowerPath_v25_8/benchmarks/v258_results/frozen_inputs_16.json');
const rows=[],cases=[];
for(const s of specs){
 const base=s.assumptions;
 for(const delay of [0,3,6,12,18])for(const overrun of [0,10,20])for(const shock of [0,200,400]){
  const sc={...base,delayMonths:delay,overrunPct:overrun,rateShockPct:shock/100};
  const a=A.evaluate(JSON.parse(JSON.stringify(sc))).summary,b=B.evaluate(JSON.parse(JSON.stringify(sc))).summary,c=B.evaluate({...JSON.parse(JSON.stringify(sc)),calendarStartYear:2025}).summary;
  const res=x=>Math.max(x.sourcesUsesMaxResidual,x.debtMaxResidual,x.reserveMaxResidual);
  rows.push({project:s.name,tier:s.evidenceTier,delay,overrun,shockBps:shock,npv_v258:a.npvM,npv_patched_sameCalendar:b.npvM,npv_patched_alignedCalendar:c.npvM,dEngine:b.npvM-a.npvM,dCalendar:c.npvM-b.npvM,minDSCR_v258:a.minDSCR,minDSCR_patched:b.minDSCR,breaches_v258:a.breachMonths.length,breaches_patched:b.breachMonths.length,default_v258:a.defaulted,default_patched:b.defaulted,maxResidual_patched:Math.max(res(b),res(c))});
  if(delay===0&&overrun===0&&shock===0)cases.push(rows.at(-1));
 }
}
const h=Object.keys(rows[0]);fs.writeFileSync('/home/claude/out/stress_720_before_after.csv',[h.join(','),...rows.map(r=>h.map(k=>typeof r[k]==='number'?+r[k].toFixed(6):JSON.stringify(r[k])).join(','))].join('\n'));
const mx=f=>rows.reduce((m,r)=>Math.abs(r[f])>Math.abs(m[f])?r:m);
const e=mx('dEngine'),k=mx('dCalendar');
console.log('scenarios',rows.length,'maxResidual',Math.max(...rows.map(r=>r.maxResidual_patched)));
console.log('max |engine delta|',e.dEngine.toFixed(2),e.project,e.delay,e.overrun,e.shockBps,'| max |calendar delta|',k.dCalendar.toFixed(2),k.project);
console.log('breach scenarios v258',rows.filter(r=>r.breaches_v258>0).length,'patched',rows.filter(r=>r.breaches_patched>0).length,'| defaults v258',rows.filter(r=>r.default_v258).length,'patched',rows.filter(r=>r.default_patched).length);
console.log('mean minDSCR v258',(rows.reduce((t,r)=>t+(r.minDSCR_v258||0),0)/720).toFixed(3),'patched',(rows.reduce((t,r)=>t+(r.minDSCR_patched||0),0)/720).toFixed(3));
for(const c of cases)console.log(c.project.padEnd(36),'NPV v258',c.npv_v258.toFixed(1).padStart(9),'patched',c.npv_patched_sameCalendar.toFixed(1).padStart(9),'d',c.dEngine.toFixed(2).padStart(7),'cal d',c.dCalendar.toFixed(2).padStart(6),'minDSCR',(c.minDSCR_v258??0).toFixed(2),'->',(c.minDSCR_patched??0).toFixed(2),'breach',c.breaches_v258,'->',c.breaches_patched);
fs.writeFileSync('/home/claude/out/case16_before_after.json',JSON.stringify(cases,null,1));
