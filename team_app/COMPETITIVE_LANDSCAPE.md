# PowerPath vs Enverus (data-center power)

*Enverus capabilities are as described on enverus.com product pages (Oct 2026); vendor claims are
not independently verified. PowerPath is a hackathon prototype running on the fictional GRIDTECH
benchmark.*

## One-line positioning (v5)
**Enverus sells the modules (Site & Screen, Interconnect for Load, gas analytics, PRISM, research).
PowerPath is the decision layer across them: screening → interconnection → generation → deal
structuring → monitoring in one workflow, ranked by deliverable power, with every decision and
assumption carried forward in a ledger.**

## Earlier positioning
**Enverus tells you where power is and what it costs. PowerPath tells you what to build, when to
open, what it costs you in carbon and reliability, and what to file on Monday.** They are
complementary: PowerPath is a decision layer that could run on Enverus-grade data.

## Side by side

| Dimension | Enverus (Site & Screen, PRISM, Interconnect for Load, Gas Transmission Analytics) | PowerPath v4 |
|---|---|---|
| Core question | Which sites/nodes have deliverable power, at what price, with what risk? | For this campus, which portfolio and opening month best fit the customer's priorities? |
| Location coverage | National parcel-level siting, real substations and nodes | Any US ZIP/state + 17 countries; state/country indices from EIA, eGRID, USDA; parcels illustrative unless a CSV is uploaded |
| Data breadth | 156M+ parcels, 43K+ substations, 60K+ LMP nodes, ~30K gas meters, 100K+ projects, 20-yr hourly nodal forecasts | One campus, the packet's 8,760-h reference year ×10 with price/CO₂ trajectories. **Enverus is far ahead.** |
| Interconnection | Large-load screening at every bus (PJM, MISO, SPP, WECC, ERCOT), upgrade costs, queue depth | Takes the grid schedule as given; delay is a sensitivity |
| Behind-the-meter | 8,760-h comparison of grid, onsite, storage and hybrid designs; gas supply validation (BYOG) | MILP sizing of 7 resources in catalog blocks + chronological dispatch of 87,600 h; gas supply assumed ready |
| Customer priorities | Site scoring against consistent criteria | **Hard must-haves vs preferences**, preferences converted into $/month of speed and $/t CO₂, break-even "where the answer flips" |
| Optimization | Valuation/ranking models; no portfolio optimizer described | Mixed-integer optimization per opening month, checked on every hour |
| Demand flexibility | Not described | Tier 0/1/2 response in grid-stress events, relocation emissions counted at the remote site |
| Reliability | "Five-nines" modeled reliability claim | Explicit largest-unit (N-1) test hour by hour, with cost to cover; optional must-have |
| Emissions | Carbon exposure, 24/7 clean-energy gap assessment | Combined intensity incl. remote, annual clean share, hourly matching, curtailment, $/t abatement of cleaner options |
| Price spikes | Congestion spikes separated from averages; 15–25% cost recoverable via dispatch/hedging (claim) | Spike premium by year vs all-merchant exposure |
| Execution / permitting | Constraint screening "reduces permitting unknowns"; no permitting workflow | Back-planned permit/order/build per resource, Texas pathways labelled as diligence, slip lever re-optimizes, evidence-first feasibility checklist |
| Auditability | Traceable IC-ready evidence | Every figure from the packet's own checker; exports pass `check_submission.py` |
| Delivery | Enterprise SaaS + analyst research (Enverus Intelligence), AI layer (Enverus ONE, Instant Analyst) | Local Streamlit app; open method README |

## What changed with the PowerPath screener
PowerPath now starts where Enverus starts (paste a location, get a feasibility view, parcels and
a price forecast) but keeps going: the same location runs through portfolio optimization, hourly
dispatch, N-1 reliability and an execution plan. Our location data is index-level, so the honest
pitch is "Enverus-style front door, decision engine behind it; plug in Enverus-grade data and the
engine doesn't change."

## Where Enverus is clearly stronger
- Real, national, continuously updated data (parcels, nodes, gas flows, queues).
- Site selection across hundreds of thousands of parcels; PowerPath assumes the site.
- Interconnection studies and network-upgrade cost estimates.
- Enterprise maturity, research team, customer base (8,000+ companies claimed).

## Where PowerPath adds something Enverus pages don't describe
1. **Preference translation**: speed/cost/clean become two dollar values the customer can challenge, with the threshold at which the recommendation changes.
2. **Hard vs soft separation**, with relaxation advice when must-haves conflict.
3. **Portfolio optimization + full chronological dispatch** with workload-tier response, not just site scoring or design comparison.
4. **N-1 reliability as a priced decision**: the cost-optimal plan relies on one 25 MW turbine block; covering its outage costs about $4/MWh.
5. **Decision → execution loop**: lead times and slips feed straight back into the optimizer.

## How to use this in the pitch (15 seconds)
"Enverus-class platforms answer *where*. Developers still have to answer *what, when and at what
trade-off*, and today that's a consultant spreadsheet. PowerPath is that decision layer: priorities
in, a checked portfolio, its reliability, and the execution plan out. In production it would sit on
top of data like Enverus's rather than compete with it."

## Sources
- Enverus Data Center Siting Solutions: https://www.enverus.com/products/data-center-siting-solutions/
- Enverus Data Center segment: https://www.enverus.com/segments/data-center/
- Enverus webinar, "From Decision to Execution: How to Validate BYOG Sites Before You Commit" (Sep 2, 2026): https://www.enverus.com/webinars/from-decision-to-execution-byog-sites/
