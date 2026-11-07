// Pass 2: drive each real workflow end to end, logging what a user would experience.
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
const BASE = process.env.BASE || 'http://127.0.0.1:8768';
const OUT = path.join(__dirname, process.env.SHOTDIR || 'flows');
fs.mkdirSync(OUT, { recursive: true });
const log = [];
const L = (...a) => { const s = a.join(' '); log.push(s); console.log(s); };

async function newPage(browser, vp = { width: 1440, height: 900 }) {
  const ctx = await browser.newContext({ viewport: vp, acceptDownloads: true });
  const page = await ctx.newPage();
  page.on('pageerror', e => L('  !! pageerror', e.message));
  page.on('console', m => { if (m.type() === 'error') L('  !! console', m.text().slice(0, 200)); });
  page.on('response', r => { if (r.status() >= 400 && r.url().includes('/api/')) L('  !! http', r.status(), r.request().method(), r.url().replace(BASE, '')); });
  page.on('dialog', d => { L('  !! native dialog', d.type(), d.message().slice(0, 100)); d.dismiss(); });
  return { ctx, page };
}
const shot = (page, n) => page.screenshot({ path: path.join(OUT, n + '.png'), fullPage: true });
const toast = async page => (await page.locator('#toast').textContent().catch(() => '')) || '';
async function step(name, fn) { try { await fn(); L('OK  ', name); } catch (e) { L('FAIL', name, '→', e.message.split('\n')[0].slice(0, 200)); } }

