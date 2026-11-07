# CODE_PATCHES — v25.8-CA

Apply from the package root with `patch -p1 < CODE_PATCHES/<file>.patch` (or use the full patched tree `PowerPath_v25_8_CA/`).

| Patch | Files | Issue |
|---|---|---|
| P1 annuity repayment of refinanced debt | underwrite25.js, reference257.py | CA-01 |
| P2 sticky shared-tranche allocation | underwrite25.js | CA-02 |
| P3 explicit tranche capacity basis (gross→IT via PUE) | underwrite25.js | CA-03 |
| P4 calendar-hour operating MWh | underwrite25.js | CA-05 |
| P5 halt unfunded construction after funding default; pro-rata exit; terminal leakage reporting | underwrite25.js, reference257.py / verify_v258_cases.py (legacy cases pinned to `continue`) | CA-04, CA-10 |
| P6 30/360 first-coupon stub | contract_notes258.js, test_contract_notes258.cjs | CA-06 |
| P7 harness calendar alignment | run_benchmarks_v258.cjs | CA-07 |

`test_claude_audit.cjs` holds the minimal reproductions. Running `node test_claude_audit.cjs <v25.8 underwrite25.js> <v25.8 contract_notes258.js>` gives 1/9 (8 fail); against the patched files it gives 9/9.
`RUN_AUDIT_CLAUDE.sh` is the bundled `RUN_AUDIT.sh` pointed at the patched tree.
New inputs (all optional, defaults shown): `fundingDefaultPolicy:'halt'|'continue'`, `trancheCapacityBasis` (defaults to `capacityBasis`), per-tranche `basis`, notes `accrualStartDate` and `firstPeriodAccrual:'regular'`.
New summary fields: `constructionHaltMonth`, `abandonedBuildings`, `peakUnfundedGapM`, `residualCashRetainedAtExitM`, `uncollectedTenantReceivableAtExitM`, `workingCapitalBalanceAtExitM`, `fundingDefaultPolicy`.
