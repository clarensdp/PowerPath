# PowerPath v25.8.1 — Independent red-team correction review

**Date:** 26 October 2026  
**Disposition:** **Original v25.8 NO-GO for comparative screening.** This corrected candidate is a **conditional pass for deterministic scenario screening only**. It is **not** a contract-verified transaction underwriting model and **not** lender-grade.

## Basis

User-supplied independent Claude review `CLAUDE_AUDIT_VERDICT.md`, `ISSUES.csv`, test reproductions, code patches and a complete proposed patched source tree. We independently retested the corrections in a new local runtime. Original engine version is retained in `red_team/baseline/underwrite25.js` (SHA-256 begins `2e01c4d7`); the v25.7 predecessor is in `red_team/baseline_v25_7`.

## Computation defects corrected

| Issue | Why it matters | Status |
|---|---|---|
| CA-01: Annuity-sized refinancing with level-principal repayment | The DSCR sizing calculation assumed one repayment schedule while the actual loan used another. First-year debt service could be ~29% too high; base-case project NPV shifts of $0.55M to $50.74M in the red-team comparison | Fixed: debt service on the same annuity basis as sizing |
| CA-02: Shared power reallocated across buildings | A later-energized building could wrongly remove existing service from an earlier one and crash valid studies | Fixed: allocated capacity stays allocated |
| CA-03: Gross versus IT capacity | Utility power tranches on gross-MW campuses were treated as IT MW | Fixed: explicit tranche capacity basis and PUE conversion |
| CA-04: Phantom spending after funding default | The model could finish projects with massive negative cash and show debt paid off | Fixed: default `halt` policy stops unfunded construction; legal recovery remains assumed |
| CA-05: Flat 730-hour annual MWh reporting | Reported MWh diverged from actual calendar-based electricity costs | Fixed |
| CA-06: First-coupon stub | Flat semiannual first coupon omitted actual number of 30/360 accrual days | Fixed in standalone notes checker; accrual start **must still be source-verified** |
| CA-07: Benchmark calendar offset | Case index and calendar-based energy costs were off by one year | Fixed |
| CA-08: Correlated reference implementation | Independent-looking Python tests used the same erroneous method | Re-tested against Claude's separately authored reference, not claimed as formal human assurance |

Additional safeguards implemented here: **scenario assurance classification and visible warning list**. Outputs surface contract source gaps, uncapped sponsor support, covenant breaches, lease-end exposure, terminal exit values unsupported by an operating lease, funding defaults, and incomplete integration of notes. Positive NPV must not be interpreted as a performing credit case.

## Evidence from this local verification

- Unpatched original: **1/9** new red-team assertions passed, eight fail as expected.
- Corrected candidate: **9/9** red-team assertions passed; **23/23** JavaScript test scripts passed (including four new status/assurance cases).
- Independent Python from-scratch reference: **10 scenarios; 24,320 month-by-month field comparisons passed**, maximum difference approximately **1.42 × 10⁻¹² $M**.
- Prior reference suite: 13,971 comparison checks, numerical residual below 2 × 10⁻¹² $M.
- Public illustrative cases: **16/16**, combined stress scenarios **720/720**, with zero reported monthly accounting imbalances. **0/16 contract verified**.
- Built HTML: verified in Chromium at 1440px and 390px with no JavaScript page errors or horizontal overflow.

**Caution:** 720/720 scenario execution does not mean 720 loans passed credit tests. The red-team found **all 720 stresses had covenant breaches**. They are *failed hypothetical financing structures*, not investable comparable projects.

## Important remaining NO-GO items

1. **CA-09 — Lease-tail / debt / exit incoherence:** refinancing amortization extends beyond leases, cash covenants fail, and a non-zero exit value can be assumed after rental expiration. Requires case-specific new leases, debt term alignment and asset-value evidence; do not solve by fitting results.
2. **CA-16 — Contract-specific notes unintegrated:** APLD, Galaxy and Core obligations differ in collateral, coupon, amortization triggers, project phase and covenants. Their note checker remains independent of the project cash waterfall.
3. **CA-17 — Executed lease schedules unavailable:** undisclosed abatements, amendments, reimbursement mechanics and pass-throughs cannot be reconstructed from headline total values.
4. **CA-18 — No qualified independent human reviewer** and no transaction-by-transaction lender signoff.
5. **CA-11 through CA-15, CA-19/20:** lender-defined cure/default waterfalls, rate shock coverage, unused inputs, interest capitalization policies, periodic DSCR definitions, source reconciliation and MW-unit normalization remain open.

## Permitted use

Use the corrected HTML and engine for **clearly labeled synthetic deterministic comparative screening**. Do not use its financing NPVs to rank the 16 real public developments, certify debt capacity, represent contracted power delivery, publish project returns, or place debt.

## Commands

```bash
bash RUN_INDEPENDENT_REVIEW.sh
```

The test script performs computational checks, public-case simulations, and rebuilds the standalone HTML. It does **not** establish contractual correctness or external model certification.
