# Site energy integration audit

Repository inspected before implementation: `server/`, `web/`, `engine/`, `feasibility/`,
`permitting/`, `infrastructure/`, `migrations/`, `data_sources/`, `tests/`, `scripts/`,
`architecture/`, `deploy/`, historical `baseline/` and `review/`. `agents/` is out of scope.

- Entry point: `server.app:app`. Features register routes through `install(app, ...)`.
- `parcels28.install` owns the initialized `GeoStore`. Public GIS queries retain source
  versions in `geo29_*`; project shortlist selection pins records in `geo29_saved_versions`.
- Browser `workspace28.js`: `selectParcel` loads project-scoped details; power paths
  are project hypotheses, not parcel utility commitments. Economics calls
  `/projects/{pid}/paths/{pathid}/schedule-impact` using a saved base scenario.
- Underwriting executes `engine/bridge.cjs` through a Python subprocess. `powerCostMWh`
  is already a supported input. Do not modify engine mathematics or frozen defaults.
- Defaults include $85/MWh electricity and $7M/MW construction. `starter.py` sizes
  buildings using illustrative defaults; `seed_demo.py` supplies illustrative paths
  and schedules. Public parcel boundaries do not validate those assumptions.
- Existing providers: `providers/regrid.py`, `public_parcels30.py` (bounded requests,
  five-minute in-memory cache), Census geocoding in `geo29.py`, permitting GIS clients.
  No shared HTTP cache/provenance client exists. Reuse urllib, Pydantic, SQLite,
  Shapely/PyProj and feature installation conventions.
- Project route prefixes are protected by existing local/managed identity middleware.
  New endpoints must use that prefix and check scenario/evidence ownership.
- Existing tests often initialize process-global app/database/auth state on import;
  run auth suites in separate processes. Use isolated temporary databases.

Design: project-scoped provider cache, normalized provenance, parcel-version lookup,
independently failing providers, explicit scenario input selection, and evidence-backed
user entries. Never derive capacity or schedules from distance. No agent changes.
