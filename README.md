# PowerPath: method README

PowerPath is a decision tool for a data-center developer choosing an energy portfolio. It turns customer priorities (speed to power, cost, environmental performance) into a feasible, hourly-dispatched portfolio. It then carries that decision through interconnection, financing and execution. Full details: `team_app/README.md`.

**Run it:**
- `pip install -r team_app/requirements.txt`, then `streamlit run team_app/app.py` (customer inputs and live re-optimization).
- Open `team_app/terminal/powerpath_terminal.html` in a browser (results terminal).
- CLI: `python team_app/run.py recommend --help`.

## Results (official benchmark, Williamson County TX)
`outputs/portfolio.json`, `outputs/dispatch.csv` (87,600 hours), `outputs/summary.md`. All pass `starter/check_submission.py`.

- **Opening:** initial service M18, full demand M28.
- **Portfolio:** 70 MW solar contract, 155 MW wind contract, 25 MW gas turbine.
- **Results:** $53.18/MWh requested, 65.0 kg CO₂/MWh, 81% clean.

Priority-change runs, each also checker-validated, are in `outputs/priority_change_*` and `outputs/extension_execution_aware_today_m0`.

## Supported customer inputs
- **Preferences** (tradeable) are weights for speed, cost and clean. They become two dollar values:
  - value of opening one month earlier = $5M × speed/cost weight (capped at $20M);
  - internal carbon price = $100/t × clean/cost weight (capped at $500/t).
- **Hard requirements** (never traded):
  - full demand by month X; open by month X;
  - maximum kg CO₂/MWh; minimum clean share; maximum cost premium;
  - no Tier 2 interruption; N-1 (survive loss of the largest onsite unit);
  - excluded resources; budget.
- **Options:** opening months to test, grid delay, equipment slips, execution-aware lead times from today, location (US ZIP/state or country).

## Selection and operating logic
1. For each candidate opening month, a mixed-integer program sizes the portfolio in catalog blocks on representative days (dense early months, low / median / high renewable days, and every stress day). Solved with SciPy HiGHS: LP relaxation, then a restricted MILP, then a full MILP as fallback.
2. A chronological LP dispatches all 87,600 hours month by month, carrying battery state of charge forward.
   - Rules applied: the import cap (25 / 50 / 75 MW from months 18 / 24 / 30) and 60% of it in stress events, the commissioning ramp, Tier 0 always served locally, Tier 1 relocation (≤ 11.43 MW) and Tier 2 interruption only in stress events, the battery charging only from clean output, and the 8-acre land limit.
   - Hard requirements feed back as constraint prices, then the plan is re-dispatched; unserved hours trigger re-sizing.
3. Each opening is scored as common cost + carbon value + delay value on a fixed 90-month basis. The lowest score wins.
4. Alternatives are shown: Fast Track, Lower Cost, Cleaner. Contradictory requirements get relaxation advice.

## Business valuations (customer-side, never added to common cost)
- **Value of time:** $5M/month at equal weights (75 MW of leased capacity at colocation rents, less operating cost).
- **Internal carbon price:** $100/t at equal weights.
- **Wait vs bridge:** the extra cost of bridging divided by months gained gives a break-even value of time.
- **Finance tab:** NPV, IRR, debt cover and probability of profit. The tenant tariff (default $60/MWh, +2%/yr) is a team assumption, not packet data.

## Simplifications
- Sizing uses representative days; the full-horizon dispatch is the feasibility proof.
- Linear operation: no unit commitment, minimum load, ramping or start costs.
- Capacities are chosen upfront; staged additions are not optimized.
- Opening months are searched on a grid (14–26), not exhaustively.
- **Terminal page, browser models:**
  - The portfolio builder and Finance tab use a browser merit-order dispatch calibrated to the engine (within about 1% on $/MWh, same kg/MWh).
  - The Interconnect explorer interpolates engine runs at grid waits of 0 / 6 / 12 / 18 / 24 / 36 months.
  - Finance probabilities hold dispatch fixed.

## Limitations
- Only the Texas benchmark is checker-validated. Other states and countries scale the benchmark's hourly shapes by regional indices; they are screening estimates, and their exports will not pass the checker.
- Grid waits, P10–P90 spreads, upgrade $/kW, lead times, parcels, and tolling and tariff terms are screening assumptions, not utility or vendor quotes.
- The terminal page's Interconnect explorer, builder, Finance and Execute views are not yet in the Streamlit app.

## Disclosure
- **AI assistance:** Claude (Anthropic) wrote most of the code and documentation. ChatGPT was used by a teammate for early ideation. The team reviewed and is responsible for all results.
- **Reused software:**
  - NumPy, pandas, SciPy (HiGHS), Streamlit, Plotly; Chart.js 4.4.1 for the terminal page.
  - jsdom, used for testing only.
  - The packet's `check_submission.py`, imported unchanged.
- **Additional data** (screening only; never used in the benchmark result):
  - EIA 2024 state retail prices, eGRID 2023 state CO₂ rates, USDA NASS 2025 land values;
  - approximate EIA 2024 state generation mixes (rounded; verify against EIA State Electricity Profiles, Table 5);
  - screening estimates for regional solar and wind capacity factors, water stress and grid waits.
- **Additional assumptions:** the tenant tariff and debt terms in Finance; lead times in Execute.
