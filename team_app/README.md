# PowerPath v7 — one decision layer for large-load power

**v7 contents:** the Streamlit decision terminal (`team_app/app.py`, five stages: Screen → Interconnect →
Generate → Structure → Execute & Monitor) and the standalone terminal page (`team_app/terminal/powerpath_terminal.html`):
market ticker (prices + news, as of the Oct 22, 2026 session), custom location screener across 68 locations
with saved screeners and a locked base case, CapIQ-style power market strip (ATC / on- / off-peak, spark
spread, solar and wind capture vs PPA price), and the five stages for the Texas benchmark and Ohio.
Rebuild the page data with `team_app/tools/build_terminal_*.py` (1 → 2 → 3 → 4), then `build_terminal_page.py`.

**Interconnect explorer (page, v7.1):** for the top-10 screened states plus Ohio, the Interconnect tab shows today's grid mix
(EIA 2024 state profiles, rounded) next to the PowerPath portfolio, speed to connection (grid P10/P50/P90, onsite
permit → procure → build back-plan) and live assumptions: grid wait, P10–P90 spread, upgrade $/kW, value of time and
per-resource lead times. Wait and bridge plans come from engine runs at grid waits of 0/6/12/18/24/36 months per state
(`tools/build_terminal_4_icx.py` with curves from the run script); costs in between are interpolated in the browser and
lead-time edits shift availability and opening dates without re-sizing. Screened states are estimates; Texas is the benchmark.
Open the HTML file directly in a browser; it needs internet only for fonts and Chart.js.

Large-load development is no longer a land problem. Power availability, queue exposure, upgrade
timelines, fuel supply and nodal economics decide which projects get built. PowerPath connects
**screening, interconnection, generation, deal structuring and monitoring** into one workflow, so a
team prioritizes projects by **deliverable power** instead of assuming power will follow demand.

## The five stages (each passes its decision to the next)

| Stage | Decision | How PowerPath decides |
|---|---|---|
| 1 · Screen | Which sites make the shortlist? | Any US ZIP/state or 17 countries; ranked by deliverable power (month the grid can carry 75 MW, then bridge MW needed) or by the weighted feasibility score; same 87,600-h engine per site |
| 2 · Interconnect | Wait for the grid, bridge with onsite power, or walk away? | P10/P50/P90 energization by grid region; deliverable-power chart with the power gap; "wait" and "bridge" plans both sized on 87,600 h and compared at the customer's value of time; plan re-sized at the P90 slip |
| 3 · Generate | What portfolio, and when to open? | MILP sizing + chronological dispatch, must-haves vs preferences, N-1, Fast Track / Lower Cost / Cleaner; benchmark scored by the packet checker |
| 4 · Structure | How to own and pay for it? | Own + PPAs (= common benchmark cost), tolling / energy-as-a-service, utility large-load tariff with bridge power; upfront capital, committed obligations, tenor, balance-sheet treatment, risk allocation; picks by capital limit and off-balance-sheet preference |
| 5 · Execute & monitor | What do we file Monday, and what would change the decision? | Back-planned permits/orders, diligence checklist, triggers (merchant +20%, gas +30%, P90 grid slip, largest-unit outage, curtailment) with impact and action, site pipeline |

A stage bar shows each stage's verdict; a decision ledger in the sidebar records every decision and
assumption carried between stages.

Screening assumptions added in v5 (labelled in the app): energization spread and indicative network
upgrade cost by grid region; tolling provider return (10% WACC + 8% margin); utility tariff demand
charge ($12/kW-month at 85% minimum take). None of these enter the common benchmark cost.

---

# PowerPath — site, power and execution terminal

**Every MW, every month, every trade-off explained.** Paste a US ZIP, a state or a major country and
PowerPath scores the location's feasibility for a 75 MW data-center campus, sizes the power
portfolio there, dispatches every hour, and turns the decision into an execution plan.

## Location screener (SITE tab)
- **Input:** US ZIP (ZIP3 → state, all 50 states + DC), state name/code, or one of 17 countries
  (Canada, UK, Ireland, Germany, Netherlands, France, Spain, Sweden, Norway, Finland, Japan,
  Singapore, India, Australia, Brazil, Mexico, UAE). Compare up to six at once.
