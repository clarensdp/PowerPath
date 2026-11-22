# Real-world site energy integration — PowerPath v30.8.3

This additive MVP connects existing parcel selection to public energy references,
mapped transmission infrastructure, solar resources and explicit underwriting inputs.
The existing JavaScript financial engines, feasibility algorithms, saved scenario format
and `agents/` subsystem are preserved. No live data replaces a scenario automatically.

## Architecture and persistence

`GeoStore` → `SiteEnergyService` → independent provider adapters → normalized results →
parcel inspector / Leaflet → explicit input selection → saved scenario → existing engine.

- Reuses `parcels28.install`'s initialized `GeoStore`, including project-pinned source versions.
- `DataPoint` distinguishes observed, estimated, user-supplied, assumed and unavailable.
  Points carry units, source URL, retrieval time, observation period, coverage and methodology.
  GIS features retain source identifiers, geometry, attributes and source dates where supplied.
- Uses urllib with eight-second request timeouts, one retry for transport failures,
  HTTP 429 or 5xx, and an 8 MB response limit. Redirects are rejected. Providers fail
  independently; normalizations never substitute demo values.
- Persistent cache TTLs: EIA 24 hours; GIS 7 days; solar 30 days.
  Transport failures are cached for 60 seconds. Expired data is not returned as fresh.
  Original retrieval timestamps survive cache hits. No API keys or credential-bearing
  request URLs are retained. Cached raw JSON and normalized context are separate.
- Provider jobs run concurrently, with bounded responses and GIS queries capped at
  200 records. Truncated inventories are labeled incomplete, not silently paginated.
- Everything uses `/api/projects/{pid}/...` so existing local/managed identity and
  tenant middleware applies. Scenario and evidence ownership are checked again.
  Cache and snapshot records are scoped by project.

SQLite startup adds three tables idempotently:

| Table | Purpose |
|---|---|
| `site_energy_cache` | Sanitized provider JSON, retrieval timestamps, expiry and safe errors |
| `site_energy_contexts` | Latest normalized full context per project/parcel, including GIS geometries |
| `site_energy_studies` | Latest user-transcribed utility-study findings with attached evidence |

No destructive migration or manual database reset is required. Existing backups include
these tables. Scenario selections are stored in `config.siteEnergyInputs` and copied into
the existing immutable run input JSON; audit events retain selections and study changes.

**PostgreSQL limitation:** these new routes explicitly return 503 on the experimental
PostgreSQL runtime. Existing routes continue to work. This avoids adding unaccepted DDL
or cache writes under read-only/viewer RLS policies. PostgreSQL migration and policy
acceptance for the new feature remains a separate task; do not enable a database URL
to use this integration.

## Electricity selection and historical records

Live PJM API pricing is removed from the MVP. Electricity selection accepts only
`eia_reference`, `assumed`, or `user_supplied`. Removed price modes and delivery-adder
fields are rejected; unavailable EIA observations require an explicit user assumption,
never an automatic replacement price. No PJM credentials or node configuration are needed.

Previously saved scenarios/runs and provenance remain intact and use their stored numeric
power cost. Selecting a new price is an explicit, versioned action. Operator-imported
PJM queue CSV history, comparisons and generic intelligence tools remain available without
PJM API access. Archived baseline examples are not part of the current MVP runtime.

## Sources and what they mean

