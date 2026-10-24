# PowerPath results summary

## Customer inputs
- Preferences (speed / cost / clean): 34 / 33 / 33 → value of opening a month earlier $5.2M, internal carbon price $100/t (customer valuations, not common costs)
- Must-haves: none
- Opening months tested: 14, 16, 18, 20, 21, 22, 23, 24, 26; grid delay 0 months

## Recommendation
- Initial service: month 22; full demand: month 32
- Portfolio: Solar contract 70 MW, Wind contract 160 MW, Battery (4h) 4 MW, Gas engines 10 MW

## Cost (common benchmark accounting, packet checker)
- Local energy cost: $260.0M (54.76 $/MWh local served)
- Relocation cost: $0.36M; interruption consequence: $1.51M
- Total decision cost: $261.9M (55.10 $/MWh requested)

## Environment
- CO₂: local 230,688 t, remote 850 t, combined 231,537 t
- Combined electricity intensity: 48.7 kg CO₂/MWh
- Clean share (annual accounting): 83.7%

## Service
- Requested 4,752,468 MWh; served locally 4,748,034; relocated 2,925 (remote electricity 3,071); interrupted 1,509
- Merchant electricity: 676,224 MWh (14.2% of local served)
- Physical checks passed: True; max grid import 75.00 MW

## v4 diagnostics
- Clean energy curtailed (paid for, unused): 786,431 MWh, $29.2M
- Hourly clean matching: 83.7% of local load; 50.8% of operating hours fully clean (annual share above is a different metric)
- Merchant price-spike premium (> $200/MWh): $10.35M vs $112.9M if all-merchant
- Largest-unit outage (5 MW gas engines): 268 hours unservable, worst 4.7 MW; expected consequence $0.04M at a 3% forced-outage planning assumption
- Availability shifts applied (execution-aware / slip): Battery (4h) +1 months, Gas engines +4 months, Gas turbine +28 months

## Why this portfolio
- **Opening at month 14 was tested and fails**: No combination of catalog resources meets the hourly demand and your must-haves at this opening month.
- **70 MW solar contract** at $40/MWh on all available energy from month 24.
- **160 MW wind contract** at $35/MWh, the cheapest clean energy; oversized beyond load because night wind fills hours solar cannot.
- **4 MW / 16 MWh battery**: charged only from clean contract energy; shifts it into stress windows and price spikes.
- **10 MW gas engines** (from month 16, 5 MW blocks): more efficient than the turbine and available earlier.
- **Grid stress**: imports fall to 60% of the connection in 32 hours a year. Over the horizon 2,925 MWh of Tier 1 is relocated and 1,509 MWh of Tier 2 interrupted; Tier 0 is always served on site.
- **Your clean weight** adds an internal carbon price of $100/t when choosing resources. This is a valuation, not a cash cost.
- **Your speed weight** values each month of earlier opening at $5.2M.

## Alternatives (each passes the packet checker)
- **Fast Track** (Earliest feasible opening: month 16): gains opens 6 months earlier, 1,333 MWh less Tier 2 interruption; gives up 20.16 $/MWh dearer, 31 kg/MWh dirtier. Wins if a month of earlier opening is worth more than $15.2M.
- **Lower Cost** (Lowest $/MWh found: opens month 22, no carbon weight): gains 0.22 $/MWh cheaper, 859 MWh less Tier 2 interruption; gives up 64 kg/MWh dirtier. Wins if avoiding CO₂ is worth less than $3/t to you.
- **Cleaner** (Same opening (month 22), +$150/t internal carbon price): gains 11 kg/MWh cleaner, 109 MWh less Tier 2 interruption; gives up 1.95 $/MWh dearer. Costs $181 per tonne avoided. Wins if your carbon value is above that.

## Execution: what's next (planning assumptions, not benchmark inputs)
- Gas engines (10 MW): needed M22; file permit by M10, order/sign by M2. TCEQ air-authorization screening for engines; confirm whether standard permit, permit by rule or case-specific authorization applies + local reviews.
- Battery (4h) (4 MW): needed M22; file permit by M13, order/sign by M7. Local fire-code review (NFPA 855 / IFC energy-storage provisions), building and electrical permits, utility interconnection of onsite equipment.
- Wind contract (160 MW): needed M22; order/sign by M16. Physical PPA execution (seller holds project permits and its own interconnection).
- Solar contract (70 MW): needed M24; order/sign by M18. Physical PPA execution (seller holds project permits and its own interconnection).
- Large-load service / interconnection screening (Texas; applicability unverified): start by M-6 (Transmission provider / ERCOT / PUCT).
- Site plan, zoning and building permits for the campus: start by M13 (Williamson County / city (ETJ dependent)).
- Natural gas supply agreement and lateral to site: start by M10 (Gas utility / pipeline).
- Texas SB 6 backup disclosure: 14 MW firm onsite vs 38 MW (50% of load).

## Annual results

| Year | Requested MWh | Total decision $ | $/MWh req. | kg CO₂/MWh | Clean share |
|---|---|---|---|---|---|
| 2 | 36,268 | 3,298,378 | 90.95 | 45 | 88.2% |
| 3 | 485,120 | 29,588,971 | 60.99 | 48 | 85.6% |
| 4 | 604,440 | 31,955,508 | 52.87 | 52 | 83.5% |
| 5 | 604,440 | 32,190,305 | 53.26 | 51 | 83.5% |
| 6 | 604,440 | 32,436,049 | 53.66 | 50 | 83.5% |
| 7 | 604,440 | 32,690,998 | 54.08 | 49 | 83.5% |
| 8 | 604,440 | 32,958,557 | 54.53 | 48 | 83.5% |
| 9 | 604,440 | 33,230,155 | 54.98 | 47 | 83.4% |
| 10 | 604,440 | 33,516,940 | 55.45 | 46 | 83.4% |