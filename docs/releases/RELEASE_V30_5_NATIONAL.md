# PowerPath v30.5.0 — PermitIQ National Foundation

**Release date:** October 29, 2026  
**Base:** `PowerPath_v30_4_0_Permitting_Alpha.zip`  
**Status:** Local-only read-only **national state-navigation + partial permitting screening alpha**, NOT nationwide zoning coverage, legal reliance, production deployment or lender-ready underwriting.

## What shipped

- New interactive **PermitIQ National Screening** page at `/permitiq-national`. Uses local Leaflet and the bundled U.S. Census TIGERweb generalized state polygons. Covers exactly **50 states + DC**. Territories excluded from this release. No external map tiles or geocoding service is required to display the state layer.
- **County catalog:** bundled Census county-equivalent interior-point references support named county selection in all states. **A county selection is an analyst claim, not geographic verification.**
- **Optional county polygon importer:** `scripts/prepare_tiger_counties.py` supports an operator-supplied, official Census 1:500,000 county boundary ZIP or GeoJSON; saves `data_sources/us_counties_500k.geojson` with source metadata. When present, county polygons enable generalized (not legal/survey-grade) county intersection. They are **not bundled**.
- **New read-only API:** `GET /api/permitting/map/states`, `GET /api/permitting/counties`, `GET /api/permitting/coverage`, `POST /api/permitting/screen`. All are disabled (`503`) in `POWERPATH_V27_AUTH_MODE=required` until they are routed through authenticated, project-scoped access controls.
- **Tri-state trigger evaluation:** TRUE/FALSE/UNKNOWN. Missing positive and negative facts yield `POSSIBLE_VERIFY`, not false clearance. The legacy v30.4 `assess()` engine remains unchanged for backward compatibility.
- **Selective rule previews:** 2 federal triggers nationally (FAA notice and 404 wetlands), partial Virginia state triggers, and Loudoun + Dominion only with county code `51107` (selected or resolved from imported polygons). There are **no complete state, county, municipal, tribal, special-district or utility rule sets nationally**. Status always remains `SCREENING`/`INCOMPLETE`; no positive approval outcome.
- **No ungrounded defaults:** IT MW does not silently become utility-request MW; backup generation is UNKNOWN unless supplied; unknown Loudoun grandfathering does not imply either by-right or legislative approval.
- **Evidence boundary:** no national permitting durations or power dates are published from this preview; the legacy Loudoun schedule and the two-tranche v8.2 limitation remain unchanged. Proposed regulations are not automatically adopted.
- **Auditability:** every screening response includes a stable SHA-256 fingerprint of project input, date, geography source hashes and applied rules. No financial engine, SQL schema, permit status, or agency records are written.

## Run locally

```bash
unzip PowerPath_v30_5_0_National_PermitIQ_Foundation.zip
cd PowerPath_v30_5_0_National_Foundation
python3 -m pip install -r requirements.txt
python3 -m uvicorn server.app:app --host 127.0.0.1 --port 8768
```

Open `http://127.0.0.1:8768/permitiq-national` or use the **PermitIQ national screening** link in the existing Development Workspace, or **National screening** from PermitIQ / Execution.

**Optional real county geometry import:**

1. Download the official 1:500,000 county cartographic boundary ZIP from the Census website, e.g. https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_500k.zip, yourself. This file is not included.
2. Install the offline importer extras: `python3 -m pip install geopandas pyogrio shapely`.
3. Run: `python3 scripts/prepare_tiger_counties.py /path/to/cb_2025_us_county_500k.zip --source-url https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_500k.zip`.
4. Restart the application. County source and geometric generalization limitations remain visible. Municipal and special-district authorities still need separate mapping.

**API example:**

```bash
curl -s http://127.0.0.1:8768/api/permitting/screen \
  -H 'Content-Type: application/json' \
  -d '{"latitude":39.08,"longitude":-77.55,"county_geoid":"51107","as_of":"2026-10-29","facts":{"design":{"it_mw":200},"parcel":{}}}'
```

## Tests executed

- `pytest -q permitting/test_permitting.py permitting/test_national.py feasibility/test_phase1.py feasibility/test_v82_integration.py feasibility/test_v83_financial_bridge.py feasibility/test_v831_bridge_proof.py tests/test_api.py tests/test_geo29.py tests/test_public30.py tests/test_regrid_pilot.py` → **166 passed** (including 30 legacy permitting and 63 new national tests).
- `python -m unittest tests.v271.test_v271_required_auth -q` → **3 passed**, separate process required by baseline suite.
- `node --check` on `permitiq-national.js`, `app.js`, and `workspace28.js` → syntax passed.
- Hash audit: **all 12 files** in `ENGINE_HASH_AUDIT_V30_3.json` unchanged from the original v30.4 archive. Legacy permitting rule data and engine also unchanged.
- Entire `pytest -q` in one process **not a green gate**: collection conflict in existing `tests/v271/test_v271_required_auth.py` because separate-process auth setup reuses a module already loaded at collection. The module passes when run independently. Do not claim complete release-gate certification.
- Chromium end-to-end visual check **not completed**: sandbox browser navigation to localhost was blocked by administrator. Syntax and API tests are not proof of browser UX.

## Deliberate open items and next release requirements

1. Live and versioned national overlays: FEMA flood, NWI wetlands, USGS terrain, EPA ECHO/FRS, protected lands and FAA height/airport surfaces. This release **does not download or intersect those layers**; user-supplied facts are not evidence that layers are clear.
2. Census county boundaries are **not pre-imported**. Imported county cartography still does not resolve municipal zoning, tribal/federal lands or special-purpose authority.
3. National rules library expansion and locally reviewed zoning package registry; Virginia state rules are partial and Loudoun local rules remain alpha. Additional utility modules must be validated against actual service territories and tariffs.
4. Project-scoped authentication and record ownership; reviewed adoption of suggested requirements into existing `permit_items` with immutable audit events, no duplicate trackers.
5. Proper per-tranche financial schedule integration, which remains blocked pending the v8.2 mismatch correction. No implicit endorsement of current P50/P90 priors.
6. External review of legal requirements and out-of-sample duration calibration before commercial or investment-grade use.

## Traceability

- National state geometry source: `data_sources/us_states.geojson` (`powerpath_source` embedded), generalized TIGERweb navigation. County interior reference points: `data_sources/us_county_locations.json` (`powerpath_source` embedded).
- New code: `permitting/national.py`, `permitting/test_national.py`, `server/national_permitting_api.py`, `scripts/prepare_tiger_counties.py`, `web/public/permitiq-national.{html,css,js}`.
- Existing modified: `server/app.py` (add new route), `package.json` (version), `web/public/{app.js,workspace28.js}` and `web/src/app.ts` (link only).
- `SHA256_MANIFEST_V30_5.json` records all release file hashes and immutable engine audit.
