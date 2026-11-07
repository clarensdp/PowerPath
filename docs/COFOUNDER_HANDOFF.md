# PowerPath — cofounder engineering handoff (2026-11-07)

**Status:** Source archive prepared for a **private** GitHub repository. This is a reproducible *local engineering alpha*, not production, a bank-verified model, or a completed PostgreSQL cutover.

## Provenance and what changed

- Baseline source: `PowerPath_Postgres_Adapter_Candidate_2026_10_30.zip` (application 30.8.1 candidate).
- Applied November 1 adapter fix: null-safe cursor description.
- Applied November 3 detailed-workspace login patch: same-origin API wrapper, sign-in screen and protected session flow.
- The `v30.9` references in `infrastructure/` are **runtime database schema generators**, not a separate `v30.9` app build.
- Added a repo entrypoint, synthetic-fixture local bootstrap, ignored runtime state, env template, GitHub CI workflow, patch smoke tests, and a source hash manifest.
- Removed private staging snapshots, mutable local evidence and QA database state from the GitHub-ready tree. These must stay in restricted operational storage, not GitHub.
- Kept historical release records and code-level engine files; core underwriting calculations were **not** modified.

## Five-minute first run

```bash
git clone <YOUR-PRIVATE-REPOSITORY-URL>
cd <your-repo>
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-feasibility.txt
./run_local.sh
```

Visit `http://127.0.0.1:8768/` for the streamlined workspace and `/advanced` for the detailed workspace. The local launcher creates the demo DB from an intentionally synthetic fixture when no local DB exists. Avoid exposing port 8768 to a network: local-only auth is deliberately not multi-tenant protection.

## Source and verification

- Backend: FastAPI + Python (`server/`); workspace: vanilla JS/TypeScript (`web/`); financial model bridge (`engine/`).
- Site feasibility / GIS / permitting: `feasibility/`, `data_sources/`, `permitting/` and `infrastructure/`.
- Bounded agent scheduling: `agents/` (opt-in, local-first).
- Source integrity and regression tooling: `scripts/run_v3081_gate.py`, `ENGINE_HASH_AUDIT_V30_3.json`, `SOURCE_MANIFEST_COFUNDER_2026-11-07.json`.

To validate:

```bash
npm run check
python -m pytest -q tests/test_cofounder_handoff.py tests/test_managed_identity.py tests/test_postgres_runtime_candidate.py tests/test_runtime_policies.py
python -m scripts.run_v3081_gate --extended
```

Node 22.23.4 and Python 3.12.10 are recommended based on November 4 review; actual CI must run before merge. `requirements-postgres-runtime.txt` is for an authorized **test** Postgres runtime only. Never point local tests at live Supabase.

## Known release gates and hard limitations

1. **P0:** Browser and API login/CRUD/evidence/export must be independently verified against a disposable PostgreSQL instance using managed identity, not just SQLite or mocked tests.
2. **P0:** Financial-output and supporting audit evidence still allow destructive paths under the November 4 policy review; implement protected append-only records and independently test RLS.
3. **P0:** Reconcile source commit, actual deployed database schema, migration, role policies, and service identity. GitHub source cannot certify the existing remote state.
4. **P1:** Pin dependencies and run fresh Mac/Linux installs, fuller browser accessibility tests, backed-up restoration, and controlled financial regression reruns under the reviewed Node version.
5. **P1:** Link utility milestones, executed lease/capex/DSRA terms, full-parcel GIS coverage and verifiable evidence before making investment-grade claims.

The source includes `runtime_migration_preview.sql` for provenance only. Never execute it on a real database without an approved migration review and independent backup.

## Suggested ownership

- Cofounder/engineering: clone, install, verify manifests, run tests and review authentication/data boundary; own branch-protected CI and staging.
- Product/founder: prioritize an end-to-end narrow site decision workflow and evidence-quality labels; approve claims and pilot scope.
- Independent security/model reviewer: RLS attack tests, evidence retention and financial reproducibility before external use.

## GitHub workflow

Create a **private** repository; commit this tree to `main`, protect it, enable required CI review and grant your cofounder access. Put new work on feature branches and use PRs. Store secrets in the platform's secret manager, never `.env` files in Git. A public repository needs a further license, third-party data-rights and history review.
