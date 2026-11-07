# PowerPath v25.7 — CFADS, sponsor commitments, forward refinancing and independent model check

## Release purpose
This release implements the priority controls identified in v25.6. It is a financial integrity and transparency upgrade, not a declaration of lender certification. No autonomous agents have been added.

## Changes to the model

1. **CFADS rather than EBITDA for debt-service coverage.** New monthly fields: cash-tax **proxy**, sustaining/maintenance capex, required working-capital investment, and CFADS. Formula: `CFADS = EBITDA − cashTaxProxy − maintenanceCapex − changeInWorkingCapital`. Borrowing DSCR uses CFADS over scheduled cash interest and principal, excluding mandatory balloon payoffs, refinancing transfers and voluntary sweeps.
2. **Forward-looking refinance underwriting.** At the actual loan-maturity month, compute a new 12-month operating forecast. Refinance DSCR limitation uses this *future* CFADS and modeled annuity debt service. A separate debt-yield limit uses future NOI proxy (EBITDA less maintenance capex). Refinancing is the minimum of LTV, DSCR and debt yield. The forecast is assumption-driven and not validated by a lender.
3. **Sponsor equity commitment limit.** Optional `sponsorCommitmentM` includes opening equity. A blank commitment preserves previous unconstrained scenario behavior, but explicitly displays **UNVERIFIED SPONSOR FUNDING**. Once entered, equity funding cannot exceed the cap, including capital injections needed for minimum liquidity, maturity payoffs and DSRA funding. Where capped equity is insufficient, the transaction is flagged as a funding default; no imaginary equity injection is introduced.
4. **Failed refinance/default protections.** A credit in uncured funding default cannot refinance as a performing asset. If there is insufficient cash and committed equity to retire maturing facilities, old debt remains outstanding with a disclosed shortfall. Exit repays only cash-available debt, and unpaid debt remains visible; defaulted assets cannot distribute to equity.
5. **Accountability.** Month-by-month sources and uses, senior/mezz principal, restricted reserves and CFADS bridges are exported with the existing CSV functionality. Added UI inputs for sponsor commitments and CFADS drivers and tiles for remaining sponsor capacity, cumulative CFADS, funding defaults, unfunded months and unpaid debt.

## Computational tests executed

- **19/19 existing and new JS test scripts passed**, including a new 15-group test suite `workspace/test_underwrite257.cjs` and 36 additional adverse financing combinations.
- **23,064 line-by-line independent Python comparisons passed** across eight different **120-month** synthetic project/financing configurations. The Python reference separately builds lease and operating cash flows, financing draws, capitalization, refinance underwriting, reserves, debt payoff and equity flows. It does not read JS monthly calculation rows as its inputs; both use the same declared input specification. Maximum absolute comparison error in any compared financial metric: approximately **9.1 × 10⁻¹³ million dollars** (floating-point precision). Outputs: `audit/reference257_results.json` and `audit/monthly_reconciliation_257.csv`.
- The independent arithmetic identity verifier adds **2,404** reserve/cash/refinance checks (`audit/results.json`). This second verifier deliberately uses JS-reported cash-flow lines and should not be confused with the independent Python forecast.
- Desktop (1440px) and mobile (390px) smoke tests: no JS exceptions or horizontal page overflow. Browser testing used controlled localStorage because sandbox Chromium blocks localhost/file navigation; a real deployment/persistence QA is still necessary.

## Illustrative impact — same input assumptions, different credit mechanics

| Scenario | v25.6 modeled levered NPV ($M) | v25.7 modeled levered NPV ($M) | Explanation |
|---|---:|---:|---|
| Unmodified built-in baseline | 436.38 | 436.38 | LTV already binds, so forward CFADS does not affect refinancing |
| Month 24 refinance, 50% senior / 10% mezz, six-month DSRA | 395.87 | 414.60 | Refinance sizing uses forward-year CFADS instead of maturity-month EBITDA × 12 |
| 22% cash-tax proxy, 30 working-capital days, $0.1M/MW-year maintenance | 436.38* | 208.68 | New CFADS deductions reduce modeled free cash flow and refinance capacity |
| Sponsor cap $75M, month 24 maturity | 400.63* | −73.72 | The old model ignores a sponsor cap; new model flags funding default rather than auto-funding |

\* The new inputs were not recognized by the prior engine; these comparisons illustrate the change in model scope rather than a historical prediction error. All project economics here are illustrative, not results for actual public assets.

## Validation status and unresolved blockers

**Financial mechanics: verified against independent synthetic Python reference calculations.** The reference uses separate source implementation; this is not review by an external auditor.

**Contractual correctness: NOT VERIFIED.** The CFADS tax proxy is **not** a full tax model; it applies an assumed cash rate to positive EBITDA and omits depreciation, loss carryforwards, interest deductibility, jurisdictional taxes and asset-sale taxes. Maintenance capex is modeled as a uniform $M/IT MW/year assumption. Working-capital need is a simple revenue-days proxy, not a legal receivables/collateral schedule. The DSCR and cash-sweep definitions are not taken from an executed loan agreement.

**Insolvency/default: simplified.** In a funding default, a negative theoretical cash balance may be carried as an **unfunded liquidity deficit**, not real bank cash. The model should not be relied on for lender recovery or restructuring proceeds; receivership, enforcement, seniority priority outside terminal repayments, delayed works and waiver/cure agreements are not fully modeled.

**Lender grade: NOT ACHIEVED.** No independent reviewer has signed off and no full project-level debt agreement or verified financing model has been reconciled. The ability to complete thousands of arithmetic checks does not validate input sources, security package, tenant arrangements, or actual loan availability.

## Reproduce

```bash
cd powerpath_v25_7/workspace
for f in test_*.cjs; do node "$f"; done
cd ..
python audit/reference257.py
python audit/create_reconciliation257.py
python audit/independent_ledger.py
python workspace/build_page.py
```

For the UI, open `PowerPath.html`; for optional local service integrations consult the earlier V23 / CONNECTORS / LIVE_DATA READMEs. Do not upload confidential data to the prototype without appropriate security review.
