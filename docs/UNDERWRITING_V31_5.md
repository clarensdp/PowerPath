# v31.5 underwriting layer

v31.5 moves PowerPath from site screening toward underwriting. Six pieces share one
assumption catalog and one review flow, and every result runs through the existing
engine. The engine itself is unchanged (the protected-engine hash check still passes).

Code: `server/underwriting/`. Routes: `/api/projects/{pid}/underwriting/...`.
This is a local SQLite workspace only, like the v31 site-energy routes. With
`POWERPATH_DATABASE_URL` set, these routes return 503.

## 1. Evidence & confidence register, plus the score ledger

Each material input is an **assumption record**. It stores:

- the value
- a downside value
- the source kind, source name, source date and URL
- an attached evidence document, with that document's hash
- a verification status
- a rationale

Records are append-only and versioned. A new record starts as **proposed** and only
enters the **approved case** after an approver accepts it. Accepting a new version
supersedes the previous one.

- **Confidence.** A transparent screening rubric: verification tier × documentation
  × source age (older than 18 months is penalised). It is labelled as uncalibrated.
- **Exposure and ranking.** Each input is run at its downside against the approved
  case. Inputs are ranked by `|ΔNPV| × (1 − confidence)`, with a materiality tier
  and a next action for each.
  - Inputs with no record still appear in the ranking, as "undocumented".
  - An input with no documented downside uses a default stress convention: power
    +25%, construction +15%, rent −10%, PUE +0.1, rate +2 pts, energization +12
    months, lease start +6 months. The output labels these as defaults.
- **Score ledger.** Forecasts are saved as issued and can never be edited. Each
  deliverability assessment issues time-to-power and deliverable-MW forecasts
  automatically.
  - An outcome is recorded once against a forecast, with optional evidence.
  - The backtest board reports mean absolute error, bias, the low–high hit rate, and
    a Brier score for yes/no forecasts.
  - Results are marked "insufficient history" until 10 forecasts are resolved.

Endpoints:

- `PUT base-case`
- `GET|POST assumptions`
- `GET priorities`
- `GET ledger`
- `POST ledger/{id}/outcome`
- `GET backtest`

## 2. Deliverability engine

Every capacity source gets a label, and the label decides which cases count it:

| Label | Counted in |
|---|---|
| nameplate | never |
| headroom | upside only |
| studied | upside and base |
| contracted | all cases |
| energized | all cases |

- The upside, base and downside cases use each source's earliest, likely and latest
  date. Dependencies (upgrades, substations, permits, equipment) form a chain, and a
  source can't energize before the dependencies it waits on finish.
- Solar and wind add zero firm MW.
- If an attached study supports less than the source's stated MW, the study figure
  caps it in the base and downside cases.
- You can compare power configurations side by side: grid only, bridge generation,
  dedicated generation, hybrid.

For each configuration the output gives:

- a plain answer
- deliverable MW at the target month, as a low/base/high range
- the time to target, as a range
- the critical items
- what must be true
- an evidence-quality score

PowerPath does not run network studies. External studies are inputs.

Endpoints: `POST|GET deliverability`.

## 3. Power-to-returns bridge

You give a set of drivers (any catalog key), or one deliverability configuration and
case. The bridge reruns the engine on every subset of drivers and attributes the
change in NPV, levered IRR and minimum DSCR using exact Shapley values.

- The parts add up to the total change, whatever order the drivers are listed in.
- The output also shows each driver's isolated impact and a waterfall in the listed
  order, for reference.
- It writes plain-English lines such as "Levered IRR fell 4.1 pts: …".
- The limit is 7 drivers, which means 128 engine runs at about 0.06 s each.
- A power path can be bridged directly. Its delay, capex uplift, energy uplift and
  capacity phases become the drivers, and the bridge's final result matches the
  existing path schedule-impact (`/schedule-impact`) result.

Catalog keys:

- `power_cost_mwh`
- `construction_cost_mw`
- `rent_per_kw_month`
- `pue`
- `interest_rate_pct`
- `grid_capacity`
- `power_capex_m`
- `energization_delay_months`
- `lease_start_delay_months`

