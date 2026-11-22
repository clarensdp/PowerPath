# PowerPath v30.8.0 — Architecture Foundation / Controlled Migration Phase 1

**Scope:** Additive stabilization release from v30.7.1 Parcel Footprint Alpha. **Status:** local-first migration preparation, NOT PostgreSQL cutover or enterprise deployment.

## What was actually implemented

1. `server/database.py` is the centralized **SQLite connection factory**, used by `server/app.py` and the installed modules that receive its `db` callback. It preserves timeout, isolation level, row factory, foreign keys and busy timeout. If `POWERPATH_DATABASE_URL` is set, it fails rather than silently writing to SQLite. **Direct SQL in legacy modules is not refactored.**
2. `server/schema_core.py` now owns the **unchanged original core table DDL** and the pre-existing `delivery_milestones.float_months` compatibility change. This consolidates the first 11 core tables. **Legacy feature modules still independently initialize their own schemas at application import time; this is explicitly unresolved.**
3. `architecture/schema_contract_v30_8.json` defines the original core column/type/PK contract, independently generated from clean v30.7.1 DDL. `infrastructure/db_audit.py` implements read-only SQLite preflight, schema fingerprinting, owner inventory, `PRAGMA quick_check`, foreign key validation, consistent SQLite online backup, SHA-256 manifest, and a separate backup-verification command. The schema inspection tool doesn't import the app and doesn't silently create a missing database.
4. `alembic.ini`, `migrations/env.py` and revision `3080_baseline` introduce the Alembic migration history, **only for an existing compatible SQLite database**. The revision checks contract columns before marking the baseline, then adds `alembic_version` and `platform_migration_audit`. It refuses to stamp an empty or incompatible database and prohibits automatic downgrade. This revision does **not** recreate legacy tables on a fresh instance and does not provide PostgreSQL schema creation.
5. `scripts/db_manage.py` exposes inspection, verified backup, and verified backup recheck. `tests/test_v308_database_foundation.py` covers core compatibility, missing columns, foreign keys, backups, checksum tampering, idempotent Alembic upgrades, refusal on empty databases, and fail-closed PostgreSQL configuration. `scripts/run_v308_gate.py` defines process-isolated release groups and protected engine integrity checks. This reduces legacy test-state cross-contamination but doesn't constitute an ordinary one-process full-suite pass.
6. Application version and package metadata updated to 30.8.0; no financial calculations, permitting rule engines, parcel-intersection algorithms or agent permissions intentionally changed.

## Safe local migration workflow

**1. Extract application, install dependencies, stop any writer before schema migration, and create a verified backup.** Use a new/unique backup filename for each migration. If `POWERPATH_DATA_DIR` is configured in your application, use the same value in the terminal.

```bash
cd PowerPath_v30_8_0_Architecture_Foundation
python3 -m pip install -r requirements.txt
python3 -m scripts.db_manage inspect
python3 -m scripts.db_manage backup --output ./backups/pre-3080.sqlite3
python3 -m scripts.db_manage verify-backup --db ./backups/pre-3080.sqlite3
```

The included local SQLite database is a development/demo artifact, not a production source of truth. Backups can contain sensitive project information: store privately, encrypt appropriately and do **not** commit them to source control.

**2. In a development or staging copy of your data, apply the SQLite baseline, and inspect again.**

```bash
python3 -m alembic upgrade head
python3 -m alembic current
python3 -m scripts.db_manage inspect
```

**3. Run the release test groups, then launch the application locally.**

```bash
python3 -m scripts.run_v308_gate
./run_local.sh
# http://127.0.0.1:8768
```

To target a separate SQLite database, set `POWERPATH_DATA_DIR` to a directory containing `powerpath.sqlite3`, not `POWERPATH_DATABASE_URL`. The migration and application pick up the same directory. Don't expose the local-only application to public traffic.

**Recovery:** On failure, stop every application/worker connected to the database, preserve the failed database for diagnosis, and manually restore a separately verified pre-migration backup. Never run an unsafe automatic downgrade or overwrite a backup. Validate source and restored content before reopening writers.

## Verification in this build

- `scripts.db_manage inspect` on bundled development SQLite: 43 schema-managed/user-facing tables (SQLite internal sequence/shadow implementation excluded), **no foreign-key violations**, clean quick-check and compatible 11-table core contract. Note: the original bundled SQLite physically also includes internal RTree shadow tables.
- A consistent source backup was created and independently verified by SHA-256, core schema fingerprint, SQLite integrity and foreign-key check.
- Alembic upgraded a **copy** of the v30.7.1 development DB to `3080_baseline` and the post-migration schema preflight passed; source database was not intentionally migrated.
- 10 database architecture tests passed; 193 other tests in focused GIS/permitting/finance group passed (203 total focused); separate agent/legacy/API/security tests passed in their isolated runs (43 additional). Protected 12/12 financial engine hashes match the previous audit. JavaScript syntax check passes.
- **Not verified:** a clean one-process full-suite run, browser UI acceptance, managed PostgreSQL/PostGIS, cloud workers, tenancy/RLS, PostgreSQL migration and cutover, disaster recovery under production load.

## Remaining P0 / P1 blockers

- Migrate the remaining schema definitions in `server/geo29.py`, `server/institutional.py`, `server/intelligence.py`, `server/parcels28.py`, `server/transaction27.py`, `server/transaction271.py`, `server/feasibility_api.py`, and `server/agent_ops_store.py` into fully owned, reviewed migration revisions; avoid changing existing result contracts as part of that refactor.
- Formalize canonical project/parcel/assessment/permit/financial/evidence relationships and their migration mappings. The schema contract here documents the legacy shape; it is **not** a consolidated new enterprise domain schema.
- Implement managed PostgreSQL + PostGIS in a separate dev environment, copy SQLite records with ID preservation, reconcile row counts/foreign keys/GIS geometry and exact financial run outputs; only after passing the gate should the application switch write backends.
- Design tenant-scoped authorization, row-level security, object-storage encryption, immutable evidence snapshots, app/worker observability and tested operational backups. Existing locally bounded agents do not run independently in the cloud.
- Fix legacy test isolation across the whole repository, validate browser flows and real GIS remote connectors in staging, and keep lender-grade certification blocked pending external source and model verification.

**Release decision:** suitable for local development and migration planning, **not** production-ready, not a live PG installation, and not an unattended deployed agent platform.
