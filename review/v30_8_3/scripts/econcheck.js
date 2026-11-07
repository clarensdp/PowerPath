const { chromium } = require('playwright');const B='http://127.0.0.1:8768';
(async()=>{const b=await chromium.launch();const p=await (await b.newContext({viewport:{width:1440,height:900}})).newPage();const errs=[];p.on('pageerror',e=>errs.push(e.message));
await p.goto(B+'/',{waitUntil:'networkidle'});await p.selectOption('#project-select',{label:'Flow Test Campus'});await p.waitForTimeout(700);await p.click('.nav [data-step="3"]');await p.waitForSelector('table.econ');await p.waitForTimeout(400);
console.log((await p.locator('table.econ small.warn').allInnerTexts()).join(' | '));console.log('timing note:',await p.locator('.warnbox').count());
await p.screenshot({path:__dirname+'/v2/03_economics.png',fullPage:true});console.log('errors:',errs.join('|')||'none');await b.close()})();
