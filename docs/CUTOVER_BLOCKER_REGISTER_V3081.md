# PowerPath infrastructure transition blocker register — v30.8.1

| Severity | Gate | Current status | Decision owner |
| --- | --- | --- | --- |
| P0 | Real PostgreSQL + PostGIS import and table/financial parity | Importer implemented, not run against PG; no PG server/driver here | CTO / operator |
| P0 | Database backend abstraction | SQLite-only application adapter remains; no PG write cutover | CTO |
| P0 | All feature DDL migrations under Alembic | Legacy modules still bootstrap schemas; staged schema from reflection only | CTO |
| P0 | Tenant-scoped auth/RLS end-to-end | New footprint assessment stage has FORCE RLS and PUBLIC revocation; legacy data blocked, not authorized for prod | Risk |
| P0 | Financial deterministic parity with PG live | 12 protected code hashes pass; cross-DB financial comparisons untested | CFO / Risk |
| P0 | Backup, restore, cutover rehearsal | SQLite backups tested; PG recovery rehearsal not run | CTO / Risk |
| P1 | Live geospatial service validation | No online FEMA/USFWS browser acceptance in this environment | CDO |
| P1 | Agent cloud runtime | Local agent system only; no managed worker or PG queue adapter | CTO / COO |
| P1 | Full clean CI gate | Process-isolated subset can run; legacy combined-suite state pollution persists | CTO |
| P1 | Verified parcel/legal buildable analysis | Polygon intersection screening only; local zoning/land rights remain unknown | Product / Risk |

**Permission needed later:** choice of approved staging/production hosting account and authorization to provision a paid service or deploy/connect credentials. No external action was taken.
