# PowerPath v25.9 Python reference — facility interpretation notes

Built only from `FACILITY_SPEC_v259.md` and the base Python reference (`powerpath_reference.py`). No engine source was opened.

## Files
| File | Purpose |
|---|---|
| `reference_v259.py` | `powerpath_reference.py` plus §0–§9 facilities. The base code is verbatim; facility hooks run only when `facilities` is non-empty. |
| `cases_v259.json` | 19 facility cases (F01–F19; F17–F19 added for Amendment 1), all with `ltc: 0, mezzLtcPct: 0`, 3 × 100 MW (F15 has one 130 MW gross building), notes $600M–$3.3B, coupons 7.25–10.5%. |
| `self_checks.py` | Checks equality with the base model, facility identities, scenario coverage, validation and Amendment 1 (group E). It takes an optional module path, so it can be run against another build. |
| `out_v259.json` | Reference output for `cases_v259.json`. |

## Run
```
cd /home/claude/work/reference-v259
python3 -I reference_v259.py cases_v259.json out_v259.json
python3 -I reference_v259.py cases.json out.json                                    # base cases: byte-identical to powerpath_reference.py
python3 -I self_checks.py
```
Output for each case is `{rows, npvM, defaulted, facilities, summary:{facilities, creditWarnings, facilityPaymentShortfallMonths, unpaidDebtAtExitM}}`. The `--balloon-in-waterfall` flag has been removed, because AM4 is now the only behaviour. If a facility case fails validation, the output is `{error}`.

## Case coverage
| Case | Covers |
|---|---|
| F01 | `none` bullet, no amortStart, no DSRA, fee 1.5%, price 99 |
| F02 | `unknown` amortization; dates as ISO strings (issue 2026-11-20 maps to month 11, etc.); fixedMonth by date; fixed DSRA 177; evidence warnings |
| F03 | `pctOriginalPerYear` with `fixedMonth` (month field beats date field); `nextPeriod` DSRA |
| F04 | `explicit` with `afterFirstRent` offset 6; `constructionThenNextPeriod` |
| F05 | `pctOriginalPerYear` with `afterFinalCommencement` offset 1; tenant rent credits (case 6 months at 50%, B3 override 12 months), so K > C |
| F06 | Debt service greater than CFADS; DSRA drawn before sponsor support |
| F07 | Capped sponsor (800 after AM3; it was 1700) causes a funding default in month 30 and a halt; B3 is abandoned, so E and L never occur and the construction lock never lifts; DSRA deficiencies and payment-shortfall months |
| F08 | Two facilities with different priority (junior listed first) and collateral (B1+B2 vs B3); different payment calendars |
| F09 | Shared plus dedicated power tranches gate full commencement |
| F10 | 48-month leases with the `renew` policy; explicit amortization; lockupDscr 1.35 |
| F11 | `tenant_direct` power at case level, `reimbursed` override on B2 |
| F12 | `delayMonths` 6 plus 10% overrun; explicit amortization |
| F13 | Maturity equals horizon; exit value too low, so unpaid at exit and defaulted |
| F14 | Priority tie (input order kept); OID and fee; explicit list shorter than the schedule; issue month 13 |
| F15 | Balloon paid in the waterfall before the horizon (month 96); gross capacity basis building |
| F16 | `none` amortization with a trigger amortStart; `constructionThenNextPeriod` switches at E=31 |
| F17 | AM2: `constructionThenNextPeriod` with `fixedMonth` 40; construction amount 140 until month 39, nextPeriod from month 40 |
| F18 | AM3: collateral B1+B3, so L = 31; proceeds retained, no sponsor money until cash runs down, distributions locked for months 1–30 and resume afterwards |
| F19 | AM4: two facilities maturing at month 120 with exit value 1800; senior (priority 1) repaid in full, junior partly recovered ($123.8M unpaid), so defaulted |

## Ambiguity resolutions (compare these against the engine)

Amendment 1 supersedes A01, A05, A06, A10 (horizon-month part) and A15; see the Amendment 1 section at the end.

