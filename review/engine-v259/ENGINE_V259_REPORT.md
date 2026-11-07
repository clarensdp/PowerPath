# PowerPath engine v25.9.0: debt-facility integration report

Spec: `FACILITY_SPEC_v259.md`, sections 0 to 11. Package: `engine-v259` at version 25.9.0. This is arithmetic implementation only. **Nothing here is lender-validated**, and the transaction templates are inputs that still need confirmation against executed documents.

## 1. What was implemented

| Area | Where |
|---|---|
| Facility validation, schedule, amortization start, DSRA requirement, DSCR, lock-up, exit payoff, warnings, summary | `src/facilities.cjs` (new, pure) |
| Integration into the monthly cash order (spec §5), per-building rent tracking for §7, rows and summary | `src/underwrite.cjs` |
| Types: `Facility`, `FacilitySummary`, `FacilityScheduleRow`, `FacilityDscrTest`, `EvidenceEntry`, the optional row fields, `summary.facilities` and `summary.facilityPaymentShortfallMonths` | `src/index.d.ts`, `test/types.check.ts` |
| Transaction templates with evidence labels and fact IDs | `data/transactions_v259.json` |
| Demo on a synthetic campus | `scripts/demo_facilities.cjs` (`npm run demo:facilities`) |
| Browser build: `underwrite.cjs` now has a `require('./facilities.cjs')`, so the bundle wraps `facilities.cjs` and serves it through a one-entry require shim. `bundle()` is exported for testing. | `scripts/build_browser.cjs` |
| Tests | `test/facilities.test.cjs` (26 tests), `test/types_drift.test.cjs` (2 tests; one is new), `test/purity.test.cjs` (now also scans `facilities.cjs`) |
| Frozen baseline engine, copied before any edit (md5 `913237555646f8522ead48970dd7b419`, same as the original) | `test/fixtures/underwrite_v2584ca1.cjs` |
| Docs and version | `README.md` (v25.9 section and limitations), `package.json` 25.9.0 |

**Compatibility.** With `facilities` absent or `[]`, nothing changes: no new row or summary keys and no changed arithmetic. Every new code path is guarded by `hasFac`, and where an existing expression gains a term, the original expression is kept verbatim in the `else` branch. `test/golden/stress720.json` is unchanged (its mtime predates this work) and passes. The facilities test compares the **full JSON output** (assumptions, rows, summary, flows) against the frozen baseline engine over 256 cases, and all are identical.

**No transaction terms are hard-coded in the engine.** The only constants are the spec defaults (`priority` 1, `lockupDscr` 1.20, `feePct` 0) and the spec's warning texts.

## 2. Test counts and CI

- `npm run ci` exit status: **0**. It runs format check, strict typecheck, tests, reference parity and browser build.
- After Amendment 1: **49 tests in 18 files, all passing**. That adds 6 in `test/amendment1.test.cjs`; `facilities.test.cjs` is still 26, with updated expectations. CI exit status is 0.
- Before Amendment 1: **43 tests in 17 files, all passing**. That is 26 new in `facilities.test.cjs`, 1 new facilities-present drift check, and the 16 pre-existing tests (golden, purity ×2, red-team ×2, drift, 10 legacy).
- Reference parity: 80,240 checks, max gap 1.42e-12 $M, no failures. These cases have no facilities; the Python reference was not modified.
- The facility tests cover:
  - OID and proceeds; stub first coupon (including ISO dates and the integer-month precedence); semiannual payment months.
  - `pctOriginalPerYear` installments; `explicit` schedules (j-indexing, capping at the balance, 0 beyond the list); the balloon at maturity; bullets.
  - `afterFirstRent` (gross-before-credit R) and `afterFinalCommencement` (C, K with building and global credit months, power-limited C, unresolved case and its warning).
  - Construction halt: a facility that is unresolved on the original plan resolves after the halt reallocates a shared tranche, while an already-set A stays unchanged.
  - Each DSRA type, including initial funding, release, sponsor top-up, a capped-sponsor deficiency, and draws before sponsor (balance, debt-service and remaining-shortfall caps, and priority order).
  - Lock-up from the DSCR test and from a DSRA deficiency; exit payoff priority and `unpaidAtExit`; a final-month balloon with an unfunded gap.
  - 27 validation cases; exact warning texts.
  - Identities over 8 varied scenarios: shared tranches with two priorities, renewal policy, tenant power pass-through and working-capital lag, delays/overrun/rate shock, capped sponsor with funding default and halt, gross basis with contracted exit, and halt re-resolution.
  - Determinism and no input mutation; byte-identity against the baseline; templates; the demo; the browser bundle.

