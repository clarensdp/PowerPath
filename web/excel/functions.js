/* PowerPath custom functions (shared runtime with the task pane).
   Read-only: no function can approve, reject or save anything. */
(function () {
  'use strict';
  var core = self.PowerPathCore;
  var session = self.PowerPathSession = self.PowerPathSession || {
    baseUrl: function () { return localStorage.getItem('pp.baseUrl') || location.origin; },
    token: function () { return localStorage.getItem('pp.token') || ''; }
  };
  var pp = self.PowerPathClient = self.PowerPathClient || core.client({ baseUrl: session.baseUrl, token: session.token });

  function fail(e) {
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.notAvailable, String((e && e.message) || e).slice(0, 250));
  }
  async function pathId(project, name) {
    var paths = await pp.paths(project);
    var hit = paths.filter(function (p) { return p.id === name || p.name.toLowerCase() === String(name).toLowerCase(); })[0];
    if (!hit) throw new Error('No power path named "' + name + '"');
    return hit.id;
  }

  /** Approved-case metric. metric: npv | irr | dscr | breach_months */
  async function METRIC(project, metric) {
    try { return core.metric(await pp.approvedCase(project), metric); } catch (e) { fail(e); }
  }
  /** NPV change ($M) if one input moves to its documented or default downside. */
  async function EXPOSURE(project, key) {
    try {
      var p = (await pp.priorities(project)).priorities.filter(function (x) { return x.key === key; })[0];
      if (!p) throw new Error('Unknown input ' + key);
      if (!p.exposure || p.exposure.npv_delta_m === null || p.exposure.npv_delta_m === undefined) throw new Error('No downside quantified');
      return p.exposure.npv_delta_m;
    } catch (e) { fail(e); }
  }
  /** Source, date, verification and review state behind an input. */
  async function SOURCE(project, key) {
    try { return core.sourceText(await pp.priorities(project), key); } catch (e) { fail(e); }
  }
  /** Diligence priorities ranked by NPV at risk (spills a table). */
  async function PRIORITIES(project) {
    try { return core.prioritiesTable(await pp.priorities(project)); } catch (e) { fail(e); }
  }
  /** What-if on the approved case: two-column range of driver keys and values. Spills cause attribution. */
  async function BRIDGE(project, drivers) {
    try { return core.bridgeTable(await pp.bridge(project, core.driversFromRange(drivers))); } catch (e) { fail(e); }
  }
  /** Attribution of a power path's change in returns, by cause. */
  async function PATHBRIDGE(project, path) {
    try { return core.bridgeTable(await pp.pathBridge(project, await pathId(project, path))); } catch (e) { fail(e); }
  }
  /** Latest deliverability: field "mw" (firm MW at target month) or "month" (time to target). case: upside | base | downside */
  async function DELIVERABLE(project, configuration, kase, field) {
    try { return core.deliverable(await pp.deliverability(project), configuration || '', kase, field); } catch (e) { fail(e); }
  }

  CustomFunctions.associate('METRIC', METRIC);
  CustomFunctions.associate('EXPOSURE', EXPOSURE);
  CustomFunctions.associate('SOURCE', SOURCE);
  CustomFunctions.associate('PRIORITIES', PRIORITIES);
  CustomFunctions.associate('BRIDGE', BRIDGE);
  CustomFunctions.associate('PATHBRIDGE', PATHBRIDGE);
  CustomFunctions.associate('DELIVERABLE', DELIVERABLE);
})();
