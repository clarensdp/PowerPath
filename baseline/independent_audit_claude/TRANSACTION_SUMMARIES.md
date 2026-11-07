# Transaction Summaries — PowerPath v25.8 independent review

As of 26 Oct 2026. All model figures are $M and come from the patched engine (v25.8-CA) with the bundle's common synthetic assumptions. **They are not valuations of the real projects** and are not ranked. The evidence labels follow the `VERIFIED_FACTS.csv` fact IDs.

One structural finding applies to all 16 cases (ISSUES CA-09): the generic refinanced loan amortizes over 240 months, longer than every lease, and the harness horizon runs 12+ months past lease expiry. So **every case breaches covenants and depends on unlimited sponsor support**. Exit is still valued at the full $12M/MW.

---

## 1. Applied Digital — Polaris Forge 1 / APLD ComputeCo (detailed)

**What the sources establish.** The 10-K (FY ended 31 May 2026) reports 400 MW of contracted critical IT at Ellendale, leased to CoreWeave. That comes from ELN-02 + ELN-03 (250 MW, leases of 28 May 2025) plus Building 4 (150 MW, lease of 28 Aug 2025) (F01, F04). The first ~100 MW building has been operational since Oct 2025, the second ~150 MW building is partially operational, and the third is expected in calendar 2027 (F02–F03). Base-term contracted revenue is **~$11.0B** over 15 years, excluding three 5-year renewals (F06). On 30 Mar 2026 ELN-02 was amended and ELN-03 was assigned to a CoreWeave subsidiary (F05); the amended economics are not modeled.

**Financing.** APLD ComputeCo LLC priced **$2.35B of 9.250% senior secured notes due 2030 at 97%** (an OID of $70.5M) (F13). The proceeds finance **only ELN-02 and ELN-03 (250 of 400 MW)**, repay the 11 Feb 2025 credit agreement and fund debt service reserves (F14). The bundle's dates (first coupon 15 Jun 2026, maturity 15 Dec 2030, amortization from 15 Dec 2027) were **not re-confirmed** in this review, because the 10-K debt footnote could not be retrieved (F15). Payment dates (15 Jun / 15 Dec from 15 Jun 2026) and the fixed **$177.0M DSRA** are now confirmed from the indenture (F15, F34); installment amounts and covenants remain unextracted (F16).

**Independent instrument check.** On 30/360 from issue date, the first coupon is 205/360 × 9.25% × $2,350M = **$123.78M**, not the $108.69M half-year the v25.8 calculator charged (CA-06, fixed). Because installment amounts are unknown, the calculator cannot produce a contractual schedule, and none is claimed.

**Model versus transaction.** The case models 400 MW in three phases (100/150/150) using 'total' rent mode, which calibrates each phase to its share of $11.0B by construction. That implies a starting rent of about **$127.8/kW-month** under an *assumed* 2.5% escalator. Debt is a generic 8% construction loan refinanced at 7%/240m, not the 9.25% notes. The two differ in coupon, amortization, collateral scope (250 vs 400 MW), OID and reserves, so the model's financing outcome is not this transaction's.

Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 −$31.3M -> patched −$10.6M (patched with harness calendar fix). Refinance binding constraint: DSCR. Covenant breach months before last lease expiry: 43 (min DSCR 0.86x); after expiry: 13. Sponsor equity required: $1,502M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.

| Assurance dimension | Verdict |
|---|---|
| Arithmetic (engine identities, independent reference) | PASS (patched; 24,320 independent monthly checks on synthetic cases) |
| Public fact normalization | QUALIFIED — MW and ~$11.0B reproduced; allocation by phase and escalator assumed; normalization is tautological |
| Contract-level cash-flow match | FAIL / NOT POSSIBLE — no lease schedules; amendment terms unknown |
| Financing structure reproduction | FAIL — 9.25% notes not integrated; scope 250 MW vs 400 MW; installments unknown |
| Physical power evidence | QUALIFIED — company-reported operational status only; no utility service agreement or metering |
| External (human) review | NOT STARTED |

**Documents needed:** ELN-02 / ELN-03 / Building 4 leases and the 30 Mar 2026 amendment and assignment; the APLD ComputeCo indenture (amortization schedule, DSRA, cash management, completion guarantee); Building 4 financing documents; utility ESAs.