## 3. Spec ambiguities and how they were resolved

These are listed so the parallel independent reference can reconcile them. Where a choice was required, the most literal reading was taken.

### Amortization start (§4)
1. **[SUPERSEDED by Amendment 1 AM1, see §4.]** **Resolution is forward-looking over the whole modeled schedule.** "In the physical schedule as modeled at that time" is read as the full horizon (months 1..`months`) of the schedule as currently computed, not only months up to and including the current one.
   - Resolution is attempted at the **start of every model month from month 1**, including months before issuance, using the current `physicalByMonth`. After a construction halt, the schedule is recomputed at the end of that month, so the next month sees the new schedule. Once A is set it never changes.
   - **Consequence:** whenever the original plan contains the triggering event, A resolves in month 1. So `constructionThenNextPeriod` uses `constructionAmountM` only while A is unresolvable on the then-current schedule. It does not switch at first rent or at commencement.
   - In the demo, Galaxy's 285.05 construction DSRA is therefore never applied: its DSRA is nextPeriod from issuance, peaking at 243.3. A "realized-events" reading (R ≤ current month) would switch at the actual commencement instead. This is the single most consequential choice and should be reconciled first.
2. `afterFirstRent`: R is the first month in 1..`months` where any collateral building's **gross** rent is > 0. That includes expected-value renewal rent and is measured before credits. A = min{p ∈ P : p > R + offset}, a strict inequality as written.
3. `afterFinalCommencement`:
   - C is the first month in 1..`months` where every collateral building's rented MW equals its IT MW, within an absolute tolerance of **1e-9 MW**.
   - K is the maximum, over collateral buildings, of the building's latest cohort start in the modeled schedule plus its credit months (`b.tenantCreditMonths ?? a.tenantCreditMonths ?? 0`). Credit months count even when the credit percentage is 0. A building with no cohorts is skipped in K, which cannot occur once C exists.
   - A = min{p ∈ P : p ≥ max(C, K) + offset}.
4. If no p ∈ P satisfies the condition, A stays unresolved. `fixedMonth` is set at validation and may be any integer month, including one that is not in P.

### Scheduled principal, maturity and balloon (§4, §6, §7)
5. **Scheduled installment at maturity.** §4 defines scheduled principal only for p < maturity. But §4's `balloonM` refers to "that payment's scheduled installment", and §7 says "the scheduled installment at maturity is included". So the installment formula is evaluated at maturity as well: `pct` gives min(B_open, face×annualPct/200), and `explicit` gives min(B_open, amountsM[j]), in both cases only when A is set and maturity ≥ A.
   - Principal paid at maturity is the full balance, and `balloonM` = balance − installment.
   - The maturity DSCR denominator is interest plus that installment.
   - A `nextPeriod` DSRA whose next payment is the maturity includes the installment but not the balloon.
6. "(0 if not amortizing)" is read as **the installment is 0**, so `balloonM` is the whole remaining balance for `none`, `unknown`, an unresolved A, or A after maturity. If the balance is already 0 before maturity, `balloonM` is 0.
7. `explicit` uses a **zero-based** j over the payment months ≥ A, and the maturity month counts.

### Interest and schedule (§2, §3, §8)
8. There is no accrual in the issue month. Accrual runs for issue < m ≤ maturity with B_open > 0. Interest is paid on every p ∈ P, even after full amortization, when it is 0.
9. **Schedule `opening` in the issue month is `faceM`**, the balance after issuance, so that the §8 identity closing = opening − principalPaid holds in every row. §3's B_open (the balance at the end of m−1) is used only for accrual, which is 0 in the issue month anyway.
10. The schedule carries three extension fields beyond the §8 list, declared in `FacilityScheduleRow`: `scheduledPrincipal`, `dsraMovement` (deposits +, releases and draws −) and `dsraDraw`. These make the DSRA roll and the DSCR denominators testable per facility.

