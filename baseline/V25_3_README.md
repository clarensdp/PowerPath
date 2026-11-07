# PowerPath v25.3 — contractual lease calibration

This patch adds three per-building rent-input modes in Project Intelligence → Underwrite: starting $/kW-month, total nominal contracted lease value ($M), or an explicit annual nominal rent schedule ($M per contract year, CSV). Total-value mode solves the starting rent using a geometric annual escalation series, rather than treating average rent as year-one rent. A new contract-value audit calculates full-capacity, full-contract nominal rent, discloses variance, and blocks financial reconciliation when no documented target exists or mismatch exceeds 0.1%.

A passed reconciliation is **arithmetic only** and is never called independently validated. Contract dates, total disclosed values, rent/pass-through definitions, escalators, IT versus gross MW, source authenticity, and legal terms require separate review. Actual recognized revenue during construction or after energization delay may be lower than the complete-contract rental sum. In annual schedule mode, each year must be explicitly entered; incomplete schedules error out.

To run: open `PowerPath.html` and go to Project Intelligence → Underwrite. For a disclosed total, select `Contract total`, specify `Contracted total ($M)`, lease term, annual escalator, and source reference. Run `Underwrite project` and inspect the contract-value reconciliation table before relying on model results. An entered reference is not independent source validation.

Tests: `cd workspace && node test_lease253.cjs` and `for f in test_*.cjs; do node "$f"; done`. All existing suites are retained.
