const fs=require('fs'),vm=require('vm'),assert=require('assert');const context={globalThis:{},console};vm.createContext(context);vm.runInContext(fs.readFileSync(__dirname+'/diligence22.js','utf8'),context);const d=context.globalThis.PowerPathDiligence;let n=0;function test(name,f){f();n++;console.log('PASS '+name)}
test('valid geodata point import',()=>{const a=d.mapFeatures({type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:[-77,38]},properties:{name:'Station A',mw:150}}]});assert.equal(a.length,1);assert.equal(a[0].lat,38)});
test('exclude invalid geodata points',()=>assert.equal(d.mapFeatures({type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:[-200,40]}}]}).length,0));
test('limit GeoJSON size',()=>assert.throws(()=>d.mapFeatures({type:'FeatureCollection',features:Array(5001).fill({})})));
test('nearest plant sorting',()=>{let r=d.nearbyPlants(40,-75,[{lat:42,lon:-75},{lat:40.1,lon:-75}],1);assert.equal(r.length,1);assert.equal(r[0].lat,40.1)});
console.log(`${n} v23 GIS tests passed`)
