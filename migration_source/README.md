# Migration source snapshots are intentionally excluded

The October 30 internal review included a private SQLite staging snapshot and a derived manifest. These are *not* appropriate to push to GitHub. Maintain them in restricted, backed-up operational storage with their original hashes. The v30.9 schema-generation **source code** lives in `infrastructure/runtime_migration.py` and `infrastructure/runtime_policies.py`. `docs/archive/runtime_migration_preview.sql` is only historical/generated preview evidence; do not execute it as a deployment.

For actual migrations, generate a reviewed snapshot from an authorized environment; use the procedures in `docs/POSTGRES_CUTOVER_RUNBOOK_V3081.md`. Nothing in this repository automatically migrates production data.