**A01 — [superseded by AM4: interest is now deferred too] A maturity balloon in the final month is repaid at exit (high impact).** Read literally, every `maturityMonth ≤ months` is fully repaid in waterfall step 2, so §5.10 would always find zero facility debt and `unpaidAtExitM` could never be non-zero. Chosen reading: if `maturityMonth == months`, step 2 pays the interest plus the scheduled installment only. The remaining balance is paid in step 10 from exit availability, and any shortfall becomes `unpaidAtExitM`. If `maturityMonth < months`, the balloon is paid in step 2 as the spec says.

**A02 — Date and month fields.**
- An integer month field wins whenever it is non-null, even if a date is also present.
- A float with an integer value is accepted; a non-integer throws.
- A `null` field counts as absent.
- The date must match `YYYY-MM-DD` with month 1..12. The day is neither validated nor used.
- `amortStart.fixedMonth` uses `month` / `date`.

**A03 — Collateral names.** Duplicate building names in one facility's `buildings` list are de-duplicated, not rejected.

**A04 — Issue month.**
- In the schedule, `opening` at issueMonth is faceM, because the balance is set at issuance. The identity closing = opening − principal therefore holds from issue onward.
- There is no accrual in the issue month.
- Proceeds and fees flow in step 1/2 of the issue month.
- The DSRA is funded in step 6 of the same month. A step-4 draw cannot happen in the issue month because the opening DSRA is 0.

**A05 — [adopted and extended by AM1] When amortization start is evaluated.**
- It is evaluated at the start of each month m, before that month's payments, on the physical schedule as rebuilt after any halt up to m−1.
- Evaluation starts at month 1, including months before issue.
- There is no look-ahead: A resolves only once the trigger event has happened on the current schedule (R ≤ m for afterFirstRent, C ≤ m for afterFinalCommencement).
- The resolution month is therefore R or C (reported as `amortStartResolvedInMonth`).
- Consequence: a halt cannot move a resolution that has already happened. It can only stop one from happening (F07).

**A06 — [superseded by AM2 for the construction DSRA] fixedMonth.**
- A fixedMonth start counts as resolved at the first evaluation (month 1).
- So `constructionThenNextPeriod` combined with `fixedMonth` uses nextPeriod from issuance, and the construction amount never applies.
- A does not have to be a payment month.

**A07 — No payment month fits.** If the trigger has happened but no p ∈ P satisfies the rule, A stays unresolved: no amortization, the "never resolved" warning, and `constructionThenNextPeriod` keeps the construction amount.

**A08 — afterFinalCommencement details.**
- C is the first month k ≥ 1 in which, for every collateral building, rented MW ≥ IT MW − 1e-9.
- Rented MW is the per-building rented MW of the physical schedule, so after lease expiry it includes the renewal-probability share.
- IT MW is converted for gross basis (itMW/PUE).
- K = max over collateral buildings of (latest cohort start with start ≤ C) + creditMonths. That is the first month without credit, not the last credit month.
- creditMonths is `b.tenantCreditMonths ?? a.tenantCreditMonths ?? 0`, and it applies even when tenantRentCreditPct is 0.
- For afterFirstRent, R is the first k ≥ 1 in which per-building gross rent (including renewal rent, before credits) > 0 for any collateral building.

**A09 — Scheduled installment at maturity.** §4 restricts scheduled principal to p < maturityMonth, while §4 (balloon) and §7 refer to a "scheduled installment at maturity". Chosen reading: the installment formula also applies at p = maturity (A set, p ≥ A, capped at the opening balance). It is used in three places:
- the DSCR denominator at maturity
- nextPeriod Q when q = maturity
- balloon = principal paid − installment

Other formula details:
- For `explicit`, j = the number of payment months in [A, p) (0-based), and amounts beyond the list are 0.
- For `pctOriginalPerYear`, the installment is face × annualPct / 200 per semiannual payment.

