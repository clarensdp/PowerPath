# FINANCIAL_ENGINE_CHANGELOG — PowerPath v27.1.0

**Scope:** financial-engine remediation (RT-A02), canonical delay economics (RT-E04b), and a new instrument engine for the Core Scientific notes. The legacy engine `engine/underwrite25.js` is unchanged; its SHA-256 is still `c4e2a090…ce29`.

**Author:** Claude (AI), acting in the CFO / model-review role the brief requested. Every financial convention below that has legal, accounting or credit consequences is a **provisional screening assumption that needs qualified human approval** (see §6).

## 1. Versioning: nothing historical was overwritten

| Item | v27.0 | v27.1 |
|---|---|---|
| Legacy underwriting engine | `engine/underwrite25.js` (v25.8.5) | **Byte-identical.** Still used for every scenario whose config lacks `engineVersion` or sets `'25.8.5'`. |
| Corrected engine | — | `engine/underwrite27.js` (engine 27.1.0). Built from the frozen file by `tools/build_underwrite27.py` using exact-match splices only; `--check` proves it rebuilds byte-for-byte. |
| Engine selection | implicit | `config.engineVersion`. New underwriting scenarios default to `'27.1.0'`; unknown versions return 422; every run records the hash of the engine that actually ran plus `engine_version`. |
| Instrument engine | — | `engine/fixed_note27.cjs` 1.0.0 (Layer 2 only). |
| Pinned hashes | `docs/ENGINE_BASELINE_SHA256.txt` | Kept, plus `docs/v27_1/ENGINE_V271_SHA256.txt` (underwrite27 `686215dd…7409`, fixed_note27 `b89e6a0b…10f0`). |
| Legacy fixtures | — | `tests/v271/fixtures/legacy_v2585_outputs.json`: output hashes for five legacy cases. Test T19 proves they are byte-identical. |

Stored runs keep their inputs, outputs and engine hash. Rerunning a stored pre-v27.1 scenario reproduces the legacy result exactly, including the RT-A02 defect, for reproducibility (test T19).

## 2. RT-A02: cash-constrained debt-service waterfall (`engine/underwrite27.js`)

**Defect reproduced on v27.0 before any change:**

- Capped sponsor ($60M) case: unrestricted cash fell to **−$50.07M**, with 98 negative months.
- **$58.99M** of interest was booked as cash-paid after the month-7 halt.
- The reported lender claim at exit was **$77.62M** (principal only).

**Root cause.** Every monthly use (capex, cash interest, principal) was deducted in full. Sponsor top-ups were the only constraint, so once the sponsor cap was exhausted, payments continued out of negative cash.

**What changed:**

