# PROJECT_VALUATION_GAPS — why no Core Scientific project value is produced

**Principle:** reconstructing a financing instrument does not establish the value of the project behind it. PowerPath v27.1 keeps three layers apart in code (`server/transaction271.py`), storage and every API response:

| Layer | Content | Status |
|---|---|---|
| 1. Publicly disclosed debt facts | Filing values with source and locator (`GET …/terms`) | Rechecked 27 Oct 2026; **not** contract-verified |
| 2. Reconstructed financing cash flows | `engine/fixed_note27.cjs` schedules and reconciliation (`GET …/debt-schedule`, `…/scenarios`, `…/reconciliation`) | Inspectable; depends on four labelled assumptions |
| 3. Illustrative project scenario | Hypothetical CFADS overlaid on the Layer 2 note service (`POST …/illustrative-project`) | **Every output is labelled NOT_A_CORE_SCIENTIFIC_VALUATION** |

## 1. Inputs missing for a verified project valuation

| Required input | What exists today | Classification | Needed to close |
|---|---|---|---|
| Site IT MW and gross MW | Prior-catalog "leased power" MW per site, total 590 | UNVERIFIED | Lease exhibits; utility allocations; company site disclosures |
| Site development capex | None. Layer 3 treats capex as sunk or financed outside the view | Missing | Construction budgets, draw schedules, completion-guarantee calls |
| Construction schedules and completion milestones | None site-specific | Missing | Construction contracts; lender reports |
| Executed commercial leases | None | Missing | Lease agreements and amendments |
| Tenant rent schedules | Layer 3 uses $170/kW-month (PowerPath generic default) | USER_ASSUMPTION, explicitly **not** a CoreWeave contract rent | Rent schedules by site and phase |
| Revenue credits and abatement | Not modelled; only the trigger definition is known | Missing | Lease credit provisions; abatement dates |
| Utility service agreements and power dates | None | Missing | ESAs, interconnection agreements, energisation evidence |
| Power pricing and pass-through | Layer 3 assumes the tenant pays power directly | USER_ASSUMPTION | Lease power clauses; utility tariffs |
| Operating costs and maintenance capex | 12% of revenue + $0.4M/month | USER_ASSUMPTION | Operating budgets |
| Working capital | Not modelled | Missing | Billing and collection terms; the 10-Q shows a $383.8M customer funding receivable, so timing matters |
| Tenant guarantees and credit support | None | Missing | Guarantee and LC documents |
| Taxes | None | Missing | Tax structure of the issuer group |
| Collateral, cross-default and ring-fencing | 8-K summary only | PUBLIC_PRIMARY_SOURCE (summary) | Security agreements; intercreditor arrangements |
| Terminal value and refinancing of the balloon | None. The balloon (≥$1.97B; $2.54B base) is shown as a payment, not refinanced | Missing | Refinancing market evidence; appraisal |
| Datacenter Lease Termination Event outcomes | Disclosed in summary only (par redemption, amortisation deferral) | PUBLIC_PRIMARY_SOURCE (summary) | Indenture definitions; scenario design |
| Tenant concentration | All five sites lease to CoreWeave; no tenant-credit dimension | Gap | Tenant credit analysis |

## 2. What Layer 3 shows, and does not show

The illustrative case uses 590 MW (UNVERIFIED), $170/kW-month, 2.5% escalator, 144-month leases, 12% opex plus $0.4M/month, and a single rent-commencement date for all sites.

| Scenario | Min DSCR (full-rent periods, ex-balloon) | Breakeven rent at 1.00x / 1.20x / 1.35x ($/kW-month) | Note service due before rent ($M) | Gap vs DSRA ($M) |
|---|---|---|---|---|
| Early | 1.70 | 100.4 / 120.3 / 135.2 | 390.0 | 45.2 |
| Base | 1.70 | 100.4 / 120.3 / 135.2 | 773.6 | 428.8 |
| Delayed | 1.70 | 100.4 / 120.3 / 135.2 | 1,029.4 | 684.6 |
| Trigger not met | n/a (no full-rent period before maturity) | n/a | 1,157.3 | 812.5 |
| Base, rent −15% ($144.5) | 1.44 | unchanged | 773.6 | 428.8 |
| Base, opex +20% | 1.65 | 103.3 / 123.8 / 139.2 | 773.6 | 428.8 |

How to read this:

- **Breakeven rents are sensitivities to assumed MW and opex.** They are not a finding that the notes are or are not covered.
- **The pre-rent gap comes from the single-date assumption.** Real commencement is phased, and some sites may already pay rent, so the gap is **not** a finding about Core Scientific liquidity.
- **The NPV fields are not returns.** `illustrative_npv_post_closing_cfadsM` and `illustrative_npv_cfads_less_note_service_incl_balloonM` exclude invested capital, taxes, refinancing and terminal value. They are not equity returns, enterprise values or debt capacity.
- **Delay downside belongs in the scenario choice.** Shifting rent without moving the amortisation trigger (`rent_shift_months`) is internally inconsistent: it showed a *higher* DSCR (1.78). Use the delayed scenario instead, which moves both.

## 2a. Hard rules enforced in code

- Every Layer 3 response carries `NOT_A_CORE_SCIENTIFIC_VALUATION: true`, input labels, `valuation_allowed: false`, and G4/G5 `BLOCKED`.
- No endpoint derives enterprise value, equity IRR, development profit or debt capacity from principal and coupon.
- Public filings and analyst assumptions cannot be promoted to `EXECUTED_CONTRACT_VERIFIED`. Promotion requires an authenticated approver, an uploaded and hashed executed document in the project's evidence room, and a non-filing source. Even then, G4/G5 remain BLOCKED. Tests T17 and T18 cover this.

## 3. Path to a verified project case

1. Obtain the executed indenture and leases under NDA, upload them to the evidence room, and have a named approver reclassify each term against the document hash.
2. Replace the UNVERIFIED and USER_ASSUMPTION Layer 3 inputs with site-level executed values, including phased commencement and credits.
3. Reconcile modelled interest, carrying amount and DSRA against the Q3 2026 10-Q.
4. Add balloon-refinancing and lease-termination scenarios.
5. Commission a qualified independent model review (G5). Only then can a project value be presented, and only to the reviewed scope.
