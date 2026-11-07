# Local-only workspace data

PowerPath creates `powerpath.sqlite3` and `evidence/` here when launched. Both are **untracked**. Never commit customer data, financial runs, evidence documents, credentials, migration snapshots, or database backups.

The initial database is copied from the curated synthetic fixture in `tests/fixtures/powerpath_synthetic.sqlite3`. The fixture contains only the illustrative demo project and public/QA GIS reference rows. This is for local development, **not a production data seed or a lender-verified dataset**.
