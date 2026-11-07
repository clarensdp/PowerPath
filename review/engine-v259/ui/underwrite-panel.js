/* PowerPath underwriting panel (browser UI). Consumes the engine; contains no financial logic. */
(function (root) {
  'use strict';
  const { defaults, evaluate } = root.PowerPathEngine;
  const escapeHtml = (s) =>
    String(s ?? '').replace(
      /[&<>"']/g,
      (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
    );
  function render(node, project) {
    const key = 'powerpath-v251-' + project.id;
    let state;
    try {
      state = JSON.parse(localStorage.getItem(key) || 'null');
    } catch {}
    state = state || defaults();
    let last = null;
    const numeric = [
      ['calendarStartYear', 'Calendar year of model M1'],
      ['calendarStartMonth', 'Calendar month of model M1 (1–12)'],
      ['rentPerKwMonth', 'Rent ($/kW-mo)'],
      ['constructionCostMW', 'Construction ($M/IT MW)'],
      ['ltc', 'Construction LTC (%)'],
      ['rate', 'Construction rate (%)'],
      ['termMonths', 'Construction maturity (months)'],
      ['refinanceLtvPct', 'Refinance LTV (%)'],
      ['refinanceValueM', 'Refinance value ($M)'],
      ['refinanceRatePct', 'Refinance rate (%)'],
      ['exitValueM', 'Exit value ($M)'],
      ['initialCash', 'Opening sponsor cash ($M)'],
      ['minLiquidity', 'Minimum liquidity ($M)'],
      ['reserveTargetM', 'Restricted reserve ($M)'],
      ['delayMonths', 'Power delay (months)'],
      ['overrunPct', 'Capex overrun (%)'],
      ['dscrCovenant', 'DSCR covenant'],
      ['powerCostMWh', 'Power ($/MWh)'],
      ['tenantCapexPct', 'Tenant-funded capex (%)'],
      ['tenantFundingLagMonths', 'Tenant reimbursement delay (months)'],
      ['tenantRentCreditPct', 'Tenant rent credits (%)'],
      ['tenantCreditMonths', 'Credit duration (months)'],
      ['debtYieldMinPct', 'Refinance minimum debt yield (%)'],
      ['refinanceDscrMin', 'Refinance minimum DSCR'],
      ['refinanceAmortMonths', 'Refinance amortization (months)'],
      ['cashSweepPct', 'Optional senior cash sweep (%)'],
      ['dsraMonths', 'DSRA months of term-loan debt service'],
      ['cashTaxRatePct', 'Cash tax proxy (%)'],
      ['maintenanceCapexMWYearM', 'Maintenance capex ($M/IT MW/yr)'],
      ['workingCapitalDays', 'Working capital days'],
      ['distributionDscrMin', 'Distribution DSCR threshold'],
      ['mezzLtcPct', 'Mezzanine LTC (%)'],
      ['mezzRatePct', 'Mezzanine rate (%)'],
      ['pue', 'PUE (gross-to-IT conversion)'],
      ['powerPassThroughPct', 'Power pass-through / direct payment share (%)'],
      ['leaseTailBufferMonths', 'Lease-tail buffer (months)'],
      ['minRefinanceAmortMonths', 'Minimum refinance amortization (months)'],
      ['renewalProbabilityPct', 'Renewal probability (%)'],
      ['renewalRentPct', 'Renewal rent (% of final rent)'],
      ['renewalTermMonths', 'Renewal term (months)'],
      ['vacantValuePct', 'Vacant MW exit value (% of exit value)'],
      ['exitTenantReceivableRecoveryPct', 'Exit tenant receivable collection (%)'],
      ['exitWorkingCapitalRecoveryPct', 'Exit working capital collection (%)'],
    ];
    const policySelects = [
      [
        'refinanceTenorPolicy',
        'Refinance tenor',
        [
          ['fixed', 'Fixed amortization'],
          ['leaseTail', 'Within remaining lease term'],
        ],
      ],
      [
        'leaseExpiryPolicy',
        'At lease expiry',
        [
          ['vacate', 'Vacate (no rent)'],
          ['renew', 'Probability-weighted renewal'],
        ],
      ],
      [
        'exitValuePolicy',
        'Exit value',
        [
          ['fixed', 'Fixed exit value'],
          ['contracted', 'Leased MW full, vacant MW discounted'],
        ],
      ],
    ];
    node.innerHTML = `<h3>Staged campus and levered financing · v25.8.4</h3><p class="v21-muted">Monthly sources-and-uses reconciliation, separately funded sponsor equity and reserves, explicit construction maturity, refinance or equity payoff, exit proceeds, and power-tranche capacity. $M unless indicated. Screening assumptions, not lender commitments.</p><div class="v21-grid">${numeric.map(([k, label]) => `<label>${label}<input data-v25="${k}" type="number" step="any" value="${escapeHtml(state[k] ?? defaults()[k])}"></label>`).join('')}<label>Maturity outcome<select id="v251Mode"><option value="refinance">Refinance</option><option value="equity">Sponsor-funded payoff</option><option value="default">Unfunded / flag default</option></select></label>${policySelects.map(([k, label, opts]) => `<label>${label}<select data-v25s="${k}">${opts.map(([v, t]) => `<option value="${v}" ${(state[k] ?? defaults()[k]) === v ? 'selected' : ''}>${t}</option>`).join('')}</select></label>`).join('')}</div><label><input type="checkbox" id="v2583AllRateShock" ${state.rateShockAllFacilities ? 'checked' : ''}> Apply interest-rate shocks to mezzanine and refinance facilities</label><p class="v21-muted">Exit collections default to 0% to prevent double-counting sale proceeds. Only activate if the purchase-price and receivable treatment are documented.</p><label>Power cost responsibility (project default)<select id="v2584PowerMode"><option value="landlord">Landlord bears electricity expense</option><option value="tenant_direct">Tenant pays utility directly (no landlord gross-up)</option><option value="reimbursed">Landlord pays; tenant reimburses at cost (gross-up)</option></select></label><p class="v21-muted">Power pass-through is separate from base contractual rent. A 100% reimbursement produces equal additional revenue and expense (no energy EBITDA hit); the 100% direct-payment mode excludes that expense and billing from the landlord P&amp;L. Verify each agreement's treatment.</p><label>Sponsor commitment ($M, total incl. opening cash; blank = not verified/unlimited for sensitivity only)<input id="v257Sponsor" type="number" min="0" step="any" placeholder="Not verified" value="${escapeHtml(state.sponsorCommitmentM ?? '')}"></label><label>Capacity entered as <select id="v252Capacity"><option value="IT">Critical IT MW</option><option value="gross">Gross facility MW</option></select></label><h3>Building-level schedule</h3><div class="table-wrap"><table><thead><tr><th>Building</th><th>IT MW</th><th>Construction start</th><th>Build months</th><th>Power month</th><th>Lease month</th><th>Lease term (months)</th><th>Rent escalator %</th><th>Rent method</th><th>Contracted total ($M)</th><th>Annual schedule ($M/yr CSV)</th><th>Source reference</th><th>Power payer</th><th>Pass-through %</th></tr></thead><tbody>${state.buildings
      .map(
        (b, i) =>
          `<tr data-b="${i}">${[
            ['name', 'text'],
            ['itMW', 'number'],
            ['constructionStart', 'number'],
            ['constructionMonths', 'number'],
            ['powerMonth', 'number'],
            ['leaseMonth', 'number'],
            ['leaseTermMonths', 'number'],
            ['rentEscalatorPct', 'number'],
          ]
            .map(
              ([k, t]) =>
                `<td><input data-f="${k}" type="${t}" style="min-width:75px;width:95px" value="${escapeHtml(b[k] ?? (k === 'leaseTermMonths' ? 180 : k === 'rentEscalatorPct' ? 2.5 : ''))}"></td>`,
            )
            .join(
              '',
            )}<td><select data-f="rentInputMode"><option value="starting" ${!b.rentInputMode || b.rentInputMode === 'starting' ? 'selected' : ''}>Starting rent</option><option value="total" ${b.rentInputMode === 'total' ? 'selected' : ''}>Contract total</option><option value="schedule" ${b.rentInputMode === 'schedule' ? 'selected' : ''}>Annual schedule</option></select></td><td><input data-f="contractedRentM" type="number" step="any" style="width:95px" value="${escapeHtml(b.contractedRentM ?? '')}"></td><td><input data-f="annualRentM" type="text" style="width:170px" value="${escapeHtml((b.annualRentM || []).join?.(',') || b.annualRentM || '')}"></td><td><input data-f="leaseSourceRef" type="text" style="width:150px" value="${escapeHtml(b.leaseSourceRef || '')}"></td><td><select data-f="powerResponsibility"><option value="" ${!b.powerResponsibility ? 'selected' : ''}>Project default</option><option value="landlord" ${b.powerResponsibility === 'landlord' ? 'selected' : ''}>Landlord</option><option value="tenant_direct" ${b.powerResponsibility === 'tenant_direct' ? 'selected' : ''}>Tenant direct</option><option value="reimbursed" ${b.powerResponsibility === 'reimbursed' ? 'selected' : ''}>Reimbursed</option></select></td><td><input data-f="powerPassThroughPct" type="number" min="0" max="100" step="any" style="width:80px" value="${escapeHtml(b.powerPassThroughPct ?? '')}"></td></tr>`,
      )
      .join(
        '',
      )}</tbody></table></div><p class="v21-muted">Optional physical power tranches: month,MW,building (one per line; building blank = shared). If blank, each building uses its Power month.</p><textarea id="v251Tranches" rows="3" placeholder="20,50,Building A&#10;30,50,Building B">${escapeHtml((state.powerTranches || []).map((t) => [t.month, t.mw, t.building || ''].join(',')).join('\n'))}</textarea><div class="v21-actions"><button id="v251Run" class="primary">Underwrite project</button><button id="v251Stress">Run stress grid</button><button id="v251Export">Export financial schedule CSV</button></div><div id="v251Output"></div>`;
    node.querySelector('#v2584PowerMode').value = state.powerResponsibility || 'landlord';
    node.querySelector('#v2583AllRateShock').checked = Boolean(state.rateShockAllFacilities);
    node.querySelector('#v251Mode').value = state.loanMaturityMode;
    node.querySelector('#v252Capacity').value = state.capacityBasis || 'IT';
    function get() {
      const a = { ...state };
      node.querySelectorAll('[data-v25]').forEach((el) => (a[el.dataset.v25] = Number(el.value)));
      node.querySelectorAll('[data-v25s]').forEach((el) => (a[el.dataset.v25s] = el.value));
      a.loanMaturityMode = node.querySelector('#v251Mode').value;
      a.rateShockAllFacilities = node.querySelector('#v2583AllRateShock').checked;
      a.powerResponsibility = node.querySelector('#v2584PowerMode').value;
      a.capacityBasis = node.querySelector('#v252Capacity').value;
      const sponsorText = node.querySelector('#v257Sponsor').value.trim();
      a.sponsorCommitmentM = sponsorText === '' ? null : Number(sponsorText);
      a.buildings = [...node.querySelectorAll('[data-b]')].map((tr) =>
        Object.fromEntries(
          [...tr.querySelectorAll('[data-f]')].map((el) => [
            el.dataset.f,
            ['name', 'rentInputMode', 'annualRentM', 'leaseSourceRef', 'powerResponsibility'].includes(
              el.dataset.f,
            )
              ? el.value || undefined
              : el.value === ''
                ? undefined
                : Number(el.value),
          ]),
        ),
      );
      a.powerTranches = node
        .querySelector('#v251Tranches')
        .value.trim()
        .split('\n')
        .filter((x) => x.trim())
        .map((line) => {
          const [m, mw, b] = line.split(',');
          return { month: Number(m), mw: Number(mw), ...(b && b.trim() ? { building: b.trim() } : {}) };
        });
      return a;
    }
    const fmt = (x) => (Number.isFinite(x) ? Number(x).toFixed(2) : 'N/A');
    function run() {
      try {
        state = get();
        last = evaluate(state);
        localStorage.setItem(key, JSON.stringify(state));
        const s = last.summary;
        node.querySelector('#v251Output').innerHTML =
          `<h3>Model assurance: ${escapeHtml(s.screeningReadiness)}</h3><p class="v21-muted"><strong>Scenario analysis only.</strong> Outputs are not contract-verified project returns or debt capacity. ${s.creditWarnings.map(escapeHtml).join(' • ')}</p><h3>Contract-value reconciliation</h3><p class="v21-muted">Status: <strong>${s.leaseReconciliationBlocked ? 'BLOCKED — missing or mismatched contracted rent' : 'Arithmetically reconciled, NOT independently validated'}</strong>. Recorded source references are not authenticated; no case is financially validated without independent documentation review.</p><div class="table-wrap"><table><thead><tr><th>Building</th><th>Mode</th><th>Disclosed ($M)</th><th>Modeled ($M)</th><th>Variance</th><th>Status</th></tr></thead><tbody>${s.leaseAudits.map((x) => `<tr><td>${escapeHtml(x.building)}</td><td>${escapeHtml(x.mode)}</td><td>${fmt(x.contractedRentM)}</td><td>${fmt(x.modeledContractRentM)}</td><td>${fmt(x.variancePct)}%</td><td>${escapeHtml(x.status)}</td></tr>`).join('')}</tbody></table></div><div class="v21-grid">${[
            ['Gross modeled energy cost', '$' + fmt(s.grossPowerCostM) + 'M'],
            ['Net landlord power cost', '$' + fmt(s.netLandlordPowerCostM) + 'M'],
            ['Power reimbursements', '$' + fmt(s.powerReimbursementM) + 'M'],
            ['Scenario NPV (unverified)', '$' + fmt(s.npvM) + 'M'],
            ['Scenario IRR (unverified)', s.leveredIRR === null ? 'N/A' : fmt(s.leveredIRR * 100) + '%'],
            ['Equity multiple', fmt(s.equityMultiple) + 'x'],
            ['Sponsor funded', '$' + fmt(s.equityInvestedM) + 'M'],
            ['Peak debt', '$' + fmt(s.peakDebtM) + 'M'],
            ['Minimum DSCR', fmt(s.minDSCR) + 'x'],
            ['Maturity month', s.maturityMonth || 'N/A'],
            ['Refinanced', s.refinanced ? 'Yes' : 'No'],
            ['DSCR breaches', s.breachMonths.length],
            ['Funding gap events', s.liquidityBreachMonths.length],
            ['Sources/uses residual', fmt(s.sourcesUsesMaxResidual)],
            ['Debt identity residual', fmt(s.debtMaxResidual)],
            ['Reserve identity residual', fmt(s.reserveMaxResidual)],
            ['DSRA shortfall months', s.dsraDeficiencyMonths.length],
            ['Cumulative CFADS', '$' + fmt(s.cumulativeCfadsM) + 'M'],
            [
              'Sponsor commitment',
              s.sponsorCommitmentM === null ? 'Unverified' : '$' + fmt(s.sponsorCommitmentM) + 'M',
            ],
            [
              'Sponsor headroom',
              s.sponsorRemainingM === null ? 'Unverified' : '$' + fmt(s.sponsorRemainingM) + 'M',
            ],
            ['Funding default', s.fundingDefault ? 'Yes' : 'No'],
            ['Unpaid exit debt', '$' + fmt(s.unpaidDebtAtExitM) + 'M'],
            ['Unfunded months', s.unfundedMonths.length],
            ['Ending debt', '$' + fmt(s.endingDebtM) + 'M'],
            ['Tenant contributions', '$' + fmt(s.tenantFundingM) + 'M'],
            ['Tenant rent credits', '$' + fmt(s.rentCreditsM) + 'M'],
            ['Refinance constraint', s.refinanceSizing?.binding || 'N/A'],
            ['Financeability', s.financeabilityStatus],
          ]
            .map(([k, v]) => `<div class="v21-tile">${k}<b>${v}</b></div>`)
            .join(
              '',
            )}</div><p class="v21-muted">Unverified sponsor funding implies an unlimited sensitivity assumption; a specified commitment caps funding, and deficits trigger a financing default. Exit value and refinance valuation are user assumptions; no appraisal or credit underwriting has been performed.</p>`;
        return last;
      } catch (e) {
        node.querySelector('#v251Output').textContent = 'Cannot underwrite: ' + e.message;
        return null;
      }
    }
    node.querySelector('#v251Run').onclick = run;
    node.querySelector('#v251Stress').onclick = () => {
      if (!run()) return;
      const a = state,
        rs = [];
      for (const delay of [0, 3, 6, 12, 18])
        for (const overrun of [0, 10, 20])
          for (const shock of [0, 200, 400]) {
            const z = evaluate({
              ...a,
              delayMonths: a.delayMonths + delay,
              overrunPct: a.overrunPct + overrun,
              rateShockPct: shock / 100,
            });
            rs.push({
              delay,
              overrun,
              shock,
              npv: z.summary.npvM,
              irr: z.summary.leveredIRR,
              breaches: z.summary.breachMonths.length,
            });
          }
      const worst = rs.reduce((x, y) => (x.npv < y.npv ? x : y));
      node.querySelector('#v251Output').innerHTML +=
        `<h3>45-case financial stress grid</h3><p>Worst NPV: $${fmt(worst.npv)}M at ${worst.delay} month delay, ${worst.overrun}% capex overrun, +${worst.shock} bps</p><div class="table-wrap" style="max-height:320px;overflow:auto"><table><thead><tr><th>Delay</th><th>Overrun</th><th>Rate</th><th>NPV ($M)</th><th>IRR</th><th>DSCR issues</th></tr></thead><tbody>${rs.map((r) => `<tr><td>+${r.delay}m</td><td>+${r.overrun}%</td><td>+${r.shock} bps</td><td>${fmt(r.npv)}</td><td>${r.irr === null ? 'N/A' : fmt(r.irr * 100) + '%'}</td><td>${r.breaches}</td></tr>`).join('')}</tbody></table></div>`;
    };
    node.querySelector('#v251Export').onclick = () => {
      if (!run()) return;
      const columns = Object.keys(last.rows[0]),
        csv = [columns.join(','), ...last.rows.map((r) => columns.map((k) => r[k] ?? '').join(','))].join(
          '\n',
        );
      const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })),
        a = document.createElement('a');
      a.href = url;
      a.download = 'PowerPath_v251_' + project.id + '.csv';
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    run();
  }

  root.PowerPathUnderwrite25 = {
    defaults,
    evaluate,
    irr: root.PowerPathEngine.irr,
    render,
    rentAudit: root.PowerPathEngine.rentAudit,
  };
})(typeof window !== 'undefined' ? window : globalThis);
