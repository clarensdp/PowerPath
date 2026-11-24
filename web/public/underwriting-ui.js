// v31.5 underwriting screens: returns bridge (step 4) and exposure-ranked diligence (step 5).
// Uses only /api/projects/{pid}/underwriting/* routes. Rendering escapes all API text.

const E = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
const money = v => (v === null || v === undefined || !isFinite(v) ? '—' : `${v < 0 ? '−' : ''}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 1, minimumFractionDigits: 1 })}M`);
const pts = v => (v === null || v === undefined || !isFinite(v) ? '—' : `${v < 0 ? '−' : '+'}${Math.abs(v * 100).toFixed(1)} pts`);
const pct = v => (v === null || v === undefined || !isFinite(v) ? '—' : `${(v * 100).toFixed(1)}%`);
const x = v => (v === null || v === undefined || !isFinite(v) ? '—' : `${v.toFixed(2)}x`);
const tag = (t, k = 'gray') => `<span class="tag ${k}">${E(t)}</span>`;
const MATERIALITY = { critical: 'red', high: 'amber', moderate: 'gray', low: 'gray', not_quantified: 'gray' };
const VERIFICATION = ['assumed', 'estimated', 'user_supplied', 'studied', 'contracted', 'observed', 'verified'];
const SOURCE_KINDS = ['utility_study', 'utility_confirmation', 'contract', 'quote', 'public_data', 'third_party_forecast', 'analyst_estimate', 'assumption', 'other'];
const SCALAR_KEYS = ['power_cost_mwh', 'construction_cost_mw', 'rent_per_kw_month', 'pue', 'interest_rate_pct', 'power_capex_m', 'energization_delay_months', 'lease_start_delay_months'];

function display(value, unit) {
  if (value && typeof value === 'object' && Array.isArray(value.phases))
    return value.phases.map(p => `${Number(p.mw).toLocaleString()} MW from M${p.month}`).join(', ') + ` (${E(value.basis || 'gross')})`;
  if (value === null || value === undefined) return '—';
  return `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 })} ${E(unit || '')}`;
}

function bars(attribution, drivers, fmt) {
  if (!attribution) return '<p class="muted">Not attributable for this metric (undefined in at least one combination).</p>';
  const max = Math.max(1e-9, ...Object.values(attribution).map(Math.abs));
  return `<div class="uwbars">${drivers
    .map(d => {
      const v = attribution[d.key] ?? 0, w = Math.max(1, (Math.abs(v) / max) * 50);
      return `<div class="uwbar"><span class="uwlabel">${E(d.label)}</span><span class="uwtrack"><i class="${v < 0 ? 'neg' : 'pos'}" data-uw-w="${w}" data-uw-side="${v < 0 ? 'right' : 'left'}"></i></span><span class="uwval">${fmt(v)}</span></div>`;
    })
    .join('')}</div>`;
}

const negligible = (r, k) => Math.abs(r.attribution.npvM?.[k] ?? 0) < 0.05 && Math.abs(r.attribution.leveredIRR?.[k] ?? 0) < 0.0005;
const moving = r => r.drivers.filter(d => !negligible(r, d.key));
const still = r => r.drivers.filter(d => negligible(r, d.key));

