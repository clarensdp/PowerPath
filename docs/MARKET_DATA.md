# Power market data (v31.5)

PowerPath pulls the latest power prices and grid metrics, shows each one with its source
and date, and can turn a market average into a proposed power-cost assumption. The data
reaches the app (Returns step) and Excel (`PP.MARKET`, `PP.TABLE`).

Code: `server/market/`. Routes: `/api/projects/{pid}/market/*`. These are project-scoped,
so licensed imports stay inside the tenant and the existing role rules apply.

## Sources

| Metric | What it is | Source | Access |
|---|---|---|---|
| `lmp_da` | Day-ahead zonal LMP: daily avg, on-peak, off-peak, max, min, intraday stdev, congestion | NYISO public CSV | No key |
| `henry_hub` | Henry Hub natural gas spot | EIA API (`natural-gas/pri/fut`, RNGWHHD) | Free EIA key |
| `spark_spread` | LMP − heat rate × Henry Hub (avg, on-peak) | Derived | – |
| `ba_demand` | Balancing-authority daily demand (and average MW) | EIA hourly grid monitor (`daily-region-data`, type D) | Free EIA key |
| `fuel_mix` | Generation share by fuel, wind + solar + hydro share, estimated carbon intensity | EIA (`daily-fuel-type-data`) | Free EIA key |
| `retail_industrial`, `retail_commercial` | Statewide average retail price by sector | EIA (`electricity/retail-sales`) | Free EIA key |
| `imported:<name>` | Any licensed series: other ISOs, forward curves, broker or consultant curves | CSV/JSON import | Your licence |

Set `POWERPATH_EIA_API_KEY` on the server. A key is free at eia.gov/opendata.

## Definitions and caveats

- **On-peak** means hours beginning 07:00–22:00, Monday to Friday. NERC holidays are not
  excluded.
- **Spark spread** uses the project's heat rate (default 7.0 MMBtu/MWh) and the latest
  Henry Hub print on or before each day.
- **Carbon intensity** is an estimate: generation-weighted screening factors (coal 1.0,
  oil 0.8, gas 0.41, other 0.4, zero-carbon 0 t CO2/MWh). It is not a reported
  inventory.
- **Wholesale LMP is an energy price only.** Delivered cost adds transmission, capacity
  and utility charges. Proposals from LMP take an explicit delivery adder.
- **Retail prices are statewide averages.** They are not a site tariff.
- **Freshness:**
  - NYISO day-ahead prices are final once published and are cached permanently.
  - EIA data is pulled again after 6 hours, because recent values get revised.
  - A file that isn't published yet isn't requested again for 10 minutes.
  - Every value has a staleness flag (for example, daily data more than about 3–10 days
    old, or monthly retail data more than 120 days old).

## Routes

| Route | Purpose |
|---|---|
| `GET/PUT market/profile` | NYISO zone, EIA balancing authority, state, heat rate |
| `GET market/snapshot?days=30` | Key metrics with source, as-of date, retrieval time, staleness, and gaps with reasons |
| `GET market/series?metric=&start=&end=` | History |
| `GET market/value?metric=&stat=&window=` | Trailing average (used by `PP.MARKET`) |
| `GET market/catalog` | Metrics, zones, imported series, whether an EIA key is set |
| `POST market/import` | Licensed series, with source and licence (append-only import log) |
| `POST market/propose-power-cost` | A market average plus an optional delivery adder becomes a proposed `power_cost_mwh` with the source filled in. It waits for an approver in Diligence. |

## In the app and in Excel

- **Returns step: "Power market context" card.** Each figure has its source and date.
  The card has a profile editor and a **Use as power cost…** button.
- **Excel formulas:**
  - `=PP.MARKET(project, "lmp_da", "on_peak", 30)` and similar formulas return a trailing
    average.
  - `=PP.TABLE(project, "market")` returns the snapshot table.
  - `=PP.TABLE(project, "history", "lmp_da")` returns a history table.
- **Excel task pane:** the formula builder has a PP.MARKET mode, and you can insert a
  stamped "PP Market" sheet.

## Not covered yet

- **Live prices for other ISOs.** PJM, ERCOT, MISO, CAISO, SPP and ISO-NE come in through
  the licensed import route until their access terms are confirmed.
- **Capacity prices and forward curves**, unless you import them.
- **Live testing.** The NYISO parser matches the published file layout. The EIA parsers
  follow EIA's documented response format and are tested on recorded payloads. Live calls
  haven't been run from this environment.
