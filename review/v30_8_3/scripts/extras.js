// Back button in detailed workspace + agent in-page dialog + synthetic parcel label + deliverability relabel
const { chromium } = require('playwright');const B='http://127.0.0.1:8768';
(async()=>{const b=await chromium.launch();const c=await b.newContext({viewport:{width:1440,height:900}});const p=await c.newPage();const errs=[];p.on('pageerror',e=>errs.push(e.message));let native=0;p.on('dialog',d=>{native++;d.dismiss()});
await p.goto(B+'/advanced',{waitUntil:'networkidle'});await p.waitForTimeout(600);
for(const n of ['Decision Center','Finance & economics','Evidence library']){await p.locator('aside').getByText(n,{exact:true}).first().click();await p.waitForTimeout(500)}
const h=async()=>await p.locator('main h1, h1').first().innerText();
console.log('at:',await h());await p.goBack();await p.waitForTimeout(700);console.log('back ->',await h(),p.url().split('?')[1]);await p.goBack();await p.waitForTimeout(700);console.log('back ->',await h());await p.goForward();await p.waitForTimeout(700);console.log('forward ->',await h());
await p.goto(B+'/agent-operations',{waitUntil:'networkidle'});await p.selectOption('#mode','live');await p.check('#enabled');await p.click('#save');await p.waitForTimeout(500);
console.log('in-page dialog open:',await p.locator('dialog#ask[open]').count(),'| title:',await p.locator('dialog#ask h2').innerText(),'| native dialogs:',native);
await p.screenshot({path:__dirname+'/v2/07_agent_dialog.png'});await p.click('dialog#ask [data-cancel]');await p.waitForTimeout(400);console.log('dialog closed:',await p.locator('dialog#ask[open]').count()===0);
await p.goto(B+'/',{waitUntil:'networkidle'});await p.waitForTimeout(1200);console.log('first parcels shown:',(await p.locator('#results strong').allInnerTexts()).slice(0,3).join(' / '));
await p.locator('[data-parcel]').first().click();await p.waitForTimeout(900);console.log('inspector source:',(await p.locator('.inspector .muted').nth(1).innerText()));
console.log('errors:',errs.join('|')||'none');await b.close()})();
