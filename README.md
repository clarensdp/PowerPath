# PowerPath

**Power infrastructure decision and underwriting workspace — engineering alpha.**

PowerPath helps evaluate how a data center site can obtain power, compare energization timing and alternatives, and understand financial consequences under stated assumptions. It combines parcel feasibility, permitting, phased power paths, evidence tracking and scenario underwriting. It does **not** verify utility commitments, grant permits or certify lender-quality cash flows.

## Local setup

Prerequisites: Python **3.12.10**, Node.js **22.23.4**, npm, and an OS with SQLite. All local services bind to `127.0.0.1`.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-feasibility.txt
./run_local.sh
```

Visit [workspace](http://127.0.0.1:8768/) or [detailed workspace](http://127.0.0.1:8768/advanced). The first launch copies a **synthetic** SQLite fixture into `data/`; subsequent launches never overwrite local data. No cloud connection, Supabase secrets or live database is needed. Do not expose the local service publicly.

## Checks

```bash
npm run check
python -m pytest -q tests/test_cofounder_handoff.py tests/test_managed_identity.py tests/test_runtime_policies.py
python -m scripts.run_v3081_gate --extended
```

The PostgreSQL runtime adapter is **experimental, disabled by default and not accepted for deployment**. Do not set `POWERPATH_DATABASE_URL` in the local demo or assume v30.9 is a new application release.

## Start here

- [Push to private GitHub](GITHUB_PUSH_GUIDE.md)
- [Verification record and remaining checks](VERIFICATION_2026-11-07.md)
- [Cofounder handoff, provenance and blockers](docs/COFOUNDER_HANDOFF.md)
- [PostgreSQL candidate limitations](POSTGRES_RUNTIME_CANDIDATE_STATUS.md)
- [Staging and cutover runbook](docs/POSTGRES_CUTOVER_RUNBOOK_V3081.md)
- [History](CHANGELOG.md)
- [Earlier v30.8.1 details](RELEASE_V30_8_1_POSTGRES_STAGING.md)

**Data classification:** Local databases, uploaded evidence, migration snapshots and credentials are intentionally excluded from Git. A single curated synthetic fixture is versioned for developer onboarding. Review third-party GIS rights before any public distribution.
