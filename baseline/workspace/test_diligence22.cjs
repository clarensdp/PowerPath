const fs=require('fs'),vm=require('vm'),assert=require('assert');const ctx={globalThis:{},window:undefined,console};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/diligence22.js','utf8'),ctx);const d=ctx.globalThis.PowerPathDiligence;let tests=0;function ok(desc,fn){fn();tests++;console.log('PASS',desc)}
ok('zero coordinate distance',()=>assert.equal(d.distance(40,-73,40,-73),0));
ok('reasonable distance 1 degree latitude',()=>assert(Math.abs(d.distance(40,-73,41,-73)-111.2)<1));
ok('coordinates valid',()=>assert(d.validCoords(40,-73)));
ok('invalid lat rejected',()=>assert(!d.validCoords(91,2)));
ok('tariff volume',()=>assert.equal(d.tariff({peakMW:100,hours:730,utilization:.8,energy:65,demand:12,fixed:25000,lossPct:2,other:5}).consumedMWh,58400));
ok('tariff demand',()=>assert.equal(d.tariff({peakMW:100,hours:730,utilization:.8,energy:65,demand:12,fixed:25000,lossPct:2,other:5}).monthlyDemand,1200000));
ok('tariff positive',()=>assert(d.tariff({peakMW:100,hours:730,utilization:.8,energy:65,demand:12,fixed:25000,lossPct:2,other:5}).allIn>80));
ok('invalid utilization rejected',()=>assert.throws(()=>d.tariff({peakMW:100,hours:730,utilization:1.2,energy:65,demand:12,fixed:25000,lossPct:2,other:5})));
ok('invalid losses rejected',()=>assert.throws(()=>d.tariff({peakMW:100,hours:730,utilization:.8,energy:65,demand:12,fixed:25000,lossPct:100,other:5})));
console.log(tests+' diligence checks passed');
