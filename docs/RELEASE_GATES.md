# PowerPath v26 release gates

| Gate | Status | Evidence |
|---|---|---|
| Web server + local project database | PASS | `server/app.py`, API acceptance tests |
| Project-centric institutional browser UI | PASS | Browser screenshots, desktop/tablet/mobile smoke tests |
| Preserve v25.8.5 and v25.9 calculations | PASS | SHA-256 baseline comparison and inherited regression suites |
| Persist exact scenario versions and monthly results | PASS | API create/edit/run/reopen tests |
| Evidence metadata, immutable local upload and checksums | PASS locally | Upload and cross-project authorization tests |
| Project data permissions | **NOT FOR SHARED USE** | Project scoping exists; user identity and RBAC do not |
| Managed PostgreSQL and secure object storage | NOT STARTED | Local SQLite and file paths only |
| Production authentication and tenant isolation | BLOCKED | Required before hosting any private data |
| Transaction contractual reconciliation (G4) | BLOCKED | 0 contract-verified transactions |
| Human external model assurance (G5) | NOT STARTED | No signoff; needs reviewer |

**Do not deploy to the public internet.** A local server with working routes is not a production-ready multi-user SaaS.

**Next work:** implement authentication and tenancy, Postgres migrations, secured evidence uploads, service observability and backup policies; independently expand financing contract tests; import source-tagged executed terms when authorized. Lender-grade claims must remain suppressed until G4/G5 gates.
