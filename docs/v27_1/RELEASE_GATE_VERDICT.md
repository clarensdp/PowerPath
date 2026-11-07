# RELEASE_GATE_VERDICT — PowerPath v27.1.0

**Assessed by:** Claude (AI model reviewer), 27 Oct 2026. **Evidence:** `MODEL_VALIDATION_REPORT.md`; 18/18 release checks from a clean extraction of the zip.

| Permitted use | Verdict | Basis | What blocks the next level |
|---|---|---|---|
| **Local prototype** | **GO** | All suites pass from the packaged zip. The corrected engine is versioned, history is reproducible, and the UI shows one delay figure. | — |
| **Financial screening** (user-entered or synthetic assumptions) | **CONDITIONAL GO** | RT-A02 and RT-E04b are fixed: no negative cash, lender claims preserved, one delay convention, monthly identities ≤1e-13. Legacy parity is exact where no shortfall occurs. | Human approval of the provisional conventions (unpaid interest, priority, arrears floor, reserve use, equity-after-cure, delay mapping). Screening defaults such as $7M/MW capex and $85/MWh remain unsourced unless the user overrides them. |
| **Public-debt instrument reconstruction** (Core Scientific Finance I) | **CONDITIONAL GO, as an inspectable reproduction of filed terms only** | The maturity table reproduces the 10-Q exactly; the effective rate is within rounding (8.264% vs 8.3%); the trigger is modelled as a scenario; every variance is visible (net proceeds −6.75 OPEN; carrying amount not disclosed in the source read). | Day count, accrual start and DSRA mechanics are assumptions. Datacenter Lease Termination Event deferral, redemptions and covenants are not modelled. No indenture reviewed. **Not** EXECUTED_CONTRACT_VERIFIED. |
| **Project-level valuation** | **NO-GO** | Layer 3 is illustrative only: unverified MW, an assumed rent that is not a contract rent, no capex, no credits, no tax, no terminal value. | Every input in `PROJECT_VALUATION_GAPS.md` §1. |
| **Hosted institutional use** | **NO-GO** | v27 identity is a local preview: password plus bearer, SQLite, no SSO/MFA, no encryption at rest, no penetration test. The default `run_local.sh` mode has no authentication. | v27.0 milestones 1–2 (managed PostgreSQL with row-level tenancy, OIDC/MFA, encrypted storage, backups, independent security review). |
| **Lender-certified use** | **NO-GO** | **G4 BLOCKED, G5 BLOCKED**, enforced in every transaction response, with no API path to unlock either. | G4: executed indenture, leases and DSRA terms reconciled by a named reviewer. G5: qualified independent human model review and sign-off. Automated tests and AI review cannot satisfy either. |

## Material open items

| ID | Severity | Item | Owner |
|---|---|---|---|
| V271-01 | MATERIAL | Provisional waterfall conventions (accrue without compounding, priority order, arrears floor, DSRA-only reserve use, residual retained after cure) need human credit and legal approval | CFO / Risk |
| V271-02 | MATERIAL | Core Scientific day count, accrual start and DSRA mechanics are assumptions. The ACT/360 first coupon would be +$2.84M | CFO |
| V271-03 | MATERIAL | Net proceeds conflict: 8-K approx. $3.24B vs $3,233.25M derived from 10-Q OID and costs | CFO |
| V271-04 | MATERIAL | Datacenter Lease Termination Event (amortisation deferral, par redemption), make-whole, clawback, change of control and asset-sale offers are not modelled | CFO |
| V271-05 | MATERIAL | Balloon refinancing risk (at least $1.97B; $2.54B base) is not modelled beyond showing the payment | CFO |
| V271-06 | MATERIAL | Delay convention uses analyst float and month increments; no calendar CPM; nothing is utility-confirmed | COO |
| V271-07 | MINOR | Equivalent mutant W08 (arrears lock is redundant with the sticky default lock); kept as defence in depth | CTO |
| V271-08 | MINOR | RT-D03: approver identity absent in local-only mode (present in required-auth mode) | CTO |
| V271-09 | MINOR | Layer 3 single rent-commencement date overstates the pre-rent funding gap; `rent_shift_months` is decoupled from the trigger (use the delayed scenario instead) | CPO / CFO |
| V271-10 | MINOR | Toolchain still unpinned (TypeScript, Playwright browser path); v26.8 RT-G02 accessibility contrast not addressed in this financial-scope release | CTO / Design |
| Carried | BLOCKER | G4 and G5 | Risk |

## Success condition

The brief's success condition was: financially consistent cash and debt accounting, reproducible schedule sensitivities, and an independently inspectable Core Scientific debt reconstruction, with facts, assumptions and contract-verified conclusions kept apart.

**Met for local and screening use.** It is not met for valuation, hosted or lender use, and nothing in this release claims otherwise.
