/* PowerPath task pane: sign in (dialog), choose a project, build PP formulas, insert stamped sheets. Read-only. */
(function () {
  'use strict';
  var core = self.PowerPathCore;
  var $ = function (id) { return document.getElementById(id); };
  var pp = function () { return self.PowerPathClient; };
  var session = function () { return self.PowerPathSession; };
  var cache = { priorities: null, deliverability: null, paths: [], market: null, plants: [] };
  var STATS = { lmp_da: ['avg', 'on_peak', 'off_peak', 'max', 'min', 'stdev', 'congestion_avg'], spark_spread: ['on_peak', 'avg'], henry_hub: ['value'],
    retail_industrial: ['value'], retail_commercial: ['value'], ba_demand: ['avg_mw', 'value'],
    fuel_mix: ['carbon_t_per_mwh', 'gas', 'renewables', 'nuclear', 'coal', 'wind', 'solar', 'hydro'] };

  function status(msg, isError) { var s = $('status'); s.textContent = msg; s.className = isError ? 'error' : ''; }
  function project() { return $('project').value; }
  function q(v) { return '"' + String(v).replace(/"/g, '""') + '"'; }
  function options(sel, items) {
    sel.innerHTML = '';
    items.forEach(function (it) { var o = document.createElement('option'); o.value = it[0]; o.textContent = it[1]; sel.appendChild(o); });
  }
  function show(id, on) { $(id).hidden = !on; }

  // ------------------------------------------------------------------ account
  async function account() {
    var me = {};
    try { me = await fetch('/api/v27/me', { headers: session().token() ? { Authorization: 'Bearer ' + session().token() } : {} }).then(function (r) { return r.json(); }); }
    catch (e) { me = {}; }
    var info = session().info();
    if (me.mode === 'LOCAL_ONLY') {
      $('who').textContent = 'Local workspace: no sign-in needed.';
      show('sign-in', false); show('sign-out', false);
      return true;
    }
    if (info && me.id) {
      $('who').textContent = 'Signed in as ' + (info.email || me.email) + (info.expires_at ? ' · session until ' + new Date(info.expires_at).toLocaleTimeString() : '');
      show('sign-in', false); show('sign-out', true);
      return true;
    }
    session().clear();
    $('who').textContent = 'Sign in with your PowerPath account to load projects.';
    show('sign-in', true); show('sign-out', false); show('project-box', false);
    return false;
  }

  function signIn() {
    Office.context.ui.displayDialogAsync(location.origin + '/excel/login.html', { height: 50, width: 30, displayInIframe: true }, function (res) {
      if (res.status !== Office.AsyncResultStatus.Succeeded) { status('Could not open the sign-in window: ' + res.error.message, true); return; }
      var dialog = res.value;
      dialog.addEventHandler(Office.EventType.DialogMessageReceived, async function (arg) {
        dialog.close();
        var msg = {};
        try { msg = JSON.parse(arg.message); } catch (e) { msg = {}; }
        if (msg.type !== 'session' || !msg.token) { status('Sign-in was not completed', true); return; }
        session().set({ token: msg.token, expires_at: msg.expires_at, email: msg.email });
        pp().clear();
        status('Signed in');
        await start();
      });
      dialog.addEventHandler(Office.EventType.DialogEventReceived, function () { status('Sign-in window closed'); });
    });
  }

  async function signOut() {
    try { await pp().logout(); } catch (e) { /* session may already be gone */ }
    session().clear(); pp().clear();
    status('Signed out');
    await account();
  }

  // ------------------------------------------------------------------ project
  async function loadProjects() {
    var list = await pp().projects();
    options($('project'), list.map(function (p) { return [p.id, p.name + ' · ' + p.target_mw + ' MW']; }));
    show('project-box', list.length > 0);
    status(list.length ? '' : 'No projects visible with this account');
    if (list.length) await describe();
  }

  async function describe() {
    var id = project();
    cache = { priorities: null, deliverability: null, paths: [], market: null, plants: [] };
    try {
      var c = await pp().approvedCase(id), r = c.result;
      $('case-line').textContent = 'Approved case: NPV $' + r.npvM.toFixed(1) + 'M · IRR ' + (r.leveredIRR * 100).toFixed(1) + '% · ' +
        Object.keys(c.assignments).length + ' approved assumption(s) · ' + c.fingerprint.slice(0, 10);
    } catch (e) { $('case-line').textContent = e.message; }
    try { cache.priorities = await pp().priorities(id); } catch (e) { cache.priorities = null; }
    try { cache.deliverability = await pp().deliverability(id); } catch (e) { cache.deliverability = null; }
    try { cache.paths = await pp().paths(id); } catch (e) { cache.paths = []; }
    try { cache.plants = (await pp().plants(id)).plants.slice().sort(function (a, b) { return b.summer_mw - a.summer_mw; }); } catch (e) { cache.plants = []; }
    try {
      var prof = await fetchJSON('/api/projects/' + encodeURIComponent(id) + '/market/profile');
      $('market-line').textContent = 'Market profile: ' + ([prof.nyiso_zone && 'NYISO ' + prof.nyiso_zone, prof.ba && 'BA ' + prof.ba, prof.state].filter(Boolean).join(' · ') || 'not set; set it in PowerPath (Returns step)');
    } catch (e) { $('market-line').textContent = ''; }
    builderOptions();
  }

  async function fetchJSON(path) {
    var t = session().token();
    var r = await fetch(path, { headers: t ? { Authorization: 'Bearer ' + t } : {} });
    var d = await r.json();
    if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'HTTP ' + r.status);
    return d;
  }

  // ------------------------------------------------------------------ formula builder
  function builderOptions() {
    var kind = $('b-kind').value;
    if (kind === 'GET') options($('b-field'), Object.keys(core.GET_FIELDS).map(function (k) { return [k, k + ': ' + core.GET_FIELDS[k].help]; }));
    if (kind === 'TABLE') options($('b-field'), Object.keys(core.TABLES).map(function (k) { return [k, k + ': ' + core.TABLES[k]]; }));
    options($('b-arg'), (cache.priorities ? cache.priorities.priorities : []).map(function (p) { return [p.key, p.label]; }));
    options($('b-conf'), [['', 'First configuration']].concat(cache.deliverability ? cache.deliverability.body.configurations.map(function (c) { return [c.name, c.name]; }) : []));
    options($('b-path'), cache.paths.map(function (p) { return [p.name, p.name]; }));
    options($('b-plant'), cache.plants.map(function (p) { return [p.plant_id, p.name + ' · ' + p.primary_fuel + ' · ' + Math.round(p.summer_mw) + ' MW']; }));
    options($('b-pfield'), Object.keys(core.PLANT_FIELDS).map(function (k) { return [k, k + ': ' + core.PLANT_FIELDS[k]]; }));
    options($('b-metric'), Object.keys(core.MARKET_METRICS).map(function (k) { return [k, core.MARKET_METRICS[k]]; }));
    statOptions();
  }

  function statOptions() {
    options($('b-stat'), (STATS[$('b-metric').value] || ['value']).map(function (k) { return [k, k]; }));
    $('b-window').value = $('b-metric').value.indexOf('retail') === 0 ? 12 : 30;
    preview();
  }

  function formula() {
    var kind = $('b-kind').value, field = $('b-field').value, id = q(project());
    if (kind === 'BRIDGE') return '=PP.BRIDGE(' + id + ',' + ($('b-range').value.trim() || 'A2:B4') + ')';
    if (kind === 'PLANT') return '=PP.PLANT(' + id + ',' + q($('b-plant').value) + ',' + q($('b-pfield').value) + ($('b-pfield').value === 'cf_year' ? ',' + (parseInt($('b-year').value, 10) || 2025) : '') + ')';
    if (kind === 'MARKET') return '=PP.MARKET(' + id + ',' + q($('b-metric').value) + ',' + q($('b-stat').value) + ',' + (parseInt($('b-window').value, 10) || 30) + ')';
    if (kind === 'TABLE') return '=PP.TABLE(' + id + ',' + q(field) + (field === 'pathbridge' ? ',' + q($('b-path').value) : '') + ')';
    var spec = core.GET_FIELDS[field] || {};
    if (spec.needs === 'priorities') return '=PP.GET(' + id + ',' + q(field) + ',' + q($('b-arg').value) + ')';
    if (spec.needs === 'deliverability') return '=PP.GET(' + id + ',' + q(field) + ',' + q($('b-case').value) + ($('b-conf').value ? ',' + q($('b-conf').value) : '') + ')';
    return '=PP.GET(' + id + ',' + q(field) + ')';
  }

  function preview() {
    var kind = $('b-kind').value, field = $('b-field').value, spec = core.GET_FIELDS[field] || {};
    show('b-field-l', kind === 'GET' || kind === 'TABLE');
    show('b-plant-l', kind === 'PLANT'); show('b-pfield-l', kind === 'PLANT'); show('b-year-l', kind === 'PLANT' && $('b-pfield').value === 'cf_year');
    show('b-metric-l', kind === 'MARKET'); show('b-stat-l', kind === 'MARKET'); show('b-window-l', kind === 'MARKET');
    show('b-arg-l', kind === 'GET' && spec.needs === 'priorities');
    show('b-case-l', kind === 'GET' && spec.needs === 'deliverability');
    show('b-conf-l', kind === 'GET' && spec.needs === 'deliverability');
    show('b-path-l', kind === 'TABLE' && field === 'pathbridge');
    show('b-range-l', kind === 'BRIDGE');
    $('b-preview').textContent = formula();
    $('b-help').textContent = kind === 'BRIDGE' ? 'Put input keys in the first column and new values in the second. Use =PP.TABLE(project,"fields") to list keys.'
      : kind === 'TABLE' ? 'Spills into the cells below and to the right; leave them empty.'
      : kind === 'PLANT' ? (cache.plants.length ? 'Plants in the market profile state, largest first. Capacity factor shows how much a plant ran, not its availability.' : 'Set the state in the project market profile to list plants.')
      : kind === 'MARKET' ? 'Uses the project market profile. Wholesale LMP is energy only; delivered cost adds transmission, capacity and utility charges.' : '';
  }

  async function insertFormula() {
    try {
      var f = formula();
      await Excel.run(async function (ctx) { ctx.workbook.getSelectedRange().getCell(0, 0).formulas = [[f]]; await ctx.sync(); });
      status('Inserted ' + f);
    } catch (e) { status(e.message, true); }
  }

  // ------------------------------------------------------------------ sheets of values
  async function writeSheet(name, blocks) {
    await Excel.run(async function (ctx) {
      var sheets = ctx.workbook.worksheets;
      var existing = sheets.getItemOrNullObject(name);
      await ctx.sync();
      if (!existing.isNullObject) existing.delete();
      var ws = sheets.add(name), row = 0;
      blocks.forEach(function (b) {
        if (b.title) { ws.getRangeByIndexes(row, 0, 1, 1).values = [[b.title]]; ws.getRangeByIndexes(row, 0, 1, 1).format.font.bold = true; row += 1; }
        if (b.note) { ws.getRangeByIndexes(row, 0, 1, 1).values = [[b.note]]; ws.getRangeByIndexes(row, 0, 1, 1).format.font.color = '#5d6d69'; row += 1; }
        if (b.rows && b.rows.length) {
          var width = b.rows[0].length;
          var rows = b.rows.map(function (r) { return r.concat(Array(width - r.length).fill('')); });
          ws.getRangeByIndexes(row, 0, rows.length, width).values = rows;
          ws.tables.add(ws.getRangeByIndexes(row, 0, rows.length, width), true).style = 'TableStyleLight9';
          row += rows.length;
        }
        row += 1;
      });
      ws.getUsedRange().format.autofitColumns();
      ws.activate();
      await ctx.sync();
    });
  }

  async function insertSheet(kind) {
    var id = project();
    status('Running PowerPath…');
    try {
      var c = await pp().approvedCase(id);
      var stamp = 'Approved case ' + c.fingerprint.slice(0, 10) + ' · scenario ' + c.scenario_id + ' v' + c.scenario_version + ' · ' + c.calculated_at + ' · values, not live formulas';
      if (kind === 'priorities') {
        var pr = await pp().priorities(id);
        await writeSheet('PP Diligence', [{ title: 'Diligence ranked by NPV at risk', note: stamp }, { rows: core.prioritiesTable(pr) }, { note: pr.method + ' ' + pr.stress_note }]);
      } else if (kind === 'paths') {
        var paths = await pp().paths(id), blocks = [{ title: 'Power path returns, by cause', note: stamp }];
        for (var i = 0; i < paths.length; i++) {
          try { blocks.push({ title: paths[i].name, rows: core.bridgeTable(await pp().pathBridge(id, paths[i].id)) }); }
          catch (e) { blocks.push({ title: paths[i].name, note: e.message }); }
        }
        blocks.push({ note: 'Shapley attribution: causes add up to the total change regardless of order. Measured from the approved case.' });
        await writeSheet('PP Path bridges', blocks);
      } else if (kind === 'market') {
        var snap = await pp().marketSnapshot(id, 30);
        await writeSheet('PP Market', [{ title: 'Power market snapshot, ' + snap.window_days + ' days', note: 'Calculated ' + snap.calculated_at + ' · values, not live formulas' },
          { rows: core.marketTable(snap) }, { note: snap.notes.join(' ') }]);
      } else {
        var d = await pp().deliverability(id);
        await writeSheet('PP Deliverability', [{ title: 'Deliverability: ' + d.body.target_mw + ' MW by month ' + d.body.target_month,
          note: 'Assessment v' + d.version + ' · ' + d.created_at + ' · scenario bounds, not probabilities' }, { rows: core.deliverabilityTable(d) }]);
      }
      status('Sheet inserted');
    } catch (e) { status(e.message, true); }
  }

  async function start() {
    try { if (await account()) await loadProjects(); } catch (e) { status(e.message, true); }
  }

  Office.onReady(function () {
    $('sign-in').onclick = signIn;
    $('sign-out').onclick = signOut;
    $('project').onchange = describe;
    $('b-kind').onchange = builderOptions;
    ['b-field', 'b-arg', 'b-case', 'b-conf', 'b-path', 'b-stat', 'b-plant', 'b-pfield'].forEach(function (id) { $(id).onchange = preview; });
    $('b-metric').onchange = statOptions;
    $('b-window').oninput = preview;
    $('b-year').oninput = preview;
    $('b-range').oninput = preview;
    $('b-insert').onclick = insertFormula;
    $('refresh').onclick = async function () {
      pp().clear();
      try { await Excel.run(async function (ctx) { ctx.workbook.application.calculate(Excel.CalculationType.full); await ctx.sync(); }); status('Refreshed'); }
      catch (e) { status(e.message, true); }
    };
    document.querySelectorAll('[data-insert]').forEach(function (b) { b.onclick = function () { insertSheet(b.dataset.insert); }; });
    start();
  });
})();