(async () => {
  const browser = await chromium.launch();
  // ---------- Streamlined workspace: 5-step flow ----------
  { const { ctx, page } = await newPage(browser);
    L('\n# Streamlined workspace');
    await page.goto(BASE + '/', { waitUntil: 'networkidle' });
    L('  landing step:', await page.locator('.nav button.active').innerText().catch(() => '?'));
    await step('create project via modal', async () => {
      await page.click('#new-project');
      await page.waitForSelector('dialog[open]');
      await shot(page, 'ws_00_newproject_modal');
      const fields = await page.$$eval('dialog[open] input, dialog[open] select, dialog[open] textarea', els => els.map(e => e.name + (e.required ? '*' : '')));
      L('  modal fields:', fields.join(', '));
      await page.fill('dialog[open] [name=name]', 'Audit Test Campus');
      if (await page.$('dialog[open] [name=target_mw]')) await page.fill('dialog[open] [name=target_mw]', '200');
      if (await page.$('dialog[open] [name=location]')) await page.fill('dialog[open] [name=location]', 'Loudoun County, VA');
      await page.click('dialog[open] button[type=submit], dialog[open] .primary');
      await page.waitForTimeout(1200);
      L('  toast:', await toast(page), '| step now:', await page.locator('.nav button.active').innerText().catch(() => '?'));
      await shot(page, 'ws_01_after_create');
    });
    await step('save brief', async () => {
      await page.click('[data-step="0"]');
      await page.fill('#brief-form [name=description]', 'Phase 1 100 MW in 2028, full 200 MW by 2030.');
      await page.click('#brief-form button.primary');
      await page.waitForTimeout(1500);
      L('  toast:', await toast(page));
      await shot(page, 'ws_02_explore');
    });
    await step('search PIN with no match', async () => {
      await page.fill('#parcel-search', 'zzzz');
      await page.waitForTimeout(300);
      L('  results text:', (await page.locator('#results').innerText()).slice(0, 140).replace(/\n/g, ' | '));
      await page.click('#reset-filters'); await page.waitForTimeout(800);
    });
    await step('select a parcel from list', async () => {
      await page.locator('[data-parcel]').first().click();
      await page.waitForTimeout(1200);
      L('  inspector:', (await page.locator('#inspector').innerText()).slice(0, 300).replace(/\n/g, ' | '));
      await shot(page, 'ws_03_inspector');
    });
    await step('save parcel to shortlist', async () => {
      await page.click('#save-parcel'); await page.waitForTimeout(1200);
      L('  toast:', await toast(page));
    });
    await step('location search "Loudoun"', async () => {
      await page.fill('#location-query', 'Loudoun'); await page.click('#location-search'); await page.waitForTimeout(1500);
      L('  location results:', (await page.locator('#location-results').innerText().catch(() => 'n/a')).slice(0, 200).replace(/\n/g, ' | '));
    });
    await step('compare step', async () => {
      await page.click('[data-step="2"]'); await page.waitForTimeout(1000);
      L('  compare:', (await page.locator('#main').innerText()).slice(0, 500).replace(/\n/g, ' | '));
      await shot(page, 'ws_04_compare');
    });
    await step('add power pathway', async () => {
      await page.click('#new-path'); await page.waitForSelector('dialog[open]');
      await page.fill('dialog[open] [name=name]', 'Phased grid + bridge');
      await page.fill('dialog[open] [name=capacity_mw]', '200');
      await page.fill('dialog[open] [name=power_month]', '24');
      await page.fill('dialog[open] [name=source_note]', 'Analyst assumption pending utility study.');
      await page.click('dialog[open] button[type=submit], dialog[open] .primary'); await page.waitForTimeout(1200);
      L('  toast:', await toast(page));
      await shot(page, 'ws_05_compare_with_path');
    });
    await step('diligence step', async () => {
      await page.click('[data-step="3"]'); await page.waitForTimeout(1200);
      L('  diligence:', (await page.locator('#main').innerText()).slice(0, 500).replace(/\n/g, ' | '));
      await shot(page, 'ws_06_diligence');
    });
    await step('assess a factor', async () => {
      const f = page.locator('[data-factor]').first();
      if (!(await f.count())) throw Error('no [data-factor] control on diligence');
      const tag = await f.evaluate(e => e.tagName);
      L('  factor control tag:', tag);
      if (tag === 'SELECT') { const opts = await f.locator('option').allTextContents(); L('  options:', opts.join('/')); await f.selectOption({ index: 1 }); }
      else await f.click();
      await page.waitForTimeout(1200); L('  toast:', await toast(page));
      await shot(page, 'ws_07_factor');
    });
    await step('add diligence task', async () => {
      const b = page.locator('[data-add-task]').first(); if (!(await b.count())) throw Error('no add-task button');
      await b.click(); await page.waitForTimeout(600);
      if (await page.$('dialog[open]')) { const inp = page.locator('dialog[open] input, dialog[open] textarea').first(); await inp.fill('Request utility load letter'); await page.click('dialog[open] button[type=submit], dialog[open] .primary'); }
      await page.waitForTimeout(1200); L('  toast:', await toast(page));
    });
    await step('decision memo', async () => {
      await page.click('[data-step="4"]'); await page.waitForTimeout(1200);
      L('  memo:', (await page.locator('#main').innerText()).slice(0, 600).replace(/\n/g, ' | '));
      await shot(page, 'ws_08_memo');
    });
    await step('export JSON', async () => {
      const [dl] = await Promise.all([page.waitForEvent('download', { timeout: 5000 }), page.click('#export-json')]);
      L('  download:', dl.suggestedFilename());
    });
    await step('reload preserves context', async () => {
      await page.reload({ waitUntil: 'networkidle' }); await page.waitForTimeout(800);
      L('  after reload project:', await page.locator('#project-select option:checked').innerText(), '| step:', await page.locator('.nav button.active').innerText());
    });
    await step('keyboard: Esc closes modal & focus returns', async () => {
      await page.click('#new-project'); await page.waitForSelector('dialog[open]');
      await page.keyboard.press('Escape'); await page.waitForTimeout(300);
      L('  dialog open after Esc:', !!(await page.$('dialog[open]')), '| focused:', await page.evaluate(() => document.activeElement?.id || document.activeElement?.tagName));
    });
    await step('validation: create project empty name', async () => {
      await page.click('#new-project'); await page.waitForSelector('dialog[open]');
      await page.click('dialog[open] button[type=submit], dialog[open] .primary'); await page.waitForTimeout(400);
      L('  still open (native validation):', !!(await page.$('dialog[open]')));
      await page.keyboard.press('Escape');
    });
    await ctx.close(); }

  // ---------- Detailed workspace ----------
  { const { ctx, page } = await newPage(browser);
    L('\n# Detailed workspace (/advanced)');
    await page.goto(BASE + '/advanced', { waitUntil: 'networkidle' }); await page.waitForTimeout(800);
    const navs = await page.$$eval('nav button, nav a, aside button', els => els.map(e => e.innerText.trim()).filter(Boolean));
    L('  nav items:', navs.join(' · '));
    for (const n of navs) {
      await step('open view: ' + n, async () => {
        await page.locator('aside').getByText(n, { exact: true }).first().click();
        await page.waitForTimeout(1000);
        const h = await page.locator('main h1, h1').first().innerText().catch(() => '?');
        const url = page.url().replace(BASE, '');
        L('   h1=', JSON.stringify(h), 'url=', url);
        await shot(page, 'adv_' + n.replace(/\W+/g, '_').toLowerCase());
      });
    }
    await step('run a scenario (Finance & economics)', async () => {
      await page.locator('aside').getByText('Finance & economics', { exact: true }).first().click(); await page.waitForTimeout(1000);
      const btns = await page.$$eval('main button', els => els.map(e => e.innerText.trim()).filter(Boolean));
      L('   buttons:', btns.slice(0, 20).join(' / '));
      const run = page.locator('main button', { hasText: /run|calculate|underwrite/i }).first();
      if (await run.count()) { await run.click(); await page.waitForTimeout(3000); L('   after run:', (await page.locator('main').innerText()).slice(0, 400).replace(/\n/g, ' | ')); await shot(page, 'adv_finance_after_run'); }
      else throw Error('no run button found');
    });
    await step('direct deep link ?view=execution', async () => {
      await page.goto(BASE + '/advanced?view=execution', { waitUntil: 'networkidle' }); await page.waitForTimeout(800);
      L('   h1=', await page.locator('h1').first().innerText());
    });
    await ctx.close(); }

  // ---------- Power deliverability ----------
  { const { ctx, page } = await newPage(browser);
    L('\n# Power deliverability');
    await page.goto(BASE + '/power-deliverability', { waitUntil: 'networkidle' }); await page.waitForTimeout(800);
    L('  state:', await page.locator('#state-note').innerText());
    L('  sample buttons disabled:', await page.locator('#sample-g').isDisabled(), await page.locator('#sample-h').isDisabled());
    await step('compare without ack', async () => { await page.click('#compare'); await page.waitForTimeout(1500); L('   results:', (await page.locator('#results').innerText()).slice(0, 300).replace(/\n/g, ' | ')); });
    await step('select the 200MW Audit Test Campus and load Site G', async () => {
      const opts = await page.locator('#project option').allTextContents(); L('   projects:', opts.join(' / '));
      const idx = opts.findIndex(o => o.includes('Audit Test')); if (idx < 0) throw Error('audit project missing');
      await page.selectOption('#project', { index: idx }); await page.waitForTimeout(1200);
      L('   disabled now:', await page.locator('#sample-g').isDisabled());
      await page.click('#sample-g'); await page.waitForTimeout(3000);
      L('   overview:', (await page.locator('#overview').innerText()).slice(0, 400).replace(/\n/g, ' | '));
      await shot(page, 'pd_site_g');
    });
    await step('ack + compare economics', async () => {
      await page.check('#ack'); await page.click('#compare'); await page.waitForTimeout(4000);
      L('   results:', (await page.locator('#results').innerText()).slice(0, 500).replace(/\n/g, ' | '));
      await shot(page, 'pd_compare');
    });
    await ctx.close(); }

  // ---------- Transaction review ----------
  { const { ctx, page } = await newPage(browser);
    L('\n# Transaction review');
    await page.goto(BASE + '/transaction-workspace', { waitUntil: 'networkidle' }); await page.waitForTimeout(800);
    L('  authBox hidden:', await page.locator('#authBox').isHidden(), '| workspace hidden:', await page.locator('#workspace').isHidden());
    await step('load review', async () => {
      const opts = await page.locator('#projectSelect option').allTextContents(); L('   projects:', opts.join(' / '));
      await page.selectOption('#projectSelect', { index: 1 }); await page.click('#load'); await page.waitForTimeout(2500);
      L('   message:', await page.locator('#message').innerText());
      L('   review hidden:', await page.locator('#review').isHidden());
      await shot(page, 'tx_review');
    });
    await step('show debt schedule', async () => { await page.click('#loadSchedule'); await page.waitForTimeout(1500); L('   schedule:', (await page.locator('#schedule').innerText()).slice(0, 200).replace(/\n/g, ' | ')); });
    await step('click Sign out in local mode', async () => { await page.click('#logout'); await page.waitForTimeout(1000); L('   authBox hidden:', await page.locator('#authBox').isHidden(), 'status:', await page.locator('#authStatus').innerText()); await shot(page, 'tx_after_signout'); });
    await ctx.close(); }

  // ---------- PermitIQ ----------
  { const { ctx, page } = await newPage(browser);
    L('\n# PermitIQ national');
    await page.goto(BASE + '/permitiq-national', { waitUntil: 'networkidle' }); await page.waitForTimeout(800);
    await step('enter Loudoun coords + screening', async () => {
      await page.fill('#lat', '39.08'); await page.fill('#lon', '-77.55'); await page.locator('#lon').blur(); await page.waitForTimeout(1500);
      const c = await page.locator('#county option').allTextContents(); L('   county options:', c.length, c.slice(0, 4).join(' / '));
      if (c.length > 1) await page.selectOption('#county', { index: 1 });
      await page.locator('button', { hasText: 'Run read-only screening' }).click(); await page.waitForTimeout(2500);
      L('   preview panel:', (await page.locator('aside, .right, #preview, #result').first().innerText().catch(() => '?')).slice(0, 500).replace(/\n/g, ' | '));
      await shot(page, 'piq_screening');
    });
    await step('find cached parcels near point', async () => { await page.click('#findparcels'); await page.waitForTimeout(1500); L('   parcel options:', (await page.locator('#parcelpick option').allTextContents()).join(' / ').slice(0, 200)); });
    await step('run full-footprint screening with nothing selected', async () => { await page.locator('button', { hasText: 'Run full-footprint screening' }).click(); await page.waitForTimeout(1500); await shot(page, 'piq_footprint_empty'); });
    await step('invalid lat 999', async () => { await page.fill('#lat', '999'); await page.locator('button', { hasText: 'Run read-only screening' }).click(); await page.waitForTimeout(1500); L('   validity:', await page.$eval('#lat', e => e.validationMessage)); });
    await ctx.close(); }

  // ---------- Agent operations ----------
  { const { ctx, page } = await newPage(browser);
    L('\n# Agent operations');
    await page.goto(BASE + '/agent-operations', { waitUntil: 'networkidle' }); await page.waitForTimeout(800);
    L('  login form visible:', await page.locator('#login').isVisible());
    await step('queue a review', async () => { await page.click('#queue'); await page.waitForTimeout(2000); L('   notice:', await page.locator('#notice').innerText()); L('   jobs:', (await page.locator('#jobs').innerText()).slice(0, 200).replace(/\n/g, ' | ')); await shot(page, 'ag_queued'); });
    await step('save schedule enabled', async () => { await page.check('#enabled'); await page.click('#save'); await page.waitForTimeout(1500); L('   notice:', await page.locator('#notice').innerText()); });
    await ctx.close(); }

  fs.writeFileSync(path.join(OUT, 'log.txt'), log.join('\n'));
  await browser.close();
})();
