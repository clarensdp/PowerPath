# PowerPath v25.8.3 — Roadmap Phase 1A Engineering Pass
26 October 2026

## Basis of review
Reviewed the six-page **PowerPath — Roadmap to a Real Tool**. The document divides work into 17 code/research issues, 10 input-dependent tasks, and five external requirements. This release takes the available-source, low-assumption subset rather than treating unsupported commercial/legal policy as engineering fact.

## Changes actually implemented

**N3 — Optional all-facility rate shock**
- Added `rateShockAllFacilities` (default `false`, for backwards-compatible scenarios).
- When explicitly true, `rateShockPct` applies to senior construction debt, mezzanine debt and refinancing rates consistently across interest charges, refinance debt sizing, annuity repayment and DSRA projections.
- Adds a checkbox to the underwriting workspace.

**N6 — Explicit end-of-horizon collections**
- Added `exitTenantReceivableRecoveryPct` and `exitWorkingCapitalRecoveryPct`, both defaulting to **0%**.
- Collections are booked separately from assumed real estate/asset sale proceeds, taken into account when paying creditors, and included in monthly cash sources-and-uses reconciliation.
- Tenant-receivable recovery cannot exceed the modeled outstanding receivable. A separately documented purchase-price definition is required to support nonzero collections: if an exit valuation already includes receivables or working capital, adding recoveries double-counts value.

**N2 — Unsupported input exposure**
- The old `amortMonths` input does not actually amortize construction loans; construction financing remains interest-only prior to payoff. `dsraReleaseAtExit=false` is not honored in the legacy terminal waterfall.
- The engine now emits explicit assurance warnings when these old inputs differ from implemented policy. An opt-in `strictDebtPolicyValidation:true` rejects these configurations. Legacy calculations remain compatible with existing regression fixtures.
- This is a **guardrail**, not an implementation of mini-perm amortization or a complete reserve disposition policy.

**N16 — Reproducible audit harness (initial)**
- Added `run_phase1a_audit.py`, a one-command runner executing all JavaScript test suites, then the 16 frozen public cases under 45 stress combinations each.
- Saves the SHA-256 hashes of major model files, per-suite logs and scenario results into a timestamped `audit_runs` folder.
- This checks calculation stability and financial accounting identities. It is **not a fresh independent lender-style model** and cannot establish whether input agreements reflect actual contracts.

## Validation
- **24/24** JavaScript test scripts passed, including **8 new Phase 1A assertions**.
- **720/720** frozen public-project stress cases executed with no model exceptions.
- Maximum monthly cash/debt/reserve identity residual: **1.82e-12 $M**.
- Baseline v25.8.2 **fails** the new N3 assertion; v25.8.3 passes.
- Chromium desktop (1440px) and mobile (390px) standalone page loading passed in the prior build check; refresh the browser check against the final file to be complete.
- No real lease/indenture/ESA has been independently verified and no lender-grade assurance is implied.

## Why the roadmap needs sequencing adjustments
1. **N1 is a hypothesis, not a verified fix.** Building-specific construction interest attribution and facility-level interest capitalization are not interchangeable. The proper allocation and capitalization policy depends on actual facility/collateral terms. The document's statement that N1 is *likely* the cause of Applied Digital covenant breaches is unproven; first establish a building-facility cash flow and reconcile the breach bridge.
2. **N7/N8 are the critical product architecture.** Multiple segregated financing facilities, borrowing entities and conditional payment triggers must be integrated into the monthly ledger before calling the current model transaction-specific.
3. **N9/N10 and documentary provenance (N15) should precede stochastic forecasting.** We should not prioritize N13 Monte Carlo P10/P50/P90 until distributions and correlations can be calibrated or plainly labelled as sensitivity priors.
4. **N12 is structurally dependent on legal entity, tax classification, jurisdiction and debt documentation.** Implement a source-backed tax input schedule rather than asserting a universally applicable result from the MACRS label alone.
5. The roadmap's scoring progression (6 → 9+) and 15–25 session estimate are not evidence of accuracy or a guaranteed schedule. Passing a third-party scoped model audit and source-backed transaction verification must be separate gates.

## Recommended build order from here
**Immediate next engineering work:** N7/N8 facility-level debt ledger (construction, senior notes, mezzanine) with actual payment dates, OID, per-facility collateral scope, document-supported amortization triggers, optional reserve rules and a priority-of-payments interface. Do **not** hard-code Applied Digital, Galaxy or Core Scientific terms as universal.

**Next:** N9 lease schedule import, N15 provenance, N4 covenant definitions, N5 default priority/recovery and N10 pass-throughs. Then independently reconcile the full model with the public terms and flag every private, missing contract term. Separate mathematical passes from actual lender-signoff.

**Not closed in this release:** N1, full N2 policy implementation, N4/N5, full N7–N17, private-document I1–I10 tasks, independent human assurance.

## Running the audit
```bash
cd PowerPath_v25_8_3_work
python3 run_phase1a_audit.py
```
The CLI writes `audit_runs/<timestamp>/audit_summary.json`, individual test logs and `stress_results.json`. It exits nonzero if a JavaScript test fails or a stress case violates its numerical identity threshold.
