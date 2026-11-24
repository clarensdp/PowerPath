// Runs powerpath-core.js against API responses captured by tests/test_excel_addin.py.
const assert = require('assert');
const fs = require('fs');
const core = require('../../web/excel/powerpath-core.js');
const fx = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
assert.strictEqual(core.metric(fx.case, 'npv'), fx.case.result.npvM);
assert.strictEqual(core.metric(fx.case, 'IRR'), fx.case.result.leveredIRR);
assert.throws(() => core.metric(fx.case, 'moic'));
const pt = core.prioritiesTable(fx.priorities);
assert.strictEqual(pt.length, fx.priorities.priorities.length + 1);
assert.strictEqual(pt[0][8], 'NPV at risk ($M)');
const bt = core.bridgeTable(fx.bridge);
const total = bt[bt.length - 1];
assert.strictEqual(total[0], 'Total');
const sum = bt.slice(1, -1).reduce((s, r) => s + r[3], 0);
assert.ok(Math.abs(sum - total[3]) < 1e-6, 'bridge rows reconcile to total');
assert.deepStrictEqual(core.driversFromRange([['energization_delay_months', 6], ['', ''], ['power_capex_m', 50]]), { energization_delay_months: 6, power_capex_m: 50 });
assert.throws(() => core.driversFromRange([['', '']]));
assert.strictEqual(core.deliverable(fx.deliverability, '', 'base', 'month'), fx.deliverability.body.configurations[0].time_to_target_month.base);
assert.throws(() => core.deliverable(fx.deliverability, 'nope', 'base', 'mw'));
assert.ok(core.sourceText(fx.priorities, 'construction_cost_mw').includes('EPC quote'));
// client caches GETs and sends the bearer token
let calls = 0;
const c = core.client({ baseUrl: () => 'https://pp.test', token: () => 'tok', fetch: (url, o) => { calls++; assert.strictEqual(o.headers.Authorization, 'Bearer tok'); return Promise.resolve({ ok: true, json: () => Promise.resolve([]) }); } });
Promise.all([c.projects(), c.projects()]).then(() => { assert.strictEqual(calls, 1); console.log('excel core ok'); });