---

## 2. Galaxy — Helios (detailed)

**What the sources establish.** On 6 Jul 2026 Galaxy reported Phase I complete: **~200 MW gross / 133 MW critical IT** delivered to CoreWeave, with rent commencing in Q2 2026 (F17). CoreWeave has committed **526 MW critical IT across Phases I–III, the full 800 MW of approved gross power**, on 15-year leases with two 5-year extensions (F18). Galaxy expects **"more than $1 billion" average annual revenue** (F19). Phase II is 260 MW IT, with data hall deliveries expected to start in 1H 2027 (F20). Total approved power is 1.63 GW (F23).

**Source discrepancy (CA-19).** The bundle's catalog uses "$1.2B+" and an $18B/15-year floor. This review could not reproduce "$1.2B+" from the sources it could reach. On the 6 Jul wording the floor is >$15B. The catalog correctly labels Helios LOWER_BOUND and does not feed the figure into rent, so the gap matters for the source register, not for the arithmetic.

**Unit finding (CA-20).** Galaxy's own gross-to-IT ratio is 800/526 = **1.52**, while the model converts at an assumed PUE of 1.30. Since energy cost is IT MW × PUE, the model's energy assumption is internally inconsistent with the disclosed campus ratio. (A gross utility allocation is not the same as an operating PUE, which is another reason not to substitute one for the other without the ESA.)

