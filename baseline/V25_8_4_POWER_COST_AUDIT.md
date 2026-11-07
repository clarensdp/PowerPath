# PowerPath v25.8.4 — Electricity Cost Responsibility and Catalog Audit

Date: 26 October 2026. Baseline: v25.8.3. Scope: repair CA-24 power cost burden in the monthly underwriting engine; implement conservative CA-25 public-case catalog improvements. **NO GO for lender-grade use and NO GO for public-project valuations.**

## Root cause and correction

`workspace/underwrite25.js` previously deducted all modeled power spending from landlord EBITDA, irrespective of who was responsible for paying. With 400 IT MW, this can create multibillion-dollar forecast distortions over a long lease even when a customer bears electricity expense.

New **per-project and per-building** modes:

| mode | Landlord P&L expense | Landlord P&L reimbursement | Tenant directly paid cost | EBITDA effect |
|---|---|---|---|---|
| landlord | 100% of relevant energy | 0 | 0 | landlord bears cost |
| tenant_direct | remainder after specified pass-through share | 0 | pass-through share | landlord bears remainder |
| reimbursed | 100% | specified pass-through share, at cost | 0 | landlord bears unreimbursed part |

Pass-through fraction is 0–100%; default mode **landlord** maintains older project outputs exactly. Separate gross-energy, reimbursement, direct payment, net landlord energy cost, lease revenue, and overall reported revenue are exported in monthly schedules. Energy billings never enter the **base rental contract reconciliation**, and percentage-of-revenue opex is applied to base lease revenue, **not** power reimbursement billings.

Model limitation: tenant direct vs bill-and-reimburse P&L and payment timing may differ by executed contract. Current reimbursements are assumed collected in their billing month. Inputs are **scenario assumptions** unless supported by executed documents; this release does not establish actual delivered electricity tariff or load profile. Zero energized/leased IT capacity means zero modeled power consumption; idle infrastructure parasitic load is not modeled.

## Public disclosure and catalog repair (16 cases)

`benchmarks/case_catalog_v2584.json` keeps sourced facts separate from assumptions and old case data remains available as `case_catalog_v258.json`.

- **Applied Digital — Polaris Forge 1/2/3, Delta Forge 1/2.** Public investor presentation explicitly says contracted lease values exclude pass-through power. Scenario mode `reimbursed` is illustrative; the *accounting presentation and collection mechanics remain unverified* without executed lease language. Polaris Forge 1 has a 100/150/150 MW configuration; preliminary $3B/$4B/$4B building allocation from the external audit is flagged **NOT independently confirmed**, rather than presented as official lease schedule. Portfolio headline values remain approximate.
- **Core Scientific — Denton/Dalton/Muskogee/Marble/Austin.** Filed description says customer pays power/utility costs, and a filed April 2026 license summary discloses a standard **$100/kW-month base fee** and **3.5% escalator**, except Austin **$115/kW-month and 3.0%**. Marked `reimbursed` as a scenario consistent with prior investor gross-up illustration; exact payment-chain timing must be verified. `leased_power_MW__not_verified_IT` replaces the implication that all licensed MW are IT MW. Actual site-specific IT allocations remain an exception.
- **Cipher Barber Lake.** Incorporates disclosed **168 + 39 = 207 critical IT MW**, two successive approximately 10-year commitments, phased delivery Q4 2026–Q1 2027, and **over $9B** total revenue as a **lower bound** rather than exact contract total. The separate leases are **not** yet integrated as consecutive building-level payment schedules.
- **Galaxy Helios.** Disclosed `>$1B` average annual revenue is not normalized into an invented $18B total contracted rent. Gross/IT capacity and project-phase financing scopes remain separate.
- **IREN Sweetwater 1/2.** September 2026 release describes conditional ERCOT Batch Zero status and 300 gross MW of construction at Sweetwater 1 with Q4 2027 targeted delivery; does not prove all 1.4 GW/600 MW has service rights.

Primary-source references included in the catalog and below. Transaction-specific lease rent schedules, power bills, indentures, utility agreements, and credit mechanics are still incomplete. No project model is contract-verified.

## Quantified *scenario* impact

The 16-case replay applies the updated per-project power payer assumption while holding old synthetic capex, electricity unit price, borrowing and exit assumptions constant. These **are not actual investment valuations**. Illustrative NPV impact in $M:

| Case | Change vs v25.8.3 |
|---|---:|
| Polaris Forge 1 | +2,648.699 |
| Polaris Forge 2 | +1,318.350 |
| Polaris Forge 3 | +1,778.618 |
| Delta Forge 1 | +1,825.413 |
| Delta Forge 2 | +1,216.065 |
| Core Scientific — Denton | +1,616.109 |

The large movements demonstrate that the cost-allocation assumption can dominate the underwrite. They do **not** indicate the projects are now profitable, performing credit cases or accurately valued. All 16 synthetic cases still show covenant breaches; this code change does not fix the underlying debt structure.

## QA evidence

- **25/25** JavaScript test scripts passed, including 10 new v25.8.4 pass-through controls.
- **1,152** independently calculated monthly power and CFADS field spot-checks passed across 6 energy-payer variants and 24 monthly periods. Maximum gap **2.22e-16 $M**.
- **16/16** public-project catalog cases completed under clearly labeled assumptions.
- **720/720** combined scenario stresses completed with zero accounting exceptions at the selected tolerance.
- Chromium smoke checks passed at widths 1440px and 390px, no JS errors or horizontal overflow.

One important qualification: the independent Python calculation isolates power and operating arithmetic only; it is not an independent lender cash waterfall.

## Still open — finance/model governance priorities

1. **N7/N8**: contract-specific multiple debt facilities, fixed-rate note schedules, amortization triggers, OID, relevant leases/collateral, DSRA and creditor priorities.
2. **N9**: actual building-level payment schedules with commencement, credits, abatements and power pass-through collection timing. Sequential Barber Lake commitments not yet modeled separately.
3. **N10**: site-specific demand charges, utility tariffs, actual PUE/load shapes and collection/billing lags. The present approach is a gross deterministic energy-cost proxy.
4. **G4/G5**: no source-backed project debt waterfall reconciliation and no external qualified lender-side model audit.
5. Underwriting outcomes are not certified and the observed contract economics must not be inferred from synthetic benchmark outputs.

## Reproduce

```
cd <unpacked PowerPath v25.8.4 source directory>
node workspace/test_power_pass2584.cjs
python independent_power_reference.py
node benchmarks/run_power_cost_2584.cjs
python workspace/build_page.py
```

## Official source references

- Applied Digital FY2026 10-K: https://ir.applieddigital.com/sec-filings/all-sec-filings/content/0001144879-26-000048/apld-20260531.htm
- Applied Digital investor presentation, slide 25 (power excluded from revenue): https://ir.applieddigital.com/sec-filings/all-sec-filings/content/0001144879-26-000036/apld_invxinvestorpresent.htm
- Core Scientific April 2026 contract summary: https://investors.corescientific.com/sec-filings/all-sec-filings/content/0001193125-26-165121/d149019dex992.htm
- Core Scientific investor presentation, power pass-through gross-up mechanics: https://investors.corescientific.com/sec-filings/all-sec-filings/content/0001628280-26-031246/q1fy26earningsdeck.htm
- Cipher Barber Lake September 2026 amendment: https://www.sec.gov/Archives/edgar/data/1819989/000181998926000043/barberlakeleaseamendmentpr.htm
- IREN Sweetwater September 2026 conditional status: https://iren.gcs-web.com/news-releases/news-release-details/irens-2gw-sweetwater-hub-included-base-load-ercot-batch-zero
