# PowerPath v25.2 — Benchmark-Driven Model Corrections

**Scope:** fixes to the six critical/high-priority items surfaced by the 16-project public benchmark run, without adding agents. The model remains a diligence/screening tool, **not lender-approved financial forecasts**.

## Corrected calculation mechanics

1. **Phase-specific lease terms:** Each building now has its own `leaseTermMonths` and `rentEscalatorPct`. Rent stops when its contracted lease term expires; annual escalators apply to monthly rent based on elapsed lease years. Building-specific base rent is supported in the evaluation API. The UI exposes terms and escalators.
2. **Capacity normalization:** Project/building `capacityBasis` explicitly distinguishes critical IT MW and gross facility MW, with gross divided by modeled PUE to obtain IT MW. Conversion is an *assumption*, not a representation of verified site capacity. The UI exposes the global capacity basis and PUE.
3. **Tenant-funded construction:** `tenantCapexPct` reduces the sponsor's funding requirement through separately identified tenant construction contributions. `tenantRentCreditPct` and `tenantCreditMonths` reduce rent for a defined period. The tenant contribution and rent credit appear separately in monthly cash flows; building-specific overrides are accepted by the engine.
4. **Refinance covenants:** Refinance size is the minimum of the LTV, cash-flow/DSCR, and minimum debt-yield limits. The binding constraint and calculated limits are visible in `summary.refinanceSizing`. When refinance proceeds are inadequate to pay existing debt, the model funds the gap with sponsor cash (subject to its simplifications). This is a first-pass *lender-style* sizing formula, not a credit agreement.
5. **Multiple facilities:** Added a separately priced mezzanine construction tranche (`mezzLtcPct`, `mezzRatePct`, `mezzFeePct`) alongside senior construction debt. Balances, cash interest/capitalized interest, fees, maturity repayment, and exit are tracked distinctly. This does **not** yet reproduce full preferred equity, loan-level covenant packages, cash sweeps, or intercreditor mechanics.
6. **Evidence-backed schedules:** The existing power tranches remain the binding input to monthly rental capacity. This release does **not** falsely convert public opening targets, source documents, or GIS proximity into contracted grid deliverability. Verified evidence should continue to be recorded in the project Evidence/Data Room layer.

## Reproducible test results

- Existing engine and feature test suites, including 300 randomized sources-and-uses cases, pass.
- **12 new v25.2 test groups** pass: lease expiry, escalators, gross-to-IT normalization, tenant contributions, tenant credits, three binding refinancing constraints, mezzanine debt, invalid leverage, combined accounting reconciliation, and unchanged capacity-evidence separation.
- **16 public project/site cases × 45 cases = 720** combined delay/overrun/rate scenarios completed; 0 execution failures and 0 reported monthly sources/uses residual. The revised benchmark sets lease term from public disclosures where available (otherwise clearly assumed).
- Browser smoke tests load the application at 1365 px and 390 px without uncaught JS errors or horizontal overflow, and exercise the revised engine.

## NPV comparison — materially changed model assumptions

| Metric across 720 **synthetic** cases | v25.1 | v25.2 |
|---|---:|---:|
| Cases with negative levered NPV | 384 | 219 |
| Cases with nonnegative levered NPV | 336 | 501 |
| Mean scenario NPV ($M) | 32.3 | 421.2 |
| Median change in scenario NPV | — | +302.3 |

**Do not interpret this difference as performance improvement or a backtest of actual returns.** The baseline 25.1 treated rents as flat and did not cut off expired leases; v25.2 adds assumed 2.5% annual increases unless overridden, and more rigorous refinancing sizing. The absolute uplift demonstrates the economic importance of lease assumptions—and the need to validate contractual escalators, reimbursement/pass-through structure, renewal probability, and market exits on each project. Scenarios with insufficient public financial disclosure are not independent project valuation validations.

## Outstanding high-value gaps

- Full construction draw waterfall with lenders' eligible capex, funding priority, and debt-linked holdbacks.
- Per-building tenant-reimbursement milestones, pass-through electricity billing, contractual rent abatement, termination rights and tenant concentration.
- Staged refinancing across multiple facilities with loan-specific amortization, cash sweeps, covenants, DSRA, taxes and bankruptcy/default recoveries.
- Historical large-load utility energization actuals, validated site-to-substation agreements and equipment firm delivery slots.
- Independent Excel reconciliation against at least one fully documented financing case, with a model assumption ledger.

The source package includes the previous regression tests, new v25.2 tests, the benchmark runner, and all results. No confidential or utility-confirmed datasets are implied.
