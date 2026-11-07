const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const F=require('./finance.js'),profiles=JSON.parse(fs.readFileSync(path.join(__dirname,'profiles.json')));let n=0;
function test(name,fn){fn();console.log('PASS',name);n++;}
for(const p of profiles){
 test(p.name+' cash and NPV reconcile',()=>{const r=F.evaluate(p);assert(Math.abs(r.rows.reduce((s,v)=>s+v.cf,0)-r.cash)<.01);assert(Math.abs(r.rows.reduce((s,v)=>s+v.npv,0)-r.npv)<.01);const recovery=p.monthly.recovery.reduce((s,v)=>s+v,0);const energy=p.monthly.variable.reduce((s,v)=>s+v,0)+p.monthly.fixed.reduce((s,v)=>s+v,0)+p.monthly.relocation.reduce((s,v)=>s+v,0)+p.monthly.consequence.reduce((s,v)=>s+v,0);assert(Math.abs(energy+recovery-p.benchmark_cost)<1);});
 test(p.name+' capital is charged once',()=>{const r=F.evaluate(p);assert(Math.abs(r.capex-(450e6+p.monthly.capex.reduce((s,v)=>s+v,0)))<.01);});
 test(p.name+' financial direction and break-even',()=>{const base=F.evaluate(p);assert(F.evaluate(p,{rent:220}).npv>base.npv);assert(F.evaluate(p,{energyShock:25}).npv<base.npv);assert(F.evaluate(p,{occupancy:75}).npv<base.npv);assert(F.evaluate(p,{overrun:15}).npv<base.npv);assert(Math.abs(F.evaluate(p,{rent:base.breakRent}).npv)<.1);assert(Number.isFinite(F.evaluate(p,{rent:0}).breakRent));assert(F.evaluate(p,{occupancy:0}).breakRent===null);assert(F.evaluate(p,{discount:0}).npv===F.evaluate(p,{discount:0}).cash);});
 test(p.name+' delay shifts operations but not campus spend',()=>{const b=F.evaluate(p),r=F.evaluate(p,{delay:6});assert.equal(r.opening,p.open+6);assert.equal(r.rows[p.open].revenue,0);assert.equal(r.rows[0].capex,b.rows[0].capex);assert(r.revenue<b.revenue);assert.equal(r.rows.length,120);});
}
test('reject invalid financial assumptions',()=>{for(const a of [{pue:0},{occupancy:101},{delay:1.5},{energyShock:-101},{discount:NaN},{dcCapex:-1}])assert.throws(()=>F.evaluate(profiles[0],a));});
console.log(n+' financial checks passed.');