| Source | Integration | Interpretation / access |
|---|---|---|
| [EIA retail-sales API](https://www.eia.gov/opendata/documentation.php) | Monthly state commercial and industrial prices, up to 24 records | Published revenue/sales averages; cents/kWh × 10 → USD/MWh. Not a tariff or negotiated data-center contract. API key required. |
| [Federal transmission feature service](https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/US_Electric_Power_Transmission_Lines/FeatureServer/0) | Nearby line geometry, owner and voltage where supplied | FWS-hosted HIFLD-derived mapped inventory, also referenced in the [NTIA GIS guide](https://broadbandusa.ntia.gov/sites/default/files/2025-09/NBAM_APPEIT_User_Guide_09_10.pdf). No key required. Not a capacity or interconnection dataset. |
| [NREL/NLR solar resource API](https://developer.nlr.gov/docs/solar/solar-resource-v1/) | GHI, DNI, latitude-tilt irradiation; annual/monthly daily averages | SUNY satellite-modeled 1998–2009 climatology, approximately 10 km grid. Units kWh/m²/day. Estimated resource, not measured parcel production. |
| [NREL/NLR PVWatts v8](https://developer.nlr.gov/docs/solar/pvwatts/v8/) | Annual AC generation for explicit DC system capacity | NSRDB TMY weather and model output. API key required. Weather station, model version and system assumptions retained. |

Source research/live checks on **2026-11-11**:

- The old HIFLD `Hp6G80Pky0om7QvQ` substation and retail-service-territory URLs returned
  ArcGIS `Invalid URL`. No automatic fallback to unrelated ArcGIS copies was added.
- The reviewed “VA Utility Service Areas” ArcGIS item belonged to a consultant and
  lacked source/rights metadata. It was not accepted as a default authoritative boundary.
- Virginia's [public energy security plan](https://www.energy.virginia.gov/public/documents/VASESP_2024_PublicVersion_Final.pdf)
  contains an approximate SCC service-territory map, not a verified parcel-level GIS service.
- [Loudoun's official utilities service](https://logis.loudoun.gov/gis/rest/services/COL/Utilities/MapServer)
  was accessible and includes major power lines, but no substation or electric-territory layer.
- Wind is explicitly unavailable. No suitable small, verified API integration was added in
  this MVP; it must not be inferred from solar resource or general regional averages.

You may configure reviewed substation and territory layers. They must return GeoJSON in
EPSG:4326, preserve stable `ID`, `OBJECTID_1`, `OBJECTID` or GeoJSON feature IDs, and use
`NAME`/`OWNER`, optional `VOLTAGE` (kV), and optional `SOURCEDATE` (epoch milliseconds).
Other schemas need a small provider-specific mapping before use. Review publisher,
vintage, geographic coverage, licensing and field meaning before configuration.
Territory polygons intersecting the parcel are screening candidates; overlapping
territories or a parcel straddling a boundary require utility review.

Distances use the shortest parcel-footprint to asset-geometry separation in a local
WGS84 azimuthal equidistant projection, expressed in km. They are approximate map
distances, not engineering cable routes or interconnection costs. Search radius is
20 km from the footprint. A line crossing a parcel correctly has distance zero.

## Setup

Use the existing Python environment and `./run_local.sh`; no new runtime dependencies
are required. API keys stay on the server. `.env.example` lists the settings, but the
launcher does **not** automatically source `.env` files. Export them in the launch shell:

```bash
source .venv/bin/activate
export POWERPATH_EIA_API_KEY='your-eia-key'
export POWERPATH_NREL_API_KEY='your-nrel-or-nlr-key'
./run_local.sh
```

Register through [EIA Open Data](https://www.eia.gov/opendata/register.php),
[NLR developer signup](https://developer.nlr.gov/signup/). Missing keys show unavailable states while
parcel search, the transmission overlay and scenario assumptions remain usable.

Optional GIS settings:

```text
POWERPATH_SUBSTATION_LAYER_URL=https://<reviewed-host>/<service>/FeatureServer/0
POWERPATH_SUBSTATION_LAYER_NAME=<actual publisher, dataset, vintage>
POWERPATH_TERRITORY_LAYER_URL=https://<reviewed-host>/<service>/FeatureServer/0
POWERPATH_TERRITORY_LAYER_NAME=<actual publisher, dataset, vintage>
```

Only public HTTPS `.gov` / `.arcgis.com` layer URLs are accepted. They are administrator
configuration, never arbitrary client-supplied URLs. No default substation/territory
source is implied. Restart after changing credentials or layers.

## Using the workflow

1. Open a project with an underwriting scenario (or create an illustrative starter).
2. Explore Virginia, select a real parcel, and inspect **Site energy data** below its
   existing diligence inspector. Public lookups run independently of parcel rendering.
3. Inspect price category, period and coverage. Click mapped assets or their list
   entries for source, distance, characteristics and unknown-capacity labels.
4. Enter solar capacity, tilt, azimuth and losses to request a PVWatts estimate.
   Standard modules, fixed open-rack mounting, DC/AC 1.2 and inverter efficiency 96%
   are explicit modeling assumptions, unrelated to buildable acreage.
5. Select a base scenario and price basis. EIA becomes a **site scenario assumption**;
   Explicit user-supplied prices require a rationale. The resulting
   estimate is not a confirmed utility tariff. A user-supplied rate can reference a
   supporting project document, but PowerPath does not certify the contract.
6. Optionally retain the solar estimate. An explicit annual blend additionally needs
   annual facility load, all-in solar energy cost and self-consumption fraction. It
   calculates `(1 − solar_share) × grid_cost + solar_share × solar_cost`, caps solar
   consumption at load and passes the result into the unchanged `powerCostMWh` input.
   It does not add firm capacity, modify power tranches, or assume solar construction.
7. **Save inputs & run underwriting** validates and versions the saved scenario, then
   runs the existing engine. Economics compares project pathways on the selected base.
   Scenario version conflicts and changed reference observations require a reload.
8. Attach a utility study in the existing evidence room to record capacity, connection
   cost or energization findings. These remain user-transcribed findings with evidence
   and source date, separate from the public map's unknown availability fields.

Existing saved scenarios remain readable. Editing electricity price through another
editor is shown as a scenario override when it differs from the retained selection.
The new metadata does not alter financial arithmetic; only explicitly selected engine
inputs do. Existing power-path energy uplifts still apply in Economics.

## API

All routes below use this base:
`/api/projects/{pid}/parcels28/{parcel_id}` (URL-encode the parcel identifier).

| Method and suffix | Behavior |
|---|---|
| `GET /energy-context` | Full normalized context, source-version reference and quality states |
| `GET /energy/electricity-prices` | EIA subset; no GIS/solar requests |
| `GET /energy/infrastructure` | Mapped transmission/substation/territory subset |
| `GET /energy/renewables` | Solar resource subset |
| `POST /energy/solar-estimate` | `{capacity_kw, tilt, azimuth, losses_pct}` |
| `POST /energy/scenario-inputs` | Explicit price/solar selection, rationale and optimistic scenario version |
| `PUT /energy/utility-study` | Project evidence ID, source/date, notes and nullable capacity/cost/date |

Unavailable upstream data returns HTTP 200 with `status: unavailable`, empty observations
and a reason; unknown is never represented as zero. Invalid selections return 422;
changed scenario/reference versions return 409. Provider failures cannot silently choose
an assumption. Errors do not expose credentials or raw upstream response bodies.

## Reproducible Virginia example

The bundled, sourced Loudoun parcel **146279040000** resolves to a point on its geometry:
**39.12137254, −77.52426106**, source version
`loudoun-county:14cf3ae701431e1b74155cd7`.

The optional live check creates a temporary project/database, queries public providers,
prints normalized results and removes its temporary database. It never writes to the
user's project or uses the synthetic demo campus:

```bash
python -m scripts.site_energy_live_check
# Explicit public-example credentials for a bounded evaluation only:
python -m scripts.site_energy_live_check --demo-keys
```

Live results on **2026-11-11 at 18:16 UTC**, using explicit demo-key opt-in:

| Item | Returned result | Interpretation |
|---|---|---|
| EIA August 2026 VA commercial | $111.40/MWh | Statewide published retail statistic |
| EIA August 2026 VA industrial | $99.80/MWh | Statewide published retail statistic |
| Transmission features within 20 km | 91 | Mapped features; not necessarily distinct circuits |
| Annual average GHI | 4.14 kWh/m²/day | Modeled 1998–2009 solar resource |
| PVWatts, assumed 1,000 kW DC | 1,384.00 MWh/year | Tilt 20°, azimuth 180°, losses 14%, fixed open rack |
| Service territory, substation | Unavailable | No accepted configured layers |

PVWatts returned model 8.5.0 and weather grid 1129531, NSRDB PSM V3 GOES tmy-2020
3.2.0, approximately 1,659 m from the requested point. These example outputs are
documentation of a live check, **not application fallback data**. Future observations
may differ. Demo-key quotas can make the optional check unavailable.

## Tests and verification

Offline new-feature tests:

```bash
python -m pytest -q tests/test_site_energy_providers.py tests/test_site_energy_api.py
python -m pytest -q tests/test_site_energy_auth.py  # separate auth process
npm run check
npm run check:ts-drift
```

Optional offline real-browser test (Playwright plus installed Chrome/Chromium):

```bash
python -m pip install playwright
# If Chrome is not installed, install Playwright Chromium separately.
python -m tests.browser_site_energy
```

It intercepts external parcel requests with the real bundled Virginia geometry and uses
clearly synthetic provider fixtures against the actual FastAPI routes. It exercises the
actual HTML/JS, Leaflet popup, PVWatts form, EIA selection, saved financial run and Economics.
Desktop/mobile screenshots go to `/tmp/powerpath-energy-browser` by default.

Validation recorded for the original integration:

- 337 passing tests across 29 process-isolated suites: new provider/API/auth tests,
  existing handoff, audit, identity, runtime-policy, PostgreSQL candidate, and every
  module in the existing extended release gate. No failures.
- Browser acceptance passed with no page errors and no mobile horizontal overflow.
- JavaScript syntax and TypeScript-generated-file drift checks passed.
- Live EIA, transmission and NREL/NLR resource/PVWatts requests succeeded.
- Existing financial outputs match when supplied the same numerical inputs. Engines
  and agent implementation files were not changed.
- Local checks ran with the installed Python 3.13 / Node 23 environment; CI retains
  the repository's pinned Python 3.12.10 / Node 22.23.4 setup. Existing dependency
  deprecation warnings do not fail the tests. Live PostgreSQL was not tested.

## Remaining assumptions and next integrations

Preserved assumptions include default electricity $85/MWh when explicitly chosen,
construction $7M/MW, building loads and PUE, power-path capacities and schedules,
rent/lease terms, financing and exit assumptions. Seeded illustrative schedules and
demo capacity remain illustrative. Solar installed capacity, layout/losses, self-use,
load and energy costs are user assumptions; PVWatts output is modeled, not measured.

Next integrations should prioritize authoritative SCC/utility territory and substation
layers with verified redistribution rights, actual utility tariffs and demand charges,
utility-study workflows for capacity/cost/timeline, hourly
load/solar/storage matching, wind resource data, and PostgreSQL cache/RLS acceptance.
The MVP does not infer available MW from voltage or distance, promise an interconnection,
or produce a bankable energy supply or development forecast.

## File inventory

New runtime files:

- `server/providers/base.py`
- `server/providers/electricity/eia.py`
- `server/providers/infrastructure/public_grid.py`
- `server/providers/renewables/nrel.py`
- `server/services/data_provenance.py`, `site_energy_data.py`
- `server/site_energy_api.py`
- `web/public/site-energy.js`

New verification/documentation files:

- `tests/site_energy_samples.py`, `test_site_energy_providers.py`,
  `test_site_energy_api.py`, `test_site_energy_auth.py`, `browser_site_energy.py`
- `scripts/site_energy_live_check.py`
- `docs/SITE_ENERGY_AUDIT.md`, `docs/SITE_ENERGY_INTEGRATION.md`

Modified existing files:

- `server/app.py`, `server/parcels28.py` — reuse parcel store and register routes
- `infrastructure/db_audit.py` — classify additive tables
- `web/public/workspace28.js`, `workspace28.css` — inspector, map and Economics integration
- `package.json`, `.github/workflows/ci.yml` — new checks
- `.env.example`, `README.md` — configuration and guide link

## PJM removal regression — 2026-11-22

- Removed the live pricing provider, node selection, delivery adder, credential setting,
  live-check option and obsolete provider fixtures/tests. New selections accept EIA or
  explicit assumed/user-supplied prices only; rejected legacy requests leave scenarios unchanged.
- Preserved existing saved numeric prices and provenance, manual queue CSV imports,
  EIA, NREL, transmission mapping, parcels and unchanged financial engines.
- 351 Python tests passed: 26 provider/API, 1 site-energy auth, 58 core/identity/runtime,
  5 historical intelligence, and 261 across the 21 process-isolated extended-gate suites.
- All 12 protected financial-engine hashes matched. JavaScript syntax and TypeScript
  generated-file drift checks passed.
- Chromium offline browser workflow passed: parcel filters/map parity, transmission popup,
  PVWatts, EIA selection, saved run and Economics; removed controls absent, zero page errors,
  no mobile horizontal overflow. Provider responses were synthetic; live external services
  and live PostgreSQL were not revalidated for this change.
