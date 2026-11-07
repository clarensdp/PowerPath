const { chromium } = require('playwright'); const fs=require('fs'); const path=require('path');
const B='http://127.0.0.1:8768', O=path.join(__dirname,'v2'); fs.mkdirSync(O,{recursive:true});
const L=(...a)=>console.log(...a);
(async()=>{const b=await chromium.launch();const c=await b.newContext({viewport:{width:1440,height:900},acceptDownloads:true});const p=await c.newPage();
const errs=[];p.on('pageerror',e=>errs.push(e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text().slice(0,160))});
const t0=Date.now();
await p.goto(B+'/',{waitUntil:'networkidle'});
L('nav:',(await p.locator('.nav button').allInnerTexts()).map(x=>x.replace(/\n/g,' ')).join(' | '));
await p.click('#new-project');await p.waitForSelector('dialog[open]');
await p.fill('dialog[open] [name=name]','Flow Test Campus');await p.fill('dialog[open] [name=target_mw]','200');await p.fill('dialog[open] [name=location]','Loudoun County, VA');
L('starter checked by default:',await p.isChecked('dialog[open] [name=starter]'));
await p.screenshot({path:O+'/01_new_project.png'});
await p.click('dialog[open] button[type=submit]');await p.waitForTimeout(1500);
// brief -> explore
await p.click('#brief-form button.primary');await p.waitForTimeout(1500);
await p.locator('[data-parcel]').first().click();await p.waitForTimeout(1000);await p.click('#save-parcel');await p.waitForTimeout(1000);
// power paths
await p.click('.nav [data-step="2"]');await p.waitForTimeout(800);
for(const [n,st,mw,pm,dly,cap,en] of [['Grid utility service','grid','200','36','6','0','0'],['Onsite bridge + grid','hybrid','200','18','2','15','8']]){
 await p.click('#new-path');await p.waitForSelector('dialog[open]');await p.fill('dialog[open] [name=name]',n);await p.selectOption('dialog[open] [name=strategy]',st);await p.fill('dialog[open] [name=capacity_mw]',mw);await p.fill('dialog[open] [name=power_month]',pm);await p.fill('dialog[open] [name=delay_months]',dly);await p.fill('dialog[open] [name=capex_uplift_pct]',cap);await p.fill('dialog[open] [name=energy_uplift_pct]',en);await p.fill('dialog[open] [name=source_note]','Analyst hypothesis for flow test only.');await p.click('dialog[open] button[type=submit]');await p.waitForTimeout(1000);}
await p.screenshot({path:O+'/02_power_paths.png',fullPage:true});
await p.click('text=Continue to economics →');await p.waitForSelector('table.econ',{timeout:20000});await p.waitForTimeout(500);
L('economics rows:\n  '+(await p.locator('table.econ tbody tr').allInnerTexts()).map(x=>x.replace(/\s+/g,' ')).join('\n  '));
L('bar widths:',await p.$$eval('.npvbar i',els=>els.map(e=>e.style.width).join(', ')));
L('mismatch notice shown:',await p.locator('#econ .notice', {hasText:'models'}).count());
L('time from landing to economics (s):',((Date.now()-t0)/1000).toFixed(1));
await p.screenshot({path:O+'/03_economics.png',fullPage:true});
await p.click('text=Continue to diligence →');await p.waitForTimeout(1200);
L('diligence has Assess evidence:',await p.locator('button',{hasText:'Assess evidence'}).count());
await p.screenshot({path:O+'/04_diligence.png',fullPage:true});
await p.click('.nav [data-step="5"]');await p.waitForTimeout(1000);
L('memo economics:',(await p.locator('.report').innerText()).split('Modelled economics')[1]?.slice(0,260).replace(/\s+/g,' '));
await p.screenshot({path:O+'/05_memo.png',fullPage:true});
const [dl]=await Promise.all([p.waitForEvent('download'),p.click('#export-json')]);const j=JSON.parse(fs.readFileSync(await dl.path(),'utf8'));
L('export has economics:',!!j.modelled_economics,'pathways:',j.modelled_economics?.pathways?.length,'release:',j.release);
// mobile economics
const m=await b.newContext({viewport:{width:390,height:844}});const mp=await m.newPage();await mp.goto(B+'/',{waitUntil:'networkidle'});
await mp.selectOption('#project-select',{label:'Flow Test Campus'});await mp.waitForTimeout(800);await mp.click('.nav [data-step="3"]');await mp.waitForSelector('table.econ',{timeout:20000});
L('mobile hscroll:',await mp.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth));
await mp.screenshot({path:O+'/06_economics_mobile.png',fullPage:true});
// existing project with no scenario -> starter CTA
const pr=await (await p.request.post(B+'/api/projects',{headers:{Origin:B},data:{name:'Legacy No Scenario',target_mw:90}})).json();
await p.goto(B+'/',{waitUntil:'networkidle'});await p.selectOption('#project-select',pr.id);await p.waitForTimeout(600);await p.click('.nav [data-step="3"]');await p.waitForTimeout(1500);
L('no-scenario CTA:',await p.locator('#econ-starter').count());await p.click('#econ-starter');await p.waitForTimeout(2000);
L('after CTA:',(await p.locator('#econ').innerText()).slice(0,120).replace(/\s+/g,' '));
L('errors:',errs.join(' || ')||'none');await b.close()})();
