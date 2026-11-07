# PowerPath v27.0 — institutional API foundation + first public-filed transaction

**Release classification: development alpha, LOCAL ONLY.** This release does NOT satisfy hosted-beta, G4 executed-contract reconciliation, G5 independent model review, real transaction valuation, or lender-certified standards.

## Implemented in this release

- Opt-in *required-mode* local identity: password-based user accounts, eight-hour bearer sessions, token-hash storage, logout/revocation, salted PBKDF2-SHA256 password hashes. No OAuth/SSO/MFA; no claim of production-grade authentication.
- Explicit tenant registry and project ownership map; required-mode middleware denies access to projects without a tenant mapping. Tenant-filtered project list; cross-tenant paths deny read/write, and tenant selection is authorized on creation.
- Roles `viewer`, `analyst`, `approver`, `admin`; analysts may write ordinary project resources, approvers may sign recorded decisions, and viewers are read-only. Existing intelligence `approve/reject` routes now enforce approver permissions in required mode.
- Named, version-locked review records for scenarios and delivery milestones; immutable version-specific one-decision constraint and SHA-256 hash-linked append-only-at-API-level audit entries. Local DB administrators can still alter records; hash chain is not a tamper-proof external ledger.
- Core Scientific Finance I LLC May 2026 $3.3B secured-note transaction term register: facts tagged by field, source URL, locator, unit, and `PUBLIC_PRIMARY_SOURCE_NOT_CONTRACT_VERIFIED`; eight unresolved documentary requirements; **G4 and G5 remain blocked** and valuation is explicitly disabled.
- No changes to legacy financial engines.

## How to inspect v27 identity locally

This feature is opt-in because the inherited UI does not yet handle bearer credentials.

```bash
cd PowerPath_v27_0_Institutional_Transaction_Alpha
python -m pip install -r requirements.txt
export POWERPATH_DATA_DIR="$PWD/data"
export POWERPATH_BOOTSTRAP_PASSWORD='replace-with-a-strong-random-password'
python -m server.v27_admin bootstrap --email admin@example.com --tenant local-fund --name 'Local Fund'
unset POWERPATH_BOOTSTRAP_PASSWORD
POWERPATH_V27_AUTH_MODE=required uvicorn server.app:app --host 127.0.0.1 --port 8000
```

To login via API use `POST /api/v27/auth/login` with email/password JSON. Use returned `Authorization: Bearer <token>` for requests, and `X-PowerPath-Tenant: local-fund` on `POST /api/projects`. For a pre-existing project, the local operator must explicitly run `python -m server.v27_admin assign-project --project <PROJECT_ID> --tenant local-fund`. No silent cross-tenant backfill occurs.

To populate source records, create a project in the API, then POST `/api/projects/<PROJECT_ID>/transactions/core-scientific-2026`. GET `/api/projects/<PROJECT_ID>/transactions` for source and gap register.

The normal `./run_local.sh` continues to launch legacy local-only mode, **without authentication**. Never expose either mode publicly.

## Verified and unverified scope

The Core Scientific filing reports the issuer, principal, coupon, issuance price, maturity, first interest date, reserve and refinancing intent. Company/SEC sources are publicly readable; this package does not attach the signed indenture or legal schedules. The evidence object is a reference and source locator, not an independently retained signed agreement.

### Primary sources

- Core Scientific SEC 8-K filed 6 May 2026: https://investors.corescientific.com/sec-filings/all-sec-filings/content/0001193125-26-208905/d47435d8k.htm
- Pricing release Exhibit 99.1 dated 22 Apr 2026: https://www.sec.gov/Archives/edgar/data/1839341/000119312526208905/d47435dex991.htm

## Remaining mandatory milestones

1. Migrate to a managed PostgreSQL service with row-level tenant enforcement and transactional migrations; create encrypted object storage and tenant-safe backups/restores.
2. Implement external identity provider (OIDC/SSO/MFA), session policies, service identities, CSRF-safe UI login, rate limiting, change monitoring, production audit sink and independent pen test.
3. Attach and reconcile executed Core Scientific indenture, amendments, covenants, debt service reserve and debt-service waterfall to the engine. Obtain construction contracts, commercial agreements and utility confirmations before project-level CFADS is represented as verified.
4. Correct known financial default negative-cash defect and reconcile delay semantics with approved policy before lender or transaction analysis; freeze versioned engine baseline with parity and mutation tests.
5. Real source ingestion and legal/licensing review; qualified human reviewer for G5; accessibility remediation; disaster recovery exercises and deployment playbook.

**Security warnings:** local SQLite and evidence files are not encrypted-at-rest by this application; local operators are privileged; no internet hosting; bearer tokens must not be put in URLs or logs; no seeded real user credentials. Audit chain alone is not immutable or externally anchored.
