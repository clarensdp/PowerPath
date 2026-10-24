# PowerPath results summary

## Customer inputs
- Preferences (speed / cost / clean): 34 / 33 / 33 → value of opening a month earlier $5.2M, internal carbon price $100/t (customer valuations, not common costs)
- Must-haves: none
- Opening months tested: 14, 16, 17, 18, 19, 20, 22, 24, 26; grid delay 0 months

## Recommendation
- Initial service: month 18; full demand: month 28
- Portfolio: Solar contract 70 MW, Wind contract 155 MW, Gas turbine 25 MW

## Cost (common benchmark accounting, packet checker)
- Local energy cost: $262.8M (53.07 $/MWh local served)
- Relocation cost: $0.22M; interruption consequence: $0.43M
- Total decision cost: $263.5M (53.18 $/MWh requested)

## Environment
- CO₂: local 321,644 t, remote 510 t, combined 322,154 t
- Combined electricity intensity: 65.0 kg CO₂/MWh
- Clean share (annual accounting): 81.0%

## Service
- Requested 4,954,893 MWh; served locally 4,952,703; relocated 1,759 (remote electricity 1,847); interrupted 430
- Merchant electricity: 664,733 MWh (13.4% of local served)
- Physical checks passed: True; max grid import 75.00 MW

## v4 diagnostics
- Clean energy curtailed (paid for, unused): 770,402 MWh, $28.6M
- Hourly clean matching: 81.0% of local load; 42.1% of operating hours fully clean (annual share above is a different metric)
- Merchant price-spike premium (> $200/MWh): $5.18M vs $117.5M if all-merchant
- Largest-unit outage (25 MW gas turbine): 7,796 hours unservable, worst 24.6 MW; expected consequence $2.92M at a 3% forced-outage planning assumption

## Why this portfolio
- **70 MW solar contract** at $40/MWh on all available energy from month 24.
- **155 MW wind contract** at $35/MWh, the cheapest clean energy; oversized beyond load because night wind fills hours solar cannot.
- **25 MW gas turbine** (from month 18): cheapest firm onsite MW; covers stress windows when imports drop to 60% of the connection.
- **Grid stress**: imports fall to 60% of the connection in 32 hours a year. Over the horizon 1,759 MWh of Tier 1 is relocated and 430 MWh of Tier 2 interrupted; Tier 0 is always served on site.
- **Your clean weight** adds an internal carbon price of $100/t when choosing resources. This is a valuation, not a cash cost.
- **Your speed weight** values each month of earlier opening at $5.2M.

## Alternatives (each passes the packet checker)
- **Fast Track** (Earliest feasible opening: month 14): gains opens 4 months earlier, 375 MWh less Tier 2 interruption; gives up 25.74 $/MWh dearer, 22 kg/MWh dirtier. Wins if a month of earlier opening is worth more than $29.2M.
- **Lower Cost** (Lowest $/MWh found: opens month 26, no carbon weight): gains 2.32 $/MWh cheaper; gives up 46 kg/MWh dirtier, opens 8 months later, 162 MWh more Tier 2 interruption. Wins if avoiding CO₂ is worth less than $51/t to you.
- **Cleaner** (Same opening (month 18), +$150/t internal carbon price): gains 15 kg/MWh cleaner, 161 MWh less Tier 2 interruption; gives up 2.96 $/MWh dearer. Costs $196 per tonne avoided. Wins if your carbon value is above that.

## Execution: what's next (planning assumptions, not benchmark inputs)
- Gas turbine (25 MW): needed M18; file permit by M-6, order/sign by M-28. TCEQ air-authorization screening for gas turbines + local permitting.
- Wind contract (155 MW): needed M18; order/sign by M12. Physical PPA execution (seller holds project permits and its own interconnection).
- Solar contract (70 MW): needed M24; order/sign by M18. Physical PPA execution (seller holds project permits and its own interconnection).
- Large-load service / interconnection screening (Texas; applicability unverified): start by M-6 (Transmission provider / ERCOT / PUCT).
- Site plan, zoning and building permits for the campus: start by M9 (Williamson County / city (ETJ dependent)).
- Natural gas supply agreement and lateral to site: start by M6 (Gas utility / pipeline).
- Texas SB 6 backup disclosure: 25 MW firm onsite vs 38 MW (50% of load).
- ⚠ Gas turbine: the first action was due in month -28, 28 months before today (month 0). Unless the offer's delivery slot is secured, expect a slip.

## Annual results

| Year | Requested MWh | Total decision $ | $/MWh req. | kg CO₂/MWh | Clean share |
|---|---|---|---|---|---|
| 2 | 151,986 | 11,383,714 | 74.90 | 167 | 65.1% |
| 3 | 571,827 | 31,269,310 | 54.68 | 91 | 77.5% |
| 4 | 604,440 | 30,954,441 | 51.21 | 61 | 82.1% |
| 5 | 604,440 | 31,139,248 | 51.52 | 60 | 82.1% |
| 6 | 604,440 | 31,333,140 | 51.84 | 59 | 82.1% |
| 7 | 604,440 | 31,529,143 | 52.16 | 58 | 82.1% |
| 8 | 604,440 | 31,742,694 | 52.52 | 57 | 82.1% |
| 9 | 604,440 | 31,952,556 | 52.86 | 56 | 82.1% |
| 10 | 604,440 | 32,173,638 | 53.23 | 55 | 82.0% |