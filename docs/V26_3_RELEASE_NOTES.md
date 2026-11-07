# PowerPath v26.3 — Geographic Intelligence and Critical-Path Scenario Linking

**Status:** LOCAL ALPHA — bounded deterministic screening only. **Not** a live grid-access platform, utility-confirmed power-availability map, actual permit approval feed, investment valuation, lender certification or deployable production SaaS.

## Executive summary

v26.3 connects correctly projected latitude/longitude infrastructure references, source provenance and milestone-linked financing sensitivity within the existing persistent project workspace. The existing financial engines are **unchanged** and all Risk G4/G5 restrictions remain blocked. This release does not claim that known power plants, transmission sites or source-record coordinates can deliver power to a user site.

## What shipped

1. **Geographic source registry:** new locally persisted `geographic_assets` table, with explicit geodetic coordinates, provider, source URL and ID, vintage, evidence-level classification, and source attributes. No populated `available_mw` promise: `capacity_available_mw: null`, `available_power_verified: false` on every API record.
2. **Real-coordinate map:** client-side WGS84 / Web Mercator plotting and accessible source-selection controls, with an optional external link to OpenStreetMap for real geographic context. The raster basemap itself and utility network/capacity layers are not provided. Source examples are derivative data, not first-party EIA-860 rows re-downloaded in this environment.
3. **CSV import:** EIA-860-compatible fields, capped at 250 records/import, consistent validation and all-or-nothing transactions, duplicate-ID checking, local storage and audit entries. The user controls source URLs and metadata, so a record must not be equated with independently authenticated documentary evidence.
4. **Milestone dependency graph:** persisted and path-scoped milestones, optional PermitIQ/evidence links, statuses and recorded delay estimates. Prevents cross-project links and cyclic dependencies. Critical delay = maximum of independent schedule drivers, with dependent chain delays accumulated. Completed milestones contribute zero newly projected delay. This is an *illustrative scenario convention* rather than a complete network/schedule engineering forecast.
5. **Schedule-based versioned underwriting:** separate `/sensitivity-v263` API evaluates the path schedule, applies the estimated governing delay and cost shocks to a fresh scenario, saves an immutable run through the preserved underwriting engine and never edits the originating scenario. Chaining another path sensitivity as the new base is explicitly rejected to avoid reapplying previously modeled delays.
6. **Demo project:** two third-party-transcribed 2025 EIA plant-location examples, disconnected from the fictional campus, and three hypothetical milestone entries. The source records cannot be used as utility service commitments.

## Reproducible validation

Run `python tests/run_audit.py`. The completed report is `V26_AUDIT.json`: **37/37 release audit jobs passed**, covering compilation, inherited financial regressions, 51 imported fixed-note subtests, independent note-engine parity, six geographic-source/critical-path API tests, prior server/API suites, desktop/tablet/mobile browser workbooks, and source-hash consistency for all imported financial/risk engines. The independent parity tests validate programmed accounting behavior against their stated specification; they are *not* real-contract validation. `docs/ENGINE_BASELINE_SHA256.txt` retains original engine hashes.

## Primary source and integrity boundaries

- EIA Form EIA-860 detailed data: https://www.eia.gov/electricity/data/eia860/ . The official annual plant records include plant locations, but not utility-confirmed available MW to serve a particular large-load connection.
- EIA location FAQ: https://www.eia.gov/tools/faqs/faq.php?id=567&t=3 . EIA explicitly says these datasets do not give substation locations.
- Demo location examples transcribed from a secondary 2025 EIA extract at https://askthegrid.com/catalog/eia860_plant_gas_declarations ; marked `secondary_extract`, **not** `Executed` or independently reconciled to official source bytes.

**Still missing**: official transmission/substation GIS with suitable licenses and permitted use, official and current ISO/RTO utility interconnection applications and queue updates, site-specific service agreements and study estimates, actual parcel geolocation and electrical system capability, production authentication/security. Do not publish this development server or send confidential counterparty documents into it.

## Upgrade/run

Unzip, enter `PowerPath_v26_3`, then run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run_local.sh
```

Open http://127.0.0.1:8768 . Existing v26.2 installations: **back up and transfer the previous `data/` folder before startup**. New SQLite tables are additive; previous scenarios and evidence records are not rewritten.

## Next gate

v26.4 should add independent canonical EIA import reconciliation, region-specific official queue ingestion with explicit freshness and term provenance, defensible utility/ISO geospatial sources, and source-backed service-study timeline updates. None of those upstream sources should automatically elevate PowerPath's Risk gates to certified use. Production multiuser cloud operation remains a separate authorization/security program.
