# PowerPath results summary

## Customer inputs
- Preferences (speed / cost / clean): 60 / 30 / 10 → value of opening a month earlier $10.0M, internal carbon price $30/t (customer valuations, not common costs)
- Must-haves: {'full_demand_by': 24}
- Opening months tested: 14; grid delay 0 months

## Recommendation
- Initial service: month 14; full demand: month 24
- Portfolio: Solar contract 45 MW, Wind contract 120 MW, Gas engines 15 MW, Fuel cells 30 MW

## Cost (common benchmark accounting, packet checker)
- Local energy cost: $393.4M (76.31 $/MWh local served)
- Relocation cost: $0.09M; interruption consequence: $0.10M
- Total decision cost: $393.6M (76.33 $/MWh requested)

## Environment
- CO₂: local 621,585 t, remote 204 t, combined 621,789 t
- Combined electricity intensity: 120.6 kg CO₂/MWh
- Clean share (annual accounting): 65.5%

## Service
- Requested 5,156,585 MWh; served locally 5,155,783; relocated 706 (remote electricity 741); interrupted 96
- Merchant electricity: 169,610 MWh (3.3% of local served)
- Physical checks passed: True; max grid import 74.80 MW

## v4 diagnostics
- Clean energy curtailed (paid for, unused): 306,631 MWh, $11.1M
- Hourly clean matching: 65.5% of local load; 13.5% of operating hours fully clean (annual share above is a different metric)
- Merchant price-spike premium (> $200/MWh): $1.27M vs $120.8M if all-merchant
- Largest-unit outage (5 MW gas engines): 143 hours unservable, worst 1.5 MW; expected consequence $0.00M at a 3% forced-outage planning assumption

## Why this portfolio
- **Opening at month 14 is before the grid arrives (month 18)**, so 30 MW fuel cells must carry the first 25 MW alone. That is what buys the early date.
- **45 MW solar contract** at $40/MWh on all available energy from month 24.
- **120 MW wind contract** at $35/MWh, the cheapest clean energy; oversized beyond load because night wind fills hours solar cannot.
- **15 MW gas engines** (from month 16, 5 MW blocks): more efficient than the turbine and available earlier.
- **30 MW fuel cells** (from month 14): the only gas unit available at month 14 and the lowest-emitting, but $4,000/kW.
- **Grid stress**: imports fall to 60% of the connection in 32 hours a year. Over the horizon 706 MWh of Tier 1 is relocated and 96 MWh of Tier 2 interrupted; Tier 0 is always served on site.
- **Your clean weight** adds an internal carbon price of $30/t when choosing resources. This is a valuation, not a cash cost.
- **Your speed weight** values each month of earlier opening at $10.0M.

## Alternatives (each passes the packet checker)
- **Fast Track** (Earliest feasible opening: month 14): gains —; gives up 0.00 $/MWh dearer, 0 kg/MWh dirtier. The recommendation is already the earliest opening that meets your must-haves.
- **Lower Cost** (Lowest $/MWh found: opens month 14, no carbon weight): gains 0.70 $/MWh cheaper; gives up 24 kg/MWh dirtier, 23 MWh more Tier 2 interruption. Wins if avoiding CO₂ is worth less than $29/t to you.
- **Cleaner** (Same opening (month 14), +$150/t internal carbon price): gains 46 kg/MWh cleaner, 60 MWh less Tier 2 interruption; gives up 4.84 $/MWh dearer. Costs $104 per tonne avoided. Wins if your carbon value is above that.

## Execution: what's next (planning assumptions, not benchmark inputs)
- Gas engines (15 MW): needed M16; file permit by M4, order/sign by M-4. TCEQ air-authorization screening for engines; confirm whether standard permit, permit by rule or case-specific authorization applies + local reviews.
- Fuel cells (30 MW): needed M14; file permit by M6, order/sign by M1. TCEQ authorization review (permit-by-rule / standard permit screening) + local building and fire permits.
- Wind contract (120 MW): needed M14; order/sign by M8. Physical PPA execution (seller holds project permits and its own interconnection).
- Solar contract (45 MW): needed M24; order/sign by M18. Physical PPA execution (seller holds project permits and its own interconnection).
- Large-load service / interconnection screening (Texas; applicability unverified): start by M-6 (Transmission provider / ERCOT / PUCT).
- Site plan, zoning and building permits for the campus: start by M5 (Williamson County / city (ETJ dependent)).
- Natural gas supply agreement and lateral to site: start by M2 (Gas utility / pipeline).
- Texas SB 6 backup disclosure: 45 MW firm onsite vs 38 MW (50% of load).
- ⚠ Gas engines: the first action was due in month -4, 4 months before today (month 0). Unless the offer's delivery slot is secured, expect a slip.

## Annual results

| Year | Requested MWh | Total decision $ | $/MWh req. | kg CO₂/MWh | Clean share |
|---|---|---|---|---|---|
| 2 | 321,065 | 34,575,342 | 107.69 | 250 | 29.6% |
| 3 | 604,440 | 45,183,005 | 74.75 | 128 | 63.5% |
| 4 | 604,440 | 44,422,092 | 73.49 | 110 | 68.6% |
| 5 | 604,440 | 44,553,529 | 73.71 | 110 | 68.6% |
| 6 | 604,440 | 44,688,766 | 73.93 | 110 | 68.5% |
| 7 | 604,440 | 44,828,221 | 74.16 | 110 | 68.5% |
| 8 | 604,440 | 44,971,412 | 74.40 | 110 | 68.5% |
| 9 | 604,440 | 45,120,229 | 74.65 | 110 | 68.5% |
| 10 | 604,440 | 45,273,460 | 74.90 | 109 | 68.5% |