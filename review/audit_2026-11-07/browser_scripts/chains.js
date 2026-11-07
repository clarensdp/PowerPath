const { chromium } = require('playwright'); const path=require('path');
const B='http://127.0.0.1:8768', O=path.join(__dirname,'flows_after');
(async()=>{const b=await chromium.launch();const c=await b.newContext({viewport:{width:1440,height:900}});const p=await c.newPage();
const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text().slice(0,140))});
const projects=await (await p.request.get(B+'/api/projects')).json();const audit=projects.find(x=>x.name==='Audit Test Campus');
// Chain 1: deliverability CTA -> new-scenario modal -> save -> compare
await p.goto(B+'/power-deliverability?project='+audit.id,{waitUntil:'networkidle'});await p.waitForTimeout(800);
console.log('CTA visible:',await p.locator('#scenario-help').isVisible(),'href:',await p.locator('#create-scenario').getAttribute('href'));
await p.screenshot({path:O+'/chain1_cta.png',fullPage:true});
await p.click('#create-scenario');await p.waitForLoadState('networkidle');await p.waitForTimeout(1000);
const modal=p.locator('.modal, [role=dialog], dialog[open]').first();console.log('modal open:',await modal.isVisible().catch(()=>false),'url:',p.url().replace(B,''));
await p.screenshot({path:O+'/chain1_modal.png'});
const nameInput=p.locator('.modal input[name=name], dialog input[name=name], [role=dialog] input[name=name]').first();
if(await nameInput.count()){await nameInput.fill('Working assumptions 200 MW');}
await p.locator('.modal button[type=submit], [role=dialog] button[type=submit]').first().click();await p.waitForTimeout(2000);
const sc=await (await p.request.get(B+`/api/projects/${audit.id}/scenarios`)).json();console.log('scenarios now:',sc.map(s=>s.name+'/'+s.mode).join(', '));
// run it
const run=p.locator('main button',{hasText:/run/i}).first();console.log('run button:',await run.count()?await run.innerText():'none');
if(await run.count()){await run.click();await p.waitForTimeout(4000);await p.screenshot({path:O+'/chain1_run.png',fullPage:true});}
await p.goto(B+'/power-deliverability?project='+audit.id,{waitUntil:'networkidle'});await p.waitForTimeout(1000);
console.log('CTA visible after:',await p.locator('#scenario-help').isVisible(),'| overview has run:',(await p.locator('#overview').innerText()).slice(0,40));
await p.check('#ack');await p.click('#compare');await p.waitForTimeout(6000);
console.log('compare result:',(await p.locator('#results').innerText()).slice(0,300).replace(/\n/g,' | '));
await p.screenshot({path:O+'/chain1_compare.png',fullPage:true});
// Decision center: sensitivity form + pins
await p.goto(B+`/advanced?project=${audit.id}&view=decision`,{waitUntil:'networkidle'});await p.waitForTimeout(1200);
const pin=await p.locator('.spatial-pin').first().evaluate(e=>({l:e.style.left,t:e.style.top})).catch(()=>null);console.log('pin geometry:',JSON.stringify(pin));
await p.screenshot({path:O+'/chain_decision.png',fullPage:true});
// Chain 2: transaction register -> review -> schedule
await p.goto(B+'/transaction-workspace',{waitUntil:'networkidle'});await p.waitForTimeout(600);
console.log('signout visible (local):',await p.locator('#logout').isVisible());
await p.selectOption('#projectSelect',audit.id);await p.click('#load');await p.waitForTimeout(1500);
console.log('register box:',await p.locator('#registerBox').isVisible());await p.screenshot({path:O+'/chain2_register.png',fullPage:true});
await p.click('#register');await p.waitForTimeout(3000);console.log('message:',await p.locator('#message').innerText(),'| review visible:',await p.locator('#review').isVisible());
await p.click('#loadSchedule');await p.waitForTimeout(2000);console.log('schedule:',(await p.locator('#schedule').innerText()).slice(0,120).replace(/\n/g,' '));
await p.screenshot({path:O+'/chain2_review.png',fullPage:true});
console.log('errors:',errs.join(' || ')||'none');await b.close()})();