**A10 — balloonM.**
- For non-amortizing facilities (none/unknown, or A unresolved) the installment is 0, so balloonM is the full maturity principal, not 0. I read "(0 if not amortizing)" as referring to the installment.
- balloonM is the principal actually paid. Under A01 that is the amount repaid at exit, excluding any unpaid part.

**A11 — Payment month with nothing owed.** If both balance and accrued are 0, the payments are 0 and the DSCR test is still recorded, with value null.

**A12 — cfadsShare.**
- The lease-revenue share uses the current schedule's per-building (gross rent including renewal rent − credits).
- The sign of CFADS is kept: negative CFADS gives a negative share.
- A denominator |den| ≤ 1e-12 gives 0.
- The share is computed for every month from 1, including before issue.

**A13 — DSCR test.**
- The window is m = p−5..p, clipped to ≥ 1, and includes months before issue.
- The denominator is the waterfall interest paid at p plus the installment (A09). Exit payments are excluded.
- A denominator ≤ 0 gives null.
- There is one test per p ∈ P.

**A14 — When a DSCR lock is in force.**
- The comparison is strict (dscr < lockupDscr).
- The lock runs from the test month through the month before the next payment month.
- The maturity test is in force only in the maturity month.
- A null DSCR never locks, and there is no DSCR lock before the first test.

**A15 — [superseded by AM3] No implicit lock while facilities are outstanding (high impact).** The base lock list ties "outstanding debt / dscr null" only to the generic loan. §5.8 adds only the four listed conditions. So when no other lock applies, excess note proceeds in the issue month are distributed. For example, F01 month 2 distributes $1.42B, and capex is then sponsor-funded. The engine may instead lock during construction or before the first test; that would change sponsor flows and NPV.

Two smaller points:
- The base `default` flag is sticky, so distributions stay locked after any funding default.
- Per-facility `lockupMonths` lists only months where that facility's own condition (DSRA deficiency, or a DSCR in force below its lockupDscr) holds. Global locks are not included.

**A16 — Warnings.**
- "never resolved" is emitted when amortStart is provided and A is still null at the end, whatever the amortization type (including none/unknown). It is not emitted when amortStart is omitted.
- "derived from modeled commencement" is always emitted for the two trigger types.
- Order: per facility in input order (derived-start, unknown, never-resolved, then evidence in key order), followed by the two FACILITIES warnings once.
- If an evidence label is missing, the text is `is None, not Executed`.

**A17 — Ordering.**
- Execution order is a stable sort on (priority, input index).
- `facilities[]` in the outputs is in input order.
- Priority affects step-4 draws, step-6 top-up claims on cash and sponsor, and exit. It does not affect step 2, where all payments are recorded as made.

**A18 — Step-4 draws.**
- The shortfall is minLiquidity − preFundingCash, after capex and all facilities' debt service.
- Each facility's draw is capped by its own step-2 interest + principal, including a non-final balloon, whatever caused the shortfall.
- `preFundingCash` in the rows is the value before draws.

**A19 — Step-6 DSRA funding.**
- Q(m) is computed at the end of m from the post-payment balance and accrued, using A as resolved at the start of m.
- Top-up comes from cash above minLiquidity first, then sponsor.
- A DSRA drawn in step 4 is refilled in step 6 of the same month (by sponsor if there is no cash). With an uncapped sponsor, draw-before-sponsor is therefore only a timing and classification effect.
- Deficiency means Q − DSRA > 1e-8 after both sources.
- Sponsor top-ups go straight into the DSRA and are included in `sponsorContribution`.
- For nextPeriod, the installment at q uses B_close(m) as q's opening balance.

**A20 — "0 once the balance is 0".** For every DSRA type, Q = 0 when the closing balance ≤ 0, so a fixed DSRA is released in the maturity month. Under A01 the balance is still > 0 in the final month, so the fixed amount is held until the exit release.

