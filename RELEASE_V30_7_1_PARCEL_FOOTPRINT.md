# PowerPath v30.7.1 — Parcel Footprint Analysis Alpha

**Release date:** 2026-10-29. Based on: v30.7.0 Agent Operating Foundation.
**Status:** Local, read-only GIS screening alpha. Not a development eligibility, environmental clearance, zoning verification, or lender-grade determination.

## Summary

This release expands PermitIQ from centroid/point lookups to true **Polygon/MultiPolygon** intersections. It is a small additive GIS milestone deliberately numbered **v30.7.1**; the planned architectural hardening / PostgreSQL transition remains separate. No financial modeling engine, agent permission system, source SQLite schema, or permitting v30.4 rule/schedule engine was modified.

### Implemented

1. `permitting/footprint.py` — validates complete polygon boundaries (including explicit closed rings), computes local Lambert azimuthal equal-area acreage, intersects/locally clips supplied hazard polygons to the exact parcel, handles holes and multipolygons, unions overlaps within and across non-zoning constraints to prevent double counting, returns acreage and percent, and preserves source metadata. Includes geometry/source snapshot SHA-256. The resulting acreage *not overlapping supplied features* is **not buildable acreage**.
2. `permitting/footprint_sources.py` — optionally retrieves geometry from existing fixed official FEMA NFHL and USFWS NWI services using a bounded envelope query, full feature IDs, and 50-record geometry pages; all results are subsequently **clipped to the actual parcel**. FEMA polygons are screened for the `SFHA_TF` flag (Special Flood Hazard Area). Other mapped flood zones are not included in this indicator. NWI wetland geometry is not a formal jurisdictional waters delineation. No layer is treated as complete without an independently established coverage envelope. The service fails closed on errors, truncation, excessive feature counts or missing geometries. **Live integration was not validated on this host.**
3. `server/footprint_api.py` — `POST /api/permitting/footprint` and `GET /api/permitting/footprint/status`; supports cached parcel `workspace_id` or user-supplied GeoJSON boundary; accepts 0–12 layers (per layer up to 250 polygon features) and optional per-layer mapped coverage geometry. Maximum payload 3 MB. **Read-only**. Disabled in required-auth mode until scoped/tenanted controls are built.
4. `web/public/parcel-footprint.js` and updates to PermitIQ national page — find locally cached parcel boundaries near a selected location, query existing NC / VA public parcel services where internet access exists, upload a GeoJSON parcel boundary, add zoning/hazard/constraint feature collections plus optional coverage boundary, run exact geometry analysis, draw the parcel and clipped overlays on the map, and review acreage, coverage cautions and next steps.
5. `requirements.txt` — add `shapely` and `pyproj`; these are required for accurate polygon analysis, rather than silently approximating acres from latitude/longitude degrees.

### Source and evidence safeguards

- **Nationwide geometry ingestion** is supported through operator-supplied GeoJSON; actual connected parcel source coverage remains limited to the preexisting Loudoun snapshot and the previously integrated NC and VA public viewport services. This is not a complete nationwide parcel dataset.
- No national municipal zoning source was invented. Users must supply zoned polygons and official jurisdiction/source evidence. Zoning boundaries do not themselves prove data-center use eligibility.
- Missing a layer, an incomplete mapped extent, or a failed API query always produces **unknown**, never all-clear.
- `coverage_geometry` is an **operator-declared mapped extent**, not independent verification. It does not change `overall=SCREENING_NOT_CLEARED` or establish buildable acreage.
- Calculations are not saved to the project, permit records, database evidence room, or underwriting scenarios. Persisting immutable reviewed evidence is a future integration task.
- Parcel footprints and bounding boxes sent to official remote GIS sources require both operator activation (`POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1`) and an explicit user checkbox. Local-only GeoJSON analysis makes **no** remote request.
- Arbitrary external service URLs cannot be supplied to the server for fetching; the remote GIS services have fixed allowlisted endpoints.
- Local example data/geometry used in tests is synthetic; numerical tests are not factual findings about any specific commercial parcel.

## Run locally

```bash
unzip PowerPath_v30_7_1_Parcel_Footprint_Alpha.zip
cd PowerPath_v30_7_1_Parcel_Footprint_Alpha
python3 -m pip install -r requirements.txt
./run_local.sh
# Visit http://127.0.0.1:8768/permitiq-national
```

In the **Analyze entire parcel** section: locate a parcel on the map; click **Find cached parcels near point**, or **Query public NC/VA parcels** (network needed), or upload a WGS84 GeoJSON Polygon or Feature. Optionally upload a FEMA/wetlands/zoning FeatureCollection along with the source and the actual coverage extent when known. Click **Run full-footprint screening**. Optional remote official layers need explicit consent and the environment switch below:

```bash
export POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1
```

**API shape** (synthetic example, not a real site):

```json
{
  "geometry": {"type":"Polygon","coordinates":[[[-77,38],[-76.99,38],[-76.99,38.01],[-77,38.01],[-77,38]]]},
  "layers": [{
    "kind": "zoning",
    "source": {"title": "Sample polygon source; not legally verified"},
    "features": {"type":"FeatureCollection","features":[]},
    "coverage_geometry": null
  }],
  "official": false
}
```

Or replace `geometry` with `"parcel_id": "<workspace_id from /api/geo29/parcels>"` to use a versioned parcel already in the local registry.

## Validation and known blockers

- **23/23 new footprint unit and API tests passed**, covering ring closure, geographic validity, holes, true polygon clipping, union accounting, source completeness, deterministic fingerprints, official HTTP mock responses, 3D GeoJSON normalization, consent, auth gating and fail-closed behavior.
- **203/203 selected GIS, permitting, feasibility and parcel regressions passed**, including the added 3D geometry test.
- Existing agent operations and legacy workflow suites pass in isolated runs. Combining legacy modules in a single process can still produce shared database/auth/test-state contamination. This was already a known v30.7 limitation and is not claimed as resolved.
- Read-only HTTP smoke test using an actual versioned parcel in the included Loudoun fixture returned **200** and a **29.34174-acre** polygon result with all environmental/zoning status **UNKNOWN**, as expected. That is calculated geometry acreage from the supplied GIS boundary, not a surveyed or buildable acreage determination.
- Headless browser execution was blocked by the environment's network policy (`ERR_BLOCKED_BY_ADMINISTRATOR`). JavaScript syntax and the actual HTTP/API routes were checked, but the UI has **not** passed browser visual acceptance.
- Direct live FEMA and USFWS polygon response compatibility remains untested on an online host; mock tests do not establish production connector reliability.
- There is no project-scoped persistent footprint assessment or immutable source archive yet. A reviewed PostGIS evidence model should accompany the v30.8 database program, not be implemented as another ad hoc SQLite table.

## Required next steps before commercial use

1. Validate official polygon-service requests and coverage masks on an internet-connected staging deployment; compare agency GIS data against approved source exports.
2. Implement official local zoning datasets for a limited number of jurisdictions (start Loudoun/VA and NC), including versioning, updating and municipal jurisdiction confirmation.
3. Introduce project-scoped, immutable assessment records and a review workflow in PostgreSQL/PostGIS with access control, migration and recovery tests.
4. Include flood-map panel/effective dates, dataset extents and more nuanced FEMA flood-zone classes rather than treating SFHA as comprehensive flood risk.
5. Test UI interactions, accessibility and responsiveness through a real supported browser automation pipeline.
6. Feed only verified reviewed GIS constraints into permit gates, milestone scheduling and financial sensitivity, with manual sign-off for legal/regulatory interpretation.
