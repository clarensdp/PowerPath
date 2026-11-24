/* PowerPath Excel add-in core: API client and response-to-grid mapping.
   Pure functions so they can be tested in Node; loaded as a classic script in Office. */
(function (root) {
  'use strict';
  var METRICS = { npv: 'npvM', irr: 'leveredIRR', dscr: 'minDSCR', breach_months: 'breachMonths' };
  var CACHE_MS = 60000;

  function fmtValue(v) {
    if (v && typeof v === 'object' && Array.isArray(v.phases))
      return v.phases.map(function (p) { return p.mw + ' MW from M' + p.month; }).join(', ');
    return v === null || v === undefined ? '' : v;
  }
  function num(v) { return typeof v === 'number' && isFinite(v) ? v : ''; }

  function metric(caseResp, name) {
    var key = METRICS[String(name || 'npv').toLowerCase()];
    if (!key) throw new Error('Metric must be npv, irr, dscr or breach_months');
    var v = caseResp.result[key];
    if (Array.isArray(v)) return v.length;
    if (v === null || v === undefined) throw new Error('Not defined for this case');
    return v;
  }

  function prioritiesTable(pr) {
    var rows = [['Rank', 'Input', 'Value', 'Unit', 'Source', 'Source date', 'Verification', 'Confidence', 'NPV at risk ($M)', 'Downside', 'Downside basis', 'Materiality', 'State', 'Next action']];
    pr.priorities.forEach(function (p) {
      var e = p.exposure || {};
      rows.push([p.rank, p.label, String(fmtValue(p.value)), p.unit, (p.source && p.source.source_name) || 'Undocumented', (p.source && p.source.source_date) || '',
        p.verification || '', p.confidence.label, num(e.npv_delta_m), String(fmtValue(p.downside_value)), p.downside_basis || '', p.materiality, p.state, p.next_action]);
    });
    return rows;
  }

  function bridgeTable(b) {
    var rows = [['Cause', 'From', 'To', 'NPV change ($M)', 'IRR change (pts)', 'Min DSCR change (x)']];
    b.drivers.forEach(function (d) {
      var a = b.attribution;
      rows.push([d.label, String(fmtValue(d.from)), String(fmtValue(d.value)), num(a.npvM && a.npvM[d.key]),
        a.leveredIRR ? num(a.leveredIRR[d.key] * 100) : '', num(a.minDSCR && a.minDSCR[d.key])]);
    });
    var t = b.total_change;
    rows.push(['Total', '', '', num(t.npvM), t.leveredIRR === null ? '' : num(t.leveredIRR * 100), num(t.minDSCR)]);
    return rows;
  }

  function driversFromRange(range) {
    var out = {};
    (range || []).forEach(function (r) {
      if (!r || r[0] === '' || r[0] === null || r[0] === undefined) return;
      var key = String(r[0]).trim(), v = r[1];
      if (typeof v === 'string' && v.trim().charAt(0) === '{') v = JSON.parse(v);
      out[key] = v;
    });
    if (!Object.keys(out).length) throw new Error('Give a two-column range of driver keys and values');
    return out;
  }

  function deliverable(assessment, configuration, kase, field) {
    var body = assessment.body;
    var conf = body.configurations.filter(function (c) { return c.name === configuration; })[0] || (configuration ? null : body.configurations[0]);
    if (!conf) throw new Error('Configuration not found: ' + configuration);
    var c = String(kase || 'base').toLowerCase();
    var map = { upside: 'high', base: 'base', downside: 'low' }, mapMonth = { upside: 'low', base: 'base', downside: 'high' };
    if (!map[c]) throw new Error('Case must be upside, base or downside');
    var f = String(field || 'mw').toLowerCase();
    var v = f === 'month' ? conf.time_to_target_month[mapMonth[c]] : conf.deliverable_mw_at_target[map[c]];
    if (v === null || v === undefined) throw new Error('Target not reached within modeled sources');
    return v;
  }

  function sourceText(pr, key) {
    var p = pr.priorities.filter(function (x) { return x.key === key; })[0];
    if (!p) throw new Error('Unknown input ' + key);
    if (!p.source) return 'Undocumented (saved scenario value)';
    return [p.source.source_name || 'Unnamed source', p.source.source_date, p.verification, p.state].filter(Boolean).join(' · ');
  }

  function client(opts) {
    var cache = {};
    var fetcher = opts.fetch || (typeof fetch !== 'undefined' ? fetch.bind(root) : null);
    function get(path) {
      var url = (opts.baseUrl() || '').replace(/\/$/, '') + '/api' + path;
      var hit = cache[url];
      if (hit && Date.now() - hit.at < CACHE_MS) return hit.p;
      var headers = { Accept: 'application/json' };
      var t = opts.token && opts.token();
      if (t) headers.Authorization = 'Bearer ' + t;
      var p = fetcher(url, { headers: headers }).then(function (r) {
        return r.json().then(function (d) {
          if (!r.ok) { delete cache[url]; throw new Error(typeof d.detail === 'string' ? d.detail : 'PowerPath HTTP ' + r.status); }
          return d;
        });
      });
      cache[url] = { at: Date.now(), p: p };
      p.catch(function () { delete cache[url]; });
      return p;
    }
    function post(path, body) {
      var url = (opts.baseUrl() || '').replace(/\/$/, '') + '/api' + path;
      var headers = { Accept: 'application/json', 'Content-Type': 'application/json' };
      var t = opts.token && opts.token();
      if (t) headers.Authorization = 'Bearer ' + t;
      return fetcher(url, { method: 'POST', headers: headers, body: JSON.stringify(body) }).then(function (r) {
        return r.json().then(function (d) { if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : 'PowerPath HTTP ' + r.status); return d; });
      });
    }
    function uw(project) { return '/projects/' + encodeURIComponent(project) + '/underwriting'; }
    return {
      clear: function () { cache = {}; },
      projects: function () { return get('/projects'); },
      paths: function (project) { return get('/projects/' + encodeURIComponent(project) + '/paths'); },
      approvedCase: function (project) { return get(uw(project) + '/approved-case'); },
      priorities: function (project) { return get(uw(project) + '/priorities'); },
      deliverability: function (project) { return get(uw(project) + '/deliverability'); },
      pathBridge: function (project, pathId) { return get(uw(project) + '/paths/' + encodeURIComponent(pathId) + '/bridge'); },
      bridge: function (project, drivers) { return post(uw(project) + '/bridge', { drivers: drivers }); },
      logout: function () { return post('/v27/auth/logout', {}); }
    };
  }

  // ---- =PP.GET(project, field, [arg1], [arg2]) and =PP.TABLE(project, name, [arg]) -------------
  var GET_FIELDS = {
    npv: { needs: 'case', help: 'Approved-case NPV ($M)' },
    irr: { needs: 'case', help: 'Approved-case levered IRR' },
    dscr: { needs: 'case', help: 'Approved-case minimum DSCR' },
    breach_months: { needs: 'case', help: 'Covenant breach months' },
    exposure: { needs: 'priorities', arg: 'input key', help: 'NPV change ($M) at the input\'s downside' },
    source: { needs: 'priorities', arg: 'input key', help: 'Source · date · verification · review state' },
    confidence: { needs: 'priorities', arg: 'input key', help: 'Confidence label (low / medium / high)' },
    value: { needs: 'priorities', arg: 'input key', help: 'Value used in the approved case' },
    rank: { needs: 'priorities', arg: 'input key', help: 'Diligence rank by NPV at risk' },
    deliverable_mw: { needs: 'deliverability', arg: 'case', arg2: 'configuration', help: 'Firm MW at the target month' },
    time_to_target: { needs: 'deliverability', arg: 'case', arg2: 'configuration', help: 'Project month the MW target is reached' }
  };
  var TABLES = { priorities: 'Diligence ranked by NPV at risk', pathbridge: 'A power path\'s returns change by cause (arg: path name)',
    deliverability: 'Deliverability ranges by configuration', fields: 'Every PP.GET field and table' };

  function priorityItem(pr, key) {
    var p = pr.priorities.filter(function (x) { return x.key === key; })[0];
    if (!p) throw new Error('Unknown input "' + key + '". Use =PP.TABLE(project,"fields") for the list.');
    return p;
  }

  function resolveGet(data, field, arg1, arg2) {
    var f = String(field || '').trim().toLowerCase();
    var spec = GET_FIELDS[f];
    if (!spec) throw new Error('Unknown field "' + field + '". Use =PP.TABLE(project,"fields").');
    if (spec.needs === 'case') return metric(data.case, f);
    if (spec.needs === 'deliverability') return deliverable(data.deliverability, arg2 || '', arg1 || 'base', f === 'time_to_target' ? 'month' : 'mw');
    if (!arg1) throw new Error('Field "' + f + '" needs an input key, e.g. energization_delay_months');
    if (f === 'source') return sourceText(data.priorities, arg1);
    var p = priorityItem(data.priorities, arg1);
    if (f === 'exposure') {
      if (!p.exposure || typeof p.exposure.npv_delta_m !== 'number') throw new Error('No downside quantified for ' + arg1);
      return p.exposure.npv_delta_m;
    }
    if (f === 'confidence') return p.confidence.label;
    if (f === 'rank') return p.rank;
    var v = fmtValue(p.value);
    return typeof v === 'number' ? v : String(v);
  }

  function fieldsTable() {
    var rows = [['Formula', 'Field / table', 'Argument', 'Returns']];
    Object.keys(GET_FIELDS).forEach(function (k) {
      var s = GET_FIELDS[k];
      rows.push(['PP.GET', k, [s.arg, s.arg2].filter(Boolean).join(', '), s.help]);
    });
    Object.keys(TABLES).forEach(function (k) { rows.push(['PP.TABLE', k, k === 'pathbridge' ? 'path name' : '', TABLES[k]]); });
    rows.push(['PP.BRIDGE', '(two-column range)', 'input key, new value', 'What-if: change in NPV, IRR, DSCR by cause']);
    return rows;
  }

  function deliverabilityTable(d) {
    var rows = [['Configuration', 'Firm MW at target: downside', 'Base', 'Upside', 'Target month: upside', 'Base', 'Downside', 'Evidence quality', 'Answer']];
    d.body.configurations.forEach(function (cf) {
      var m = cf.deliverable_mw_at_target, t = cf.time_to_target_month;
      rows.push([cf.name, m.low, m.base, m.high, t.low === null ? '' : t.low, t.base === null ? '' : t.base, t.high === null ? 'not reached' : t.high, cf.evidence_quality.label, cf.answer]);
    });
    return rows;
  }

  var api = { resolveGet: resolveGet, fieldsTable: fieldsTable, deliverabilityTable: deliverabilityTable, GET_FIELDS: GET_FIELDS, TABLES: TABLES,
    metric: metric, prioritiesTable: prioritiesTable, bridgeTable: bridgeTable, driversFromRange: driversFromRange,
    deliverable: deliverable, sourceText: sourceText, client: client, METRICS: METRICS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.PowerPathCore = api;
})(typeof self !== 'undefined' ? self : this);
