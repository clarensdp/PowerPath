# PowerPath

**Power infrastructure decision and underwriting workspace — engineering alpha (v30.8.3).**

> Edit TypeScript in `web/src/`, then run `npm run build:ts`. Never hand-edit `web/public/app.js` or `geo.js`; CI fails on drift.

PowerPath helps evaluate how a data center site can obtain power, compare energization timing and alternatives, and understand financial consequences under stated assumptions. It combines parcel feasibility, permitting, phased power paths, evidence tracking and scenario underwriting. It does **not** verify utility commitments, grant permits or certify lender-quality cash flows.

## Local setup

Prerequisites: Python **3.12.10**, Node.js **22.23.4**, npm, and an OS with SQLite. All local services bind to `127.0.0.1`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock   # exact pins verified Nov 7 (ranges remain in requirements*.txt)
./run_local.sh
```

Visit the [workspace](http://127.0.0.1:8768/): create a project (keep "illustrative working scenario" ticked), then follow the six steps. The [detailed workspace](http://127.0.0.1:8768/advanced) and other pages are expert tools. The first launch copies a **synthetic** SQLite fixture into `data/`; subsequent launches never overwrite local data. No cloud connection, Supabase secrets or live database is needed. Do not expose the local service publicly.

## Checks

```bash
npm run check && npm run check:ts-drift
python -m pytest -q tests/test_cofounder_handoff.py tests/test_audit_v3082.py tests/test_managed_identity.py tests/test_runtime_policies.py
python -m scripts.restore_drill                 # SQLite backup + evidence + restore drill
python -m scripts.run_v3081_gate --extended
# Optional, disposable LOCAL PostgreSQL 16 + PostGIS only (never Supabase/production):
# PP_PG_HOST=127.0.0.1 PP_PG_PORT=55432 PP_PG_USER=... PGPASSWORD=... ./scripts/pg_acceptance.sh
```

The PostgreSQL runtime adapter is **experimental, disabled by default and not accepted for deployment**. Do not set `POWERPATH_DATABASE_URL` in the local demo or assume v30.9 is a new application release.

## Repository layout

- `web/` — frontend pages, styles and TypeScript/JavaScript.
- `server/` — backend API, database access and external data providers.
- `engine/`, `feasibility/`, `permitting/`, `agents/` — calculation and workflow logic.
- `data/` — local runtime database and uploaded evidence; `data_sources/` — reference datasets.
- `tests/`, `scripts/`, `infrastructure/`, `migrations/` — verification, operations and database tooling.
- `docs/` — setup guides and technical documentation; see the [documentation index](docs/README.md).
- `docs/releases/` — release history and older quickstarts.
- `docs/manifests/` — historical file fingerprints and protected-engine hash baselines.
- `docs/reports/` — audit and test results, including regenerated release-gate reports.
- `docs/archive/` — historical supporting artifacts.

## Start here

- [Real-world site energy integrations: setup, sources, API, Virginia example and limitations](docs/SITE_ENERGY_INTEGRATION.md)
- **[v30.8.3 release: single flow, economics, append-only, PostgreSQL acceptance](docs/releases/RELEASE_V30_8_3.md)**
- **[Nov 7 technical + UX audit: findings, fixes and open items](docs/AUDIT_2026-11-07.md)**
- [Push to private GitHub](docs/GITHUB_PUSH_GUIDE.md)
- [Verification record and remaining checks](docs/VERIFICATION_2026-11-07.md)
- [Cofounder handoff, provenance and blockers](docs/COFOUNDER_HANDOFF.md)
- [PostgreSQL candidate limitations](docs/POSTGRES_RUNTIME_CANDIDATE_STATUS.md)
- [Staging and cutover runbook](docs/POSTGRES_CUTOVER_RUNBOOK_V3081.md)
- [History](docs/CHANGELOG.md)
- [Earlier v30.8.1 details](docs/releases/RELEASE_V30_8_1_POSTGRES_STAGING.md)

**Data classification:** Local databases, uploaded evidence, migration snapshots and credentials are intentionally excluded from Git. A single curated synthetic fixture is versioned for developer onboarding. Review third-party GIS rights before any public distribution.
