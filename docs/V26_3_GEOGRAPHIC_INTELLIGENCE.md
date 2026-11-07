# PowerPath v26.3 — Georeferenced infrastructure + critical-path underwriting

**Build classification:** local development alpha; screening-only, not a public SaaS, utility study, permit approval, power-rights evidence, project valuation or lender-grade software.

## What actually changed

- Added `geographic_assets` source registry. Each record includes actual WGS84 latitude/longitude, asset type, publisher/provider, dated source, a source record identifier, evidence grade, and attributes. Both the API and UI say available MW is **unknown**; generating stations, voltage levels and queue records do not demonstrate deliverable MW at a prospective site. The geographic map uses a real Web Mercator projection of these coordinates (not schematically positioned dots). It does **not** ship a full map basemap, transmission network routing, utility GIS datasets, geocoding or connection-capacity forecasts. A source-record inspector links to the source and OpenStreetMap.
- CSV bulk import: up to 250 points per request, all-or-nothing persistence, no row without a valid source URL/ID/lat/lon, per-project scope, SHA independent metadata and activity records. Compatible with EIA-860 plant-location columns `Plant Code`, `Plant Name`, `Latitude`, `Longitude`, `State`, `County`, `Grid Voltage (kV)`, etc.; more specialized generators/queue files require mapping before import.
- Two preloaded example **plant locations** (Dickinson and Loop 463 in Texas) are derived from the third-party *Ask the Grid* EIA-860 2025 extracts, **not independently ingested from EIA's canonical 2025 ZIP**. The records are marked `secondary_extract`. They are deliberately unrelated to the fictional demo campus. Import the canonical EIA-860 plant CSV after downloading it separately for first-party reproducibility; do not relabel the examples as direct official data.
- Added `delivery_milestones` linked to power paths, PermitIQ records and optional document sources. Dependencies cannot form cycles or point to another project's records. An estimated delay along a dependency chain sums incrementally; independent branches use the maximum. A linked PermitIQ delay is not added a second time. When multiple schedule drivers overlap, the resulting sensitivity uses the **maximum**, not their sum. This is a conservative scenario convention, not a validated critical-path method based on a full engineering schedule.
- New `sensitivity-v263` creates a distinct saved financial scenario from an existing underwriting version and applies the incremental schedule delay and path cost shocks to the previous, frozen input. The original remains unchanged and the preexisting v26.2 sensitivity API is not silently altered. Saved run still goes through the frozen underwriting engine and Risk controls.
- Added EIA CSV import, source inspector, geo-positioned pins, interconnection/permit dependency form, and launchable critical-path sensitivity in the web workspace. All model statuses still block lender-grade claims.

## Evidence boundaries

**Relevant primary source:** U.S. EIA, *Form EIA-860 detailed data* — https://www.eia.gov/electricity/data/eia860/ . Annual EIA-860 reports power plant coordinates/plant identification and information on generating units; it does not establish spare interconnection headroom or a supply commitment. EIA FAQ: https://www.eia.gov/tools/faqs/faq.php?id=567&t=3 ; EIA explicitly says they do not publish substation geolocations in their datasets. Secondary demo extract: https://askthegrid.com/catalog/eia860_plant_gas_declarations .

**Not provided:** a real-time authenticated utility grid map, engineering-level substation GIS, actual large-load service availability, proof of reserve capacity, official permitting / queue milestone statuses, grid routing and line impedance studies. The system is deliberately **offline/local** and does not scrape sources or run unsupervised third-party requests.

## New acceptance tests

Run `python tests/run_audit.py` in the project root. New tests cover geographic provenance, source URL validation, cross-project scoping, duplicate import atomicity, milestone DAGs and cycle rejection, separate unlinked PermitIQ delay handling, unchanged baseline scenarios, Risk screening labels, and the full workflow in desktop/tablet/mobile browser sizes. Existing frozen-engine SHA check remains in force. No JS engine change is in this release.

## Next true-data integrations

1. Obtain complete official EIA-860 plant and generator surveys (2025 annual; EIA-860M for preliminary monthly inventory) and build a documented normalization import with native EIA plant IDs. Do not equate generation nameplate to utility service capacity.
2. Select supported ISO/RTO regions and ingest *their official* interconnection queue datasets, keeping queue status, jurisdiction, timestamp and source record separate. Generation interconnection queue projects are not large-load service commitments.
3. Source utility-specific tariff sheets, service study outcomes, public transmission lines with documented provenance, and actual customer utility correspondence. Distinguish independent primary documents and internal user estimates. Do not derive a projected energized date until a dated utility milestone is available.
4. Upgrade from screening delay max-convention to a full resource-constrained critical path, only after task durations and dependency types are validated by project teams.
5. Production hosting requires authentication, RBAC, tenant isolation, private storage, backups, privacy review and a qualified external model assurance; none is included.
