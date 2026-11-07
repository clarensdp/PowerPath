// Pass 1: load every surface at 3 viewports, capture screenshots, console errors, failed requests, axe violations, overflow.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const BASE = 'http://127.0.0.1:8768';
const OUT = path.join(__dirname, process.env.SHOTDIR||'shots');
fs.mkdirSync(OUT, { recursive: true });
const pages = ['/', '/advanced', '/power-deliverability', '/transaction-workspace', '/permitiq-national', '/agent-operations'];
const vps = { desktop: { width: 1440, height: 900 }, tablet: { width: 820, height: 1180 }, mobile: { width: 390, height: 844 } };

(async () => {
  const browser = await chromium.launch();
  const report = [];
  for (const [vpName, vp] of Object.entries(vps)) {
    for (const p of pages) {
      const ctx = await browser.newContext({ viewport: vp, bypassCSP: true });
      const page = await ctx.newPage();
      const errors = [], failed = [];
      page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text()); });
      page.on('pageerror', e => errors.push('pageerror: ' + e.message));
      page.on('response', r => { if (r.status() >= 400) failed.push(r.status() + ' ' + r.request().method() + ' ' + r.url().replace(BASE, '')); });
      const t0 = Date.now();
      await page.goto(BASE + p, { waitUntil: 'networkidle' });
      await page.waitForTimeout(1200);
      const loadMs = Date.now() - t0;
      const name = (p === '/' ? 'home' : p.slice(1)) + '_' + vpName;
      await page.screenshot({ path: path.join(OUT, name + '.png'), fullPage: true });
      const metrics = await page.evaluate(() => {
        const de = document.documentElement;
        const over = [];
        document.querySelectorAll('body *').forEach(el => { const r = el.getBoundingClientRect(); if (r.right > de.clientWidth + 2 && r.width > 0 && getComputedStyle(el).position !== 'fixed') over.push(el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className && typeof el.className === 'string' ? '.' + el.className.split(' ')[0] : '')); });
        const small = [...document.querySelectorAll('button, a, input, select')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.height < 24 || r.width < 24); }).length;
        return { scrollW: de.scrollWidth, clientW: de.clientWidth, docH: de.scrollHeight, overflow: [...new Set(over)].slice(0, 8), smallTargets: small, h1: [...document.querySelectorAll('h1')].map(h => h.innerText.trim()).slice(0, 3), title: document.title, buttons: document.querySelectorAll('button').length, inputs: document.querySelectorAll('input,select,textarea').length };
      });
      let axe = [];
      if (vpName !== 'tablet') {
        await page.addScriptTag({ content: AXE });
        axe = await page.evaluate(async () => { const r = await axe.run(document, { resultTypes: ['violations'] }); return r.violations.map(v => ({ id: v.id, impact: v.impact, n: v.nodes.length, help: v.help, sample: v.nodes.slice(0, 2).map(n => n.target.join(' ')) })); });
      }
      report.push({ page: p, vp: vpName, loadMs, errors: [...new Set(errors)].slice(0, 15), failed: [...new Set(failed)].slice(0, 15), ...metrics, axe });
      await ctx.close();
    }
  }
  fs.writeFileSync(path.join(__dirname, (process.env.SHOTDIR||'shots')+'_sweep.json'), JSON.stringify(report, null, 1));
  for (const r of report) {
    console.log(`\n## ${r.page} [${r.vp}] ${r.loadMs}ms title="${r.title}" h1=${JSON.stringify(r.h1)} docH=${r.docH} hscroll=${r.scrollW > r.clientW ? r.scrollW + '>' + r.clientW : 'no'} small=${r.smallTargets} btn=${r.buttons} inputs=${r.inputs}`);
    if (r.overflow.length) console.log('  overflow:', r.overflow.join(', '));
    r.errors.forEach(e => console.log('  console', e.slice(0, 220)));
    r.failed.forEach(e => console.log('  http', e));
    r.axe.forEach(a => console.log(`  axe ${a.impact} ${a.id} x${a.n}: ${a.help} | ${a.sample.join(' ; ').slice(0, 160)}`));
  }
  await browser.close();
})();