- **Ground truth:** the packet's 87,600-hour Williamson County benchmark, scored by the official
  checker. Every other location re-runs the same engine for the default customer (opening month 20,
  the customer's carbon price) on the benchmark's hourly shapes scaled by regional indices:
  merchant price (EIA 2024 state retail price ÷ Texas), grid CO₂ (eGRID2023 state rate ÷ Texas),
  solar and wind capacity factors (screening estimates), and a regional grid-connection wait.
  Regional results use PowerPath's line-by-line mirror of the checker formulas on those inputs.
- **Feasibility score (0–100):** Cost, Speed to power and Carbon (60%, split by the customer's
  sliders) + Land & parcels (15%) + Water (10%) + Policy & permitting (15%). Each component shows
  its input. Verdicts: Strong ≥ 70, Conditional ≥ 50, Weak < 50, or *Blocked within catalog* when no
  portfolio serves the load. Confidence: High (benchmark), Medium (US state indices), Low (country).
- **Parcels:** illustrative, seeded candidates per location (acreage, substation headroom, gas
  distance, flood zone, zoning, land $/acre from USDA 2025 state values), scored against gates
  (≥ 50 acres, outside flood zone, power or gas access). Upload a real parcel CSV (county or Regrid
  export mapped to the listed columns) to replace them.
- **Price forecast:** benchmark ERCOT hourly shape × regional index × packet real-terms trajectory.
- **Make active site:** one click re-runs every tab (recommendation, stress, N-1, execution) for
  that location. Exports for a screening site are labelled and will not pass the packet checker
  by design; the official submission stays on the benchmark.

Data sources: EIA State Electricity Profiles (2024 average retail price); EPA eGRID2023 summary
tables (state CO₂ output rate); USDA NASS Land Values 2025. Solar/wind capacity factors, water-stress
tiers, grid-connection waits, policy flags and all country values are labelled screening estimates.
No live GIS, utility study or permit search is performed.

---

# PowerPath v4

## What's new in v4
- **Execution-aware mode** (sidebar): each resource can run no earlier than *today + permit/procure/build*
  (editable planning assumptions). The optimizer re-plans around real lead times instead of assuming
  catalog delivery slots are secured. Fixes the v3 inconsistency where the recommendation relied on a
  turbine the Execution tab flagged as late.
- **Largest-unit outage (N-1)**: hour-by-hour check with one block of the biggest onsite unit out,
  using only permitted Tier 1/Tier 2 flexibility and the import limit; expected consequence at a
  labelled 3% forced-outage rate; cost of covering options. New must-have **"Survive loss of the
  largest onsite unit"** enforced inside the optimizer.
- **Curtailed clean energy** (paid for, unused) and **hourly clean matching** reported next to the
  annual clean share.
- **Merchant price-spike chart**: premium paid above $200/MWh by year vs an all-merchant yardstick.
- **Where the answer flips**: value-per-month and carbon-price thresholds at which another tested
  opening month would win.
- **±1 month refinement** around the winner when searching on a coarse grid.
- **Cache versioning**: cached results are keyed to the engine's code hash, so edits can't serve stale answers.
- **Slider caps**: implied values capped at $20M/month and $500/t (typed overrides still allowed).
- Tabs consolidated (PermitIQ now inside Execution plan); new presets 7 (N-1) and 8 (execution-aware).
- `COMPETITIVE_LANDSCAPE.md`: PowerPath vs Enverus.


PowerPath helps a data-center developer choose an energy portfolio for the Williamson County
campus. The customer states **must-haves** and **nice-to-haves**; PowerPath searches opening
months, sizes a portfolio for each with an optimizer, dispatches all 87,600 hours, scores the
result with the packet's own checker, and explains why the winner won and when an alternative
would be better.

## Run

From the packet folder (`Contestant_Packet/`), Python 3.10+:

```sh
pip install -r team_app/requirements.txt
python team_app/run.py warm                      # optional: precompute the demo presets (~5–10 min)
streamlit run team_app/app.py                    # the product
python team_app/run.py recommend --out outputs   # headless recommendation + exports
python starter/check_submission.py outputs/portfolio.json outputs/dispatch.csv > outputs/check_results.json
```

Results are cached in `team_app/.cache/` so repeated questions return instantly.

## Supported customer inputs

| Kind | Input | Treatment |
|---|---|---|
| Must-have | Full demand by month *N* / open by month *N* | Only opening months ≤ *N*−10 (or ≤ *N*) can be recommended |
| Must-have | Max combined intensity (kg CO₂/MWh, includes remote emissions of relocated load) | Optimizer constraint; re-checked on the checker's horizon figure |
| Must-have | Min clean share, max merchant share | Optimizer constraints; re-checked |
| Must-have | Max total decision cost ($M) | Optimizer constraint on cost |
| Must-have | Max premium % vs cheapest month-20 opening (brief example 6) | Filter on $/MWh requested |
| Must-have | No Tier 2 interruption (example 4), allow/forbid Tier 1, excluded resources | Variable bounds |
| Preference | Speed / cost / clean sliders | Converted to **$ per month of earlier opening** (anchor $5M/month at equal weight) and an **internal carbon price** (anchor $100/t). Shown to the customer and overridable. |
| Scenario | Grid connection delay (example 5), opening months to test | Re-runs the model |
| Execution | Equipment / permit slip: one resource arrives *N* months late | Re-runs the optimizer with that resource's availability shifted; the on-schedule benchmark is shown alongside as the anchor |

The month-30 full-demand target is treated as a **preference** by default (speed slider) and
becomes a **hard deadline** when "Full demand by" is ticked.

## How a recommendation is made

1. **Inputs.** `prepare_inputs()` from `starter/check_submission.py` builds the 87,600-hour table
   for each opening month and grid delay (ramp, grid upgrades, stress limits, price and CO₂
   trajectories). No input is modified.
2. **Sizing (mixed-integer program, HiGHS via SciPy).** Decision: block counts for all seven
   resources. Constraints: maxima, 8-acre land, availability dates, hourly balance, shared
   import limit (60% during events), Tier 1 within eligibility and remote capacity, Tier 2 within
   eligibility, battery power/energy/efficiency/daily cycling, clean-only charging, and any
   must-haves. Capacity charges and available-generation payments are exact over the horizon;
   variable costs come from representative days (low/median/high renewable days for every month
   in the first year after opening and around grid milestones, then every fifth month — coprime
   with 12 so every season is covered — plus every stress day). Objective: common cost + the
   customer's carbon valuation.
   We solve the LP relaxation first (a proven lower bound), then the integer problem restricted
   to the floor/ceiling block counts around it; the reported gap to the bound is typically
   0–3%.
3. **Chronological dispatch.** One LP per 730-hour model month, battery state of charge carried
   across months and years, SOC 0 at the start and end, annual cycle cap allocated by month.
   Shadow prices of portfolio-level must-haves from step 2 are carried into dispatch.
   Simultaneous charge/discharge is netted out exactly.
4. **Verification loop.** Any unserved hour adds those days to step 2 and re-solves. If a
   portfolio-level must-have is missed on the full horizon, its target is tightened and re-solved.
5. **Accounting.** `check()` and `score()` from the packet checker are run on our dispatch; every
   cost, emissions and service number in the product is that common benchmark figure.
6. **Choice.** Among portfolios meeting every must-have: lowest
   `common $/MWh requested × 90 mature months of MWh + carbon price × intensity × same MWh +
   value per month × months later`. The per-requested-MWh basis stops a later opening looking
   cheaper only because it serves fewer MWh in the fixed horizon.
7. **Explanation.** Build table with commitment start and horizon cost per resource, must-have
   check, reasons per resource, binding constraints (dual prices), and alternatives with what
   they gain, give up, and the break-even $/month or implied $/t at which they would win.
8. **Conflicts.** If no tested month passes, the tool relaxes one must-have at a time (later
   opening, looser cap with the cleanest portfolio found, allow Tier 2, higher cost cap, restore
   excluded resources) and reports the nearest fix. A failed search is not proof of
   impossibility; the tested months are always listed.

## Alternatives

Every recommendation comes with three named, checker-validated alternatives: **Fast Track**
(earliest opening meeting every must-have), **Lower Cost** (lowest $/MWh tested, no carbon
weight) and **Cleaner** (same opening, +$150/t internal carbon price). Each shows what it gains,
what it gives up, and the break-even $/month or $/t at which it would beat the recommendation.

## Execution layer (decision → what's next)

The Execution plan tab back-plans each selected resource from its need date (the later of
opening and its catalog offer date): latest permit filing, order or contract signature, and
construction start, plus site-level steps (large-load interconnection, site permits, gas supply).
Items whose first action falls before "today" are flagged, and one click models that item
slipping, re-running the optimizer so the developer sees the new opening date, portfolio and cost.
It also checks the Texas SB 6 backup-generation disclosure threshold (onsite firm ≥ 50% of load).

Planning assumptions (editable in the product; never fed into the benchmark):

| Resource | Pathway (Texas) | Permit / procure / build (months) |
|---|---|---|
| Gas engines | TCEQ Air Quality Standard Permit for Natural Gas EGUs (spark-ignited engines, effective Jan 30 2025) + local permits | 6 / 14 / 6 |
| Gas turbine | TCEQ case-by-case NSR (standard permit covers engines, not turbines) + local | 14 / 36 / 10 |
| Fuel cells | TCEQ authorization screening + local fire/building | 4 / 9 / 4 |
| Battery | Fire-code review (NFPA 855 / IFC), building/electrical permits | 4 / 10 / 5 |
| Solar / wind PPA | Contract negotiation and credit support (seller permits the project) | 0 / 6 / 0 |
| Nuclear PPA | Contract; NRC licensing is the seller's risk | 0 / 12 / 0 |

Sources: TCEQ NG EGU standard permit page; Utility Dive (Wood Mackenzie: gas turbine lead times
near five years after order in 2025); Bracewell summary of Texas SB 6 (large loads > 75 MW,
≥ $100k study fee, backup-generation disclosure, ERCOT curtailment equipment). Planning aid, not
legal advice. Capacity charges in slip scenarios follow the common rule from the catalog date
(conservative), because the checker applies that rule.

## Business valuations (separate from common cost)

- **Value of earlier opening:** anchor $5M per month at equal weight. Rough basis: 75 MW of
  leased critical capacity at wholesale colocation rents in the low-to-mid $100s per kW-month,
  less operating costs. It is a customer valuation and is never added to common cost.
- **Internal carbon price:** anchor $100/t at equal weight; customer valuation only.
- **Premium cap:** compares $/MWh requested with the cheapest month-20 portfolio.

## Simplifications and limitations

- Sizing uses representative days; the full 87,600-hour dispatch is the feasibility proof.
- Monthly dispatch windows are myopic about battery energy across month boundaries (small
  value given a 48 MWh maximum battery).
- Linear operation: no unit commitment, minimum load, ramping or startup costs (not required).
- Upfront capacities only (as `portfolio.json` requires); staged additions not modelled.
- Opening months are searched on the grid shown in the product, not exhaustively.

## Disclosure

Built with AI assistance (Claude, Anthropic) for code and documentation; the team reviewed and is
responsible for the results. Libraries: NumPy, pandas, SciPy (HiGHS), Streamlit, Plotly. The
packet's `check_submission.py` is imported unchanged for inputs and accounting. No additional data.


## Revised release: reproducibility and compliance boundaries

- The distribution root now includes the unmodified official packet `starter/` and `data/` directories, so run `python team_app/run.py recommend --out outputs` or `streamlit run team_app/app.py` from the ZIP root after installing requirements.
- Candidate opening search returns an empty set when user minimum exceeds the maximum allowed by hard deadlines. No implicit constraint relaxation.
- Customer decision scores normalize requested energy to a reference horizon. They are **not** official total costs or developer cash flows. The official checker total decision cost remains displayed separately.
- Any LP relaxation gap applies only to the sampled sizing optimization and is NOT an optimality guarantee for the full-horizon mixed-integer portfolio.
- PermitIQ is a conservative regulatory diligence and draft checklist workflow. It includes no confirmed jurisdiction-specific permit decisions or legal compliance certification. Validate all official sources and effective dates with qualified reviewers.
- All procurement and permit duration assumptions in execution planning are scenario inputs, separate from contest resource availability. The official baseline is unchanged.
- Run `python -m unittest discover -s tests -v` from this root for fast regression smoke tests, followed by the official checker on produced dispatch files.

## Decision explainability and UX (October 24 update)

The **🔎 Explain this decision** tab is the default drill-down companion to the Recommendation tab. It provides hoverable resource output (MW capacity versus GWh actually dispatched), expandable definitions of benchmark outcomes, a reconciled cost breakdown, transparent customer shadow-price assumptions, and links to grid-stress and annual details. Headline metric help icons and preference-slider help text are available in the Recommendation/sidebar.

**Interpretation safeguards:** physical capacity is not delivered energy; battery output is shifted energy, not new clean generation; customer valuations are not common benchmark cash flows; sampled-model gaps do not establish global full-horizon optimality. The app is a decision model and the PermitIQ content remains preliminary screening rather than a legal determination.

## PowerPath Feasibility (new)

The **🧭 Site feasibility** tab provides an evidence-first desktop screen with 30 criteria across power, land, water/cooling, connectivity, permitting/compliance, and project finance/delivery. Users can record status, evidence source and reviewer for each item; download a structured JSON assessment and a review memo; and apply an **optional grid delay** to the core recommendation scenario.

**Boundaries:** This is *not* a live parcel intelligence service. No GIS lookup, parcel zoning determination, moratorium lookup, confirmed utility capacity, permitting authorization, supplier inventory, or automated commercial-operation date is inferred. A `Verified` label only contributes to the completeness counter when a reference and reviewer are entered; the platform cannot authenticate those inputs. All entries default to unknown. A delayed grid scenario is separate from the benchmark assumptions. Treat any diligence status as a workflow aid requiring qualified professional review.
