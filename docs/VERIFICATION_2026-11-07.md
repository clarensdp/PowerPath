# PowerPath source handoff: verification record (November 7, 2026)

**Scope:** Offline source and test checks performed on the handoff candidate. The product remains an engineering alpha. This is not a production deployment, lender validation, managed-identity acceptance, or security certification.

## Confirmed in the current execution environment

- Node `--check` on the six workspace JS entrypoints (`npm run check`): **passed** (Node 22.16.0 here; recommended Node is 22.23.4).
- `python -m pytest -q tests/test_cofounder_handoff.py tests/test_managed_identity.py tests/test_runtime_policies.py tests/test_postgres_runtime_candidate.py`: **44 passed** (Python 3.13.5 here; recommended Python is 3.12.10).
- `python -m pytest -q tests/test_v3081_pg_staging.py tests/test_v308_database_foundation.py`: **21 passed**.
- Historical protected engine contents were left unchanged by the handoff preparations; integrity audit identifiers remain in the repo. No new model accuracy certification was issued.
- Git staging excludes `data/powerpath.sqlite3`, mutable evidence, private migration/source snapshots, logs, `.env` files and interpreter caches. The only committed SQLite DB is a **synthetic** developer fixture at `tests/fixtures/powerpath_synthetic.sqlite3`.
- A regex-based, source-file credential scan found no private key blocks, AWS access keys, GitHub PAT patterns, Supabase secret key patterns or JWT-like tokens. This **does not replace** dedicated secret scanning or historical git-commit review.

## Not demonstrated / pending

- Full regression gate: a new `scripts.run_v3081_gate --extended` attempt was interrupted after 10 of 21 groups; those first 10 reported passing. The archived regression report predates these changes and has its own environment caveats. **Do not claim the full gate passed in this handoff.** Allow GitHub Actions to perform a complete run and review its results.
- Full PostgreSQL dependency installation (`psycopg`) and end-to-end application parity were not demonstrated in this environment because package downloads were unavailable; the live Supabase instance was not accessed or modified.
- Mac/Linux fresh install, browser sign-in/CRUD/replay/export, cross-tenant attacks, immutable evidence controls, and backup/restore acceptance remain outstanding.
- Dependency libraries in `requirements.txt` use version ranges instead of a complete lockfile. Reproducibility beyond the pinned Python/Node interpreter versions remains an improvement item.

**Release posture:** Appropriate for **private GitHub source sharing with a technical cofounder**, subject to a second reviewer checking any additional internal/proprietary datasets and running organization-level secret scanning before publishing. Not approved for production or public release.
