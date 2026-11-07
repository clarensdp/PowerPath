# CORE_SCIENTIFIC_TERMS — Core Scientific Finance I LLC 7.750% Senior Secured Notes due 2031

**Layer 1 (publicly disclosed facts) and the Layer 2 assumptions applied to them.**

All terms were rechecked on **27 Oct 2026** against:

- the 8-K filed 6 May 2026, and its Exhibit 99.1 (pricing release, 22 Apr 2026);
- the 10-Q for the quarter ended 30 June 2026 (filed 28 Jul 2026).

The Q3 2026 10-Q has not been filed; results are scheduled for 5 Nov 2026.

**Nothing here is executed-contract verified.** The indenture, its definitions and schedules, the security documents, the leases and the DSRA terms were not available. A filing is a public primary source, not the contract.

## 1. Register (as seeded by `POST …/transactions/core-scientific-2026/model`)

| Input | Value | Units | Classification | Source / locator | Source date |
|---|---|---|---|---|---|
| Issuer | Core Scientific Finance I LLC | entity | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01 | 2026-05-06 |
| Principal | 3,300.0 | $M | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01; 10-Q Note 7 | 2026-05-06 |
| Coupon | 7.750 | % p.a. | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01 | 2026-05-06 |
| Issue price | 99.250 | % of par | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01; Ex. 99.1 | 2026-05-06 |
| Issue / indenture date | 2026-05-06 | date | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01 | 2026-05-06 |
| Maturity | 2031-05-15 | date | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01 | 2026-05-06 |
| Interest dates | 15 May and 15 Nov, in arrears | calendar | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01 | 2026-05-06 |
| First interest date | 2026-11-15 | date | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01 | 2026-05-06 |
| Amortisation | 11.50% p.a. of **issue-date** principal, semiannual (5.75% = $189.75M per installment) | % | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01; 10-Q Note 7 | 2026-05-06 |
| First Installment Payment Date | First semiannual payment date ≥15 days after the later of rent commencement and abatement of all revenue credits | definition | PUBLIC_PRIMARY_SOURCE | 10-Q Note 7 (paraphrase; indenture text not reviewed). **The 8-K does not define it.** | 2026-07-28 |
| Issuer's assumed first installment | 2029-11-15 | date | PUBLIC_PRIMARY_SOURCE (**issuer assumption, not a contractual date**) | 10-Q Note 7 maturity-table footnote | 2026-07-28 |
| Maturities under that assumption | 2029: 189.75; 2030: 379.50; 2031: 2,730.75 | $M | PUBLIC_PRIMARY_SOURCE | 10-Q Note 7 | 2026-07-28 |
| Original issue discount | 24.8 | $M | PUBLIC_PRIMARY_SOURCE | 10-Q Note 7 | 2026-07-28 |
| Debt issuance costs | 42.0 | $M | PUBLIC_PRIMARY_SOURCE | 10-Q Note 7 | 2026-07-28 |
| Effective interest rate | 8.3 | % | PUBLIC_PRIMARY_SOURCE | 10-Q Note 7 debt table | 2026-07-28 |
| DSRA balance at 2026-06-30 | 344.8 | $M | PUBLIC_PRIMARY_SOURCE | 10-Q Notes 2/7 | 2026-07-28 |
| Restricted cash, total, at 2026-06-30 | 781.656 (165.745 current + 615.911 non-current) | $M | PUBLIC_PRIMARY_SOURCE | 10-Q balance sheet | 2026-07-28 |
| Q2 2026 coupon interest, **all debt** | 48.690 | $M | PUBLIC_PRIMARY_SOURCE (not notes-specific) | 10-Q Note 7 | 2026-07-28 |
| Q2 2026 discount and cost amortisation, **all debt** | 3.682 | $M | PUBLIC_PRIMARY_SOURCE (not notes-specific) | 10-Q Note 7 | 2026-07-28 |
| Net proceeds (8-K) | "approximately $3.24 billion" | $M | **CONFLICTING_EVIDENCE** | 8-K | 2026-05-06 |
| Guarantors / collateral scope | Issuer + Austin, Denton, Dalton, Marble, Muskogee subsidiaries (first-priority liens; also Holdco equity and Parent Collateral) | entities | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01 | 2026-05-06 |
| Completion guarantee | Uncapped, all Projects **except Austin**; it is not a guarantee of the notes | scope | PUBLIC_PRIMARY_SOURCE | 8-K Item 1.01 | 2026-05-06 |
| Day count | 30/360 | convention | **USER_ASSUMPTION**: not stated in the sources read; US high-yield convention | — | — |
| Interest accrual start | 2026-05-06 | date | **USER_ASSUMPTION** | — | — |
| DSRA mechanics | Hold the 344.8 balance; no funding or release modelled | policy | **USER_ASSUMPTION**: sizing and release terms not disclosed | — | — |
| Per-site leased MW | Denton 260, Dalton 175, Muskogee 70, Marble 65, Austin 20 | MW IT | **UNVERIFIED**: prior catalog, not re-confirmed; Layer 3 only | prior AI review | — |