**Financing.** Galaxy Helios Data Centers II priced **$3.507B of 9.875% senior secured notes due 1 Aug 2031**. Interest is semiannual from 1 Feb 2027. The notes amortize **4% of original principal per year, subject to adjustment**, with the first payment due at least 10 months after project completion. They finance **Phase II only: 400 MW utility / 260 MW IT** (F21–F22, from a secondary report; the primary notes PDF was not reachable). The issue price is **99.500%** per the 8-K (F35; the bundle's 100% proxy was wrong, OID $17.5M). The indenture keys first amortization to the first Payment Date after **10 months from first rent payment** (F36), not to completion; Phase II rent timing is unknown, so the first amortization date is still **Unknown**. DSRA: $285.05M during construction (F37). The calculator's illustrative 1 Feb 2029 start is an assumption, and with 30/360 from 28 Jul 2026 the first coupon is $176.04M.

**Model versus transaction.** The model treats all 526 IT MW as one generically financed campus at the default $170/kW-month rent. The real structure is phase-specific, has project-level notes on Phase II, and its Phase I financing is not described in the sources read.

Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $1,644.4M -> patched $1,676.4M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 11 (min DSCR 1.14x); after expiry: 13. Sponsor equity required: $1,425M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.

| Assurance dimension | Verdict |
|---|---|
| Arithmetic (engine identities, independent reference) | PASS (patched) |
| Public fact normalization | QUALIFIED — MW reproduced; revenue is a management floor with a source discrepancy; gross/IT ratio mismatch |
| Contract-level cash-flow match | FAIL / NOT POSSIBLE |
| Financing structure reproduction | FAIL — Phase II notes not integrated; Phase I financing unknown; completion trigger unknown |
| Physical power evidence | QUALIFIED — Phase I delivery is company-reported; Phase II/III are expectations |
| External (human) review | NOT STARTED |

**Documents needed:** CoreWeave leases by phase (rent, escalators, credits, commencement mechanics); the Helios II indenture (issue price, amortization adjustment, completion definition, reserves); Phase I financing; ERCOT/utility interconnection and ESA for the 800 MW.

---

## 3. Core Scientific — CoreWeave sites (detailed)

**What the sources establish.** Core Scientific Finance I LLC issued **$3.3B of 7.750% Senior Secured Notes due 15 May 2031 at 99.250%** under an indenture dated 6 May 2026, paying interest on 15 May and 15 Nov from 15 Nov 2026 (F24). Principal amortizes semiannually at **11.50% per annum of issue-date principal (5.75% per installment)**. Nothing is payable before the First Installment Payment Date, defined as the first semiannual date at least 15 days after the later of rent commencement and abatement of all revenue credits, and amortization can be deferred on a Datacenter Lease Termination Event (F25–F26). The 10-Q maturity table **assumes** a first installment on 15 Nov 2029 (F27). As of 30 Jun 2026: DSRA $344.8M (F28); total restricted cash $781.7M (F29); customer funding receivable $383.8M against $302.2M of related accrued expenses and $81.6M of payables (F30); carrying amount $3,300.0M at 7.75% stated / 8.3% effective (F31). The subsidiary guarantors (whose assets secure the notes) are the **Austin, Denton, Dalton, Marble and Muskogee** entities; only the completion guarantee excludes Austin (F32, corrected 26 Oct).

**Independent instrument check.** The first coupon on 30/360 from 6 May 2026 is $134.27M (v25.8: $127.88M). Using the 10-Q's assumed 15 Nov 2029 start, the schedule has 3 installments of $189.75M and a **$2,730.8M balloon** at maturity. Most principal is therefore refinancing risk in 2031, not amortized from CFADS. This is a provisional calculation, because the trigger date is contingent.

**Why tenant-cash timing matters.** The $383.8M receivable is direct evidence that customer-funded construction is not same-month cash. That supports the v25.8 lag feature. In this review the fix also reports any receivable still uncollected at the horizon (CA-10).

**Model versus transaction.** The five Core cases use "leased power" MW as IT MW at the default rent, with 12-year (Austin 7-year) terms. These per-site MW were not re-confirmed here (F33). The notes, the DSRA balance and the contingent amortization are not in the monthly engine.

| Site | Model NPV v25.8 → patched ($M) | Breach months pre/post expiry | Comment |
|---|---|---|---|
| Denton | 815.8 → 827.0 | 2 / 13 | Notes subsidiary guarantor; 260 leased |
| Dalton | 513.0 → 520.7 | 0 / 13 | Notes subsidiary guarantor; 175 leased |
| Muskogee | 189.3 → 192.3 | 0 / 16 | Notes subsidiary guarantor; 70 leased |
| Marble | 194.4 → 196.9 | 0 / 14 | Notes subsidiary guarantor; 65 leased |
| Austin | 2.7 → 3.3 | 0 / 49 | Notes guarantor (no completion guarantee); 7-year term; 20 leased |

| Assurance dimension | Verdict |
|---|---|
| Arithmetic (engine identities, independent reference) | PASS (patched) |
| Public fact normalization | QUALIFIED — notes terms reproduced; site MW and revenue not site-disclosed |
| Contract-level cash-flow match | FAIL / NOT POSSIBLE |
| Financing structure reproduction | FAIL — 7.75% notes, DSRA and contingent amortization not integrated |
| Physical power evidence | QUALIFIED — physical screen only |
| External (human) review | NOT STARTED |

**Documents needed:** the CoreWeave colocation agreements by site (rent, revenue-credit schedule, commencement); the notes indenture (cash waterfall, reserve mechanics, deferral events); the customer funding invoicing and collection terms; site ESAs.

---

## 4. Other 13 cases (one-page summaries)

### Applied Digital — Polaris Forge 2
- **Disclosure:** 200 IT (modeled 200.00 IT MW); reported ~$5,000M over 15 years; window 2026-09 to 2027-03. Tier `APPROX_DISCLOSED_CONTRACT_TOTAL`. Source facts: F08.
- **Catalog note:** 200 IT MW, first 2H26, full early 2027
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 −$230.2M -> patched −$223.0M (patched with harness calendar fix). Refinance binding constraint: DSCR. Covenant breach months before last lease expiry: 39 (min DSCR 0.55x); after expiry: 13. Sponsor equity required: $1,116M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization QUALIFIED (tautological total-rent calibration) · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** per-building lease schedules, escalators and commencement dates; actual financing.

### Applied Digital — Polaris Forge 3
- **Disclosure:** 300 IT (modeled 300.00 IT MW); reported ~$7,500M over 15 years; window 2027-09 to 2028-06. Tier `APPROX_DISCLOSED_CONTRACT_TOTAL`. Source facts: F09.
- **Catalog note:** 300 IT MW, 2H27–2H28 delivery
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 −$305.0M -> patched −$296.2M (patched with harness calendar fix). Refinance binding constraint: DSCR. Covenant breach months before last lease expiry: 41 (min DSCR 0.56x); after expiry: 13. Sponsor equity required: $1,665M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization QUALIFIED (tautological total-rent calibration) · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** per-building lease schedules, escalators and commencement dates; actual financing.

### Applied Digital — Delta Forge 1
- **Disclosure:** 300 IT (modeled 300.00 IT MW); reported ~$7,500M over 15 years; window 2027-03 to 2028-06. Tier `APPROX_DISCLOSED_CONTRACT_TOTAL`. Source facts: F10.
- **Catalog note:** 300 IT MW, 1H27–1H28 delivery
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 −$329.5M -> patched −$319.1M (patched with harness calendar fix). Refinance binding constraint: DSCR. Covenant breach months before last lease expiry: 39 (min DSCR 0.57x); after expiry: 13. Sponsor equity required: $1,683M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization QUALIFIED (tautological total-rent calibration) · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** per-building lease schedules, escalators and commencement dates; actual financing.

### Applied Digital — Delta Forge 2
- **Disclosure:** 210 IT (modeled 210.00 IT MW); reported ~$5,200M over 15 years; window 2028-03 to 2028-06. Tier `APPROX_DISCLOSED_CONTRACT_TOTAL`. Source facts: F11.
- **Catalog note:** 210 IT MW, 1H28 delivery
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 −$225.4M -> patched −$219.6M (patched with harness calendar fix). Refinance binding constraint: DSCR. Covenant breach months before last lease expiry: 44 (min DSCR 0.52x); after expiry: 13. Sponsor equity required: $1,195M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization QUALIFIED (tautological total-rent calibration) · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** per-building lease schedules, escalators and commencement dates; actual financing.

### Cipher — Barber Lake
- **Disclosure:** 168 IT (modeled 168.00 IT MW); reported ~$9,000M over 20 years; window 2026-10 to 2027-01. Tier `LOWER_BOUND_OR_SCOPE_MISMATCH`. Source facts: bundle catalog only — not re-opened in this review.
- **Catalog note:** 168 IT MW disclosed first phase vs 300 gross MW campus; $9B+ over 20 years minimum proxy
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $654.1M -> patched $665.4M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 0; after expiry: 13. Sponsor equity required: $569M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization NOT APPLICABLE / scope-limited · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** the revenue figure is a minimum or portfolio-level number; do not treat it as rent.

### Cipher — Black Pearl AWS
- **Disclosure:** 300 gross (modeled 230.77 IT MW); reported ~$5,500M over 15 years; window 2026-08 to 2026-12. Tier `MIXED_CAPACITY_AND_CONTRACT_SCOPE`. Source facts: bundle catalog only — not re-opened in this review.
- **Catalog note:** 300 gross MW, not IT MW; assumed PUE 1.30 converts to IT MW
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $786.7M -> patched $799.7M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 2 (min DSCR 1.11x); after expiry: 13. Sponsor equity required: $775M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization NOT APPLICABLE / scope-limited · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** gross MW converted at an assumed PUE of 1.30; the contract scope does not match the capacity scope.

### Crusoe — Abilene Lancium Stargate
- **Disclosure:** 1200 gross (modeled 923.08 IT MW); no public lease value; window 2025-06 to 2026-07. Tier `PHYSICAL_SCREEN_ONLY`. Source facts: bundle catalog only — not re-opened in this review.
- **Catalog note:** 1200 total gross MW; phase 1 200+ MW; no public lease terms in cited release
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $3,594.8M -> patched $3,646.0M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 4 (min DSCR 0.42x); after expiry: 13. Sponsor equity required: $2,716M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization NOT APPLICABLE / scope-limited · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** no lease terms; rent is the $170/kW-month default; gross MW converted at an assumed PUE.

### IREN — Sweetwater 1 initial construction
- **Disclosure:** 300 gross (modeled 230.77 IT MW); no public lease value; window 2027-10 to 2027-12. Tier `PHYSICAL_SCREEN_ONLY`. Source facts: bundle catalog only — not re-opened in this review.
- **Catalog note:** 300 gross MW under construction, initial 1400 MW planned; conditional ERCOT process
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $711.2M -> patched $722.2M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 1 (min DSCR 1.13x); after expiry: 13. Sponsor equity required: $783M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization NOT APPLICABLE / scope-limited · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** no lease terms; rent is the $170/kW-month default; gross MW converted at an assumed PUE.

### IREN — Sweetwater 2 planned
- **Disclosure:** 600 gross (modeled 461.54 IT MW); no public lease value; window 2028-06 to 2029-06. Tier `PHYSICAL_SCREEN_ONLY`. Source facts: bundle catalog only — not re-opened in this review.
- **Catalog note:** 600 gross MW planned; date is MODEL ASSUMPTION, not disclosed target
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $1,274.4M -> patched $1,297.1M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 6 (min DSCR 1.13x); after expiry: 13. Sponsor equity required: $1,475M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS (patched) · public normalization NOT APPLICABLE / scope-limited · contract cash flows FAIL/NOT POSSIBLE · financing reproduction FAIL (generic debt) · physical power QUALIFIED (disclosure only) · external review NOT STARTED.
- **Key gaps:** no lease terms; rent is the $170/kW-month default; gross MW converted at an assumed PUE.

### Core Scientific — Denton
- **Disclosure:** 260 leased per catalog (not re-confirmed, F33); term 12 years; tier `PHYSICAL_SCREEN_ONLY`. Notes subsidiary guarantor (F32).
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $815.8M -> patched $827.0M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 2 (min DSCR 0.98x); after expiry: 13. Sponsor equity required: $799M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS · normalization NOT APPLICABLE · contract FAIL/NOT POSSIBLE · financing FAIL (see §3) · physical QUALIFIED · external NOT STARTED.

### Core Scientific — Dalton
- **Disclosure:** 175 leased per catalog (not re-confirmed, F33); term 12 years; tier `PHYSICAL_SCREEN_ONLY`. Notes subsidiary guarantor (F32).
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $513.0M -> patched $520.7M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 0; after expiry: 13. Sponsor equity required: $525M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS · normalization NOT APPLICABLE · contract FAIL/NOT POSSIBLE · financing FAIL (see §3) · physical QUALIFIED · external NOT STARTED.

### Core Scientific — Muskogee
- **Disclosure:** 70 leased per catalog (not re-confirmed, F33); term 12 years; tier `PHYSICAL_SCREEN_ONLY`. Notes subsidiary guarantor (F32).
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $189.3M -> patched $192.3M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 0; after expiry: 16. Sponsor equity required: $239M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS · normalization NOT APPLICABLE · contract FAIL/NOT POSSIBLE · financing FAIL (see §3) · physical QUALIFIED · external NOT STARTED.

### Core Scientific — Marble
- **Disclosure:** 65 leased per catalog (not re-confirmed, F33); term 12 years; tier `PHYSICAL_SCREEN_ONLY`. Notes subsidiary guarantor (F32).
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $194.4M -> patched $196.9M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 0; after expiry: 14. Sponsor equity required: $216M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS · normalization NOT APPLICABLE · contract FAIL/NOT POSSIBLE · financing FAIL (see §3) · physical QUALIFIED · external NOT STARTED.

### Core Scientific — Austin
- **Disclosure:** 20 leased per catalog (not re-confirmed, F33); term 7 years; tier `PHYSICAL_SCREEN_ONLY`. Notes subsidiary guarantor, excluded from the completion guarantee (F32).
- **Model:** Synthetic common-assumption run (capex $7M/IT MW, 65% LTC at 8%, refinance, exit $12M/MW, unlimited sponsor): equity NPV v25.8 $2.7M -> patched $3.3M (patched with harness calendar fix). Refinance binding constraint: LTV. Covenant breach months before last lease expiry: 0; after expiry: 49. Sponsor equity required: $106M. These are illustrative outputs of assumed inputs, not project returns, and must not be ranked.
- **Verdicts:** arithmetic PASS · normalization NOT APPLICABLE · contract FAIL/NOT POSSIBLE · financing FAIL (see §3) · physical QUALIFIED · external NOT STARTED.
