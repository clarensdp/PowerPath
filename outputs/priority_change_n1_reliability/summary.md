# PowerPath results summary

## Customer inputs
- Preferences (speed / cost / clean): 34 / 33 / 33 → value of opening a month earlier $5.2M, internal carbon price $100/t (customer valuations, not common costs)
- Must-haves: none
- Opening months tested: 14, 16, 17, 18, 19, 20, 22, 24, 26; grid delay 0 months

## Recommendation
- Initial service: month 18; full demand: month 28
- Portfolio: Solar contract 65 MW, Wind contract 150 MW, Gas turbine 50 MW

## Cost (common benchmark accounting, packet checker)
- Local energy cost: $283.4M (57.20 $/MWh local served)
- Relocation cost: $0.02M; interruption consequence: $0.00M
- Total decision cost: $283.4M (57.20 $/MWh requested)

## Environment
- CO₂: local 365,773 t, remote 51 t, combined 365,824 t
- Combined electricity intensity: 73.8 kg CO₂/MWh
- Clean share (annual accounting): 79.5%

## Service
- Requested 4,954,893 MWh; served locally 4,954,713; relocated 177 (remote electricity 186); interrupted 2
- Merchant electricity: 639,475 MWh (12.9% of local served)
- Physical checks passed: True; max grid import 74.98 MW

## v4 diagnostics
- Clean energy curtailed (paid for, unused): 649,951 MWh, $24.1M
- Hourly clean matching: 79.5% of local load; 38.0% of operating hours fully clean (annual share above is a different metric)
- Merchant price-spike premium (> $200/MWh): $0.20M vs $117.5M if all-merchant
- Largest-unit outage (25 MW gas turbine): 0 hours unservable, worst 0.0 MW; expected consequence $0.02M at a 3% forced-outage planning assumption

## Why this portfolio
- **Opening at month 14 was tested and fails**: No combination of catalog resources meets the hourly demand and your must-haves at this opening month.
- **65 MW solar contract** at $40/MWh on all available energy from month 24.
- **150 MW wind contract** at $35/MWh, the cheapest clean energy; oversized beyond load because night wind fills hours solar cannot.
- **50 MW gas turbine** (from month 18): cheapest firm onsite MW; covers stress windows when imports drop to 60% of the connection.
- **Grid stress**: imports fall to 60% of the connection in 32 hours a year. Over the horizon 177 MWh of Tier 1 is relocated and 2 MWh of Tier 2 interrupted; Tier 0 is always served on site.
- **Your clean weight** adds an internal carbon price of $100/t when choosing resources. This is a valuation, not a cash cost.
- **Your speed weight** values each month of earlier opening at $5.2M.

## Alternatives (each passes the packet checker)
- **Fast Track** (Earliest feasible opening: month 16): gains opens 2 months earlier, 2 MWh less Tier 2 interruption; gives up 9.07 $/MWh dearer, 8 kg/MWh dirtier. Wins if a month of earlier opening is worth more than $20.6M.
- **Lower Cost** (Lowest $/MWh found: opens month 26, no carbon weight): gains 3.45 $/MWh cheaper; gives up 62 kg/MWh dirtier, opens 8 months later, 16 MWh more Tier 2 interruption. Wins if avoiding CO₂ is worth less than $55/t to you.
- **Cleaner** (Same opening (month 18), +$150/t internal carbon price): gains 20 kg/MWh cleaner, 2 MWh less Tier 2 interruption; gives up 3.67 $/MWh dearer. Costs $179 per tonne avoided. Wins if your carbon value is above that.

## Execution: what's next (planning assumptions, not benchmark inputs)
- Gas turbine (50 MW): needed M18; file permit by M-6, order/sign by M-28. TCEQ air-authorization screening for gas turbines + local permitting.
- Wind contract (150 MW): needed M18; order/sign by M12. Physical PPA execution (seller holds project permits and its own interconnection).
- Solar contract (65 MW): needed M24; order/sign by M18. Physical PPA execution (seller holds project permits and its own interconnection).
- Large-load service / interconnection screening (Texas; applicability unverified): start by M-6 (Transmission provider / ERCOT / PUCT).
- Site plan, zoning and building permits for the campus: start by M9 (Williamson County / city (ETJ dependent)).
- Natural gas supply agreement and lateral to site: start by M6 (Gas utility / pipeline).
- Texas SB 6 backup disclosure: 50 MW firm onsite vs 38 MW (50% of load).
- ⚠ Gas turbine: the first action was due in month -28, 28 months before today (month 0). Unless the offer's delivery slot is secured, expect a slip.

## Annual results

| Year | Requested MWh | Total decision $ | $/MWh req. | kg CO₂/MWh | Clean share |
|---|---|---|---|---|---|
| 2 | 151,986 | 13,140,761 | 86.46 | 169 | 64.8% |
| 3 | 571,827 | 33,723,093 | 58.97 | 98 | 76.3% |
| 4 | 604,440 | 33,375,826 | 55.22 | 70 | 80.5% |
| 5 | 604,440 | 33,509,294 | 55.44 | 69 | 80.5% |
| 6 | 604,440 | 33,649,171 | 55.67 | 68 | 80.5% |
| 7 | 604,440 | 33,785,283 | 55.90 | 67 | 80.5% |
| 8 | 604,440 | 33,939,932 | 56.15 | 66 | 80.5% |
| 9 | 604,440 | 34,084,100 | 56.39 | 66 | 80.4% |
| 10 | 604,440 | 34,233,536 | 56.64 | 65 | 80.4% |