**A21 — Unfunded gap and shortfall months.**
- `unfundedGapM` = minLiquidity − cash after step 5, when > 1e-8 (the same threshold as the base default).
- It triggers the existing funding default and halt. A DSRA or base-reserve deficiency does not.
- `facilityPaymentShortfallMonths` lists months with a gap > 0 and step-2 facility debt service > 0.

**A22 — Exit.**
- available = max(0, cash + terminal + collections + base reserve + ΣDSRA). The base clip at 0 is kept.
- Facilities are paid in priority order, accrued interest then principal for each facility before moving to the next. Generic debt (always 0) comes after.
- Exit payments are included in that month's `facilityInterestPaid/PrincipalPaid/DebtService` and in the schedule `interestPaid/principalPaid`, and are also shown separately (`exitInterestPaid/exitPrincipalPaid`, row `facilityExitPaid`).
- The DSRA released at exit is booked as `dsraRelease` in month `months`.
- Any unpaid amount sets `defaulted`. The remaining cash is distributed only if nothing is defaulted; under the base rule, an earlier funding default also blocks it.

**A23 — Final month.** The full waterfall, including DSRA and base-reserve top-ups (with sponsor), runs before exit in the final month, even though everything is released at exit.

**A24 — sourcesUsesResidual.**
- pool = cash + base reserve + ΣDSRA.
- residual = open pool + cfads + tenantCashReceipt + generic draws/refi + notesProceeds + sponsorContribution + exitProceeds − capex − generic fees/interest/principal − notesFees − facilityDebtService − distribution − close pool.

**A25 — Row fields.**
- New fields are added only when facilities are present, which keeps the no-facility output byte-identical.
- Extra diagnostic fields: `facilityDsraDeposit`, `facilityDsraRelease`, `facilityExitPaid`, `preFundingCash`, `unfundedGapM`, `exitProceeds`, `distributionLocked`.
- `facilityDsraMovement` = deposits − releases − draws.
- The schedule also carries `accruedStart`, `issued`, `scheduledPrincipal`, `dsraOpening/Deposit/SponsorDeposit/Release/Draw`, `dsraDeficiency` and `dscr`.

**A26 — Validation beyond the §1 list.** The reference also throws on:
- type ≠ 'fixed_note'
- faceM ≤ 0
- coupon, price or fee out of range
- non-integer priority
- non-integer or negative offsetMonths
- amortStart missing for pct/explicit
- unknown amortization, amortStart or DSRA types
- non-finite or negative DSRA amounts
- non-finite lockupDscr

Error texts match the engine only for the ltc/mezz message. Errors are `ValueError`.

**A27 — Accrual.** Accrual is on B_open(m) = closing(m−1) for issue < m ≤ maturity and stops after maturity. Under A01, a balance unpaid at exit does not accrue further, because the horizon ends.

**A28 — OID.** OID = face − proceeds is reported and not amortized. The fee is a cash use in the issue month.

**A29 — Halt.** The halt uses the base rule: buildings unfinished at the default month are abandoned from m+1. Their past rent is unchanged by the rebuild, so earlier trigger months stay valid.

**A30 — Sponsor cap.** One cap covers, in order within a month, step-5 support, then facility DSRA top-ups (priority order), then base-reserve top-ups.

## Amendment 1 (FACILITY_SPEC_v259_AMENDMENT_1.md): implementation and remaining readings

**What changed in the code**
- **AM1.** Each facility tracks the event month E (`constructionEndMonth`).
  - `afterFirstRent`: E = R.
  - `afterFinalCommencement`: E = T = max(C, K). A now resolves only once T ≤ m. Before, it resolved at C; in F05, A now resolves at 43, not 31, and A = 47 is unchanged.
  - `fixedMonth`: E = A = the given month, known from month 1.
  - amortStart omitted: E = null.
  - E is evaluated at the start of each month from month 1 and is never re-evaluated once set.
- **AM2.** For `constructionThenNextPeriod`, Q = constructionAmountM while E is null or m < E, and nextPeriod from month E onward. Installments use A if it is resolved, otherwise 0. Consequences:
  - With `afterFirstRent`, the switch happens at R even though A comes later. This applies to F04, F14 and F16.
  - With `fixedMonth`, the switch happens at the given month (F17).