Endpoints: `POST bridge`, `GET paths/{id}/bridge`.

## 4. Change pipeline and queue monitoring

The flow is the same for every change: detect it, rerun the model, send it for review.

- **Proposing an assumption** creates a change that carries its returns impact.
  - It must be accepted or rejected under `/approvals/`, which needs the approver
    role when authentication is required.
  - Each decision records the approved case's fingerprint before and after.
- **`POST changes/scan-utility-studies`** turns new or revised parcel utility studies
  into proposed grid-capacity assumptions for that parcel. Running it again creates
  nothing new.
- **Queue snapshots** (any ISO or utility feed, uploaded as JSON) are compared with
  the previous snapshot from the same source. Within a radius of the given sites, the
  comparison flags:
  - new requests
  - withdrawals
  - status changes
  - in-service-date slips
  - MW changes
  - entries that disappeared from the feed

  Queue events can only be **acknowledged** with an analysis note. A withdrawal is
  never credited as freed capacity. An entry that disappears from a feed is not
  treated as a withdrawal.
- **The queue summary** gives:
  - nearby concentration by fuel and status
  - the historical withdrawal rate
  - the median in-service-date slip
  - the median time from queue entry to in-service

Endpoints:

- `GET changes`
- `POST approvals/{id}/accept|reject|acknowledge`
- `POST queue/snapshots`
- `GET queue/summary`

## 5. Forecast interface

Forecasts use one provider-neutral schema: monthly p10/p50/p90 in USD/MWh, with the
provider, market, location, issue date and licence. You can import them as JSON or
CSV. Imports are kept as issued.

- The price-scenario route maps low/base/high to p10/p50/p90 for as long as the
  forecast runs. It then glides to the long-term planning path you set (starting
  price and escalation).
- Each price path enters the engine as its energy-weighted average, because the
  engine takes a single power price. The output reports the scenario's pass-through
  terms, which decide how much price matters.
- There is no provider-specific adapter yet. Add one once a provider's API terms are
  confirmed (for example, Ask the Grid's hub-level forecasts).

Endpoints: `GET|POST forecasts`, `POST price-scenarios`.

## 6. Copilot brief and MCP server

- **`GET brief`** returns a sourced project brief:
  - the approved-case result
  - the top diligence priorities, each with its reference
  - the latest deliverability answer
  - pending changes
  - the forecast track record
  - guidance for an AI copilot
- **`tools/powerpath_mcp.py`** is an MCP server (stdio) that calls the API over HTTP,
  so tenant and role checks apply. It has 8 tools. All are read-only, except that
  `returns_bridge` computes a what-if without saving anything. It has no approval
  tools.

Run it with:

```
pip install -r requirements-mcp.txt
POWERPATH_URL=http://127.0.0.1:8768 POWERPATH_TOKEN=<token> python -m tools.powerpath_mcp
```

There is no LLM chat inside the app yet. The brief and the MCP server are how
Claude or Copilot reach PowerPath today.

## Screens and Excel

- **Workspace step 4 (Returns)** shows a breakdown by cause under the pathway table. The
  totals match that table exactly, and the screen flags any approved assumption the table
  doesn't include yet.
- **Workspace step 5 (Diligence)** ranks every input by NPV at risk. It has a "Waiting
  for review" queue with accept, reject and record-analysis actions, plus a
  "Document" form that creates a proposal. It also shows the latest deliverability
  answer. None of this needs a saved parcel.
- **Excel add-in:** see `docs/EXCEL_ADDIN.md`.

## Not built yet

- Screens for the queue, forecasts and the ledger.
- PostgreSQL tables.
- Live queue feed adapters.
- A provider-specific forecast adapter.
- Calibrated probabilities. These need resolved outcomes in the ledger first.

## Tests

```
pytest -q tests/test_underwriting.py
pytest -q tests/test_underwriting_auth.py
pytest -q tests/test_underwriting_mcp.py
```

Run the auth test on its own. The MCP test needs `mcp`.
