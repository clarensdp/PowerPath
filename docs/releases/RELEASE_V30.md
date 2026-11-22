# PowerPath v30 — North Carolina and Virginia public parcels

Live public parcel queries are connected to NC OneMap and Virginia VGIN. No paid parcel subscription or API key is required. This is a local alpha with internet-dependent parcel retrieval, not a bundled download of every parcel in either state.

## Launch

```
python3 -m pip install -r requirements.txt
./run_local.sh
```

Open http://127.0.0.1:8768. Select or create a project, then open **Explore parcels**. Use **Explore North Carolina** or **Explore Virginia**; these start at Raleigh and eastern Loudoun respectively. Search for another county or select a state, then zoom in. Parcel outlines work without enabling the optional OpenStreetMap basemap.

Pan/zoom to fetch up to 200 records per service per query. The UI displays up to 200 records and labels truncation. Broad views require zooming in. The initial acreage filter is zero so smaller parcels remain visible; increase it for site screening. PIN search applies within the returned viewport subset, not the entire state. Virginia acreage filtering also applies after the bounded source query, so zoom in when results are truncated.

## Data sources

- NC OneMap: https://services.nconemap.gov/secure/rest/services/NC1Map_Parcels/MapServer/1
- Virginia VGIN: https://vginmaps.vdem.virginia.gov/arcgis/rest/services/VA_Base_Layers/VA_Parcels/FeatureServer/0
- Virginia source catalog: https://www.arcgis.com/sharing/rest/content/items/29627d7c051a47dc8ce71b4484531ab3

NC's source aggregates all 100 counties and Eastern Band of Cherokee Indians lands. Virginia's aggregation has locality-dependent participation and update dates. A live connection is not a completeness or accuracy guarantee. NC metadata and its use limitations accompany this build at data_sources/nc_onemap_metadata.xml. The Virginia catalog identifies CC0; retain agency attribution and consult local records for diligence. Neither source is a survey, title opinion, sale listing or utility service commitment.

County-provided dates are displayed separately from retrieval time. NC acreage uses source GIS acreage when present. VA acreage is an approximate spherical calculation from geometry; neither is a buildable-area determination. Provider parcel IDs are visible; jurisdiction-qualified internal IDs prevent cross-county collisions.

## Workflow and persistence

Live parcels can be inspected, shortlisted, assessed, compared and included in existing diligence/memo workflows. Fetches retain source versions; saved project parcels stay pinned to their version. Other viewed parcels remain in a local latest-record cache, and repeat identical queries reuse responses for five minutes. On source failure, the API labels the failure and returns previously fetched records where available. On an empty successful query, the app does not substitute old geometry as current results.

Viewing a new parcel does not create an assessment or reliability score. The prior evidence thresholds remain in place. Existing Loudoun records remain supported and can appear as cached fallback data. Other states remain navigation only. Remote calls run through the local server; providers receive requested map bounds and the server's network address. Source datasets are public across this installation; project evidence remains governed by the existing access controls.

## Verification

Live requests returned 20 real parcel features each from NC and VA, with successful project-shortlist saves for both. The capped requests correctly reported additional results. See docs/V30_LIVE_CHECKS.json. Representative source dates were 2025-06-02 (NC sample) and 2026-07-31 (VA sample); they are not statewide freshness guarantees.

Automated checks cover public-source normalization, hole-subtracted area, viewport guards, truncation, cache retention, saved snapshots and outage fallback, plus existing parcel/national/provider and required-auth regressions. DOM tests cover navigation and live map API bindings with Leaflet mocked. Full browser rendering and visual map interaction remain unverified. The financial engines are unchanged; the inherited financial fixture mismatch documented in v28 remains unresolved.

## Operational limits

No service SLA, refresh scheduler, automatic removal of retired parcels, cache eviction for database history, nationwide feed or production-scale spatial warehouse is included. The local cache grows as users explore; it is a pilot store. A maximum 0.8-degree viewport dimension, bounded result count, 15-second source timeout and 16 MiB response cap limit individual requests. Dense areas require zooming. Invalid source records are omitted and counted in the status. The source query is a geometric intersection, not an engineering suitability test.
