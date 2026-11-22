// Plain ES module: the workspace owns selection, authentication and the Leaflet map.
const E = value => String(value ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sourceLink = (url, text = 'Source') => /^https:\/\//.test(url || '')
  ? `<a href="${E(url)}" target="_blank" rel="noopener noreferrer">${E(text)} ↗</a>` : E(text);
const val = p => p?.value == null ? 'Unknown' : `${Number(p.value).toLocaleString(undefined, {maximumFractionDigits: 3})} ${E(p.unit)}`;
const pointHTML = p => `<strong>${val(p)}</strong> <span class="tag gray">${E(p.status)}</span>
  <small>${E(p.category)} · ${E(p.coverage)} · ${E(p.effective_date || 'Period not supplied')}</small>
  <small>${sourceLink(p.source_url, p.source_name)} · retrieved ${E(p.retrieved_at)}</small>
  <small>${E(p.methodology)}</small>`;
const errorHTML = p => p?.status === 'unavailable' ? `<p class="nodata">${E(p.error || 'No usable observations returned')} · unavailable</p>` : '';

export function createSiteEnergy({api, selection, onApplied}) {
  let key = '', data = null, scenarios = [], evidence = [], generation = null, system = null;
  let busy = false, error = '', result = '', requestId = 0, layer = null, currentMap = null;
  const selectedKey = () => `${selection().pid}/${selection().parcel}`;
  const path = () => `/projects/${encodeURIComponent(selection().pid)}/parcels28/${encodeURIComponent(selection().parcel)}/energy`;
  const matches = () => key === selectedKey();
  const field = (label, name, value = '', attrs = '') => `<label>${label}<input name="${name}" value="${E(value)}" ${attrs}></label>`;

  function html() {
    if (!selection().parcel) return '';
    if (!matches() || !data) return `<section class="panel panelpad" id="site-energy"><h2>Site energy data</h2>
      <p>${busy && matches() ? 'Loading available public data… Parcel search remains available.' : E(error || 'Load public energy references for this parcel.')}</p>
      <button id="energy-load" ${busy && matches() ? 'disabled' : ''}>Load site energy data</button></section>`;
    const eia = data.electricity.eia;
    const infra = Object.values(data.grid_infrastructure), solar = data.renewable_resources.solar;
    const refs = eia.points.map((p, i) => ({p, i, mode:'eia_reference'})).filter(x => x.p.value != null);
    const saved = data.utility_study;
    return `<section class="panel panelpad" id="site-energy"><div class="row"><h2>Site energy data</h2><button id="energy-load" ${busy ? 'disabled' : ''}>${busy ? 'Loading…' : 'Reload cached references'}</button></div>
      <p class="muted">${E(data.parcel.state || 'State unknown')} · parcel point ${data.parcel.latitude.toFixed(5)}, ${data.parcel.longitude.toFixed(5)} · source version ${E(data.parcel.source_version)}</p>
      ${error ? `<p class="error" role="alert">${E(error)}</p>` : ''}
      <div class="energy-grid">
      <section><h3>Electricity</h3><p>Delivered utility tariff: <strong>Unknown</strong>. EIA state averages are references.</p>
        ${errorHTML(eia)}${eia.points.slice(0, 2).map(p => `<div class="energy-point">${pointHTML(p)}</div>`).join('')}
        <details><summary>All retrieved price observations</summary>${eia.points.map(p => `<div class="energy-point">${pointHTML(p)}</div>`).join('') || '<p>No observations available.</p>'}</details>
      </section>
      <section><h3>Power infrastructure</h3><p>Mapped lines/stations within 20 km of the parcel footprint. Click an asset on the map to inspect it.</p>
        ${infra.map(p => `${errorHTML(p)}<p>${sourceLink(p.source_url, p.provider)} · ${E(p.status)}</p>${p.features.length ? `<details open><summary>${p.features.length} mapped features</summary><div class="energy-assets">${p.features.map(f => `<button type="button" class="link" data-energy-asset="${E(f.properties.kind + ':' + f.id)}">${E(f.properties.name)} · ${f.properties.distance_km} km · ${E(f.properties.voltage_kv == null ? 'voltage unknown' : f.properties.voltage_kv + ' kV')}</button>`).join('')}</div></details>` : p.status !== 'unavailable' ? '<p>No matching mapped features returned; this is not proof of absence.</p>' : ''}<small>${p.warnings.map(E).join(' ')}</small>`).join('')}
        <p><strong>Available capacity, connection cost and energization date: Unknown.</strong></p>
        ${saved ? `<div class="notice">Study entry: ${E(saved.status)} · ${saved.capacity_mw ?? 'Unknown'} MW · ${saved.connection_cost_usd == null ? 'Cost unknown' : '$' + saved.connection_cost_usd.toLocaleString()} · energization ${E(saved.energization_date || 'unknown')}<br>${E(saved.verification)}<br>Document date ${E(saved.source_date)} · evidence ${E(saved.evidence_id)}<br>${sourceLink(saved.source_url)} · ${E(saved.notes)}</div>` : ''}
      </section>
      <section><h3>Renewable resources</h3>${errorHTML(solar)}${solar.points.filter(p => p.coverage.endsWith('; annual')).map(p => `<div class="energy-point">${pointHTML(p)}</div>`).join('')}
        <form id="energy-solar" class="formgrid">${field('Assumed solar capacity · kW DC', 'capacity_kw', system?.capacity_kw ?? '', 'type="number" min="0.05" max="500000" step="any" required')}
        ${field('Tilt · degrees', 'tilt', system?.tilt ?? 20, 'type="number" min="0" max="90" step="any" required')}
        ${field('Azimuth · degrees', 'azimuth', system?.azimuth ?? 180, 'type="number" min="0" max="359.99" step="any" required')}
        ${field('System losses · %', 'losses_pct', system?.losses_pct ?? 14, 'type="number" min="0" max="99" step="any" required')}
        <button class="span2" type="submit">Estimate solar generation</button></form>
        <p class="nodata">PVWatts: standard modules, fixed open rack, DC/AC 1.2, inverter 96%. Capacity is your assumption, not inferred from parcel acreage. Wind is unavailable.</p>
        ${generation ? errorHTML(generation) + generation.points.map(p => `<div class="energy-point">${pointHTML(p)}</div>`).join('') : ''}
      </section></div>
      <hr><h3>Select scenario inputs</h3><p>Save an explicit cost assumption and run the existing underwriter. Public references never overwrite a scenario automatically.</p>
      <form id="energy-apply" class="formgrid">
      <label>Underwriting scenario<select name="scenario_id" required>${scenarios.map(s => `<option value="${E(s.id)}">${E(s.name)} · v${s.version}</option>`).join('')}</select></label>
      <label>Price basis<select name="basis" id="energy-basis"><option value="assumed">Explicit scenario assumption</option><option value="user_supplied">User-supplied rate (not independently verified)</option>${refs.map(x => `<option value="${x.mode}:${x.i}">${E(x.p.source_name)} · ${E(x.p.coverage)} · ${E(x.p.effective_date)} · $${x.p.value}/MWh</option>`).join('')}</select></label>
      ${field('Scenario price · USD/MWh (assumed / user-supplied)', 'price_mwh', scenarios[0]?.config.powerCostMWh ?? 85, 'type="number" min="0" max="10000" step="any"')}
      <label>Supporting document (optional)<select name="evidence_id"><option value="">No supporting document</option>${evidence.map(e => `<option value="${E(e.id)}">${E(e.title)}</option>`).join('')}</select></label>
      <label>Rationale / remaining charges<textarea name="rationale" minlength="10" maxlength="3000" required placeholder="Explain why this is a useful scenario assumption and which charges remain uncertain."></textarea></label>
      ${generation?.status === 'available' ? `<label class="check span2"><input name="include_solar" type="checkbox"> Retain this solar estimate in scenario inputs</label><label class="check span2"><input name="blend_solar" type="checkbox"> Also apply annual solar/grid cost blend (screening sensitivity)</label>
        ${field('Assumed annual facility load · MWh', 'annual_load_mwh', '', 'type="number" min="0.01" step="any"')}
        ${field('Assumed all-in solar cost · USD/MWh', 'solar_cost_mwh', '', 'type="number" min="0" step="any"')}
        ${field('Assumed self-consumption · %', 'solar_self_use_pct', 100, 'type="number" min="0" max="100" step="any"')}
        <p class="nodata">Annual blend is capped at load and held constant over model months. No hourly matching, firm solar capacity, new solar capex, storage or demand-charge model.</p>` : ''}
      <button class="primary span2" ${!scenarios.length ? 'disabled' : ''}>Save inputs & run underwriting</button></form>
      ${!scenarios.length ? '<p>Create an illustrative working scenario in Economics first.</p>' : ''}
      <p class="nodata">EIA averages remain assumed when applied to this site. The $85/MWh electricity and $7M/MW construction defaults remain illustrative; other saved inputs remain unchanged.</p>
      ${result ? `<div class="notice" id="energy-run-result">${result}</div>` : ''}
      <details><summary>Record utility study / engineering findings</summary><p>User transcription requires a supporting file in this project’s evidence room. PowerPath does not independently certify the findings.</p>
      <form id="energy-study" class="formgrid"><label>Attached evidence<select name="evidence_id" required>${evidence.map(e => `<option value="${E(e.id)}">${E(e.title)}</option>`).join('')}</select></label>
      ${field('Document date', 'source_date', '', 'type="date" required')}${field('Source URL', 'source_url', '', 'type="url" required')}
      ${field('Documented available capacity · MW', 'capacity_mw', '', 'type="number" min="0" step="any"')}
      ${field('Documented connection cost · USD', 'connection_cost_usd', '', 'type="number" min="0" step="any"')}
      ${field('Documented energization date', 'energization_date', '', 'type="date"')}
      <label class="span2">Study scope and qualifications<textarea name="notes" minlength="10" maxlength="3000" required></textarea></label><button ${!evidence.length ? 'disabled' : ''}>Save study entry</button></form>
      <p><a href="/advanced?project=${encodeURIComponent(selection().pid)}&view=evidence">Open evidence room to attach a study ↗</a></p></details></section>`;
  }

  function repaint() {
    const element = document.querySelector('#site-energy');
    if (element && matches()) { element.outerHTML = html(); bind(); }
    draw(currentMap);
  }

  async function load() {
    const nextKey = selectedKey(), id = ++requestId;
    if (key !== nextKey) { data = null; generation = null; system = null; result = ''; }
    key = nextKey; busy = true; error = ''; repaint();
    const {pid} = selection(), base = path();
    try {
      const values = await Promise.all([api(base + '-context'),
        api(`/projects/${encodeURIComponent(pid)}/scenarios`), api(`/projects/${encodeURIComponent(pid)}/evidence`)]);
      if (id !== requestId || !matches()) return;
      [data, scenarios, evidence] = values;
      scenarios = scenarios.filter(s => s.mode === 'underwrite' && !s.config.powerPathLink);
      evidence = evidence.filter(e => e.stored_filename);
    } catch (e) { if (id === requestId && matches()) error = e.message; }
    finally { if (id === requestId && matches()) { busy = false; repaint(); } }
  }

  function bind() {
    const box = document.querySelector('#site-energy');
    if (!box) return;
    box.querySelector('#energy-load')?.addEventListener('click', load);
    box.querySelector('#energy-apply [name=scenario_id]')?.addEventListener('change', event => {
      const sc = scenarios.find(s => s.id === event.target.value);
      box.querySelector('#energy-apply [name=price_mwh]').value = sc?.config.powerCostMWh ?? 85;
    });
    const form = (id, callback) => box.querySelector(id)?.addEventListener('submit', async event => {
      event.preventDefault();
      const button = event.submitter, identity = selectedKey();
      button.disabled = true;
      try {
        await callback(Object.fromEntries(new FormData(event.target)));
        if (identity === selectedKey()) { error = ''; repaint(); }
      } catch (e) {
        if (identity === selectedKey()) {
          error = e.message;
          // Preserve user-entered form values on provider/validation errors.
          let message = box.querySelector('[data-energy-error]');
          if (!message) { message = document.createElement('p'); message.dataset.energyError = '1'; message.className = 'error'; message.setAttribute('role', 'alert'); event.target.prepend(message); }
          message.textContent = error;
        }
      } finally { button.disabled = false; }
    });
    form('#energy-solar', async d => {
      const identity = selectedKey(), nextSystem = Object.fromEntries(Object.entries(d).map(([k,v]) => [k,Number(v)]));
      const response = await api(path() + '/solar-estimate', 'POST', nextSystem);
      if (identity !== selectedKey()) return;
      generation = response; system = nextSystem;
    });
    form('#energy-study', async d => {
      const identity = selectedKey();
      ['capacity_mw','connection_cost_usd'].forEach(k => { d[k] = d[k] === '' ? null : Number(d[k]); });
      d.energization_date ||= null;
      const saved = await api(path() + '/utility-study', 'PUT', d);
      if (identity === selectedKey()) data.utility_study = saved;
    });
    form('#energy-apply', async d => {
      const identity = selectedKey(), {pid} = selection(), base = path();
      const sc = scenarios.find(s => s.id === d.scenario_id), [mode, index] = d.basis.split(':');
      const reference = mode === 'eia_reference' ? data.electricity.eia.points[Number(index)] : null;
      const body = {scenario_id: sc.id, expected_version: sc.version, price_mode: mode,
        price_mwh: d.price_mwh === '' ? null : Number(d.price_mwh), reference_index: Number(index || 0),
        reference_period: reference?.effective_date ?? null, reference_coverage: reference?.coverage ?? null,
        reference_value: reference?.value ?? null,
        evidence_id: d.evidence_id || null, rationale: d.rationale,
        solar: d.include_solar || d.blend_solar ? system : null, blend_solar: !!d.blend_solar,
        annual_load_mwh: d.annual_load_mwh ? Number(d.annual_load_mwh) : null,
        solar_cost_mwh: d.solar_cost_mwh === '' || d.solar_cost_mwh == null ? null : Number(d.solar_cost_mwh),
        solar_self_use_pct: Number(d.solar_self_use_pct ?? 100)};
      const saved = await api(base + '/scenario-inputs', 'POST', body);
      sc.version = saved.version; sc.config = saved.config;
      const run = await api(`/projects/${encodeURIComponent(pid)}/scenarios/${encodeURIComponent(sc.id)}/runs`, 'POST', {});
      if (identity !== selectedKey()) return;
      result = `Saved scenario v${saved.version} and run ${E(run.id)}. Applied electricity cost: $${Number(saved.config.powerCostMWh).toFixed(2)}/MWh · ${E(saved.config.siteEnergyInputs.effective_electricity.status)}. ${run.summary?.npvM != null ? 'Modeled NPV: $' + Number(run.summary.npvM).toFixed(2) + 'M.' : ''} Screening / unverified. Open Economics to compare pathways.`;
      onApplied();
    });
    box.querySelectorAll('[data-energy-asset]').forEach(button => button.onclick = () => {
      layer?.eachLayer(asset => {
        const f = asset.feature;
        if (`${f.properties.kind}:${f.id}` === button.dataset.energyAsset) {
          if (asset.getBounds) currentMap.fitBounds(asset.getBounds(), {maxZoom: 15});
          else if (asset.getLatLng) currentMap.setView(asset.getLatLng(), 15);
          asset.openPopup();
        }
      });
    });
  }

  function draw(map) {
    if (currentMap && layer) { try { currentMap.removeLayer(layer); } catch {} }
    layer = null; currentMap = map;
    if (!map || !matches() || !data || !window.L) return;
    const features = Object.values(data.grid_infrastructure).flatMap(p => p.features);
    layer = L.geoJSON({type:'FeatureCollection', features}, {
      style: f => ({color: f.properties.kind === 'service_territory' ? '#7564a6' : '#b75a16', weight: 3, fillOpacity: 0.06}),
      pointToLayer: (f, point) => L.circleMarker(point, {radius: 6, color:'#b75a16'}),
      onEachFeature: (f, asset) => {
        const p = f.properties;
        asset.bindPopup(`<strong>${E(p.name)}</strong><br>${E(p.kind)} · ${E(p.status)}<br>${p.distance_km} km from parcel · estimated distance<br>${p.voltage_kv == null ? 'Voltage unknown' : E(p.voltage_kv) + ' kV'}<br>Capacity and energization unknown<br>${sourceLink(p.source_url, p.source_name)}<br>Source date ${E(p.effective_date || 'not supplied')}<br>Retrieved ${E(p.retrieved_at)}`);
      }
    }).addTo(map);
  }
  return {html, bind, load, draw};
}
