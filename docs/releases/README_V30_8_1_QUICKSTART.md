# PowerPath v30.8.1 quick start

PowerPath v30.8.1 retains the v30.7.1 interface and v30.8.0 SQLite migration foundation while adding a PostgreSQL/PostGIS staging importer.

## Current application (SQLite; local-only)

```bash
python3 -m pip install -r requirements.txt
./run_local.sh
```

## PostgreSQL staging readiness (no network, no credentials required)

```bash
python3 -m infrastructure.pg_stage --out ./local-pg-preview
python3 -m scripts.run_v3081_gate
```

`local-pg-preview` is ignored from ZIP packaging when generated within the root; keep it local. For a real staged import, use `docs/POSTGRES_CUTOVER_RUNBOOK_V3081.md`. The active application refuses `POWERPATH_DATABASE_URL` until a proper read/write PostgreSQL adapter passes parity checks. This is intentional; **do not interpret staged data as a production cutover**.
