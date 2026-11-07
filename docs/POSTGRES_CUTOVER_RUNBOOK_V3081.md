# PowerPath — PostgreSQL staged cutover runbook (v30.8.1)

**Status:** staging import implemented, but NO PostgreSQL instance, cloud service, credentials, live tenant permissions, production cutover or deployed agent worker has been authorized or tested here. v30.8.1 is NOT enterprise-ready.

## Safety gates and operator decisions

1. Confirm authorized target: dedicated dev/staging PostgreSQL with PostGIS. **Never provide production credentials to the staging importer.** Operator approval is required before provisioning paid services, using credentials, exposing networks, deploying application/worker code, or changing production data.
2. Before any cutover, stop all SQLite writers and save a separate verified SQLite backup (`python -m scripts.db_manage backup ...`; validate its `.json` checksum). The stage import makes a consistent online SQLite snapshot but **does not itself freeze future SQLite writes**.
3. Inspect `python -m infrastructure.pg_stage --out /path/to/private/report`. Output is a structural DDL preview and hash-only data manifest; **do not execute the preview SQL as a replacement for the importer**.
4. On a machine with Docker and an approved image, optional **local-only** PostGIS service:

   ```bash
   export POWERPATH_PG_USER=powerpath_stage_admin
   export POWERPATH_PG_PASSWORD='<retrieve secret from your secret manager>'
   docker compose -f deploy/compose.postgis.staging.yml up -d
   python -m pip install 'psycopg[binary]>=3.1,<4'
   export POWERPATH_PG_STAGE_DSN='postgresql+psycopg://powerpath_stage_admin:<secret>@127.0.0.1:55432/powerpath_stage'
   python -m infrastructure.pg_stage --execute --confirm-stage
   ```

   **Do not check a DSN, password, or backup into version control.** Prefer DSN injection from an approved secret manager. The importer refuses an existing `powerpath_stage_v3081` schema; it never drops a previous staging schema or automatically retries a partially failed import. It uses a transaction and verifies every table's count and canonical data fingerprint plus financial runs before committing. PostgreSQL extension installation and role permissions must be provided by the database administrator.
5. Verify the returned `staging_loaded`, `tables_reconciled`, `rows_reconciled`, financial hash, and polygon count. Check `pp_import_audit_v1` and compare its manifest hash to locally generated stage manifest. Perform read-only GIS comparison on real polygon fixtures. Independently validate the restored database and source backups.
6. **Not ready for app cutover:** The application still contains SQLite direct SQL, boot-time DDL, `?` positional parameters, RTree-specific queries, and SQLite transaction semantics. A passing staging import does not convert those to PostgreSQL automatically. Build and test repository adapters before switching `POWERPATH_DATABASE_URL`. The active DB boundary will reject that variable today.
7. **Not ready for production tenant usage:** Imported legacy tables are not exposed or granted to application users. New assessment table has FORCE RLS, a conservative policy using tenant context, and no grants to PUBLIC. A separate tenant-scoped application role, verified authorization tests, explicit table policies, and a security review are needed. NEVER run the application as schema owner or database superuser.
8. **Not ready for autonomous cloud agents:** Current worker remains local-first with SQLite state. A PostgreSQL task-queue adapter, service identity, cost/permissions controls, safe retry/outbox semantics, supervised runtime and a real disaster-recovery rehearsal must be implemented and tested.

## Engineering acceptance criteria before promotion

- One clean all-suite regression test run, reproducible CI, and browser/API end-to-end tests on PG staging.
- Full legacy read/write feature parity or audited replacement; no silent fallback to SQLite when PG is configured.
- Every financial scenario's exact source/target inputs, outputs, covenant and cash-flow hashes match. Protected engine file audit remains unchanged.
- Verified PostGIS acreage and overlap result parity with the Python footprint engine, including holes, multipolygons, CRS and adverse geometries.
- A fresh Postgres migration and a staged restore drill pass; DB backup encryption and access controls reviewed.
- Organization access, RLS (including worker role), approvals, audit integrity, and fault-injection tests pass on a non-owner role.
- Live agency GIS connectors tested online, evidence provenance verified, and incomplete/unknown screening fails closed.
- Human authorization for production/service deployment and financial model sign-off. Never silently promote staging output to lender-verified.

## Rollback and recoverability

No automatic DB rollback or destructive schema recreation. Keep original SQLite read-only and retain backup with hash manifest. If import fails, Postgres transaction rolls back; any schema left by environment-specific behavior must be inspected manually. If later cutover fails, stop writers, preserve both databases and logs, reconcile writes, restore from an approved recovery point, then only reopen the validated backend. Do not assume switching back to SQLite is safe if PostgreSQL has received new writes.
