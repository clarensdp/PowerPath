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
// PP.GET / PP.TABLE resolution
assert.strictEqual(core.resolveGet({ case: fx.case }, 'NPV'), fx.case.result.npvM);
assert.strictEqual(core.resolveGet({ case: fx.case }, 'dscr'), fx.case.result.minDSCR);
const delay = fx.priorities.priorities.find(p => p.key === 'energization_delay_months');
assert.strictEqual(core.resolveGet({ priorities: fx.priorities }, 'exposure', 'energization_delay_months'), delay.exposure.npv_delta_m);
assert.strictEqual(core.resolveGet({ priorities: fx.priorities }, 'rank', 'energization_delay_months'), delay.rank);
assert.strictEqual(core.resolveGet({ priorities: fx.priorities }, 'value', 'construction_cost_mw'), 8);
assert.ok(['low', 'medium', 'high'].includes(core.resolveGet({ priorities: fx.priorities }, 'confidence', 'construction_cost_mw')));
assert.ok(core.resolveGet({ priorities: fx.priorities }, 'source', 'construction_cost_mw').includes('EPC quote'));
assert.strictEqual(core.resolveGet({ deliverability: fx.deliverability }, 'time_to_target', 'base'), fx.deliverability.body.configurations[0].time_to_target_month.base);
assert.strictEqual(core.resolveGet({ deliverability: fx.deliverability }, 'deliverable_mw', 'upside'), fx.deliverability.body.configurations[0].deliverable_mw_at_target.high);
assert.throws(() => core.resolveGet({ priorities: fx.priorities }, 'exposure'), /needs an input key/);
assert.throws(() => core.resolveGet({}, 'moic'), /Unknown field/);
assert.throws(() => core.resolveGet({ priorities: fx.priorities }, 'value', 'nope'), /Unknown input/);
const ft = core.fieldsTable();
assert.ok(ft.length === 1 + Object.keys(core.GET_FIELDS).length + Object.keys(core.TABLES).length + 1 + Object.keys(core.MARKET_METRICS).length + Object.keys(core.PLANT_FIELDS).length);
assert.strictEqual(core.deliverabilityTable(fx.deliverability).length, fx.deliverability.body.configurations.length + 1);
// market tables
const mt = core.marketTable(fx.market);
assert.strictEqual(mt.length, 3); assert.strictEqual(mt[1][1], 51.5); assert.strictEqual(mt[2][5], 'unavailable');
const ht = core.historyTable(fx.history);
assert.deepStrictEqual(ht[0], ['Period', 'avg', 'on_peak', 'Source']); assert.strictEqual(ht[2][2], '');
assert.throws(() => core.historyTable({ stats: ['value'], observations: [], warnings: ['No key'] }), /No key/);
assert.ok(core.fieldsTable().some(r => r[0] === 'PP.MARKET' && r[1] === 'lmp_da'));
// plant fields and tables
assert.strictEqual(core.resolvePlant(fx.plant, 'worst_year'), 2023);
assert.strictEqual(core.resolvePlant(fx.plant, 'name'), 'Riverbend Hydro');
assert.ok(core.resolvePlant(fx.plant, 'cf_worst') < core.resolvePlant(fx.plant, 'cf_avg'));
assert.strictEqual(core.resolvePlant(fx.plant, 'cf_year', 2023), fx.plant.capacity_factor.years.find(y => y.year === 2023).cf);
assert.throws(() => core.resolvePlant(fx.plant, 'cf_year', 1990), /No generation/);
assert.throws(() => core.resolvePlant(fx.plant, 'moic'), /Unknown plant field/);
assert.strictEqual(core.plantsTable(fx.plants)[1][1], 'Riverbend Hydro');
assert.strictEqual(core.plantCfTable(fx.plant).length, fx.plant.capacity_factor.years.length + 1);
// client caches GETs and sends the bearer token
let calls = 0;
const c = core.client({ baseUrl: () => 'https://pp.test', token: () => 'tok', fetch: (url, o) => { calls++; assert.strictEqual(o.headers.Authorization, 'Bearer tok'); return Promise.resolve({ ok: true, json: () => Promise.resolve([]) }); } });
Promise.all([c.projects(), c.projects()]).then(() => { assert.strictEqual(calls, 1); console.log('excel core ok'); });