- **AM3.** L (`constructionLockupEndMonth`) is the first month k ≤ m in which every collateral building has gross rent > 0 in the same month.
  - While L has not occurred and the facility's balance after this month's step-2 payments is > 0, distributions are locked.
  - The row field `facilityConstructionLockup` is true if any facility is in construction lock that month.
- **AM4.** If maturityMonth equals the horizon month, nothing is paid in step 2 for that facility in that month: neither interest nor principal. Before, my A01 reading paid the interest and installment in step 2. Settlement in that month works as follows:
  - Because the step-2 debt service is 0, the step-4 DSRA draw cap is 0.
  - The DSCR test uses interest due (accrued, including the month's own accrual) plus the scheduled installment.
  - In the exit waterfall each facility gets interest then principal, in priority order. Any shortfall goes to `unpaidAtExitM` / `unpaidDebtAtExitM` and sets `defaulted`.
- **AM5.** All §8 names are emitted, plus `constructionEndMonth`, `constructionLockupEndMonth` and `rows[].facilityConstructionLockup`. Self-check group E verifies they are present.

**Readings the amendment leaves open (please compare)**
- **AM1-a.** For `afterFinalCommencement`, K is recomputed each month from the current schedule until T ≤ m. The cohorts for K are those starting at or before C.
- **AM1-b.** For `fixedMonth`, E is the given month even if it is not a payment month or is beyond the horizon. Before month E, `constructionThenNextPeriod` uses the construction amount.
- **AM1-c.** If E has occurred but no payment month satisfies the rule, E is reported and A stays null, with the "never resolved" warning.
- **AM3-a.** "Balance > 0" is tested on the balance after this month's step-2 payments. Before issue there is no lock; from the issue month the lock applies.
- **AM3-b.** L is tracked from month 1, whether or not the facility has been issued yet. Once L occurs the lock ends permanently, even if a collateral building later has zero rent (for example, lease expiry with vacate).
- **AM3-c.** A halt that abandons a collateral building means L never occurs, so the lock is permanent while the facility is outstanding (F07).
- **AM3-d.** The construction lock counts in that facility's `lockupMonths`.
- **AM4-a.** Step 6 still runs normally in the horizon month. A `nextPeriod` DSRA has Q = 0 there (no next payment month), so it is released to cash in step 6, where it can fund the base-reserve top-up before sponsor support. A `fixed` DSRA keeps Q = amountM (balance > 0), may be topped up, and is then released into the exit pool. I did not skip step 6 for deferred facilities. If the engine releases straight to the exit pool, sponsor support in that month may differ (F19 junior).
- **AM4-b.** `balloonM` = max(0, principal paid at exit − scheduled installment at maturity). Unpaid principal is excluded.
- **AM4-c.** Exit payments appear in that month's `facilityInterestPaid`, `facilityPrincipalPaid` and `facilityDebtService`, and in the schedule `interestPaid` and `principalPaid`. The separate fields `exitInterestPaid` and `exitPrincipalPaid` show the same amounts.
- **AM4-d.** `facilityPaymentShortfallMonths` considers only step-2 debt service, so a deferred horizon-month maturity never creates a shortfall month. Exit shortfalls show up in `unpaidDebtAtExitM` instead.

**Tests failing before and passing after.** `python3 -I self_checks.py <module>` runs the checks against any build. Against the pre-amendment logic, given the new field names through a shim, these checks fail:
- AM1: F05 resolves at C, not T; "A from E".
- AM2: 38 construction-DSRA month checks, plus the F05 and F17 switch checks.
- AM3: about 2,500 lock-up flag and distribution checks, the F18 L = 31 check, and the F18 proceeds-retained check.
- AM4: horizon-month step-2 payments, DSRA draw, unpaid-at-exit, and F13 interest at exit.

Against the pre-amendment file as it stands, every case fails the AM5 field check. The current build passes all of them.
