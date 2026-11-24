/* PowerPath task pane: connect, choose a project, insert sourced sheets. Read-only. */
(function () {
  'use strict';
  var core = self.PowerPathCore;
  var $ = function (id) { return document.getElementById(id); };
  var pp = function () { return self.PowerPathClient; };

  function status(msg, isError) { var s = $('status'); s.textContent = msg; s.className = isError ? 'error' : ''; }
  function project() { return $('project').value; }

  async function loadProjects() {
    try {
      localStorage.setItem('pp.baseUrl', $('base-url').value.trim() || location.origin);
      pp().clear();
      var list = await pp().projects();
      $('project').innerHTML = list.map(function (p) {
        var o = document.createElement('option'); o.value = p.id; o.textContent = p.name + ' · ' + p.target_mw + ' MW'; return o.outerHTML;
      }).join('');
      $('project-box').hidden = !list.length;
      status(list.length ? list.length + ' project(s) available' : 'No projects visible with these credentials');
      if (list.length) await describe();
    } catch (e) { status(e.message, true); }
  }

  async function signIn() {
    try {
      localStorage.setItem('pp.baseUrl', $('base-url').value.trim() || location.origin);
      var r = await pp().login($('email').value, $('password').value);
      localStorage.setItem('pp.token', r.token || r.access_token || '');
      $('password').value = '';
      status('Signed in');
      await loadProjects();
    } catch (e) { status(e.message, true); }
  }

  async function describe() {
    var id = project();
    $('examples').textContent = [
      '=POWERPATH.METRIC("' + id + '","npv")',
      '=POWERPATH.EXPOSURE("' + id + '","energization_delay_months")',
      '=POWERPATH.SOURCE("' + id + '","construction_cost_mw")',
      '=POWERPATH.PRIORITIES("' + id + '")',
      '=POWERPATH.BRIDGE("' + id + '",A2:B4)',
      '=POWERPATH.PATHBRIDGE("' + id + '","Grid utility service")',
      '=POWERPATH.DELIVERABLE("' + id + '","","base","month")'
    ].join('\n');
    try {
      var c = await pp().approvedCase(id), r = c.result;
      $('case-line').textContent = 'Approved case: NPV $' + r.npvM.toFixed(1) + 'M · IRR ' + (r.leveredIRR * 100).toFixed(1) + '% · ' +
        Object.keys(c.assignments).length + ' approved assumption(s) · ' + c.fingerprint.slice(0, 10);
    } catch (e) { $('case-line').textContent = e.message; }
  }

  async function writeSheet(name, blocks) {
    await Excel.run(async function (ctx) {
      var sheets = ctx.workbook.worksheets;
      var existing = sheets.getItemOrNullObject(name);
      await ctx.sync();
      if (!existing.isNullObject) existing.delete();
      var ws = sheets.add(name);
      var row = 0;
      blocks.forEach(function (b) {
        if (b.title) { ws.getRangeByIndexes(row, 0, 1, 1).values = [[b.title]]; ws.getRangeByIndexes(row, 0, 1, 1).format.font.bold = true; row += 1; }
        if (b.note) { ws.getRangeByIndexes(row, 0, 1, 1).values = [[b.note]]; ws.getRangeByIndexes(row, 0, 1, 1).format.font.color = '#5d6d69'; row += 1; }
        if (b.rows && b.rows.length) {
          var width = b.rows[0].length;
          var rows = b.rows.map(function (r) { return r.concat(Array(width - r.length).fill('')); });
          ws.getRangeByIndexes(row, 0, rows.length, width).values = rows;
          var t = ws.tables.add(ws.getRangeByIndexes(row, 0, rows.length, width), true);
          t.style = 'TableStyleLight9';
          row += rows.length;
        }
        row += 1;
      });
      ws.getUsedRange().format.autofitColumns();
      ws.activate();
      await ctx.sync();
    });
  }

  async function insert(kind) {
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
      } else {
        var d = await pp().deliverability(id), body = d.body, rows = [['Configuration', 'Firm MW at target (downside)', 'Base', 'Upside', 'Target month (upside)', 'Base', 'Downside', 'Evidence quality', 'Answer']];
        body.configurations.forEach(function (cf) {
          var m = cf.deliverable_mw_at_target, t = cf.time_to_target_month;
          rows.push([cf.name, m.low, m.base, m.high, t.low === null ? '' : t.low, t.base === null ? '' : t.base, t.high === null ? 'not reached' : t.high, cf.evidence_quality.label, cf.answer]);
        });
        await writeSheet('PP Deliverability', [{ title: 'Deliverability: ' + body.target_mw + ' MW by month ' + body.target_month, note: 'Assessment v' + d.version + ' · ' + d.created_at + ' · scenario bounds, not probabilities' }, { rows: rows }]);
      }
      status('Sheet inserted');
    } catch (e) { status(e.message, true); }
  }

  Office.onReady(function () {
    $('base-url').value = localStorage.getItem('pp.baseUrl') || location.origin;
    $('load-projects').onclick = loadProjects;
    $('sign-in').onclick = signIn;
    $('project').onchange = describe;
    $('refresh').onclick = async function () {
      pp().clear();
      try { await Excel.run(async function (ctx) { ctx.workbook.application.calculate(Excel.CalculationType.full); await ctx.sync(); }); status('Recalculated'); }
      catch (e) { status(e.message, true); }
    };
    document.querySelectorAll('[data-insert]').forEach(function (b) { b.onclick = function () { insert(b.dataset.insert); }; });
    loadProjects();
  });
})();
