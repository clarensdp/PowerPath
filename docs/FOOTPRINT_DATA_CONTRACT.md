# PermitIQ v30.7.1 — Polygon intersection contract

`POST /api/permitting/footprint` accepts **one** of `geometry` (WGS84 GeoJSON Polygon or MultiPolygon) or `parcel_id` (local versioned `geo29`/`geo30` record). The maximum request body is 3 MB.

`layers` is an array of objects containing `kind` (`flood`, `wetlands`, `zoning`, `protected_land`, `setback`, `easement`, `other`), `source` (`title` required; optional `url`, `published_at`, `retrieved_at`, `license`), `features` (GeoJSON FeatureCollection with polygon/multipolygon features), and optional `coverage_geometry` (a valid WGS84 Polygon/MultiPolygon of the region for which that source declares mapped completeness). **A layer geometry is not the coverage polygon.** Passing only the feature polygons never implies that unmapped regions were searched comprehensively.

`official: true` requires `consent_remote: true` and operator environment `POWERPATH_PERMITIQ_REMOTE_OVERLAYS=1`. This mode queries the fixed FEMA and NWI endpoints for polygon geometries. The parcel's bounding box is sent; its exact boundary remains local to the intersection calculation. Any official service failure creates an `UNAVAILABLE` record and a warning, never a negative/clear finding.

Response semantics:

- `parcel.area_acres`: equal-area projected acreage using the WGS84 polygon geometry provided (not a survey).
- `layers[].intersection_acres`: area intersecting a given layer, polygon-unioned to remove duplicates inside the layer.
- `layers[].intersection_geometry`: layer union clipped to the full parcel boundary, rendered on the map.
- `summary.intersecting_supplied_constraints_acres`: union of all **non-zoning** constraint layers, not sum of individual overlaps.
- `summary.no_mapped_overlap_acres`: purely a geometric residual; `no_mapped_overlap_is_buildable` always `false`.
- `summary.certified_buildable_acres`: always `null` in this alpha.
- `coverage.*`: `UNKNOWN` without full declared source extent; operator-declared complete coverage is not agency-verified or evidence of permit compliance.
- `snapshot_sha256`: stable digest of supplied parcel boundary, sources, and overlay geometry. It does not establish signature authenticity, immutability of external services, or proof of chain of custody.
- `persisted`: always `false`. No financial changes.

All user-supplied zoning polygons are **unverified** until reconciled to current official municipal zoning source, district ordinance and relevant use/conditional-use provisions. If needed, capture these in a future separate signed/approved legal-rules workflow. No cross-state legal rule inference is supported.
