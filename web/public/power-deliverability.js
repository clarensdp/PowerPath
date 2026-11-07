const $ = s => document.querySelector(s);
const esc = v =>
  String(v ?? '').replace(
    /[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
  );
const money = v => (v === null || v === undefined ? '—' : '$' + Number(v).toFixed(2) + 'M');
const percent = v => (v === null || v === undefined ? '—' : (Number(v) * 100).toFixed(2) + '%');
const viab = v =>
  String(v || '') === 'Verified viable'
    ? 'Verified viable (analyst-asserted, not independently checked)'
    : String(v || '');
const num = (v, d = 2) => (v === null || v === undefined ? '—' : Number(v).toFixed(d));
const state = { project: null, run: null, scenarios: [], projects: [] };
async function api(path, method = 'GET', body) {
  const r = await fetch('/api' + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined
  });
  let data;
  try {
    data = await r.json();
  } catch {
    throw Error('Server response could not be parsed');
  }
  if (!r.ok) throw Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data));
  return data;
}
function message(t, error = false) {
  $('#state-note').textContent = t;
  $('#state-note').style.color = error ? '#aa3d39' : '';
}
function mwCheck() {
  const box = $('#mw-help');
  if (!box) return;
  const sc = state.scenarios.find(x => x.id === $('#scenario').value);
  const total = sc ? (sc.config?.buildings || []).reduce((a, b) => a + Number(b.itMW || 0), 0) : null;
  const target = Number(state.project?.target_mw || 0);
  if (sc && target && Math.abs(total - target) > 1e-6) {
    box.hidden = false;
    box.querySelector('span').textContent =
      `The selected scenario models ${num(total, 1)} MW of IT load across its buildings; this project targets ${num(target, 1)} MW. Financial comparison requires them to match exactly, and PowerPath never changes building capacity for you.`;
    box.querySelector('a').href = '/advanced?project=' + encodeURIComponent(state.project.id) + '&view=model';
  } else box.hidden = true;
}
function error(t) {
  $('#results').innerHTML = `<div class="pwr-error" role="alert">${esc(t)}</div>`;
}
function reportState() {
  const r = state.run?.result;
  if (!r) {
    $('#overview').innerHTML =
      '<div class="pwr-note">No feasibility snapshot for this project. Start with an evidence-backed input set; for a 200 MW test project you can use a fictional validation example below.</div>';
    return;
  }
  $('#overview').innerHTML =
    `<div class="pwr-metrics"><div class="pwr-stat"><span class="pwr-label">Screening tier</span><strong>${esc(r.tier)}</strong></div><div class="pwr-stat"><span class="pwr-label">Decision</span><strong class="pwr-strong-sm">${esc(r.decision)}</strong></div><div class="pwr-stat"><span class="pwr-label">Selected power path</span><strong>${esc(r.selected || 'None')}</strong></div><div class="pwr-stat"><span class="pwr-label">First / full power</span><strong>${esc(r.first_power ?? '—')} / ${esc(r.full_load ?? '—')} <small>mo</small></strong></div></div><p class="pwr-muted">Model ${esc(r.model_version)} · Source claims are user supplied, not independently verified. The screening tier and site score are not proof of power availability.</p>`;
}
async function selectProject(id) {
  state.project = state.projects.find(x => x.id === id) || null;
  state.run = null;
  $('#results').innerHTML = '';
  if (!id) {
    reportState();
    return;
  }
  try {
    const [scenarios, run] = await Promise.all([
      api(`/projects/${encodeURIComponent(id)}/scenarios`),
      api(`/projects/${encodeURIComponent(id)}/feasibility?allow_empty=true`)
    ]);
    state.scenarios = scenarios.filter(x => x.mode === 'underwrite' && !x.config?.powerPathLink);
    state.run = run;
    $('#scenario').innerHTML =
      state.scenarios.map(x => `<option value="${esc(x.id)}">${esc(x.name)} · v${esc(x.version)}</option>`).join('') ||
      '<option value="">No original underwriting scenario</option>';
    $('#scenario-help').hidden = state.scenarios.length > 0;
    mwCheck();
    $('#create-scenario').href = '/advanced?project=' + encodeURIComponent(id) + '&view=model&action=new-scenario';
    const is200 = Number(state.project.target_mw) === 200;
    $('#sample-g').disabled = !is200;
    $('#sample-h').disabled = !is200;
    reportState();
    message(
      state.run
        ? 'Feasibility run loaded. Choose an original scenario to compare four paths.'
        : 'No feasibility run yet; you can load a synthetic 200 MW test.'
    );
  } catch (e) {
    message(e.message, true);
  }
}
function renderFinancial(result) {
  if (!result.paths.length) {
    $('#results').innerHTML =
      '<div class="pwr-note">No feasible power path remains in this snapshot. Financial comparison is intentionally unavailable.</div>';
    return;
  }
  const heading = `<div class="pwr-head"><div class="eyebrow">FINANCIAL COMPARISON · READ-ONLY</div><h2>How each power path changes the investment case</h2><p>Values are calculated by the unchanged versioned PowerPath underwriting engine. First-power timing determines supply; physical building readiness and contractual lease timing also control revenue commencement.</p></div>`;
  const row = r => {
    const s = r.summary,
      a = r.assumptions;
    return `<tr><td><strong>${esc(r.name)}</strong><small>${esc(viab(r.viability))}</small><small>${esc(r.decision)}</small></td><td>${num(r.first_power_month, 0)} mo<small>${num(r.first_power_mw, 0)} MW initial</small><small>Full load ${num(r.full_load_month, 0)} mo</small></td><td>${money(a.extra_capex_musd)}<small>Incremental</small></td><td>${money(a.curtailment_annual_compute_value_musd)}<small>Compute value / yr, before allocation</small></td><td>${num(s.first_rent_month, 0)} mo</td><td><strong>${money(s.npv_musd)}</strong></td><td>${percent(s.levered_irr)}</td><td>${num(s.stabilized_min_dscr)}x<small>Min incl. pre-rent ${num(s.minimum_dscr)}x</small></td><td>${money(s.pre_rent_debt_service_musd)}<small>${num(s.months_debt_service_before_rent, 0)} months before rent</small></td><td>${s.defaulted || s.funding_default ? 'Funding/default flag' : s.dscr_breach_months.length ? 'DSCR breach flag' : 'Screening only'}<small>${esc(s.financeability_status || 'Not certified')}</small></td></tr>`;
  };
  const notes = result.paths
    .map(
      r =>
        `<section class="panel panelpad pwr-gap"><div class="row"><strong>${esc(r.name)} · ${esc(viab(r.viability))}</strong><span class="pwr-label">Model assumptions</span></div><p class="pwr-help">${esc(r.assumptions.capex_treatment)}. ${esc(r.assumptions.curtailment_treatment)}.</p><p class="pwr-help">Schedule uses ${esc(r.assumptions.schedule_method)} and retains existing building readiness.</p>${r.warnings.length ? `<div class="pwr-warning-list">${r.warnings.map(w => `<span>• ${esc(w)}</span>`).join('')}</div>` : ''}</section>`
    )
    .join('');
  $('#results').innerHTML =
    `<section class="pwr-result">${heading}<div class="panel pwr-table"><table><thead><tr><th>Path & status</th><th>Energization</th><th>Extra capex</th><th>Curtailment</th><th>First rent</th><th>NPV</th><th>Equity IRR</th><th>Stabilized DSCR</th><th>Pre-rent debt service</th><th>Credit flags</th></tr></thead><tbody>${result.paths.map(row).join('')}</tbody></table></div><div class="pwr-note"><strong>Human review required.</strong> This comparison does not recommend the fastest path as the most profitable. G4 / G5 remain ${esc(result.certification.g4)} / ${esc(result.certification.g5)}. Lease, utility, construction costs, and commissioning dates are not contract verified. ${esc(result.reason_no_economic_recommendation)}.</div>${notes}<p class="pwr-secondary">Feasibility snapshot ${esc(result.feasibility_run_id)} · Financial scenario v${esc(result.source_scenario_version)} · ${esc(result.source_engine)} · No changes saved to financial runs or contracts.</p></section>`;
}
async function compare() {
  if (!state.project || !state.run) {
    return error('Select a project with a saved feasibility assessment.');
  }
  const sid = $('#scenario').value;
  if (!sid)
    return error(
      state.scenarios.length
        ? 'Choose an original underwriting scenario first.'
        : 'This project has no underwriting scenario yet. Create one in the detailed workspace, then return here to compare.'
    );
  $('#compare').disabled = true;
  message('Calculating each eligible power-path scenario in the frozen underwriter…');
  try {
    const result = await api(
      `/projects/${encodeURIComponent(state.project.id)}/feasibility/${encodeURIComponent(state.run.run_id)}/financial-preview`,
      'POST',
      {
        source_scenario_id: sid,
        curtailment_allocation: $('#allocation').value,
        acknowledge_contract_assumption: $('#ack').checked
      }
    );
    renderFinancial(result);
    message(`Compared ${result.paths.length} path(s), read-only. No lender or utility certification.`);
  } catch (e) {
    const m = /must exactly equal feasibility target/.test(e.message)
      ? 'Building IT MW in the scenario does not match the project target. Edit the scenario buildings in Finance & economics, save, and compare again.'
      : e.message;
    error(m);
    message(m, true);
    mwCheck();
  } finally {
    $('#compare').disabled = false;
  }
}
async function sample(which) {
  if (!state.project) return;
  const data = await (await fetch('/assets/v82_samples.json')).json();
  const key = 'Site ' + which;
  const payload = {
    site_name: 'SYNTHETIC ' + key,
    mode: 'default',
    inputs: data[key],
    evidence: [{ note: 'FICTIONAL VALIDATION FIXTURE. NOT AN ENGINEERING, UTILITY, LAND OR CONTRACT ASSESSMENT.' }]
  };
  try {
    const r = await api(`/projects/${encodeURIComponent(state.project.id)}/feasibility`, 'POST', payload);
    state.run = r;
    reportState();
    $('#results').innerHTML = '';
    message(
      `${key} synthetic sample stored as a new immutable test snapshot; choose a 200 MW underwriting scenario and compare.`
    );
  } catch (e) {
    error(e.message);
    message(e.message, true);
  }
}
async function boot() {
  try {
    state.projects = await api('/projects');
    $('#project').innerHTML =
      state.projects
        .map(p => `<option value="${esc(p.id)}">${esc(p.name)} · ${esc(p.target_mw)} MW</option>`)
        .join('') || '<option value="">Create a project in the project workspace</option>';
    const desired = new URLSearchParams(location.search).get('project');
    const chosen = state.projects.find(x => x.id === desired) || state.projects[0];
    if (chosen) {
      $('#project').value = chosen.id;
      await selectProject(chosen.id);
    } else {
      message('Create a project in the project workspace first.');
      reportState();
    }
  } catch (e) {
    message(e.message, true);
    error(e.message);
  }
}
$('#project').onchange = e => selectProject(e.target.value);
$('#scenario').onchange = mwCheck;
$('#compare').onclick = compare;
$('#sample-g').onclick = () => sample('G');
$('#sample-h').onclick = () => sample('H');
boot();
