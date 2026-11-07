# PowerPath v25.4 — model-integrity audit

## Verified changes
1. Debt draw base now equals gross construction cost less tenant-funded contributions. Prior version drew debt against costs already funded by tenants, inflating financing sources. Both senior and mezzanine use the sponsor-funded eligible base.
2. Post-refinance scheduled principal uses `refinanceAmortMonths`, not the separate construction-loan `amortMonths` input.
3. When no tranches are explicitly supplied, building lease commencement is no earlier than physical power availability, construction completion, or specified contractual lease month. Disclosed nominal lifetime contract totals remain distinct from revenue actually recognized within the model horizon.
4. A modeled unpaid loan maturity is explicitly labeled DEFAULT in financing outputs and prevents interim sponsor distributions. These remain illustrative distressed outcomes, not a modeled insolvency waterfall.
5. Added six targeted regression groups, including 80 parameterized accounting reconciliations, on top of the previous suite.

## Independent accounting checks
Monthly sources-and-uses residuals are tested for zero, and end-horizon debt payoffs are tested under multiple assumptions. The refinance principal-paydown test uses a separately calculated straight-line benchmark, while lease cash flow is reconciled to the disclosed nominal contract fixture.

## Strict qualification
This release is **not** independently validated against an executed lender waterfall, contract, or appraiser valuation. No lender-specific cash sweeps, withholding, tax equity, intercreditor priorities, credit loss waterfall, interest reserve triggers, contractual curtailment terms, or statistical forecast calibration has been independently certified. Programmatic zero residual is necessary but not sufficient for economic correctness.

## Usage
Open `PowerPath_v25_4.html` or run the project server as documented in previous releases. Underwrite is in Project Intelligence. The interface reports the financeability state, contract reconciliation and separate physical power assumptions. Tests can be rerun using `cd workspace && for f in test_*.cjs; do node "$f"; done`.
