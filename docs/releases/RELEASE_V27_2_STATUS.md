# PowerPath v27.2 — Institutional Transaction Workspace Alpha

## What changed
- Added `/transaction-workspace`, a dedicated browser review surface for Core Scientific financing.
- Authenticated sign-in uses existing v27 local bearer sessions in required-auth mode; token held in memory only; logout revokes it.
- Tenant-filtered project selection and project-scoped Layer 1 facts, Layer 2 scenarios and payment schedules, and filing reconciliations.
- All sourced terms are displayed with classification and locator; outstanding differences are presented without plugs.
- G4 and G5 are explicitly blocked. The workspace is read-only; it cannot override evidence classifications or trigger consequential finance changes.
- New restrictive CSP for the transaction workspace; no inline scripts or HTML interpolation of source data.
- Added `tests/v271/test_v272_workspace.py` (3 checks, pass).

## Verification
- v27.1 waterfall, Core Scientific, scheduling and required-auth test suites passed independently.
- Focused inherited audit passed 15/16 sections on the first run: Chromium not located by Playwright automatically.
- Browser desktop/tablet/mobile reran successfully with `POWERPATH_CHROMIUM=/usr/bin/chromium` (3/3).
- TypeScript compilation and engine baseline hashes passed; no financial-engine modifications in this release.
- WARNING: tests that mutate global process environment must run in separate Python invocations; combined unittest imports cause cross-suite state contamination.

## Not implemented and not claimed
- Production PostgreSQL with database-enforced tenant isolation, SSO/OIDC, MFA, external key management, envelope encryption, offsite backups and restore tests, security review and penetration testing.
- Transaction-specific executed contracts, indenture and lease reconciliation; project-level valuation remains illustrative only.
- Full schedule CPM and revised debt instrument documentation. $6.75M open proceeds variance remains visible.
- Default local launch mode has no authentication. Never expose this server publicly. To exercise the local auth preview, provision users and tenants via v27 admin tooling and set `POWERPATH_V27_AUTH_MODE=required` before launch.
- Risk gates G4/G5 remain BLOCKED; no lender certification or hosted-beta approval.

## Run
```
python -m pip install -r requirements.txt
./run_local.sh
```
Visit `http://127.0.0.1:8000/transaction-workspace` (or the port reported by run_local). In required-auth mode, sign in with a locally provisioned user, choose an authorized project, and ensure Core Scientific inputs have been registered via the documented model endpoint.
