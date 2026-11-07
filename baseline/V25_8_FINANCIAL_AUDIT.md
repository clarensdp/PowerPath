# PowerPath v25.8 — Transaction Verification and Model Corrections

**As of:** October 26, 2026  
**Nature:** Internal CFO/CTO/Risk model audit; NOT third-party certification or lender approval.

## Decision

**PASS for bounded deterministic comparative scenario analysis. NO-GO for lender-grade transaction certification or unsupervised investment decisions.** The tested financial identities now reconcile, but none of the 16 public cases has a complete, independently validated executed project lease + debt waterfall + physical utility-rights file.

## v25.8 fixes in the actual `workspace/underwrite25.js` engine

1. **Retired construction facility does not reopen.** Previously, an equity-funded payoff left the draw flag open, allowing late buildings to draw on a paid-off loan. Introduced a `constructionFacilityClosed` flag independently of the refinancing flag.
2. **Partial energization creates separately aged rent cohorts.** Revenue no longer escalates before a tranche starts physical service. Lease term and credits begin on each delivered tranche's start (contract-specific rent rules still require review). Gates include construction completion, target power month, and lease date.
3. **Separate general restricted reserve and DSRA.** Former implementation used `max(baseReserve, DSRA)`; under v25.8 they are additive. This assumes the two requirements are distinct and should not be used where the agreement expressly cross-credits balances.
4. **Tenant capex reimbursement timing.** Added `tenantFundingLagMonths`, receipt/receivable tracking, and funding-shortfall consequences instead of treating customer-funded construction accrual as cash received immediately. Building debt is sized against sponsor-eligible capex, not tenant reimbursement.
5. **Input validation.** Rejects tenant contribution/credit percentages over 100%, fractional lease term months, excessive assigned MW, and unsupported lag values.
6. **Calendar-month energy hours.** Replaces the flat 730 hours per month with actual calendar month hours (including leap-year February), using explicit first modeled year and month. This fixes an avoidable cash-flow timing distortion; actual hourly load, tariffs and demand charges remain outside this model.
7. **Separate contractual-notes checker.** Added `contract_notes258.js` for dated coupons, issue discounts, original-face amortization proxies, and balloon schedules. **This is not yet integrated into the primary asset underwriting waterfall** and never asserts contractual verification when triggers or amortization amounts are unknown.

## Quantified defect demonstrations (synthetic, not real investment valuations)

From `audit/change_impact258.json`:

| Defect case | v25.7 | v25.8 | Meaning |
|---|---:|---:|---|
| Tranche example, month 15 rent ($M) | 11.20 | 10.60 | Later cohort must start at initial rent, not previously accrued escalator |
| Tranche example, month 27 rent ($M) | 0.00 | 5.60 | Later tranche has its own remaining contractual term |
| Unauthorized construction draws after equity payoff ($M) | 147.00 | 0.00 | Paid-off construction debt cannot be redrawn without a new facility |
| Post-refinance combined restricted balance ($M) | 27.36 | 39.36 | Independent base reserve of $12M added to DSRA |
| Tenant reimbursement lag, funding default | Not explicitly modeled | Triggered with 3-month lag | Cash reimbursement is different from accrued tenant construction funding |

NPV changes from these examples are in the JSON. Do not interpret improvement/deterioration as a change to a real project's investment merits.

## Scope and reproducible checks

- **21/21 JavaScript test suites** run successfully, including nine targeted v25.8 correction cases and three disclosed-notes arithmetic fixtures.
- **8 earlier independent Python baseline cases:** 24,024 monthly field comparisons, maximum reference gap $9.095e-13 **in $M units**.
- **7 v25.8 independent Python edge cases:** 13,971 monthly field comparisons, maximum gap $1.364e-12 **in $M units**.
- **16/16 public project/site cases** executed using strict disclosure labels.
- **720/720** stress scenarios executed (delay × capex × rate); no calculation exceptions and no reported monthly cash/debt/reserve residuals at CSV precision. The maximum change versus the same v25.7 input scenarios is about **$6.83M NPV**, driven by the calendar-hour calculation (not by a new real-world project disclosure).
- **5/5 Applied Digital campus approximate contractual-revenue totals** arithmetically normalized to public headline values. This is a consistency condition by construction, **not** an independent test of individual lease cash flows.
- **0/16 cases contract-verified**. A lease headline is not a full contractual schedule, and the common capex/tariff/debt/exit inputs remain synthetic.
- **Desktop 1440px and mobile 390px Chromium smoke tests** passed with no uncaught JavaScript errors or horizontal overflow.

## Three priority transaction findings

### Applied Digital — Polaris Forge 1 / APLD ComputeCo

Primary FY2026 10-K: https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm

- Discloses ~400 MW critical IT across 100/150/150 MW tranches and **approximately** $11.0B initial lease revenue across 15-year base terms; first tranche operational October 2025, later lease amendments/assignments and future delivery tranches. The $11B is not a single lease with a verified 2.5% escalator.
- Discloses $2.35B 9.25% senior notes issued at 97% of par, first coupon June 15, 2026, maturity December 15, 2030, scheduled amortization beginning December 15, 2027. Coupon and discount arithmetic in the notes checker matches these headline terms, but installment amounts and covenants need the indenture.
- **Material open issues:** individual building contractual rental flows/amendments, project-specific costs and multiple financing tranches/guarantees are not represented by the synthetic common base case.

### Galaxy — Helios

Source: https://www.sec.gov/Archives/edgar/data/1859392/000185939226000084/glxy-20260630xpressrelease.htm  
Note details: https://investor.galaxy.com/node/11521/pdf

- Discloses Phase I power delivery of 200 MW gross / 133 MW critical IT, scaling rent commencement through Q2 2026, plus $3.5B-class Phase II notes.
- Published note terms include $3.507B principal at 9.875% due August 1, 2031, 4.00% original-principal annual amortization, with first payment dependent on at least ten months after project completion. The completion milestone is not sufficiently established to declare a verified first amortization date.
- **Material open issues:** construction progress/completion condition, Phase II rent and expenses, the actual indenture's amortization adjustments, and financing waterfall integration. A $1.2B+ average-annual-revenue commentary is **not** an exact project-level lease payment schedule.

### Core Scientific — CoreWeave

Source: https://www.sec.gov/Archives/edgar/data/1839341/000183934126000014/core-20260630.htm

- Discloses $3.30B 7.75% senior secured notes (99.25% issue price), $344.8M DSRA deposit remaining as of June 30, 2026, and semiannual principal amortization at 11.50% of original face starting when qualifying rent and credit-abatement conditions are met.
- The company reports customer construction funding receivables and accrued customer-funded construction, demonstrating why reimbursements cannot safely be assumed to arrive in the same modeling month.
- **Material open issues:** actual rent-credit abatement dates, original notes covenants, customer funding invoicing/collection calendars, deferred revenue treatment, and cash-versus-GAAP operating schedules. Fixed original-principal semiannual note amortization is different from the current monthly bank-loan approximation.

## Unresolved material exceptions / no-go list

1. **B1 — Transaction-level financing integration (BLOCKER):** APLD, Galaxy and Core structured notes and real waterfall terms are not fully represented in the main monthly loan engine. Standalone note arithmetic must not be presented as integrated cash-flow reconciliation.
2. **B2 — Executed lease documentation (BLOCKER):** full phased rent, credits, pass-through/abatement, lender covenants and amendment terms unavailable for most reviewed cases. Public headline total matching is insufficient.
3. **B3 — Independent human signoff (BLOCKER):** no external project-finance model auditor or lender-side reviewer has examined or approved this frozen release.
4. **M1 — Load and tariff realism (MATERIAL):** power costs now use actual calendar-month operating hours, but still assume a flat 24-hour load at a uniform PUE and a modeled $/MWh price. Demand charges, measured curtailment, pass-through contracts and utility invoices have not been reconciled.
5. **M2 — Physical deliverability (MATERIAL):** modeled MW schedules are assumptions; public generation/geographic proximity cannot certify utility service.
6. **M3 — Taxes, accounts and cures (MATERIAL):** CFADS tax/working-capital logic and distressed recovery remain proxies; cash sweeps and intercreditor clauses may differ materially.
7. **M4 — Contract coverage (MATERIAL):** for Galaxy, Cipher, Core, Crusoe and IREN, public disclosures are often floor, portfolio-level, mixed gross/IT, or physical-only. Their simulated equity NPVs are not calibrated project returns.

## Validation gates

- **G0 Input provenance:** PASS for the public source register; transaction verification incomplete.
- **G1 Public headline normalization:** PASS for approximate Applied Digital portfolio campus totals; building-level cash flows unverified.
- **G2 Independent synthetic engine reconciliation:** PASS for the specified 15 Python scenarios / 37,995 monthly field checks; not full executed-contract verification.
- **G3 Targeted adverse computational tests:** PASS for tested error classes; unknown contract-specific defaults remain open.
- **G4 Real transaction reconciliation:** **FAIL/NOT READY** (material contract differences and evidence gaps remain).
- **G5 Independent external assurance:** **NOT STARTED**.

**Conclusion:** v25.8 fixes substantial economic mechanics, but cannot honestly be declared a lender-grade model. No invented missing lender or lease facts are used to force agreement. Continue into contract-driven facility modeling, source-backed benchmark acquisition, and independent external review.
