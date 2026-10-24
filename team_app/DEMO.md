<<<<<<< HEAD
# PowerPath demo script · one decision layer (5 minutes)

**Open line (15 s):** "Large-load projects now live or die on deliverable power: queue exposure,
upgrade timelines, fuel and nodal economics. Enverus-class tools tell you what's true at a site.
PowerPath makes the decision: it screens, picks the interconnection path, sizes the plan, structures
the deal and tells you what would change it, in one workflow."

1. **Stage bar + ledger (20 s).** Point at the five verdicts across the top and the decision ledger
   in the sidebar: every stage's answer and assumptions in one place.
2. **1 · Screen (45 s).** Default list: Georgetown TX, Ashburn VA, Iowa, Ohio, Ireland. Rank by
   *Deliverable power*: Texas carries 75 MW at month 30, PJM sites not until month 54. Switch to
   *Feasibility score* to show the breakdown. Make **Ohio** the active site.
3. **2 · Interconnect (45 s).** "PJM P50 grid wait +24 months. Bridge: opens 22 months sooner for
   $64M more, $2.9M per month gained; at $5.2M/month value of time, bridge." Show the power-gap chart.
4. **Back to Texas, 3 · Generate (75 s).** Recommendation, Explain, Speed·cost·CO₂, Stress & N-1:
   the rubric core (portfolio, grid-stress response, alternatives, costs, carbon). Preset 1 (full
   demand by 24) shows the price of speed; the N-1 button shows reliability priced in.
5. **4 · Structure (40 s).** Own vs tolling vs utility tariff: capital, obligations, risk table.
   Tick *Prefer off-balance-sheet*: the pick flips to tolling at +3%.
6. **5 · Execute & monitor (40 s).** Execution Gantt with the late turbine flag, then triggers:
   merchant +20%, gas +30%, P90 grid slip, each with impact and action.
7. **Close (15 s).** "Every number for the benchmark comes from the packet's own checker; other sites
   use labelled regional indices. Plug in Enverus-grade data and the decision layer doesn't change."



## Previous script (detail)
=======
>>>>>>> 10d34e8308ad89fdb3f0f82e1a66d94629501b7f
# PowerPath 5-minute demo script (mapped to the rubric)

## 0:00–0:45 · Open on the SITE screener (new)
"Paste any ZIP." Default compares Georgetown TX (78626), Ashburn VA (20147), Iowa, Ohio and Ireland.
Point at the score bars (cost, speed, carbon, land, water, policy, each with its basis), the map of
candidate parcels, and the price forecast. "Texas is our ground truth: the official 87,600-hour
benchmark. Every other site re-runs the same engine on regional inputs." Click **Make Texas the
active site** (or stay) and move to PORT.


**Tagline:** "Every MW, every month, every trade-off explained."

**Positioning line (10 s):** "Most tools rank technologies or pick a weighting. PowerPath turns the
customer's priorities into two dollar numbers they can argue with, keeps hard requirements as
hard constraints, and every number on screen comes from the packet's own checker."

## 0:00–1:00 · Product + Methodology
1. Sidebar: point at the two boxes. *Must-haves* (never traded away) vs *Nice-to-haves* (traded).
2. Move the speed slider: the blue box updates "opening one month earlier is worth $X; a tonne of
   CO₂ is worth $Y". That sentence is the whole preference model.
3. Preset **Default priorities** → Recommendation tab: display the actual verified optimized opening and full-demand date, portfolio,
   checker ✅, "Why this portfolio" bullets.

## 1:00–2:15 · Change a priority (required)
4. Preset **1 · Speed: full demand by 24** → opening jumps to M14; fuel cells + engines appear
   because the grid is 0 MW until month 18. Read the cost premium off the KPI.
5. **Speed vs cost vs carbon** tab: the date curve (cost and kg/MWh by opening month), the
   stacked "how your preferences pick the winner" bar, and the *price of speed* line ($ per month
   gained). Point out the per-requested-MWh basis ("a later opening can't look cheap by running
   fewer months").
6. **Compare** tab: pinned Default vs Speed side by side.

## 2:15–3:15 · Portfolio viability + Reliability
7. **Grid stress** tab: pick a year-5 event. Import limit drops to 60%; onsite units and the
   battery carry the gap; Tier 1 / Tier 2 bands appear only in event hours; Tier 0 line always
   covered. Then preset **4 · zero Tier 2** to show what continuity costs.

## 3:15–4:15 · Financial + Environmental
8. **Year by year** tab: cost by year, supply mix, intensity falling as prices/CO₂ trend; ledger
   shows commitments continuing after they're displaced. Merchant price-spike exposure line.
9. Preset **3 · Clean under 100 kg/MWh** → either the earliest feasible opening and its cost, or
   (if infeasible) the relaxation cards: "raise cap to N kg" / "open at month M".
   Alternatives cards: "implied abatement cost $/t".

## 4:15–5:00 · What's next: execution
10. **Execution plan** tab: Gantt of permit / procure / build per resource, back-planned from need
    dates; TCEQ pathway per unit; illustrative capacity screen (not a compliance certification). Click **Model a slip** on a red
    item (e.g. fuel cells 6 months late) → the warning banner shows opening, $/MWh and kg/MWh vs
    the on-schedule benchmark. "A decision tool should tell you what to do on Monday."
11. Preset **5 · Grid slips 6 months** if time allows.
12. "Exports pass `check_submission.py`; sampled sizing model uses an LP relaxation; no global full-horizon optimality claim; tested dates
    always listed; infeasible ≠ impossible."

## Likely judge questions
- *Why these anchors ($5M/month, $100/t)?* They're starting points the customer overrides in the
  expander; we show the break-even values where the answer would flip.
- *Is it optimal?* Each opening month is sized with a MILP on representative days and reports
  the gap to the LP bound; feasibility is proven on all 87,600 hours by the checker.
- *Why not one giant LP?* 87,600 h × 14 variables; we size on ~4k representative hours and
  dispatch month by month with SOC carried — seconds, not hours.


## PermitIQ demonstration (optional, 20 seconds)
The PermitIQ screening tab distinguishes unverified permit tasks from validated energy-model assumptions. Export a review checklist, then show how a confirmed slip can be modeled in Execution plan. Never claim a jurisdiction-wide moratorium without official dated evidence.

### Explainability segment (recommended in the five-minute demo)
After demonstrating a priority change in Recommendation, select **🔎 Explain this decision**. Hover over the resource bars to show selected MW and dispatched GWh. Expand the total-cost and combined-emissions definitions, then show the three-part cost reconciliation and the speed/carbon shadow-price assumptions. Explain that the official checker supplies the physical/common-accounting outcomes while customer valuations govern trade-offs only. Move to Grid stress for one hourly reliability example.


## v4 beats to add (pick one or two)
- **Reliability (Grid stress & reliability tab):** "The cheapest plan rests on one 25 MW turbine. Lose it
  during commissioning and protected load drops. One click makes N-1 a must-have: second block,
  about +$4/MWh, zero unservable hours."
- **Execution-aware (preset 8):** "Turbines take years to arrive. Re-optimize from today and the plan
  changes: that's decision to execution."
- **Where the answer flips** banner on the Recommendation tab answers "why these anchors?" before it's asked.
- *If asked "isn't this Enverus?":* "Enverus answers where power is and what it costs. We answer what
  to build, when to open, and what to file. We'd sit on their data, not compete with it."