| Area | Treatment in 27.1.0 |
|---|---|
| Quantities kept separate | Interest **due** (`cashInterestDue`); interest **paid** (`cashInterest`, from any source); construction interest **capitalised** (IDC, unchanged legacy convention); interest **accrued but unpaid** (`unpaidInterestSenior/Mezz/Closing`); **PIK** (`pikInterest`); principal **scheduled** (`scheduledPrincipalDue`) vs **paid**; principal **past due** (`pastDuePrincipalClosing`); unpaid **operating** and **construction** payables; restricted reserve draws (`reserveDrawForDebtService`). |
| Sponsor support | Sized exactly as before: current obligations plus minimum liquidity, within the enforceable cap. This is why unconstrained months are identical to legacy. |
| Payment priority | 1. operating shortfall (negative CFADS)<br>2. funded refinancing/payoff transactions<br>3. construction capex and fees<br>4. debt service in the configurable order `debtServicePriority` (default: senior interest → senior principal → mezz interest → mezz principal), with restricted reserves usable per `reserveDebtServicePolicy` (`dsra_only` default / `all` / `none`)<br>5. arrears, **only from cash above minimum liquidity**, so sponsor liquidity support is never silently turned into lender recovery<br>6. reserve top-ups and releases (legacy)<br>7. sweep (legacy, not in default)<br>8. distributions, locked while any claim is unresolved. |
| Cash floor | Unrestricted cash never goes below zero. A shortfall becomes an explicit unpaid obligation, never a disappearing one. |
| Minimum liquidity | Breaching it is reported separately (`unfundedGapM`, liquidity default) from missed payments (`currentShortfallM`, `paymentDefault`). A minimum-cash breach does not mean cash is zero. |
| Unpaid interest | `unpaidInterestPolicy: 'accrue'` (default) carries it as a separate lender claim with **no compounding and no default rate**. `'pik'` capitalises it **only if** `pikPermittedByInstrument: true`; otherwise the engine throws. `defaultInterestRatePct` (default 0) accrues only on overdue amounts and is labelled an assumption whenever it is used. |
| Maturity without repayment | All outstanding principal becomes **past due** (`maturedUnpaid`) and is not "paid". Legacy kept accruing interest while hoarding excess cash; 27.1.0 applies cash above the liquidity floor to the matured principal. |
| Post-refinancing amortisation | The annuity is computed on the balance not already past due, so arrears are not re-amortised and double-counted. |
| Terminal waterfall | Cash, reserves and exit proceeds go to lender claims in the configured priority (unpaid interest before principal within each tranche), then to unpaid construction and operating payables, then to equity. Reported fields: `lenderClaimAtExitBeforeM`, `lenderRecoveryAtExitM`, `lenderRecoveryPct`, `unpaidLenderClaimsAtExitM` (principal + interest), `unpaidPayablesAtExitM`. |
| Monthly identities | Emitted on every row and re-derived independently by the test oracle: cash (`cashIdentityResidual`), interest (`interestIdentityResidual`), principal (`debtResidual`/`mezzResidual`, PIK included), reserve (`reserveResidual`, net of reserve draws), payables (`payablesResidual`). Maximum residual across every tested case: **≤1.1e-13**. |
| Row semantics | Legacy field names are kept. `cashInterest`, `principal` and `mezzPrincipal` now mean amounts **actually paid** (from any source). |

### Before/after on the four required cases

Full monthly detail is in `DEFAULT_WATERFALL_RECONCILIATION.csv` (480 rows).

| Case | First differing month | Legacy | v27.1 | Why the difference exists |
|---|---|---|---|---|
| Base (defaults) | none | NPV 438.79; min cash 0 | **Identical** (NPV 438.79; max row gap 3.6e-15) | No shortfall, so no changed treatment applies. |
| Capped sponsor default (`sponsorCommitmentM:60, initialCash:50`) | 23 | Min cash **−50.07**; 98 negative months; cash interest "paid" 58.99; lender claim at exit **77.62** (principal only) | Min cash **0.00**; interest paid 18.41; **unpaid interest 40.58** carried; claim before exit 128.21; exit recovery 10.00 (reserve); **unpaid claims 118.21** (77.62 principal + 40.58 interest); recovery 7.8% | Interest that could not be paid is a claim, not a payment. Legacy understated the lender claim by **$40.58M (34% of the true $118.21M)**. Equity NPV is unchanged (−59.57) because sponsor flows are identical. |
| Refinance failure (`sponsorCommitmentM:450, refinanceValueM:150`) | 60 | Matured principal left outstanding while cash accumulated; interest paid 432.96; lenders repaid at exit | Matured principal becomes past due and is repaid from cash above minimum liquidity; interest paid **335.31** (97.65 less); lenders repaid in full; recovery 100% | Matured debt is due, so excess cash goes to the lender instead of accruing interest. Equity NPV is unchanged (−189.92) because distributions were locked in both versions. |
| Terminal recovery (hand case, exit value $20M) | 51 | Min cash **−20.99**; unpaid principal at exit 37.50 | Min cash 0; unpaid interest 21.29 accrues and is **paid first at exit** from proceeds; unpaid principal 37.50; recovery 29.60 of 67.10 (44.1%) | In legacy, negative cash behaved like an unrecorded loan, netted against exit proceeds (and written off when there were none, as in the capped case). Unpaid principal matches only because proceeds existed. |

