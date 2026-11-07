const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1440,height:900}});const errs=[];p.on('pageerror',e=>errs.push(e.message));await p.goto('file://'+process.argv[2]);await p.waitForTimeout(1200);
// mount the panel directly into a test node with a synthetic project, exactly as project21.js does
const out=await p.evaluate(()=>{const d=document.createElement('div');document.body.appendChild(d);window.PowerPathUnderwrite25.render(d,{id:'smoke'});
 const sels=d.querySelectorAll('[data-v25s]').length,nums=['leaseTailBufferMonths','renewalProbabilityPct','vacantValuePct'].map(k=>d.querySelector(`[data-v25="${k}"]`)?.value);
 const before=d.querySelector('#v251Output').textContent.match(/Levered NPV\$?(-?[\d.]+)/);
 d.querySelector('[data-v25s="leaseExpiryPolicy"]').value='renew';d.querySelector('[data-v25s="exitValuePolicy"]').value='contracted';d.querySelector('[data-v25s="refinanceTenorPolicy"]').value='leaseTail';d.querySelector('#v251Run').click();
 const after=d.querySelector('#v251Output').textContent.match(/Levered NPV\$?(-?[\d.]+)/);
 return {sels,nums,before:before&&before[1],after:after&&after[1],err:d.querySelector('#v251Output').textContent.startsWith('Cannot')}});
console.log(JSON.stringify(out),'errors',errs);await b.close()})();
