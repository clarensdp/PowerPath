const U=require(process.argv[2]);const cases=require(process.argv[3]);const out={};
for(const [k,v] of Object.entries(cases)){try{const z=U.evaluate(JSON.parse(JSON.stringify(v)));out[k]={rows:z.rows,npvM:z.summary.npvM,defaulted:z.summary.defaulted,summary:z.summary}}catch(e){out[k]={error:e.message}}}
require('fs').writeFileSync(process.argv[4],JSON.stringify(out));