Across the 31 bundled reference cases, 27 are identical to legacy on every monthly field. The other 4 are identical up to the first changed-treatment month (60, a matured default) and differ only after it, with equity NPV delta 0 (`tests/v271/reference_parity_v271.cjs`).

## 3. RT-E04b: one canonical delay convention (`server/schedule27.py`)

**Defect reproduced on v27.0:** for the demo grid path, the v26.2 sensitivity applied **16 months** (path 9 + linked permit 7) and NPV $780.9M, while the v26.3 sensitivity applied **9 months** and NPV $906.7M. The Decision Center footnote said "not a summed delay" directly above the form that summed it.

**What changed:**

- One function computes COD delay for every interface. The method is in `DELAY_CONVENTION.md`: delays accumulate along dependencies; independent drivers run in parallel, so COD moves by the longest; float reduces impact; the path-level estimate is never added.
- These consumers now call it:
  - `/paths/{id}/schedule`
  - `/sensitivity` (v26.2 route, now an alias)
  - `/sensitivity-v263`
  - the new read-only `/schedule-impact`
  - change-proposal previews, which is the route agent-generated proposals use
  - Decision Center, Power paths and the comparison table, which now read the API instead of computing a client-side "max permit" figure
  - PermitIQ / Execution, through the same `/schedule` response
- Every result carries `schedule_version`, a hash of the method and the normalised inputs. Sensitivity scenarios store it in `powerPathLink.scheduleVersion`.
- Milestones gain `float_months` (default 0 = critical) and two new categories (`equipment`, `tenant`). Milestone inserts now use named columns.
- `include_open_permit_delay` is accepted but can no longer change the answer; the response reports `include_open_permit_delay_superseded`.
- **Inherited test changed, not weakened:** `tests/test_v262_workflows.py::test_04` asserted the additive 16-month result, i.e. the defect itself. It now asserts the canonical 9 months and matching `schedule_version`, with a comment explaining why.

## 4. New instrument engine (`engine/fixed_note27.cjs`)

Fixed-rate semiannual note with:

- explicit day count (`30/360`, `ACT/360`, `ACT/365`);
- first-period stub;
- installments of a percentage of **original** principal from a contingent first-installment date;
- the maturity payment split into the scheduled final installment and the true balloon;
- optional DSRA hold or release at maturity;
- an effective-interest yield on net proceeds and an amortised-cost carrying value at reporting dates;
- illustrative required CFADS at 1.00x, 1.20x and 1.35x.

It computes financing cash flows only. It does not value a project or size debt.

## 5. Packaging regression found in v27.0 and fixed

v27.0 omitted `review/engine-v259/data/transactions_v259.json`, so the inherited audit ran **36/37** (the facilities note-engine test could not load its fixture). The file is restored from v26.8 unchanged, and the inherited audit is back to **37/37**.

## 6. Provisional conventions requiring qualified human approval

| Convention | Default | Why it needs approval |
|---|---|---|
| Unpaid interest | Accrue, no compounding, no default rate | Contract-specific; may understate claims if the instrument compounds or carries default interest. |
| PIK | Disallowed unless `pikPermittedByInstrument` | Legal permission required. |
| Payment priority | Ops → refinancing → construction → senior int → senior prin → mezz int → mezz prin | Intercreditor and account-agreement specific. |
| Arrears | Paid only from cash above minimum liquidity | Standstill and acceleration terms are unknown. |
| Reserve use | DSRA portion only | Base reserve purpose is unknown. |
| Equity after cure | Legacy rule kept: a once-defaulted case retains residual cash rather than distributing it, even after full repayment | Conservative; enforcement outcomes are legal questions. |
| Construction IDC | Capitalised while constructing (legacy) | Facility-specific. |
| Delay mapping | COD delay shifts energisation and lease start; construction spend is unchanged | Screening convention, not a CPM schedule. |
