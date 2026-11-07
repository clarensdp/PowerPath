# PowerPath v25.1 — Public Project Benchmark and Stress Test

Run generated 2026-10-25. 16 distinct campus/site benchmarks; 720 synthetic stress cases (45 per project). 0 errors. Max monthly sources/uses residual in resulting stress cases: 0.

## Limitations (read before interpreting)

**These are not independent comparisons of actual project levered returns.** Public projects rarely disclose the debt, opex, capex, delivery tranches, equity waterfall, refinancing valuation, and lease details needed. The disclosed figures calibrate capacity and, where available, contractual revenue. All other financial inputs are deliberately common illustrative assumptions. Gross MW and leased customer power are not automatically critical IT MW; conversion is hypothetical and tagged. The model's exit value is a scenario assumption, not observed market valuation. All stress results are therefore sensitivity testing, not forecast accuracy.

## Dataset summary

| Public case | MW input | Evidence quality | Proxy annual revenue ($M) | Modeled equity NPV ($M) | Maximum residual |
|---|---:|---|---:|---:|---:|
| Polaris Forge 1 | 400 IT | lease_economics | 733.33 | 765.53 | 0 |
| Polaris Forge 2 | 200 IT | lease_economics | 333.33 | 165.69 | 0 |
| Polaris Forge 3 | 300 IT | lease_economics | 500 | 228.04 | 0 |
| Delta Forge 1 | 300 IT | lease_economics | 500 | 220.6 | 0 |
| Delta Forge 2 | 210 IT | lease_economics | 346.67 | 136.42 | 0 |
| Helios CoreWeave phases I–III | 526 IT | lease_economics | 1200 | 2453.06 | 0 |
| Barber Lake | 168 IT | lease_economics | 450 | 1487.22 | 0 |
| Black Pearl AWS | 300 gross | mixed_units_proxy | 366.67 | 75.42 | 0 |
| Denton | 260 leased | physical_schedule_only | n/d | 813.64 | 0 |
| Dalton | 175 leased | physical_schedule_only | n/d | 512.38 | 0 |
| Muskogee | 70 leased | physical_schedule_only | n/d | 189.91 | 0 |
| Marble | 65 leased | physical_schedule_only | n/d | 194.77 | 0 |
| Austin | 20 leased | physical_schedule_only | n/d | 3.42 | 0 |
| Abilene Lancium Stargate | 1200 gross | physical_schedule_only | n/d | 3479.03 | 0 |
| Sweetwater 1 initial construction | 300 gross | physical_schedule_only | n/d | 711.85 | 0 |
| Sweetwater 2 planned | 600 gross | physical_schedule_only | n/d | 1276.15 | 0 |

## Key model weaknesses surfaced
- Uniform cost, exit, and refinancing assumptions drive outputs more than the limited public facts; do not rank projects by synthetic NPV.
- The engine has no lease-expiry cessation for shorter leases, so late-horizon rents remain modeled even after reported base terms end.
- The engine uses shared global construction loan/exit assumptions; it cannot represent some disclosed tenant-funded capex structures, 15-20 year contractual escalators, power pass-through arrangements, or multiple debt facilities.
- Refinance debt sizing uses assumed property value and LTV, not lender DSCR and debt yield checks.
- A historical quote is not a signed grid capacity agreement and benchmark construction dates are often target rather than actual.

## Disclosures and traceability
- **Polaris Forge 1**: 100+150+150 IT MW; 15-year contracted value. https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm
- **Polaris Forge 2**: 200 IT MW, first 2H26, full early 2027. https://ir.applieddigital.com/sec-filings/all-sec-filings/content/0001144879-26-000048/apld-20260531.htm
- **Polaris Forge 3**: 300 IT MW, 2H27–2H28 delivery. https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm
- **Delta Forge 1**: 300 IT MW, 1H27–1H28 delivery. https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm
- **Delta Forge 2**: 210 IT MW, 1H28 delivery. https://www.sec.gov/Archives/edgar/data/1144879/000114487926000048/apld-20260531.htm
- **Helios CoreWeave phases I–III**: $1.2B+ average annual revenue; $18B/15y is MINIMUM proxy; 526 IT MW, 800 gross MW; 133 IT MW Phase I. https://www.sec.gov/Archives/edgar/data/1859392/000185939226000084/glxy-20260630xpressrelease.htm
- **Barber Lake**: 168 IT MW disclosed first phase vs 300 gross MW campus; $9B+ over 20 years minimum proxy. https://investors.cipherdigital.com/news-releases/news-release-details/cipher-digital-expands-barber-lake-lease-term-20-years/
- **Black Pearl AWS**: 300 gross MW, not IT MW; assumed PUE 1.30 converts to IT MW. https://www.sec.gov/Archives/edgar/data/1819989/000181998925000110/ciphermining_businessupd.htm
- **Denton**: ~260 MW customer leased power; revenue only group disclosed. https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm
- **Dalton**: ~175 MW customer leased power; phase 1 30 MW delivered. https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm
- **Muskogee**: ~70 MW leased power; no per-site revenue disclosed. https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm
- **Marble**: ~65 MW leased power, handed over; no per-site revenue disclosed. https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm
- **Austin**: ~20 MW leased power, delivered, 7-year contract rather than 12. https://www.sec.gov/Archives/edgar/data/1839341/000162828026031246/q1fy26earningsdeck.htm
- **Abilene Lancium Stargate**: 1200 total gross MW; phase 1 200+ MW; no public lease terms in cited release. https://www.crusoe.ai/resources/newsroom/crusoe-expands-ai-data-center-campus-in-abilene-to-1-2-gigawatts
- **Sweetwater 1 initial construction**: 300 gross MW under construction, initial 1400 MW planned; conditional ERCOT process. https://iren.gcs-web.com/news-releases/news-release-details/irens-2gw-sweetwater-hub-included-base-load-ercot-batch-zero
- **Sweetwater 2 planned**: 600 gross MW planned; date is MODEL ASSUMPTION, not disclosed target. https://iren.gcs-web.com/news-releases/news-release-details/irens-2gw-sweetwater-hub-included-base-load-ercot-batch-zero

## Recommended model changes
1. Fix lease term, escalators, and revenue recognition by phase; explicitly distinguish site gross, IT and leased customer power.
2. Connect real capex and financing disclosures as dated versions rather than scenario assumptions.
3. Debt sizing should constrain the minimum of LTV, DSCR, debt yield, and LTC.
4. Add a true backtest mode with forecast as-of dates and realized actuals; this dataset does not justify accuracy statistics.
5. Report cases with incomplete information as stress-only, not calibrated.
