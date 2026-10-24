# PowerPath results summary

## Customer inputs
- Preferences (speed / cost / clean): 80 / 20 / 0 → value of opening a month earlier $20.0M, internal carbon price $0/t (customer valuations, not common costs)
- Must-haves: {'max_intensity_kg': 100.0}
- Opening months tested: 14, 16, 17, 18, 19, 20, 22, 24, 26; grid delay 0 months

## Recommendation
- Initial service: month 18; full demand: month 28
- Portfolio: Solar contract 65 MW, Wind contract 130 MW, Gas turbine 25 MW

## Cost (common benchmark accounting, packet checker)
- Local energy cost: $252.7M (51.03 $/MWh local served)
- Relocation cost: $0.24M; interruption consequence: $0.58M
- Total decision cost: $253.5M (51.17 $/MWh requested)

## Environment
- CO₂: local 461,304 t, remote 563 t, combined 461,867 t
- Combined electricity intensity: 93.2 kg CO₂/MWh
- Clean share (annual accounting): 75.1%

## Service
- Requested 4,954,893 MWh; served locally 4,952,365; relocated 1,944 (remote electricity 2,041); interrupted 584
- Merchant electricity: 695,772 MWh (14.0% of local served)
- Physical checks passed: True; max grid import 74.93 MW

## v4 diagnostics
- Clean energy curtailed (paid for, unused): 384,279 MWh, $14.4M
- Hourly clean matching: 75.1% of local load; 27.7% of operating hours fully clean (annual share above is a different metric)
- Merchant price-spike premium (> $200/MWh): $7.33M vs $117.5M if all-merchant
- Largest-unit outage (25 MW gas turbine): 7,796 hours unservable, worst 24.6 MW; expected consequence $2.91M at a 3% forced-outage planning assumption

## Why this portfolio
- **65 MW solar contract** at $40/MWh on all available energy from month 24.
- **130 MW wind contract** at $35/MWh, the cheapest clean energy; oversized beyond load because night wind fills hours solar cannot.
- **25 MW gas turbine** (from month 18): cheapest firm onsite MW; covers stress windows when imports drop to 60% of the connection.
- **Grid stress**: imports fall to 60% of the connection in 32 hours a year. Over the horizon 1,944 MWh of Tier 1 is relocated and 584 MWh of Tier 2 interrupted; Tier 0 is always served on site.
- **Your emissions cap is binding**: the optimizer is paying an implied $14/t to stay under it.
- **Your speed weight** values each month of earlier opening at $20.0M.

## Alternatives (each passes the packet checker)
- **Fast Track** (Earliest feasible opening: month 14): gains opens 4 months earlier, 513 MWh less Tier 2 interruption; gives up 26.47 $/MWh dearer, 7 kg/MWh dirtier. Wins if a month of earlier opening is worth more than $30.0M.
- **Lower Cost** (Lowest $/MWh found: opens month 26, no carbon weight): gains 0.22 $/MWh cheaper, 42 MWh less Tier 2 interruption; gives up 7 kg/MWh dirtier, opens 8 months later. Wins if avoiding CO₂ is worth less than $33/t to you.
- **Cleaner** (Same opening (month 18), +$150/t internal carbon price): gains 35 kg/MWh cleaner, 211 MWh less Tier 2 interruption; gives up 3.04 $/MWh dearer. Costs $86 per tonne avoided. Wins if your carbon value is above that.

## Execution: what's next (planning assumptions, not benchmark inputs)
- Gas turbine (25 MW): needed M18; file permit by M-6, order/sign by M-28. TCEQ air-authorization screening for gas turbines + local permitting.
- Wind contract (130 MW): needed M18; order/sign by M12. Physical PPA execution (seller holds project permits and its own interconnection).
- Solar contract (65 MW): needed M24; order/sign by M18. Physical PPA execution (seller holds project permits and its own interconnection).
- Large-load service / interconnection screening (Texas; applicability unverified): start by M-6 (Transmission provider / ERCOT / PUCT).
- Site plan, zoning and building permits for the campus: start by M9 (Williamson County / city (ETJ dependent)).
- Natural gas supply agreement and lateral to site: start by M6 (Gas utility / pipeline).
- Texas SB 6 backup disclosure: 25 MW firm onsite vs 38 MW (50% of load).
- ⚠ Gas turbine: the first action was due in month -28, 28 months before today (month 0). Unless the offer's delivery slot is secured, expect a slip.

## Annual results

| Year | Requested MWh | Total decision $ | $/MWh req. | kg CO₂/MWh | Clean share |
|---|---|---|---|---|---|
| 2 | 151,986 | 10,359,658 | 68.16 | 178 | 63.1% |
| 3 | 571,827 | 29,745,404 | 52.02 | 113 | 72.7% |
| 4 | 604,440 | 29,783,828 | 49.28 | 90 | 75.9% |
| 5 | 604,440 | 30,007,820 | 49.65 | 89 | 75.9% |
| 6 | 604,440 | 30,236,762 | 50.02 | 88 | 75.9% |
| 7 | 604,440 | 30,477,522 | 50.42 | 87 | 75.9% |
| 8 | 604,440 | 30,720,529 | 50.82 | 87 | 75.9% |
| 9 | 604,440 | 30,976,742 | 51.25 | 86 | 75.9% |
| 10 | 604,440 | 31,241,612 | 51.69 | 86 | 75.9% |