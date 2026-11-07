# Independent red-team request: PowerPath v25.8.4

You are the independent adversarial reviewer. Audit **the attached v25.8.4 source without relying on the author's test claims**. Examine `workspace/underwrite25.js`, `workspace/test_power_pass2584.cjs`, `benchmarks/case_catalog_v2584.json`, `benchmarks/run_power_cost_2584.cjs`, and `independent_power_reference.py`.

Priority attack surfaces:
1. Is the tenant electricity payer correct for each contract? Reopen primary executed/exhibit filings. Distinguish customer directly paying utilities from a lessor reimbursed for costs; identify any accrual/billing/cash-flow timing differences.
2. Ensure no double recognition or unintended WC/CFADS benefits from reimbursements. Challenge whether operating expenses use the correct denominator, whether demand charges, ratchets, taxes or losses are absent, and what happens with power available but no paying tenant.
3. Confirm capacity bases (critical IT, gross, allocated utility power, licensed power) for all 16 public cases; no silent proxy conversion. Challenge the Polaris $3B/$4B/$4B building-value claim: find a primary source or retain UNVERIFIED.
4. Check that month-to-month cost identity holds across mixed buildings and shared power tranches, lease expiry/renewal, partial reimbursement, delays, default/halt and forward-CFADS refinancing.
5. Compare to v25.8.3 frozen baseline provided. Produce failing-before/passing-after tests for any additional material defects and a separately written calculation reference. Never infer lender validation from arithmetic matching.
6. Do not rank the 16 cases as actual investments. Record each public assumption's source, tier and remaining contractual blocker; do not backsolve economics to an attractive NPV.

Return: prioritized `ISSUES.csv`, reproducible code patches, independently generated test log, exception register, and a bounded go/no-go verdict. No unsupported 'flawless' or lender-grade claims.
