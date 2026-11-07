'use strict';
// Tokens remain in memory, are never stored, and are never interpolated into HTML.
let token = null,
  mode = 'required',
  pid = '',
  illustrativeMW = {};
const $ = id => document.getElementById(id);
const setText = (id, value) => {
  $(id).textContent = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
};
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = 'Bearer ' + token;
  if (options.body) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, { ...options, headers, cache: 'no-store' });
  if (!response.ok) {
    let detail = 'HTTP ' + response.status;
    try {
      detail = (await response.json()).detail || detail;
    } catch {}
    throw Error(String(detail));
  }
  return response.json();
}
function cell(tr, val) {
  const td = document.createElement('td');
  td.textContent = val == null ? '—' : typeof val === 'object' ? JSON.stringify(val) : String(val);
  tr.appendChild(td);
}
function tableRows(body, items, fields) {
  body.replaceChildren();
  for (const item of items) {
    const tr = document.createElement('tr');
    for (const field of fields) cell(tr, field(item));
    body.appendChild(tr);
  }
}
function clear() {
  token = null;
  pid = '';
  $('workspace').hidden = true;
  $('review').hidden = true;
  $('authBox').hidden = false;
  $('projectSelect').replaceChildren(new Option('Select a project', ''));
}
async function init() {
  try {
    const r = await api('/api/v27/me');
    mode = r.mode === 'LOCAL_ONLY' ? 'local_only' : 'required';
    if (mode === 'local_only') {
      $('authBox').hidden = true;
      $('logout').hidden = true;
      await loadProjects();
    }
  } catch {
    setText('authStatus', 'Sign in to access transaction data.');
  }
}
async function loadProjects() {
  const list = await api('/api/projects');
  $('projectSelect').replaceChildren(new Option('Select a project', ''));
  for (const p of list) $('projectSelect').add(new Option(p.name, p.id));
  $('workspace').hidden = false;
}
$('login').addEventListener('submit', async e => {
  e.preventDefault();
  setText('authStatus', 'Authenticating…');
  try {
    const r = await api('/api/v27/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email: $('email').value, password: $('password').value })
    });
    token = r.access_token;
    $('password').value = '';
    await loadProjects();
    $('authBox').hidden = true;
  } catch (e) {
    token = null;
    setText('authStatus', e.message);
  }
});
$('logout').addEventListener('click', async () => {
  try {
    if (token) await api('/api/v27/auth/logout', { method: 'POST' });
  } catch {}
  clear();
});
const base = () => '/api/projects/' + encodeURIComponent(pid) + '/transactions/core-scientific-2026';
$('load').addEventListener('click', async () => {
  pid = $('projectSelect').value;
  $('review').hidden = true;
  $('registerBox').hidden = true;
  if (!pid) {
    setText('message', 'Select a project.');
    return;
  }
  try {
    setText('message', 'Loading public-source financing data…');
    const b = base();
    const inputs = await api(b + '/inputs');
    const [terms, scenarios, recon] = await Promise.all([
      api(b + '/terms'),
      api(b + '/scenarios'),
      api(b + '/reconciliation')
    ]);
    const facts = terms.facts || [];
    const dl = $('factSummary');
    dl.replaceChildren();
    for (const f of facts.filter(x =>
      ['principal', 'coupon', 'issue_price', 'maturity_date', 'amortization_rate', 'first_interest_date'].includes(
        x.name
      )
    )) {
      const wrap = document.createElement('div');
      const dt = document.createElement('dt');
      dt.textContent = f.name.replaceAll('_', ' ');
      const dd = document.createElement('dd');
      dd.textContent = String(f.value) + ' ' + (f.units || '');
      wrap.append(dt, dd);
      dl.append(wrap);
    }
    tableRows($('termsRows'), facts, [
      x => x.name,
      x => x.value,
      x => x.classification,
      x => (x.source_document || 'Assumption') + ' · ' + (x.source_locator || 'not specified')
    ]);
    const siteFact = (inputs.inputs || []).find(x => x.name === 'site_leased_mw');
    illustrativeMW = siteFact && siteFact.value && typeof siteFact.value === 'object' ? siteFact.value : {};
    $('phaseSite').replaceChildren();
    for (const [site, mw] of Object.entries(illustrativeMW))
      $('phaseSite').add(new Option(site + ' (' + mw + ' MW, unverified)', site));
    if ($('phaseSite').options.length) {
      $('phaseEarlyMW').value = (Number(illustrativeMW[$('phaseSite').value]) / 2).toFixed(2);
    }
    setText('phaseStatus', 'Site MW is unverified. Preview is a read-only illustration, not a liquidity conclusion.');
    const cases = scenarios.scenarios || [];
    tableRows(
      $('scenarioRows'),
      Array.isArray(cases) ? cases : Object.entries(cases).map(([key, value]) => ({ scenario: key, ...value })),
      [x => x.scenario || x.name, x => x.first_installment_date, x => x.final_maturity_principalM, x => x.balloonM]
    );
    setText('reconciliation', recon);
    $('review').hidden = false;
    setText('message', 'Loaded ' + facts.length + ' public-source facts. G4/G5 remain blocked.');
  } catch (e) {
    if (/Register the v27\.1 model inputs/.test(e.message)) {
      setText('message', 'No financing inputs registered for this project yet.');
      $('registerBox').hidden = false;
    } else setText('message', e.message);
  }
});
$('register').addEventListener('click', async () => {
  if (!pid) return;
  $('register').disabled = true;
  try {
    setText('message', 'Registering public-filing inputs…');
    await api(base() + '/model', { method: 'POST', body: '{}' });
    $('registerBox').hidden = true;
    $('load').click();
  } catch (e) {
    setText('message', e.message);
  } finally {
    $('register').disabled = false;
  }
});
$('loadSchedule').addEventListener('click', async () => {
  try {
    setText('schedule', await api(base() + '/debt-schedule?scenario=' + encodeURIComponent($('scenario').value)));
  } catch (e) {
    setText('schedule', e.message);
  }
});
$('phaseSite').addEventListener('change', () => {
  const mw = Number(illustrativeMW[$('phaseSite').value]);
  if (mw > 0) $('phaseEarlyMW').value = (mw / 2).toFixed(2);
});
$('runPhasing').addEventListener('click', async () => {
  try {
    const site = $('phaseSite').value,
      total = Number(illustrativeMW[site]);
    const earlyMW = Number($('phaseEarlyMW').value),
      early = Number($('phaseEarlyMonth').value),
      full = Number($('phaseFullMonth').value);
    if (
      !site ||
      !Number.isFinite(total) ||
      !Number.isFinite(earlyMW) ||
      earlyMW <= 0 ||
      earlyMW >= total ||
      !Number.isInteger(early) ||
      !Number.isInteger(full) ||
      early < 1 ||
      full < early ||
      full > 240
    )
      throw Error('Enter valid early MW and chronological power months.');
    const payload = {
      scenario: $('phaseScenario').value,
      site_schedules: [
        {
          site,
          tranches: [
            { mw: earlyMW, power_month: early },
            { mw: Math.round((total - earlyMW) * 1e6) / 1e6, power_month: full }
          ]
        }
      ]
    };
    setText('phaseStatus', 'Running read-only illustrative sensitivity...');
    const x = await api(base() + '/illustrative-power-paths', { method: 'POST', body: JSON.stringify(payload) });
    const figures = [
      ['First / full rent month', x.first_rent_month + ' / ' + x.full_rent_month],
      ['Note first installment', x.first_installment_date || 'No installment before maturity'],
      [
        'Peak cumulative funding gap vs static DSRA ($M), headline',
        x.peak_funding_gap_after_static_dsra_ex_balloonM.toFixed(2)
      ],
      ['Peak cumulative funding need before DSRA ($M)', x.peak_cumulative_cash_funding_need_ex_balloonM.toFixed(2)],
      ['Simple zero-rent gap ($M), lower bound only', x.simple_pre_rent_reserve_gapM.toFixed(2)],
      ['Legacy single-date simple gap ($M)', x.legacy_single_date_reference.simple_pre_rent_reserve_gapM.toFixed(2)],
      ['Excluded maturity balloon ($M)', x.balloon_at_maturityM.toFixed(2)]
    ];
    const dl = $('phaseStats');
    dl.replaceChildren();
    for (const [key, value] of figures) {
      const wrapper = document.createElement('div'),
        dt = document.createElement('dt'),
        dd = document.createElement('dd');
      dt.textContent = key;
      dd.textContent = value;
      wrapper.append(dt, dd);
      dl.append(wrapper);
    }
    tableRows($('phaseRows'), x.periods, [
      p => p.date,
      p => p.rent_status,
      p => p.lease_revenueM.toFixed(1),
      p => p.cfadsM.toFixed(1),
      p => p.scheduled_debt_serviceM.toFixed(1),
      p => p.cumulative_cash_before_reservesM.toFixed(1)
    ]);
    setText(
      'phaseStatus',
      'Illustrative only. G4 ' +
        x.g4 +
        ', G5 ' +
        x.g5 +
        '. This is NOT an issuer reserve shortfall or actual investment valuation.'
    );
  } catch (error) {
    setText('phaseStatus', error.message);
  }
});
init();
