# PowerPath v25.8.2 — Second Claude Audit Integration
Date: October 26, 2026
Status: **CONDITIONAL PASS FOR SYNTHETIC COMPARATIVE SCREENING ONLY. NO-GO FOR TRANSACTION FINANCING, PUBLIC-PROJECT RETURNS AND LENDER-GRADE USE.**

## Baselines and provenance
- Previous candidate: the red-team-corrected `PowerPath_v25_8_1_RedTeam_Source.zip` / working tree `/mnt/data/PowerPath_v25_8_Reviewed`.
- New external submission: `PowerPath_v25_8_Claude_Audit (1).zip` from the user, containing an updated Claude review, CA2 lease-tail patches, source facts and transaction summaries.
- This release merges the new model logic and its UI controls **without removing the prior explicit screening warnings**.
- It **does not** integrate the three contractual note instruments. All transaction terms in the external audit are claims from that submitted review and need primary-document/contract-level confirmation for a transaction audit.

## Changes merged
1. **Lease-tail-constrained refinance tenor:** optional `refinanceTenorPolicy='leaseTail'`, amortization limited by modeled MW-weighted remaining lease life, subject to an explicit 12-month placeholder buffer and minimum-term floor. The floor can exceed lease life. We added `leaseTailTenorWarning` and a prominent warning rather than calling that loan lease-tail compliant.
2. **Renewal scenarios:** optional probability-weighted rent after expiry (`leaseExpiryPolicy='renew'`). An *expected-value assumption*, not an executed extension or calibrated probability. Inputs are editable in the UI.
3. **Exit underwriting:** optional `exitValuePolicy='contracted'` marks leased capacity at the full assumed exit multiple and vacant capacity at a separate assumed percentage. This is not a property appraisal.
4. **Assurance preserved:** `screeningReadiness`, detailed credit warnings, visible unverified NPV/IRR labels, lease reconciliation flags, and restrictions on presenting numbers as verified debt capacity or public-company returns.
5. Imported Claude's five new CA2 regression cases and the second audit's evidence for reproducibility.
6. v25.8.2 is a new standalone HTML build. The older v25.8.1 remains available; it is not overwritten.

## Reproduction
From the extracted application root:
```
for f in workspace/test_*.cjs; do node "$f" || exit; done
node test_lease_tail_portfolio.cjs
node verify_policy_720.cjs
node benchmarks/run_benchmarks_v258.cjs
python3 workspace/build_page.py
```
Tests require Node.js; build requires Python 3. The browser smoke test (`smoke_v2582.py`) additionally requires Playwright and Chromium.

## Observed test results
- 23/23 JavaScript test scripts pass (including the supplied CA2 tests and prior screening safeguard regression).
- 16/16 frozen public-project synthetic cases and 720/720 baseline stress calculations completed; maximum reported financial identity residual below $1e-6 million.
- 16/16 lease-tail scenario comparisons reconcile. With all three optional illustrative policies turned on: zero post-expiry breach months, but **188 pre-expiry covenant-breach months across eight cases**. NPV fell in 14/16 versus original synthetic defaults.
- Additional 720/720 combined lease-tail/renewal/exit stress calculations completed, no computation errors, maximum financial identity residual `9.095e-13` million. **659/720 still have at least one modeled covenant breach.** None are contract-verified.
- 1440px and 390px browser smoke tests: rendered new policy controls, executed a policy change, displayed credit warnings and unverified scenario labels, no JS errors or viewport overflow.
- These tests are deterministic integrity checks. They do not demonstrate contractual accuracy or external auditor certification.

## New source-level findings from the supplied audit
- Applied Digital ComputeCo: submitted review reports fixed construction DSRA $177.0M; exact legal scope, note amortization and covenant details remain outstanding.
- Helios Phase II: submitted review reports 99.5% notes issue price, during-construction DSRA $285.05M, and amortization beginning on the first payment date after ten months from the first rent payment. Do not continue using 'project completion' as a generic substitute for this trigger.
- Core Scientific Finance I: submitted review reports construction DSRA about $343M, with contingent amortization and special credit treatment; no implemented legal waterfall.
- These figures are not inserted into the underwriting engine automatically. They are held as evidence for human verification against executed instruments.

## Mandatory open blockers
- Actual note cashflow integration (issuer/obligor/collateral, OID, issue date, first stub, contractual installments, revenue credit and completion triggers, DSRA, waterfalls, cross collateral, mandatory prepayments).
- Build-by-build executed lease terms and utility service rights; 0/16 cases meet the contract verification gate.
- Resolve construction-to-operation financing mismatch: 8/16 still have pre-expiry covenant breaches under illustrative policies; never hide them by adjusting terminal value.
- Commercial treatment of lease renewal and vacancy, investor/sponsor funding commitments, recoveries, actual debt/credit test definitions.
- Independent qualified human model review for a frozen version and specified use.

## Scope and decision
Safe within documented assumptions: compare **hypothetical** delivery and financing sensitivities with all warnings visible.
Not safe: certified project debt capacity, public-project rank ordering by NPV, transaction returns, approved utility MW, or lender credit decisions.
Next release should be a proper event-driven instrument-level debt engine, not further model-output tuning.
