# PowerPath PostgreSQL runtime adapter candidate

Date: October 30, 2026. Status: **incomplete integration; do not deploy or cut over**.

## Changes made

- Added an explicit PostgreSQL routing branch at the existing central database boundary. PostgreSQL failures never fall back to SQLite.
- Added psycopg 3 compatibility for qmark parameters, mapping/positional rows, ignore-on-conflict inserts, generated parcel/task identifiers, and literal parcel substring searches.
- Replaced PostgreSQL boot-time schema creation with checks for pre-provisioned tables. Schema changes remain an operator migration responsibility.
- Adapted explicit BEGIN IMMEDIATE transactions to PostgreSQL transactions plus a shared advisory lock for legacy writer serialization.
- Require hostname-verified TLS, named application authentication, a separate runtime schema, and a non-owner/non-bypass database role with RLS on runtime tables.
- Candidate remains disabled by default. POWERPATH_PG_RUNTIME_EXPERIMENTAL=1 is a development override, not approval or proof of readiness.
- Financial engines and staged source records were not edited. No live database writes were made in this continuation.

## Validation and limits

25 new local adapter contract tests passed. The 10 existing database-foundation tests also passed (35 combined). These tests verify translation, routing, configuration rejection and bootstrap behavior; they do not establish actual psycopg/PostgreSQL application parity. See TEST_REPORT_V30_8_1.json for the separately rerun regression gate and its explicit limitations.

Live read-only Supabase checks confirmed the private staging schema, 13 projects and 18 financial runs. There are zero Supabase Auth users, local application users, memberships and project-tenant assignments. No identities or tenant ownership were invented. No runtime role or runtime schema has been provisioned by this continuation.

The execution environment cannot resolve either the project's database host or API host. The connected SQL tool can query the database, but does not provide the application process with a persistent database connection, credentials, a verified user session, or a deployment runtime. Do not embed that tool in the application or treat its access as a service credential.

## Required to finish

1. A runtime with network access to Supabase and a database credential injected through its secret configuration. Do not paste secrets into chat or put them in the release archive.
2. Provision a separate runtime schema and least-privilege role, migrate all tables including a PostgreSQL replacement for geo29_bounds, and reconcile with the preserved snapshot. Do not use the closed staging schema as the application schema.
3. Complete managed identity and authoritative organization/project ownership. Implement and adversarially test tenant policies for direct and indirect project tables, global GIS data, identity lookups and workers. Existing local identity is still a preview.
4. Run the complete application on PostgreSQL, including startup, HTTP/browser CRUD, concurrent queue claims, integrity error handling, transaction rollback, cross-tenant denials and evidence downloads. Investigate/fix any failures before enabling the adapter.
5. Demonstrate schedule-to-financial-output/export parity and a real PostgreSQL backup/restore drill. No financial or lender certification is implied.
6. Review production hosting and cutover separately; leave original SQLite writers stopped only during the actual controlled cutover.

This archive is a recoverable engineering candidate, not a finished Supabase integration. Staging stays private and the existing SQLite application remains the supported backend until acceptance passes.

## Regression gate result

The 21-group process-isolated regression gate reported 256 passes and one failure in the historical base-case financial hash fixture. JavaScript checks passed and all 12 protected engine hashes were unchanged. The same base-case hash mismatch was independently reproduced using the untouched engine and fixture extracted from the original archive, so it predates this adapter in this environment. Four other original historical scenarios match their fixture hashes. The baseline failure remains unresolved; fixture expectations and financial engine outputs were not changed to conceal it. This is an additional cutover gate. Evidence: baseline_hash_reproduction.json and regression.log.


## Continuation after cutover authorization

User explicitly authorized finishing integration and running cutover. No further authorization has been requested. Cutover has **not** executed. No live schema, policy, identity, writer or database record was changed by this continuation.

Added a managed Supabase identity adapter to the existing sign-in, request authorization and logout paths. Server-side identity verification uses the configured Supabase /auth/v1/user service, rejects anonymous/unconfirmed identities, and ignores user-editable metadata. Stored memberships determine tenant/role access. Unprovisioned accounts are denied. A local hashed-token revocation check blocks logged-out tokens independently of upstream JWT expiry. Global mutations remain operator-only. This is locally tested implementation, not live managed-identity acceptance.

The PostgreSQL connection now propagates verified actor and tenant context. Added a policy compiler covering the inventoried relations, with explicit project/indirect-child scope, role-based write checks, read-only global GIS data, protected memberships and immutable local revocations. Added an additive runtime migration generator that creates an independent private schema and a NOLOGIN/non-bypass application role, preserves 45 source tables using typed multiset comparisons, rebuilds parcel bounds from valid staged geometries, and emits the policies. New project ownership columns avoid relying on a hidden mapping to determine access. Bootstrap source imports are disabled for PostgreSQL. runtime_migration_preview.sql is a preview, **not applied or live-verified**; it requires independent SQL and adversarial database validation. No role credential is created in that preview.

New local test group: 40 passed (adapter, managed identity/authorization/revocation, policy coverage). Separate 21-group process-isolated regression gate: 256 passed, one historical base-case hash failure. Protected engines unchanged, JavaScript checks passed. Combined execution of older authentication suites was also attempted and exposed their previously documented shared test-state collision; the process-isolated gate reran those groups successfully.

Historical hash investigation: the mismatch remains reproducible from the untouched original archive. Disabling Node JIT/optimization did not change it. Root cause is not established; no fixture or engine output was altered. The regression remains blocking.

Executed the read-only cutover preflight. CUTOVER_PREFLIGHT_RESULT.json records missing application credentials/configuration, unreachable Supabase host, failing regression, missing live application/tenant/browser acceptance and missing restore-drill evidence. It left writers untouched. A connection supplied through runtime secrets and an application host with Supabase network access are prerequisites to continuing those live checks. The source snapshot/manifest are included under migration_source for reproducibility; no secrets are included.

There is no production claim: policy SQL, managed login and logout, worker concurrency, financial workflow/browser parity and PostgreSQL restore still require live acceptance. The preflight only reports prerequisites; it is not a completed cutover executor or an acceptance attestation.
