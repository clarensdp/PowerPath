/* Read-only v30.7.1 polygon overlays. Does not persist site findings or claim clearance. */
(() => {
  'use strict';
  const $f = id => document.getElementById(id);
  const safe = x =>
    String(x ?? '').replace(
      /[&<>"']/g,
      c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]
    );
  let selection = null,
    uploadedBoundary = null,
    layers = [],
    parcelOutline = null,
    intersections = [];
  const fc = features => ({ type: 'FeatureCollection', features });
  async function parseFile(element, limit = 3000000) {
    const f = element.files?.[0];
    if (!f) throw Error('Select a GeoJSON file');
    if (f.size > limit) throw Error('File exceeds size limit');
    return JSON.parse(await f.text());
  }
  function asPolygon(doc) {
    const d = doc?.type === 'Feature' ? doc.geometry : doc;
    if (!d || !['Polygon', 'MultiPolygon'].includes(d.type)) throw Error('Requires a Polygon or MultiPolygon GeoJSON');
    return d;
  }
  function selectedParcel() {
    if (uploadedBoundary) return { geometry: uploadedBoundary, source: 'Uploaded parcel geometry' };
    if (selection) return selection;
    throw Error('First select a cached parcel or upload its boundary geometry. A map point is not a parcel.');
  }
  function drawBoundary(geometry) {
    if (typeof map === 'undefined' || !map) return;
    if (parcelOutline) map.removeLayer(parcelOutline);
    parcelOutline = L.geoJSON(
      { type: 'Feature', properties: {}, geometry },
      { style: { color: '#e28b3c', weight: 3, fillOpacity: 0.08 } }
    ).addTo(map);
    try {
      map.fitBounds(parcelOutline.getBounds(), { padding: [15, 15], maxZoom: 14 });
    } catch (e) {}
  }
  function selected(id) {
    const sel = $f('parcelpick');
    const f = sel.options[sel.selectedIndex];
    return f?.value || null;
  }
  async function searchParcels(live) {
    const lat = Number($f('lat').value),
      lon = Number($f('lon').value);
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || !$f('lat').value || !$f('lon').value)
      throw Error('Select a point first');
    const bbox = [
      Math.max(-180, lon - 0.012),
      Math.max(-90, lat - 0.012),
      Math.min(180, lon + 0.012),
      Math.min(90, lat + 0.012)
    ].join(',');
    const endpoint = live ? '/api/geo30/parcels' : '/api/geo29/parcels';
    $f('parcelinfo').textContent = live
      ? 'Contacting NC/VA public parcel services…'
      : 'Looking up locally cached parcel boundaries…';
    const response = await fetch(`${endpoint}?bbox=${encodeURIComponent(bbox)}&limit=100`);
    const data = await response.json();
    if (!response.ok) throw Error(data.detail || 'Parcel source unavailable');
    const feats = (data.features || []).filter(x => x?.geometry && x?.properties?.workspace_id);
    const select = $f('parcelpick');
    select.replaceChildren(new Option('No parcel selected', ''));
    for (const feature of feats) {
      const p = feature.properties;
      select.add(
        new Option(
          `${p.parcelnumb || p.PA_MCPI || p.workspace_id} · ${p.locality || p.source_id || 'source parcel'}`,
          p.workspace_id
        )
      );
    }
    select._features = feats;
    $f('parcelinfo').textContent =
      `${feats.length} bounded source parcel(s) returned. ${data.status || ''} ${data.messages?.join(' ') || ''} Selection is not a survey or a title review.`;
  }
  function attachParcel() {
    const id = selected();
    const select = $f('parcelpick');
    const f = select._features?.find(x => x.properties.workspace_id === id);
    selection = f ? { id, geometry: f.geometry, source: f.properties.source_id || 'Public/cached GIS' } : null;
    if (selection) {
      uploadedBoundary = null;
      $f('boundaryfile').value = '';
      drawBoundary(selection.geometry);
      $f('parcelinfo').textContent =
        `Selected source parcel ${id} · GIS boundary unverified. Locally cached version will be used.`;
    }
  }
  async function addLayer() {
    const source = $f('layersource').value.trim();
    if (!source) throw Error('Specify the source or publisher before adding a layer');
    const doc = await parseFile($f('layerfile'));
    if (doc.type !== 'FeatureCollection' || !Array.isArray(doc.features))
      throw Error('Overlay must be a GeoJSON FeatureCollection');
    const coverage = $f('coveragefile').files.length ? asPolygon(await parseFile($f('coveragefile'))) : null;
    layers.push({
      kind: $f('layertype').value,
      source: { title: source, url: $f('layerurl').value.trim() },
      features: doc,
      coverage_geometry: coverage
    });
    if (layers.length > 10) {
      layers.pop();
      throw Error('Maximum 10 local overlays');
    }
    renderLayerList();
  }
  function renderLayerList() {
    $f('layerlist').innerHTML = layers.length
      ? layers
          .map(
            (l, i) =>
              `<span class="layerchip">${i + 1}. ${safe(l.kind)} · ${safe(l.source.title)} · ${l.features.features.length} polygon(s) · ${l.coverage_geometry ? 'extent declared' : 'extent unknown'}</span>`
          )
          .join('')
      : 'No local constraint layers loaded.';
  }
  async function assessFootprint() {
    const btn = $f('analyzefootprint');
    btn.disabled = true;
    $f('footresult').textContent = 'Analyzing parcel polygon…';
    try {
      const item = selectedParcel();
      const official = $f('footconsent').checked;
      const body = { layers, official, consent_remote: official };
      if (item.id) body.parcel_id = item.id;
      else {
        body.geometry = item.geometry;
        body.parcel_source = { title: item.source };
      }
      const response = await fetch('/api/permitting/footprint', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const d = await response.json();
      if (!response.ok) throw Error(d.detail || 'Footprint service unavailable');
      for (const old of intersections) map.removeLayer(old);
      intersections = [];
      if (typeof map !== 'undefined' && map) {
        drawBoundary(d.parcel.geometry);
        const shades = {
          flood: '#e07d36',
          wetlands: '#377c9d',
          zoning: '#6862be',
          protected_land: '#488c4f',
          easement: '#9f6d36',
          setback: '#cf5262',
          other: '#ad7c6d'
        };
        for (const l of d.layers) {
          if (l.intersection_geometry) {
            const lay = L.geoJSON(
              { type: 'Feature', geometry: l.intersection_geometry, properties: {} },
              { style: { color: shades[l.kind] || '#888', fillOpacity: 0.38, weight: 1 } }
            ).addTo(map);
            intersections.push(lay);
          }
        }
      }
      const meta = d.parcel;
      let html = `<div class="eyebrow">FULL PARCEL GEOMETRY · ${safe(d.coverage.overall)}</div><h3>${safe(meta.area_acres)} acres analyzed</h3>
  <div class="statrow"><div class="stat"><small>INTERSECTING SUPPLIED CONSTRAINTS</small><strong>${safe(d.summary.intersecting_supplied_constraints_acres)} ac</strong></div>
  <div class="stat"><small>NO MAPPED OVERLAP*</small><strong>${safe(d.summary.no_mapped_overlap_acres)} ac</strong></div></div>
  <p class="warning">* No mapped overlap does not establish buildable acreage. Zoning and data completeness must be verified. No results are saved to a project or fed into financial decisions.</p>`;
      for (const l of d.layers) {
        html += `<article class="entry"><b>${safe(l.kind.toUpperCase())} · ${safe(l.source.title)}</b><span class="tag ${l.intersecting_features ? 'needed' : 'unknown'}">${safe(l.intersection_acres)} ac · ${safe(l.intersection_pct)}%</span>
  <small>${safe(l.intersecting_features)} intersecting polygons / ${safe(l.polygon_count)} provided · <span class="coverageunknown">${safe(l.coverage_status.replaceAll('_', ' '))}</span></small></article>`;
      }
      if (!d.layers.length)
        html +=
          '<p class="coverageunknown">No constraint layers supplied or successfully retrieved. Entire parcel status is UNKNOWN.</p>';
      html +=
        '<h3>Coverage and limitations</h3><ul class="diligence">' +
        d.warnings.map(x => `<li>${safe(x)}</li>`).join('') +
        '</ul>';
      html +=
        '<h3>Next-dollar diligence</h3><ol class="diligence">' +
        d.next_diligence.map(x => `<li>${safe(x)}</li>`).join('') +
        '</ol>';
      html += `<div class="hash">Snapshot SHA-256: ${safe(d.snapshot_sha256)}</div>`;
      $f('footresult').innerHTML = html;
      $f('footstatus').textContent = `${d.layers.length} layer(s) reviewed · ${d.coverage.overall}`;
    } catch (e) {
      $f('footresult').innerHTML =
        `<p class="failure">${safe(e.message)}</p><p class="muted">No missing polygon result was interpreted as clearance.</p>`;
    } finally {
      btn.disabled = false;
    }
  }
  function handle(fn) {
    return (...a) =>
      Promise.resolve()
        .then(() => fn(...a))
        .catch(e => {
          $f('parcelinfo').textContent = 'Parcel workflow: ' + e.message;
        });
  }
  $f('findparcels').addEventListener(
    'click',
    handle(() => searchParcels(false))
  );
  $f('findpublic').addEventListener(
    'click',
    handle(() => searchParcels(true))
  );
  $f('parcelpick').addEventListener('change', attachParcel);
  $f('boundaryfile').addEventListener(
    'change',
    handle(async () => {
      uploadedBoundary = asPolygon(await parseFile($f('boundaryfile')));
      selection = null;
      $f('parcelpick').value = '';
      drawBoundary(uploadedBoundary);
      $f('parcelinfo').textContent = 'Using uploaded boundary (not an official survey).';
    })
  );
  $f('addlayer').addEventListener('click', handle(addLayer));
  $f('clearlayers').addEventListener('click', () => {
    layers = [];
    renderLayerList();
  });
  $f('analyzefootprint').addEventListener('click', assessFootprint);
  fetch('/api/permitting/footprint/status')
    .then(x => x.json())
    .then(d => {
      $f('footstatus').textContent = d.official_polygon_service_enabled
        ? 'Remote polygon sources opt-in available'
        : 'Local layers only · remote GIS disabled by operator';
    })
    .catch(() => {
      $f('footstatus').textContent = 'Local layers only';
    });
})();
