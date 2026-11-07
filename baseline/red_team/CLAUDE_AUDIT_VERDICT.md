# PowerPath v25.8 — Independent Red-Team Audit Verdict

**Reviewer:** Claude (AI), acting as independent counterparty reviewer. **Date:** 26 Oct 2026. **Scope:** offline package (v25.7 baseline, v25.8 candidate) plus public sources re-opened on the review date.

## Verdict

| Question | Answer |
|---|---|
| Can v25.8 be called lender-grade? | **No.** |
| Is v25.8 fit for comparative screening as shipped? | **No — CONDITIONAL NO-GO.** Five computationally material defects were found that the 21 bundled suites and the bundled Python reference did not detect. |
| Is the patched candidate (v25.8-CA) fit for bounded, deterministic comparative screening on synthetic assumptions? | **Yes, qualified.** All patches are tested failing-before and passing-after, and the engine matches a from-scratch independent reference on 24,320 monthly checks (max gap 1.4e-12 $M). |
| Is any of the 16 public cases a verified transaction model? | **No.** 0/16 are contract-verified, and the financing of the three priority transactions is not reproduced (G4 FAIL). |

The bundled report's headline, "PASS for bounded comparative analysis", **did not hold for v25.8 as delivered**. Its 37,995 "independent" checks came from a Python reference that ports the same JS logic, so it agreed with the engine's errors (CA-08).

## Defects found and closed (details in `ISSUES.csv`, patches in `CODE_PATCHES/`)
1. **CA-01 Refinancing sized on an annuity but repaid level-principal (Material).** Early debt service ran ~29% above the sized payment. A DSCR-sized refinancing opened at **0.93x against a 1.25x sizing test**, producing 37 breach months; after the patch it opens at 1.198x with 2 breach months. This affects every refinanced case: base NPV moves **+$0.55M to +$50.74M** across the 16 public cases, and the max |ΔNPV| over 720 stresses is $50.74M. That is larger than the $6.83M "max version delta" in the bundled report.
2. **CA-04 Phantom financing after a funding default (Material).** With a sponsor cap, v25.8 kept building on a negative cash balance (down to **−$861M**), finished and leased every building, and reported the senior debt as repaid. After the patch, unfinished buildings halt and, in that case, $64.5M of senior debt is correctly shown unpaid. The engine still offers a `continue` option to reproduce the old results.
3. **CA-02 Shared-tranche crash (Material):** valid shared-supply schedules threw an exception.
4. **CA-03 Gross/IT unit mixing in tranches (Material):** a hard-rule violation.
5. **CA-05 to CA-07 (Minor):** flat-730 h MWh reporting; first-coupon stubs (APLD's first coupon is **$123.78M on 30/360**, not $108.69M); and a one-year calendar misalignment in the benchmark harness.

## Most important open findings (not code-fixable without documents or owner policy)
- **CA-09:** all **16/16 cases and 720/720 stresses breach covenants**. The generic 240-month refinancing outlives every lease, and the horizon runs past lease expiry with zero revenue before exiting at the full $12M/MW. The Applied Digital cases also breach for 37–44 months *before* expiry, at minimum DSCRs of 0.52–0.86x. Every NPV relies on unlimited sponsor support.
- **CA-16 (Blocker):** the real notes are not in the waterfall, and their scope differs from the modeled campuses. APLD's 9.25% notes cover **250 of Polaris Forge 1's 400 MW**. Helios II's 9.875% notes finance **Phase II only (260 of 526 IT MW)**. Core's 7.75% notes amortize from a contingent date; the 10-Q *assumes* 15 Nov 2029, which leaves a ~$2.73B balloon at maturity.
- **CA-19/CA-20 (source and units):** Galaxy's own release says "more than $1 billion" of average annual revenue, while the catalog uses $1.2B+. Helios discloses 800 gross / 526 IT MW (ratio 1.52) against the model's PUE of 1.30. The Core sites use "leased power" MW as IT MW.
- **The adversarial hypothesis is confirmed in all three parts.** (a) The headline-total calibration is a tautology and implies ~$128/kW-month for Polaris Forge 1 under an *assumed* escalator. (b) The real fixed-rate notes differ from the generic debt in coupon, amortization, collateral scope and OID. (c) The energy and opex assumptions, together with the lease-tail treatment, drive covenant outcomes in every case.

## Model use restrictions (v25.8-CA)
1. Use only for deterministic **comparative screening** of user-entered assumptions. Do **not** rank the 16 public projects by NPV or IRR.
2. Do not present any output as a project return, a debt capacity, a delivered-MW figure, a recovery or a lender view.
3. Treat any case with an unlimited sponsor (`sponsorCommitmentM` blank) as a sensitivity only.
4. Do not use the notes calculator as a debt schedule until the indenture triggers and installments are sourced.
5. Funding-default outputs reflect a screening convention (halt and pro-rata exit), not a legal recovery analysis.

## What would be required for lender-grade status
The executed leases and amendments; the three indentures plus the APLD Building 4 and Helios Phase I financing documents; utility ESAs and interconnection agreements; integration of the notes into the monthly waterfall with source-backed triggers; resolution of CA-09 through CA-15; and **a scoped review by a qualified human project-finance model auditor and the lender side (G5)**. Automated test passes, including this review's, are not certification.
