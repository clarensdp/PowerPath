# PowerPath v29 — National coverage foundation

This local alpha adds navigation across all 50 states and DC. It does **not** claim national parcel coverage. The only bundled real parcel source remains the 120-record Loudoun County snapshot.

## Start

Install requirements with `python3 -m pip install -r requirements.txt`, then run `./run_local.sh`. Open http://127.0.0.1:8768. Use Explore parcels → state selector or county search. Search “Loudoun” to inspect the connected pilot. Basemap tiles require opt-in and network access; state boundaries are bundled.

## Implemented

- Census state boundaries and state/county location search.
- Coverage status per state, source attribution, dates and scope.
- SQLite R*Tree spatial index and viewport parcel API (`/api/geo29/parcels`). Queries support bbox, state FIPS, minimum acreage, parcel ID substring, limit and offset.
- Versioned geometry and metadata, jurisdiction-qualified IDs for imported sources, immutable source-version links for saved parcels.
- Import validation for WGS84 polygons, duplicate IDs, area values and source metadata.
- Existing project flow, evidence scores, tasks and financial tools retained. Feasibility scores do not measure electrical reliability.

## Add a county snapshot

Prepare a GeoJSON FeatureCollection and source metadata JSON. Run from the release directory:

```
python3 -m tools.import_parcels29 county.geojson source.json --id-field PARCEL_ID --square-feet-field AREA_SQFT
```

Required source fields: `id` (2–24 lowercase slug characters), `name`, `state_fips`, `county_fips`, `source_url` (HTTPS), `license_note`, `coverage_scope`, `retrieved_at` (timezone-aware ISO timestamp). Optional `provenance` defaults to user_supplied. Do not label analyst-created data official. The acreage input field must contain square feet; omit it when unavailable.

Each import is a complete replacement snapshot for that source, limited to 5,000 features. Do not split one source into sequential batches: the newest batch becomes its active snapshot. Use distinct clearly scoped source IDs for partitions. Prior versions remain retained for saved decisions. Imports are a local operator command, not an exposed upload API. Connected datasets are visible to authenticated users of the installation and must not contain tenant-private information.

## Verification

11 national/parcel API tests pass; 3 required-auth tests pass. JavaScript syntax and DOM workflow smoke checks pass. Financial engine JavaScript/TypeScript files match the existing workspace. A full browser visual/map interaction check remains outstanding in this environment. The inherited financial fixture hash mismatch documented in v28 is not resolved by this release.

## Remaining work

No national parcel license, automated refresh scheduler, production PostGIS deployment, vector tile service, zoning or utility-capacity feed is included. State polygons include geographic extents that can give Alaska a broad fit; county search is available for closer navigation. Spatial matching uses bounding-box overlap, not exact polygon intersection or development eligibility. The UI shows at most 500 viewport matches and asks users to zoom/filter for more. The optional Census address API is available server-side with explicit consent but is not yet wired into the interface.
