# PowerPath technical debt register — v30.8.0 baseline

| Priority | Debt | Current observation | Planned gate |
| --- | --- | --- | --- |
| P0 | Direct/boot-time DDL | Eleven original core tables extracted; many feature modules still create their own tables | Every table is created from reviewed Alembic revisions on an empty dev DB |
| P0 | SQLite-only data access | Connection centralized; SQLite syntax and direct SQL remain throughout application | PostgreSQL dev/staging load and functional parity |
| P0 | Production tenant isolation | Agent read/write routes and historical GIS endpoints are not all production-auth enabled | Tenant boundary tests and independent RLS enforcement |
| P0 | Financial deterministic parity | Protected code unchanged, financial regression tests passing | Identical inputs/outputs, hashes, covenants and cash-flow residuals after PG migration |
| P0 | Incomplete GIS evidence model | Footprint assessments still read-only without an immutable project-specific store | Versioned geometry/evidence and operator review controls |
| P1 | Cross-suite state pollution | Targeted process-isolated suites pass; full combined run not demonstrated | One clean, reproducible CI run |
| P1 | Recovery and credentials | Local SQLite verified backups only | Managed backup/restore drill and secrets/monitoring setup |
| P1 | Agent runtime | Local opt-in worker and task queue | Supervised cloud worker with structured task ownership and safe audit trail |
| P1 | External data validation | GIS official service integration unverified online | Staging connectivity tests and reviewed coverage masks |
| P2 | Unused/overlapping UI and modules | Existing versions still exposed within app | Deferred retirement only after migration and browser acceptance |

**Ownership proposal:** CTO maintains schema migration and CI gate; CDO owns datasets and evidence lineage; Risk controls permissions and sign-off; CFO signs off on the financial comparison report. These are proposed responsibilities, not autonomous agent-completed tasks.