### Cash order (§5)
11. **`uses` is extended; `loanSources` is not.** The `uses` row includes `notesFees` and the facility interest and principal due, following §5.2. `loanSources` keeps its generic meaning (draws plus refinance proceeds, so 0). `notesProceeds` is added separately to `preFundingCash` and to the residual.
12. `liquidityBreach` still uses the (extended) `preFundingCash`, before DSRA draws.
13. A DSRA draw (§5.4) per facility is min(DSRA balance, that facility's interestPaid + principalPaid this month, remaining shortfall), in priority order. A facility with no debt service due cannot be drawn.
14. Facility payments are never reduced. A shortfall that remains after the DSRA and the sponsor becomes `unfundedGapM` (an existing funding default, with the existing halt policy). Facility payments continue after a default: there is no acceleration and no arrears.
15. DSRA funding (§5.6):
    - Cash above `minLiquidity` is used first.
    - The sponsor is drawn only if the remaining requirement is **> 1e-8**, mirroring the existing base-reserve rule.
    - A deficiency is recorded when Q − DSRA > 1e-8.
    - A sponsor-funded deposit goes straight to the DSRA: it is counted in `sponsorContribution` and in the DSRA movement, and is cash-neutral.
    - Facilities are processed in priority order; any excess is released to cash.
16. Q(m) is 0 before issuance and whenever the closing balance is ≤ 0. The issue-month funding uses Q(issueMonth).
17. **Lock-up (§5.8)** is OR'ed into the existing `locked` expression. The conditions are:
    - any facility with a DSRA deficiency this month;
    - any facility whose most recent DSCR test is in force and < `lockupDscr`;
    - an unfunded gap this month (already implied by the existing `defaulted`, which is sticky).

    A test at p is in force for months p..(next p − 1). **The final (maturity) test is in force only in its own month.** A null DSCR never locks.
18. **[SUPERSEDED by AM3, see §4.]** **Distributions are not locked before the first DSCR test** unless another condition holds, so unused note proceeds in the issue month are distributed as excess cash under `distributionPolicy: 'excess'`. This is literal behaviour, not a design choice, and is documented as a limitation.
19. **[Amended by AM4, see §4: no longer vacuous when maturity = `months`.]** **Exit (§5.10) is vacuous under §1 validation.** Since maturity ≤ `months` and payments are always recorded as made, every facility balance and accrual is 0 at exit. For the same reason the DSRA requirement is 0 once the balance is 0, so DSRAs are already released in step 6.
    - Step 10 is still implemented generically: DSRAs are released into cash, then `exitPayoff` pays accrued interest and then principal in priority order from max(0, cash + terminal + collections + base reserve).
    - Unpaid amounts are added to `unpaidDebtAtExitM` and set `defaulted`.
    - Exit payments would be added to the row and schedule `interestPaid`, `principalPaid` and `facilityDebtService`, and taken into the residual, but **not** into `uses`.
    - The helper is unit-tested directly with outstanding balances.
20. `facilityPaymentShortfallMonths` lists months with `unfundedGapM` > 1e-8 while facility interest plus principal due (§5.2, before any exit payoff) is > 0.

### DSCR and CFADS allocation (§7)
21. `cfadsShare(m)` = cfads(m) × (collateral lease revenue) / (all-building lease revenue).
    - Both numerator and denominator are sums of per-building (gross − credits) from the same physical month the row uses.
    - The share is 0 when the denominator is ≤ 0.
    - It is computed every month from month 1, **including before issuance**, because the trailing window can reach back before the issue month.
22. The window is Σ over k = p−5..p, ascending, of cfadsShare(k). Months k < 1 contribute 0.
23. DSCR is null when the denominator is ≤ 0. `minDscr` is the minimum over non-null tests, or null if there are none. Null tests are kept in `dscrTests`.
24. `lockupMonths` (per facility) lists months where that facility's own DSRA deficiency or in-force DSCR test triggered a lock. Locks caused only by an unfunded gap are not attributed to a facility; the row field `facilityLockup` (an extension) shows them.

### Inputs, validation and outputs (§1, §8, §9)
25. **Dates.** The format must be `YYYY-MM-DD` with month 1..12 and day 1..31; the day is otherwise ignored. Integer month fields must be integers and take precedence. A missing month and missing date together throw.
26. **Validations beyond the literal §1 list (all throw):**
    - `name` must be a string, `type` must be `'fixed_note'`, and `faceM` must be > 0.
    - The ranges for coupon, price and fee from the §1 field list are enforced.
    - `priority` must be an integer, `offsetMonths` an integer ≥ 0, DSRA amounts finite and ≥ 0, and `lockupDscr` finite and ≥ 0.
    - Evidence labels must be in the five-label vocabulary.
    - Duplicate collateral buildings within one facility are rejected.
    - A non-array `facilities` is rejected.
    - A facility with `modelable: false` is refused, so templates with unknown dates cannot be modeled by accident.
27. The ltc/mezz check uses the merged assumptions, so omitting `ltc` (default 65) with facilities throws.
28. **Facility fields appear only when facilities are modeled**, so that the absent case stays byte-identical. This applies to the row fields and the two summary keys (declared optional in `index.d.ts`). When facilities are present they are emitted on every row. The extension row field `facilityLockup` is included.
29. Existing summary fields (`interestM`, `principalM`, `feesM`, `peakDebtM`, `minDSCR`, `endingDebtM`, `dsraDeficiencyMonths` and so on) keep their generic-debt meaning. Facility totals are reported only in `summary.facilities[]`.
30. **Warnings.**
    - Each facility's warnings are listed in its `warnings` array and appended to `creditWarnings` after all existing warnings, in input order. Within a facility the order is: derived start, unknown amortization, never resolved, then evidence terms in key order.
    - The two `FACILITIES:` warnings are added once, to `creditWarnings` only.
    - The "derived" warning fires for any `afterFirstRent` or `afterFinalCommencement` start, whatever the amortization type.
    - "Never resolved" fires whenever such a start was given and A is still null at the end.
    - The existing generic warning 'Fixed-rate transaction notes … not contract-integrated' is still emitted unchanged, because existing behaviour was not changed.
31. Coupons are fixed: `rateShockPct` and `rateShockAllFacilities` (which refer to the generic facilities) do not apply to notes.
32. The schedule covers every month from `issueMonth` to `months`, so it includes months after maturity, with zeros.

### Templates (§10)
33. **`apld_computeco_2030` is treated as modelable.** Its dates are stated in full (issue 2025-11-20, payments Jun 15 / Dec 15 from 2026-06-15, maturity 2030-12-15). The spec labels them "Unknown, not re-confirmed", and that label is carried as evidence (`firstPaymentDate` and `maturityDate` are `Unknown`), so warnings are emitted. The rule "where dates are Unknown → modelable false" is applied to templates whose date **values** are unknown: `apld_computeco3_2031` and `apld_computeco2_2031`. If the reconciler reads "Unknown" as the label, APLD 2030 flips to `modelable: false`.
    - APLD 2030 issues before 2026, so it needs a campus calendar that starts by 2025-11; the demo uses 2025-01.
    - Its amortization is `unknown` with `amortStart` omitted. The bundle's asserted 2027-12-15 start is recorded only as `Unknown` evidence.
34. **Labels not stated in the spec** (face, coupon, price, most dates, collateral scope) are recorded as `Public approximate` with source "FACILITY_SPEC_v259 s.10 (label not stated)" and **no fact ID**; none were invented. Fee (0%) and `lockupDscr` (1.20) are `Assumption`.
    - The fact IDs are exactly those the spec gives: F14 (APLD 2030 collateral), F34 (APLD 2030 DSRA), F46 (ComputeCo 3 collateral), F47 (ComputeCo 2 collateral), F37 (Galaxy DSRA) and F39 (Core DSRA).
    - Core's DSRA, "Executed est.", is labelled `Executed` as the spec says, and its source notes that the amount is an estimate. That means it raises **no** warning, which may need reconciling.
    - Galaxy's `amortStart` takes the amortization clause's label (Public approximate), and Core's takes "Executed, 8-K".
    - The DSRA of the non-modelable notes is a `none` placeholder labelled `Unknown`.
35. Template building names (`ELN-02`, `Phase II`, `Austin` and so on) are scope labels. A campus has to define buildings with those names; the demo builds synthetic ones.

## 4. Amendment 1 (FACILITY_SPEC_v259_AMENDMENT_1.md)

AM1 to AM5 are implemented in `src/facilities.cjs` (`updateEvents`, `monthFlows`, `dsraRequirement`, `exitPayoff`, `facilitySummary`) and `src/underwrite.cjs` (the construction lock-up in step 8, and the `facilityConstructionLockup` row field). Facilities-absent output is still byte-identical, and the golden snapshot is unchanged.

**Failing-before proof.** The pre-amendment source is frozen in `test/fixtures/underwrite_v259_pre_am1/` (`underwrite.cjs` and `facilities.cjs`). Each AM1 to AM4 test in `test/amendment1.test.cjs` runs its checks on both engines: they must pass on the current one and throw on the frozen one. The economic assertions run first, so the pre-amendment failure is substantive, not a missing new field. Those failures are:
- AM1: an installment is paid on halted collateral at month 32.
- AM2: no construction DSRA amount in month 2.
- AM3: a distribution is paid in month 2 during construction.
- AM4: the DSRA is drawn for a final-month balloon.

Tests that encoded pre-amendment behaviour in `test/facilities.test.cjs` were updated to the amended semantics: the halt, `constructionThenNextPeriod`, DSRA draw, DSCR lock-up and final-month maturity tests. The final-month test became a pre-horizon shortfall test, because the final-month case is now covered by AM4.

**Effect on the synthetic demo.** Galaxy's DSRA now peaks at the 285.05 construction amount, and Core's at 343. Sponsor contributions fall, because note proceeds fund capex instead of being distributed.

### New ambiguity resolutions under Amendment 1
A1. **Event detection timing.** Events are evaluated at the start of month m on the schedule current at month m. They are scanned over months 1..m only, and an event in month m itself counts (E ≤ m), so E is recognised in month E. Once E has occurred it is fixed. A halt recomputes the schedule at the end of its month, and only months after the halt can change.

A2. **`afterFinalCommencement`.** E = T = max(C, K) occurs only once C ≤ m **and** T ≤ m. If C has occurred but K (latest cohort start plus credit months) is still in the future, resolution waits until month T. K uses the current schedule's cohorts; none can start after C.

A3. **E occurred but no payment month qualifies.** A stays null while E (`constructionEndMonth`) is still reported. The "never resolved" warning fires whenever A is null at the end and a derived start was given.

A4. **`fixedMonth`.** E is the given month, reported as `constructionEndMonth` even if it lies beyond the horizon. A is known from month 1. A `constructionThenNextPeriod` DSRA therefore uses the construction amount for m < E.

A5. **AM2 after E with A unresolved.** The `nextPeriod` requirement counts scheduled principal as 0.

A6. **AM3 construction lock-up.**
- L (`constructionLockupEndMonth`) is tracked from month 1, regardless of the issue month. It is the first month in which every collateral building has gross rent > 0 (before credits), and it is fixed once it has occurred.
- In month m a facility locks distributions if its closing balance after step 2 is > 0 and L has not occurred by m. The issue month is locked, and month L itself is not.
- The construction lock-up months are **included in that facility's §8 `lockupMonths`** and in the extension row field `facilityLockup`. `facilityConstructionLockup` is true if any facility is in construction lock-up.

A7. **AM4 final-month maturity** (applies only when maturityMonth = `months`):
- That month's accrual happens as normal. Step 2 pays no interest or principal for the facility, so it is excluded from `uses`, from the step-4 DSRA draw cap and from `facilityPaymentShortfallMonths`.
- The DSCR test runs with denominator = interest due (all accrued, including that month) plus the scheduled installment at maturity; the balloon is excluded.
- Step 6 computes Q normally with the balance still outstanding. A `fixed` DSRA keeps `amountM`. A `nextPeriod` DSRA, or a `constructionThenNextPeriod` DSRA after E, has Q = 0 because there is no later payment month, so it is released to cash. Before E it keeps the construction amount.
- Every facility DSRA is then released into the exit pool.
- The pool is max(0, cash + terminalProceeds + exitCollections + base reserve), after the DSRA release. Any unfunded gap that left cash below zero therefore reduces it.
- Payment is in priority order, accrued interest first, then principal.
- Exit payments are recorded in that month's schedule `interestPaid`/`principalPaid` and in the row's `facilityInterestPaid`/`facilityPrincipalPaid`/`facilityDebtService`, and taken into the sources/uses residual. They are not added to `uses`.
- The unpaid principal plus interest goes to `unpaidAtExitM` and to `summary.unpaidDebtAtExitM`, and sets `defaulted`. Under the existing rule, residual cash is then not distributed.

A8. **`balloonM` under AM4** is max(0, principal actually paid at exit − the scheduled installment at maturity). It is floored at 0 for a partial payment smaller than the installment. The alternative reading is the contractual balloon (balance due − installment); the two differ only when the exit pool cannot pay the full principal.

A9. **Field names (AM5).** All §8 fields are emitted under their exact names, plus `constructionEndMonth`, `constructionLockupEndMonth` and `rows[].facilityConstructionLockup`. The extension fields are diagnostic and outside reconciliation: rows `facilityLockup`, and schedule `scheduledPrincipal`, `dsraMovement` and `dsraDraw`.

A10. **Templates.** `data/transactions_v259.json` needed no change: AM1 to AM4 change the engine's semantics, not any term.

## 5. Other notes
- `dist/PowerPath_engine_package_build.html` is a prebuilt artifact that the build script does not regenerate, so it was left as is. `dist/powerpath-engine.js` and `SHA256SUMS` were regenerated by CI.
- `CI_LOG.txt` was replaced with the v25.9.0 run.
- `reference-v259` and `ui-v259` were not read or written.
