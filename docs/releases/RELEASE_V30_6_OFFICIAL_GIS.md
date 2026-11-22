# PowerPath v30.6.0 — National GIS Evidence Connectors (Alpha)

**Base:** v30.5.0 National PermitIQ Foundation. **Date:** 2026-10-29.

**Release classification:** Local-only, opt-in government GIS *point screening*. **Not** verified parcel boundaries in all counties, production-ready remote GIS, comprehensive local zoning, legal permit clearance, authority to file, or underwritten power dates.

## What is implemented

- **U.S. Census coordinate geographies:** service adapter queries the Census Geocoder for candidate counties and incorporated places. It rejects mismatched state GEOIDs, unknown county IDs and conflicts with any imported Census county polygon. An incorporated-place match is a geographic candidate, not a zoning-authority finding.
- **FEMA National Flood Hazard Layer (NFHL):** queries FEMA's Flood Hazard Zones service (layer 28) at the selected latitude/longitude and returns zone attributes for identified features.
- **USFWS National Wetlands Inventory (NWI):** queries the official NWI MapServer wetlands layer (0) at the selected latitude/longitude, returning mapped classes and attributes.
- **Fail-closed evidence schema:** `MAPPED_INTERSECTION`, `NO_MAPPED_INTERSECTION_AT_POINT`, `UNAVAILABLE`, `MATCHED`, `NO_UNAMBIGUOUS_MATCH`, `CONFLICT_REVIEW`. No point result implies clearance for the *parcel*, and no GIS result confirms the requirements under the Clean Water Act, zoning law or a local permit.
- **Read-only API:** `POST /api/permitting/official-gis` and `GET /api/permitting/official-gis/status`. Existing `/api/permitting/screen` and v30.4 Loudoun rule engine are unchanged.
- **UI:** new optional *Official GIS point check* in `/permitiq-national`, separate from the permitting-rule assessment. Displays agency source, field results, a timestamp and evidence SHA-256.
- **Census county polygon installer:** `scripts/download_tiger_counties.py` downloads the **official Census 2025 1:500,000 county boundary ZIP** and invokes the preexisting geometry importer. Running this is optional, network-dependent and not required to open the national map. The ZIP is not bundled because downloading external datasets was blocked in this build environment.

### Security and privacy

- **Disabled by default.** Operators must set `POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1` before source requests are enabled. End users must also explicitly check a consent box. Census, FEMA and USFWS then receive the selected coordinates from the hosting server.
- Official endpoints are constants. No user-provided URL, network host, raw SQL or arbitrary ArcGIS service is allowed. Responses are size-limited, timed out and parsed only for allowlisted attributes. An in-memory limit of 20 requests/hour/client is applied (not a distributed production rate limiter).
- No GIS evidence is persisted to PowerPath's database or financial model. Raw request/response content is not written by PermitIQ. An evidence fingerprint includes the retrieval timestamp, point, official-source observations, and source descriptions.
- Both new GIS endpoints return HTTP 503 in `POWERPATH_V27_AUTH_MODE=required` pending a proper authenticated, project-scoped release. Do not deploy alpha endpoints in a publicly exposed environment.

### Run

```bash
unzip PowerPath_v30_6_0_National_GIS_Connectors.zip
cd PowerPath_v30_6_0_National_GIS_Connectors
python3 -m pip install -r requirements.txt
python3 -m uvicorn server.app:app --host 127.0.0.1 --port 8768
# open http://127.0.0.1:8768/permitiq-national
```

To enable live point checks on a local development machine **with internet connectivity**:

```bash
export POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1
python3 -m uvicorn server.app:app --host 127.0.0.1 --port 8768
```

The web page requires the user to check the coordinate-sharing consent box before each official GIS request.

For optional nationwide **generalized county polygon geometry**:

```bash
python3 -m pip install geopandas pyogrio shapely
python3 scripts/download_tiger_counties.py
# restart the app; allow --allow-overwrite to update an existing import
```

The importer checks source host, basic size, projection, unique county GEOIDs and polygon validity. Census geometry is deliberately generalized and can disagree with legal permitting jurisdictions, municipal boundaries and surveyed parcel edges. It cannot supply a local zoning permit by itself.

## Verification performed

- `pytest -q permitting/test_official_gis.py permitting/test_permitting.py permitting/test_national.py feasibility/test_phase1.py feasibility/test_v82_integration.py feasibility/test_v83_financial_bridge.py feasibility/test_v831_bridge_proof.py tests/test_api.py tests/test_geo29.py tests/test_public30.py tests/test_regrid_pilot.py` — **180 passed**. This includes **14 new GIS contract tests using fixture responses**; it does not demonstrate live connections.
- `python -m unittest tests.v271.test_v271_required_auth -q` — **3 passed** as a separate process.
- `node --check` passed for national PermitIQ UI JS, `app.js`, and `workspace28.js`.
- Financial engine SHA-256 audit — all **12 of 12** files matched `ENGINE_HASH_AUDIT_V30_3.json`.
- Local server HTTP status and disabled remote-GIS API were checked successfully.
- Full combined pytest collection remains blocked by the pre-existing separate-process required-auth module test collection setup. No clean full-suite claim.
- Chromium visual browser test was attempted using system Chromium but localhost navigation was blocked by the sandbox administrator. Browser visual test not passed.
- **Live Census, FEMA and USFWS service responses were not tested** because outbound network access was unavailable in the build environment. The GIS service contracts must be confirmed against real responses on a connected machine before any pilot.
- **Nationwide county polygon data was not downloaded or bundled.** The operator importer is ready but was not executed against the official ZIP.

## Work still required for production/commercial use

1. Perform end-to-end service checks on a networked host with representative locations in VA, NC, TX and flood/wetlands test parcels. Validate Census response fields, FEMA/NWI schema, feature limits, and outage handling.
2. Import and version Census county polygons, then add official municipal/tribal/federal special-jurisdiction geometry and parcel footprints. Geometry-free point intersection is not sufficient for parcel underwriting.
3. Add actual clipped polygon overlays with source vintages, and meaningful **parcel footprint** intersections, not just point samples. Consider FEMA's coverage limitations and NWI source imagery dates.
4. Review authoritative state and local zoning rule packages beyond Loudoun (starting with Virginia and North Carolina) and utility tariffs. GIS selection alone does not confer local legal coverage.
5. Integrate independently reviewed permits and dated milestones with the project-scoped PermitIQ tracker and separate grid/on-site energy tranches. Do not infer P50/P90 or financial readiness from these map checks.
6. Replace alpha open-access routes with authenticated project-scoped access, distributed quotas, source-use/license review, appropriate outbound privacy controls and operational monitoring.

## Official sources

- Census: https://www.census.gov/data/developers/data-sets/Geocoding-services.html
- Census county boundaries: https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_500k.zip
- FEMA NFHL GIS: https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer
- USFWS NWI GIS: https://www.fws.gov/program/national-wetlands-inventory/web-mapping-services
