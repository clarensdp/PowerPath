/* PowerPath custom functions, namespace PP (shared runtime with the task pane).
   =PP.GET(project, field, [arg1], [arg2])   one value
   =PP.TABLE(project, name, [arg])           spilled table
   =PP.BRIDGE(project, range)                what-if attribution by cause
   Read-only: no function can approve, reject or save anything. */
(function () {
  'use strict';
  var core = self.PowerPathCore;
  var KEY = 'pp.session';

  // Session lives in memory (shared runtime) and sessionStorage only (never persistent browser storage),
  // so it ends when Excel closes. Sessions also expire server-side.
  var session = self.PowerPathSession = self.PowerPathSession || (function () {
    var current = null;
    try { current = JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch (e) { current = null; }
    function valid() { return current && current.token && (!current.expires_at || new Date(current.expires_at) > new Date()); }
    return {
      baseUrl: function () { return location.origin; },
      token: function () { if (current && !valid()) this.clear(); return current ? current.token : ''; },
      set: function (s) { current = s; try { sessionStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* storage blocked */ } },
      clear: function () { current = null; try { sessionStorage.removeItem(KEY); } catch (e) { /* ignore */ } },
      info: function () { return valid() ? { email: current.email, expires_at: current.expires_at } : null; }
    };
  })();
  var pp = self.PowerPathClient = self.PowerPathClient || core.client({ baseUrl: session.baseUrl, token: function () { return session.token(); } });

  function fail(e) {
    var msg = String((e && e.message) || e);
    if (/401|Authentication required|Invalid|expired/i.test(msg)) msg = 'Sign in from the PowerPath task pane (Home → PowerPath).';
    throw new CustomFunctions.Error(CustomFunctions.ErrorCode.notAvailable, msg.slice(0, 250));
  }

  async function dataFor(project, field) {
    var spec = core.GET_FIELDS[String(field || '').trim().toLowerCase()];
    if (!spec) return {};
    if (spec.needs === 'case') return { case: await pp.approvedCase(project) };
    if (spec.needs === 'priorities') return { priorities: await pp.priorities(project) };
    return { deliverability: await pp.deliverability(project) };
  }

  /** One PowerPath value. field: npv, irr, dscr, breach_months, exposure, source, confidence, value, rank, deliverable_mw, time_to_target. */
  async function GET(project, field, arg1, arg2) {
    try { return core.resolveGet(await dataFor(project, field), field, arg1, arg2); } catch (e) { fail(e); }
  }

  /** A spilled table. name: priorities, pathbridge (arg = path name), deliverability, fields. */
  async function TABLE(project, name, arg) {
    try {
      var n = String(name || '').trim().toLowerCase();
      if (n === 'fields') return core.fieldsTable();
      if (n === 'priorities') return core.prioritiesTable(await pp.priorities(project));
      if (n === 'deliverability') return core.deliverabilityTable(await pp.deliverability(project));
      if (n === 'pathbridge') {
        if (!arg) throw new Error('pathbridge needs a power path name');
        var paths = await pp.paths(project);
        var hit = paths.filter(function (p) { return p.id === arg || p.name.toLowerCase() === String(arg).toLowerCase(); })[0];
        if (!hit) throw new Error('No power path named "' + arg + '"');
        return core.bridgeTable(await pp.pathBridge(project, hit.id));
      }
      throw new Error('Unknown table "' + name + '". Tables: priorities, pathbridge, deliverability, fields.');
    } catch (e) { fail(e); }
  }

  /** What-if on the approved case from a two-column range (input key, new value). Parts add up to the total. */
  async function BRIDGE(project, range) {
    try { return core.bridgeTable(await pp.bridge(project, core.driversFromRange(range))); } catch (e) { fail(e); }
  }

  CustomFunctions.associate('GET', GET);
  CustomFunctions.associate('TABLE', TABLE);
  CustomFunctions.associate('BRIDGE', BRIDGE);
})();
