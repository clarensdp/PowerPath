# PowerPath v30.8.1 — PostgreSQL/PostGIS Staging Transition

**2026-10-29 — Additive infrastructure implementation. NOT the production PostgreSQL cutover.**

## What changed

- `infrastructure/pg_stage.py`: safe staging importer for the existing SQLite app database. It creates a consistent private SQLite snapshot, runs source integrity and FK checks, completes agent-operations schema on the snapshot only, reflects the actual 45-table relational schema (excluding SQLite RTree shadow/internal tables), maps all REAL values to binary64 PostgreSQL `FLOAT(53)`, and preserves row identifiers, relational constraints, indexes and serialized financial data. It refuses missing tables or an existing target staging schema; it creates a new schema and PostGIS extension only when explicitly executed. The importer compares **every table** by row count and canonical data hash and separately checks financial run fingerprints and PostGIS parcel geometry counts before committing. A dedicated import-audit row records the reconciled source manifest. PostgreSQL runtime driver and credentials are not bundled.
- PostGIS footprint stage models: `pp_parcel_geometry_v1` with WGS84 polygon geometry and GIST index, official/source provenance, overlay source and polygon tables, geometry-intersection views with coverage classification, append-only assessment/review event tables, and a FORCE-RLS policy for staged assessments. Public access to staging tables is revoked by default. **No legacy tables are tenant-safe for app use yet, and no application role/grants are supplied.**
- `deploy/compose.postgis.staging.yml`: optional local-only Docker PostGIS staging service template. **Not deployed here.**
- `docs/POSTGRES_CUTOVER_RUNBOOK_V3081.md`: startup, operator secrets, staging import, parity/security gates and recovery requirements.
- `docs/CUTOVER_BLOCKER_REGISTER_V3081.md`: next-gate register. `tests/test_v3081_pg_staging.py`: schema/compiler and fail-closed tests. `scripts/run_v3081_gate.py`: bounded, process-isolated quick and optional extended validation.
- Application and package version updated to `30.8.1`; financial, permitting, parcel analysis and agent execution algorithms intentionally unchanged.

## Test evidence and exact caveats

- **214 selected GIS/permitting/financial/architecture tests passed together**, including 11 new PostgreSQL staging preview/contract tests and 10 v30.8.0 schema/backup tests.
- **15 agent tests passed when run in three isolated processes** (9 + 3 + 3). Running all three together in one process causes seven failures/three errors due to legacy test global-state coupling. The quick process-isolated release gate passes **89 selected tests**, 12 protected engine file hashes and JS syntax check. The full combined suite was not validated.
- The preview on the bundled development database reconciled **45 staged relational table definitions and 321 rows** (one staging-only migration row). Source data are unchanged, and the manifest contains only hashes/counts, not raw records. This is not a run against PostgreSQL.
- **NOT verified or complete:** Postgres connection, PostgreSQL transaction rollback, actual PostGIS geometry conversion and intersection parity, end-to-end tenant authentication/RLS, full legacy API SQL portability, managed backup/restore, worker deployment, browser UI acceptance, remote GIS services or production cutover.

## Quick start

```bash
cd PowerPath_v30_8_1_Staging_Transition
python3 -m pip install -r requirements.txt
python3 -m infrastructure.pg_stage --out ./local-pg-preview
python3 -m scripts.run_v3081_gate
./run_local.sh
```

The application **still runs SQLite**. The preview only writes non-sensitive DDL and hash-only metadata; it does not connect to any database outside the local SQLite copy. For staging import, see `docs/POSTGRES_CUTOVER_RUNBOOK_V3081.md`. `requirements-postgres-staging.txt` adds an optional PostgreSQL driver to install **only on an authorized staging machine**.

## Approval boundary

The next meaningful step requires permission to connect a managed PostgreSQL/PostGIS staging provider, provision resources that may incur fees, supply securely held service credentials and test a real import. Supabase is an option if the user connects the integration. No external service was provisioned or used, no network permission granted, no paid service action taken, and no production data changed in this release.

**Ship status: local staging engineering alpha only. Not enterprise-ready.**