Disclosed but **not modelled**:

- make-whole before 15 May 2028;
- 40% equity clawback;
- post-2028 call prices;
- Datacenter Lease Termination Event: par redemption, MRC mandatory redemption, and **deferral of amortisation**;
- 101% change-of-control put;
- asset-sale and casualty offers;
- covenants and events of default.

## 2. Changes against the v27.0 register and the earlier audit's leads

| Item | Before | Now | Basis |
|---|---|---|---|
| Net proceeds 3.24B | v27.0: PUBLIC_PRIMARY_SOURCE fact | **CONFLICTING_EVIDENCE** | Derived from 10-Q OID and costs: 3,300 × 99.25% − 42.0 = **3,233.25**, which is $6.75M below the 8-K "approximately" figure. No plug applied. |
| "~8.3% effective rate" (earlier audit lead) | Lead | **Reproduced within rounding.** The bond-equivalent yield on net proceeds under the issuer's 2029-11-15 assumption is **8.264%**. | The annual-compounded equivalent (8.435%) would round to 8.4, so the filing appears to use a nominal semiannual rate. That is an inference. |
| "~$2.73B balloon" (earlier audit lead) | Called a balloon | **Corrected:** 2,730.75 is the whole 2031 maturity payment, including the scheduled 15 May 2031 installment of 189.75. **The balloon proper is 2,541.00.** | 10-Q maturity table plus reconstruction |
| Amortisation trigger | Prior audit cited the indenture via F25–F26 | Definition now sourced from 10-Q Note 7. The 8-K says only "no amortization prior to the First Installment Payment Date". | 8-K and 10-Q |
| DSRA | Prior audit F28 | 344.8 confirmed. Sizing is unexplained: it equals **1.315×** the modelled coupons payable 1 Jul 2026 – 30 Jun 2027 (262.14). | 10-Q |

## 3. Contingent amortisation scenarios (Layer 2)

Rent-commencement and abatement dates are **hypothetical scenario variables**, not contractual facts. Each one is mapped to a first-installment date with the 10-Q definition. Per-period detail is in `CORE_SCIENTIFIC_SCENARIOS.csv`.

| Scenario | Hypothetical abatement date | First installment | Installments before maturity | Total coupon ($M) | Final maturity principal ($M) | Balloon proper ($M) | Bond-equivalent EIR |
|---|---|---|---|---|---|---|---|
| Early | 2028-04-30 | 2028-05-15 | 6 | 1,130.73 | 2,161.50 | 1,971.75 | 8.309% |
| **Base** (issuer's 10-Q assumption) | 2029-10-31 | **2029-11-15** | 3 | 1,241.03 | **2,730.75** | **2,541.00** | 8.264% |
| Delayed | 2030-10-31 | 2030-11-15 | 1 | 1,277.79 | 3,110.25 | 2,920.50 | 8.251% |
| Trigger not met before maturity | 2031-05-01 | none | 0 | 1,285.14 | 3,300.00 | 3,300.00 | 8.249% |

Under every scenario:

- the first coupon is **$134.27M** (189/360 × 7.75% × 3,300) and each full semiannual coupon is $127.875M;
- the peak semiannual scheduled debt service, excluding the balloon, is **$317.6M** (in amortising scenarios);
- the DSRA is assumed to be held at $344.8M.

**Most of the principal is refinancing risk at maturity in every case:** at least $1.97B, and $2.54B in the base case.

## 4. Open documentary requirements

1. Executed indenture, all definitions (First Installment Payment Date, Datacenter Lease Termination Event, revenue credits), the DSRA covenant and the account waterfall.
2. Security and collateral agreements, and the Parent Collateral schedule.
3. Lease commencement certificates and revenue-credit schedules per site.
4. Day count and interest-accrual terms.
5. Completion guarantee instrument.
6. Q3 2026 10-Q (due after 5 Nov 2026) for the notes-specific carrying amount, accrued interest and DSRA movements.