export function createUnderwritingUI({ api, toast, pid, dialog }) {
  const base = () => '/projects/' + encodeURIComponent(pid()) + '/underwriting';

  // ------------------------------------------------------------------ returns bridge
  async function loadBridges(box, paths, scenarioId) {
    if (!box) return;
    if (!paths.length) { box.innerHTML = ''; return; }
    box.innerHTML = '<section class="panel empty"><p class="loading">Splitting each pathway\'s change in returns by cause…</p></section>';
    const q = '?include_approved=false' + (scenarioId ? '&scenario_id=' + encodeURIComponent(scenarioId) : '');
    const results = await Promise.all(paths.map(async path => {
      try { return { path, r: await api(base() + '/paths/' + encodeURIComponent(path.id) + '/bridge' + q) }; }
      catch (e) { return { path, error: e.message }; }
    }));
    if (!box.isConnected) return;
    const pending = Object.keys(results.find(r => r.r)?.r.approved_not_applied || {});
    box.innerHTML = `<section class="panel panelpad"><div class="row"><div><h3>Why returns change: attribution by cause</h3><p class="muted">Each pathway's final figures match the table above. The change is measured from the base scenario before any pathway adjustment, and split by cause so the parts add up to the total in any order (Shapley attribution).</p></div></div>${pending.length ? `<div class="notice">${pending.length} approved assumption${pending.length > 1 ? 's are' : ' is'} not yet in this comparison (${E(pending.join(', ').replace(/_/g, ' '))}). Diligence shows the approved case.</div>` : ''}<div class="uwgrid">${results
      .map(({ path, r, error }) => {
        if (error) return `<article class="uwcard"><h4>${E(path.name)}</h4><p class="muted">${E(error)}</p></article>`;
        const t = r.total_change;
        return `<article class="uwcard"><div class="row"><h4>${E(path.name)}</h4>${tag(path.strategy)}</div>
          <div class="uwtotals"><div><small>NPV</small><strong>${money(t.npvM)}</strong></div><div><small>Levered IRR</small><strong>${pts(t.leveredIRR)}</strong></div><div><small>Min DSCR</small><strong>${t.minDSCR === null ? '—' : (t.minDSCR < 0 ? '−' : '+') + Math.abs(t.minDSCR).toFixed(2) + 'x'}</strong></div></div>
          <p class="muted">NPV ${money(r.base.npvM)} before pathway adjustments → ${money(r.final.npvM)}</p>
          <h5>NPV by cause</h5>${bars(r.attribution.npvM, moving(r), money)}
          <h5>IRR by cause</h5>${bars(r.attribution.leveredIRR, moving(r), pts)}
          ${still(r).length ? `<p class="muted">No effect: ${E(still(r).map(d => d.label.toLowerCase()).join(', '))}${still(r).some(d => d.key === 'power_cost_mwh') ? ' (power cost is passed through to the tenant in this scenario)' : ''}.</p>` : ''}
          <ul class="uwexplain">${r.explanation.map(l => `<li>${E(l)}</li>`).join('')}</ul>
          <details><summary>Inputs and reconciliation</summary><table><thead><tr><th>Cause</th><th>From</th><th>To</th></tr></thead><tbody>${r.drivers.map(d => `<tr><td>${E(d.label)}</td><td>${display(d.from, d.unit)}</td><td>${display(d.value, d.unit)}</td></tr>`).join('')}</tbody></table><p class="muted">Base NPV ${money(r.base.npvM)} → ${money(r.final.npvM)}. Residual ${money(r.reconciliation_residual.npvM)} · ${r.engine_runs} engine runs.</p></details></article>`;
      })
      .join('')}</div></section>`;
    // CSP forbids inline style attributes; size bars through the CSSOM.
    box.querySelectorAll('[data-uw-w]').forEach(el => { el.style[el.dataset.uwSide] = '50%'; el.style.width = el.dataset.uwW + '%'; });
  }

  // ---------------------------------------------------------------- diligence
  async function loadDiligence(box) {
    if (!box) return;
    box.innerHTML = '<section class="panel empty"><p class="loading">Ranking diligence by financial exposure…</p></section>';
    let pr, changes, deliver = null;
    try {
      [pr, changes] = await Promise.all([api(base() + '/priorities'), api(base() + '/changes?pending=true')]);
      try { deliver = await api(base() + '/deliverability'); } catch { deliver = null; }
    } catch (e) {
      box.innerHTML = `<section class="panel empty"><h2>Diligence ranking unavailable</h2><p class="error">${E(e.message)}</p><p class="muted">It needs an underwriting scenario. Create one in Economics.</p></section>`;
      return;
    }
    if (!box.isConnected) return;
    const b = pr.base_result;
    box.innerHTML = `
      ${changes.length ? `<section class="panel panelpad uwreview"><h3>Waiting for review <small>${changes.length}</small></h3>${changes.map(changeCard).join('')}</section>` : ''}
      <section class="panel"><div class="panelhead"><h3>What to diligence next, ranked by NPV at risk</h3><small>Approved case NPV ${money(b.npvM)} · IRR ${pct(b.leveredIRR)} · min DSCR ${x(b.minDSCR)}</small></div>
      <div class="tablewrap"><table class="uwtable"><thead><tr><th>#</th><th>Input</th><th>Current value and source</th><th>Confidence</th><th>NPV at risk</th><th>Next action</th><th></th></tr></thead><tbody>
      ${pr.priorities.map(p => {
        const e = p.exposure || {};
        return `<tr><td data-label="#">${p.rank}</td><td data-label="Input"><strong>${E(p.label)}</strong>${tag(p.materiality.replace('_', ' '), MATERIALITY[p.materiality])}${p.state === 'proposed' ? tag('proposed, not approved', 'amber') : ''}</td>
        <td data-label="Value and source">${display(p.value, p.unit)}<small>${p.source ? E([p.source.source_name, p.source.source_date].filter(Boolean).join(' · ') || 'No source named') : 'Undocumented: saved scenario value'}</small></td>
        <td data-label="Confidence">${E(p.confidence.label)} <small>${E(p.confidence.basis)}</small></td>
        <td data-label="NPV at risk">${p.downside_value === null || p.downside_value === undefined ? '<small>No downside set. Add one when documenting.</small>' : e.error ? `<small class="error">${E(e.error)}</small>` : `<strong>${money(e.npv_delta_m)}</strong><small>at ${display(p.downside_value, p.unit)} · ${E(p.downside_basis || '')}</small>${e.covenant_breach_months?.length ? `<small class="warn">${e.covenant_breach_months.length} covenant breach months at downside</small>` : ''}`}</td>
        <td data-label="Next action">${E(p.next_action)}</td>
        <td>${SCALAR_KEYS.includes(p.key) ? `<button data-uw-document="${E(p.key)}">${p.documented ? 'Update' : 'Document'}</button>` : '<small>Set from a utility study or deliverability assessment</small>'}</td></tr>`;
      }).join('')}</tbody></table></div>
      <p class="muted sourcefoot">${E(pr.method)} ${E(pr.stress_note)}</p></section>
      ${deliver ? deliverCard(deliver) : ''}`;
    box.querySelectorAll('[data-uw-document]').forEach(btn => (btn.onclick = () => documentForm(btn.dataset.uwDocument, pr, box)));
    box.querySelectorAll('[data-uw-decide]').forEach(btn => (btn.onclick = () => decide(btn.dataset.uwChange, btn.dataset.uwDecide, box)));
  }

  function changeCard(c) {
    const b = c.body, im = b.impact || {};
    const actions = b.requires === 'analysis'
      ? `<button data-uw-change="${E(c.id)}" data-uw-decide="acknowledge">Record analysis</button>`
      : `<button class="primary" data-uw-change="${E(c.id)}" data-uw-decide="accept">Accept</button><button data-uw-change="${E(c.id)}" data-uw-decide="reject">Reject</button>`;
    return `<article class="uwchange"><div class="row"><div><strong>${E(b.title)}</strong> ${tag(b.requires === 'analysis' ? 'analysis only' : 'needs approver', b.requires === 'analysis' ? 'gray' : 'amber')}</div><div class="actions">${actions}</div></div>
      ${b.requires === 'analysis' ? `<p>${E(b.detail)}</p>` : `<p>${b.previous ? `${display(b.previous.value)} → ` : ''}<strong>${display(b.proposed.value, b.proposed.unit)}</strong> · ${E(b.proposed.source_name || 'no source named')} ${b.proposed.source_date ? '· ' + E(b.proposed.source_date) : ''} · ${E(b.proposed.verification)}</p>${im.note ? `<p class="muted">${E(im.note)}</p>` : im.explanation ? `<ul class="uwexplain">${im.explanation.map(l => `<li>${E(l)}</li>`).join('')}</ul>` : im.error ? `<p class="error">${E(im.error)}</p>` : ''}<p class="muted">${E(b.recommendation)}</p>`}</article>`;
  }

  function deliverCard(d) {
    const body = d.body;
    return `<section class="panel panelpad"><h3>Deliverability: ${E(body.target_mw)} MW by month ${E(body.target_month)}</h3><p class="muted">Assessment v${d.version} · ${E(new Date(d.created_at).toLocaleString())} · ranges are scenario bounds, not probabilities</p>${body.configurations.map(c => `<div class="factor"><strong>${E(c.name)}</strong> ${tag('evidence ' + c.evidence_quality.label, c.evidence_quality.label === 'high' ? '' : 'amber')}<p>${E(c.answer)}</p><details><summary>What must be true</summary><ul>${c.what_must_be_true.map(w => `<li>${E(w)}</li>`).join('')}</ul></details></div>`).join('')}</section>`;
  }

  function documentForm(key, pr, box) {
    const item = pr.priorities.find(p => p.key === key);
    const opt = (list, sel) => list.map(v => `<option value="${v}" ${v === sel ? 'selected' : ''}>${v.replace(/_/g, ' ')}</option>`).join('');
    dialog(`Document: ${E(item.label)}`,
      `<label>Value (${E(item.unit)})<input name="value" type="number" step="any" required value="${typeof item.value === 'number' ? item.value : ''}"></label>
       <label>Downside value<input name="downside_value" type="number" step="any" value="${typeof item.downside_value === 'number' ? item.downside_value : ''}"></label>
       <label>Source type<select name="source_kind">${opt(SOURCE_KINDS, 'quote')}</select></label>
       <label>Verification<select name="verification">${opt(VERIFICATION, 'estimated')}</select></label>
       <label class="span2">Source name<input name="source_name" maxlength="300" placeholder="e.g. EPC budgetary quote, utility facilities study"></label>
       <label>Source date<input name="source_date" type="date"></label>
       <label>Source link<input name="source_url" type="url" placeholder="https://"></label>
       <label class="span2">Rationale<textarea name="rationale" required minlength="10" maxlength="3000"></textarea></label>
       <p class="span2 muted">This creates a proposal. It enters the approved case only after an approver accepts it.</p>`,
      async data => {
        const body = { key, value: Number(data.value), source_kind: data.source_kind, verification: data.verification, rationale: data.rationale };
        if (data.downside_value !== '') body.downside_value = Number(data.downside_value);
        for (const k of ['source_name', 'source_date', 'source_url']) if (data[k]) body[k] = data[k];
        await api(base() + '/assumptions', 'POST', body);
        toast('Proposed. It appears under "Waiting for review".');
        loadDiligence(box);
      });
  }

  function decide(changeId, verdict, box) {
    const analysis = verdict === 'acknowledge';
    dialog(analysis ? 'Record the analysis' : verdict === 'accept' ? 'Accept into the approved case' : 'Reject this change',
      `<label class="span2">${analysis ? 'Conclusion (required)' : 'Note for the record'}<textarea name="note" ${analysis ? 'required minlength="10"' : ''} maxlength="3000"></textarea></label>
       <p class="span2 muted">${analysis ? 'Queue events never change the approved case. A withdrawal is not credited as capacity.' : 'Approver role required. The decision and the approved case before and after are recorded permanently.'}</p>`,
      async data => {
        await api(base() + '/approvals/' + encodeURIComponent(changeId) + '/' + verdict, 'POST', { note: data.note || '' });
        toast(analysis ? 'Analysis recorded' : verdict === 'accept' ? 'Accepted into the approved case' : 'Rejected');
        loadDiligence(box);
      });
  }

  // ---------------------------------------------------------------- market data
  const mbase = () => '/projects/' + encodeURIComponent(pid()) + '/market';
  const fmtMarket = i => i.value === null || i.value === undefined ? '—'
    : i.unit === 'share' ? `${(i.value * 100).toFixed(1)}%`
    : `${Number(i.value).toLocaleString(undefined, { maximumFractionDigits: i.unit === 'USD/MMBtu' || i.unit === 't CO2/MWh' ? 3 : 1 })} ${E(i.unit)}`;

  async function loadMarket(box) {
    if (!box) return;
    box.innerHTML = '<section class="panel empty"><p class="loading">Pulling the latest power market data…</p></section>';
    let snap, cat;
    try { [snap, cat] = await Promise.all([api(mbase() + '/snapshot?days=30'), api(mbase() + '/catalog')]); }
    catch (e) { box.innerHTML = `<section class="panel empty"><h3>Market data unavailable</h3><p class="error">${E(e.message)}</p></section>`; return; }
    if (!box.isConnected) return;
    const p = snap.profile;
    const where = [p.nyiso_zone && 'NYISO ' + p.nyiso_zone, p.ba && 'BA ' + p.ba, p.state].filter(Boolean).join(' · ') || 'No market profile yet';
    box.innerHTML = `<section class="panel panelpad"><div class="row"><div><h3>Power market context</h3><p class="muted">${E(where)} · last 30 days · every figure shows its source and date</p></div>
      <div class="actions"><button data-mk-profile>Market profile</button><button class="primary" data-mk-propose>Use as power cost…</button></div></div>
      ${snap.items.length ? `<div class="mkgrid">${snap.items.map(i => `<div class="mkitem${i.stale ? ' stale' : ''}"><small>${E(i.label)}</small><strong>${fmtMarket(i)}</strong><span>${E(i.location)} · as of ${E(i.as_of)}${i.stale ? ' · stale' : ''}</span><details><summary>Source</summary><p>${E(i.source)}</p><p>${E(i.method)}</p><p>Retrieved ${E(i.retrieved_at ? new Date(i.retrieved_at).toLocaleString() : '—')}</p></details></div>`).join('')}</div>` : ''}
      ${snap.gaps.length ? `<ul class="mkgaps">${snap.gaps.map(g => `<li><strong>${E(g.metric.replace(/_/g, ' '))}:</strong> ${E(g.reason)}</li>`).join('')}</ul>` : ''}
      ${cat.imported.length ? `<p class="muted">Licensed series in this project: ${cat.imported.map(x => E(x.metric.replace('imported:', '') + ' (' + x.location + ', to ' + x.latest + ')')).join(', ')}</p>` : ''}
      <p class="muted sourcefoot">${snap.notes.map(E).join(' ')}</p></section>`;
    box.querySelector('[data-mk-profile]').onclick = () => profileForm(p, cat, box);
    box.querySelector('[data-mk-propose]').onclick = () => proposeForm(cat, box);
  }

  function profileForm(p, cat, box) {
    dialog('Market profile',
      `<label>NYISO zone<select name="nyiso_zone"><option value="">None</option>${cat.nyiso_zones.map(z => `<option ${z === p.nyiso_zone ? 'selected' : ''}>${E(z)}</option>`).join('')}</select></label>
       <label>Balancing authority (EIA code)<input name="ba" value="${E(p.ba || '')}" placeholder="e.g. NYIS, PJM, ERCO, MISO" pattern="[A-Z0-9-]{2,10}"></label>
       <label>State<input name="state" value="${E(p.state || '')}" placeholder="e.g. NY" pattern="[A-Z]{2}"></label>
       <label>Heat rate for spark spread (MMBtu/MWh)<input name="heat_rate" type="number" step="0.1" min="5" max="15" value="${p.heat_rate}"></label>
       <p class="span2 muted">Live ISO prices are NYISO for now (public, no key). EIA data needs ${cat.eia_key_configured ? 'a key: configured ✓' : 'POWERPATH_EIA_API_KEY on the server'}. Other ISOs and forward curves come in as licensed imports.</p>`,
      async d => {
        await api(mbase() + '/profile', 'PUT', { nyiso_zone: d.nyiso_zone || null, ba: d.ba ? d.ba.toUpperCase() : null, state: d.state ? d.state.toUpperCase() : null, heat_rate: Number(d.heat_rate) });
        toast('Market profile saved'); loadMarket(box);
      });
  }

  function proposeForm(cat, box) {
    const metrics = [['lmp_da', 'Day-ahead LMP (wholesale energy)'], ['retail_industrial', 'State industrial retail price'], ['retail_commercial', 'State commercial retail price']]
      .concat(cat.imported.map(x => [x.metric, x.metric.replace('imported:', '') + ' (licensed)']));
    dialog('Propose a power cost from market data',
      `<label>Series<select name="metric">${metrics.map(([k, l]) => `<option value="${E(k)}">${E(l)}</option>`).join('')}</select></label>
       <label>Average over (days, or months for retail and imports)<input name="window" type="number" min="1" max="730" value="30"></label>
       <label>Delivery adder (USD/MWh)<input name="adder_mwh" type="number" step="0.5" min="0" value="0"></label>
       <label>Downside (+%)<input name="downside_pct" type="number" min="0" max="300" value="25"></label>
       <label class="span2">Note<textarea name="rationale" maxlength="2000" placeholder="Why this series and adder fit the site"></textarea></label>
       <p class="span2 muted">Wholesale LMP is an energy price only. Add transmission, capacity and utility charges as the adder. This creates a proposal that waits for an approver in Diligence.</p>`,
      async d => {
        const stat = d.metric === 'lmp_da' ? 'avg' : 'value';
        const r = await api(mbase() + '/propose-power-cost', 'POST', { metric: d.metric, stat, window: Number(d.window), adder_mwh: Number(d.adder_mwh), downside_pct: Number(d.downside_pct), rationale: d.rationale || '' });
        toast(`Proposed $${r.assumption.body.value.toFixed(2)}/MWh. Review it in Diligence.`);
        loadMarket(box);
      });
  }

  return { loadBridges, loadDiligence, loadMarket };
}
