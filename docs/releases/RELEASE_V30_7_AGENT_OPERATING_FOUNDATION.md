# PowerPath v30.7.0 — Agent Operating Foundation (Local Alpha)

**Date:** 2026-10-29. **Based on:** v30.6.0 National GIS Connectors.

**Status: IMPLEMENTED LOCAL PROTOTYPE, NOT DEPLOYED, NOT AN ALWAYS-ON CLOUD SERVICE.**
No real Responses API calls were made in the release environment. Model interactions were mocked in tests. Nothing in the release executes external actions, changes model assumptions, files permits, contacts utilities, or deploys software.

## What changed

1. `server/agent_ops_store.py`: first **versioned, checksum-guarded SQLite migration** (agent operations scope only). Adds per-project configuration, durable jobs, per-attempt API-call slots, reviews and chained local events. Application startup applies this idempotently. Legacy database initialization is **not** yet migrated.
2. `agents/operations.py`: ten allowlisted role/task types, UTC daily idempotent scheduler, atomic multi-worker job claims, bounded 5-minute leases, interruption recovery without automatic replay, explicit retry (max twice), common daily API-call cap, source metadata minimization, and report/content hashes. All results require human review; no execution tools are exposed.
3. `agents/ops_worker.py`: opt-in CLI worker with `--once` and `--watch`. Runs in the **foreground** while the host process remains alive. It does not fetch remote sources. It reads previously operator-imported public queue metadata from Intelligence.
4. `server/agent_ops_api.py`: project-scoped operations overview, config, job queue, job detail, retry, reviews, decision and event-chain verification APIs. Required-auth middleware protects project access; live-scheduling modifications require approver role in required-auth mode. Review decisions always require a named authenticated approver, and are acknowledgments or rejections **only**, not execution authorization.
5. `web/public/agent-operations.{html,js,css}`: functional project-first dashboard with schedule opt-in, task queue, report readout, review list, and optional login/acknowledgment workflow. Linked from the main sidebar.
6. `agents/run_live.py`: existing ten-role review runner now shares the API-call ceiling with the new per-role worker, preventing two simultaneous local agent systems from exceeding their combined reservation budget.

## Ten roles and task assignments

| Role | Default task |
| --- | --- |
| Chief of Staff | executive_brief |
| CFO | finance_risks |
| CTO | engineering_health |
| CPO | product_priorities |
| Head of Product Design | ux_findings |
| CDO | source_freshness |
| COO | permitting_dependencies |
| CRO | customer_hypotheses |
| CMO | positioning_review |
| Chief Risk Officer | controls_review |

Tasks may output analyses and recommendations. They cannot automatically update permits, leases, scenarios, valuations or production systems. Offline rules outputs are **not independent AI**. Live runs are model API requests using fixed, allowlisted role instructions, not tool-using agents.

## Start locally (safe default, no model API calls)

```bash
unzip PowerPath_v30_7_0_Agent_Operating_Foundation.zip
cd PowerPath_v30_7_0_Agent_Operating_Foundation
python3 -m pip install -r requirements.txt
./run_local.sh
# http://127.0.0.1:8768/agent-operations
```

Select the seeded project or another project, choose **Offline rules (no API)**, check **Enable daily scheduling**, and save. Starting the web app **does not** start the worker.

Run in a second terminal:

```bash
python3 -m agents.ops_worker --project demo-campus-001 --once
# To keep checking every ten minutes while this terminal/host remains running:
python3 -m agents.ops_worker --project demo-campus-001 --watch --interval 600
```

It generates at most one scheduled task for each role per project per UTC day. Manually queued tasks are also picked up. Existing jobs and reports are persisted in `data/powerpath.sqlite3`; stop the worker or disable scheduling at any time. Shutdown does not automatically resolve incomplete provider calls; stale leases become `abandoned` and must be deliberately retried.

### Optional actual model calls

**Requires your own API account, model permissions, and a networked host.** Set these locally; never put a key into the app UI, Git or a ZIP:

```bash
export OPENAI_API_KEY='YOUR_PRIVATE_API_KEY'
export POWERPATH_AGENT_MODEL='A_MODEL_ENABLED_ON_YOUR_ACCOUNT'
export POWERPATH_LIVE_AGENTS=1
export POWERPATH_SHARE_PROJECT_METADATA=1
export POWERPATH_MAX_CALLS_PER_DAY=20
```

Then set the dashboard schedule mode to **Live model** and run the separate worker as above. The worker only transmits up to 12 public-queue source change descriptions, dates and field **names** (not raw row values, leases or project documents), along with a fixed role-specific task brief. Its output is an unverified memo. Provider failures consume the reserved API-call slot and remain recorded. Configure your own cost and security limits independently.

## Human approvals

Human review actions are **disabled in local unauthenticated mode**. Required-auth deployments need a provisioned v27 tenant, user account and `approver` role. The review API records `acknowledged` or `rejected` with actor, reason, timestamp and output SHA-256. It **never runs the underlying recommendation**. The operational API is still an alpha and must not be publicly deployed without an independent security review and managed identity, secrets and TLS controls.

## Tests and release gates

- **15 new isolated agent operations tests passed:** 9 local logic/API tests + 3 required-auth tests + 3 concurrency/retry tests.
- **180 existing permitting, GIS, feasibility, finance bridge, API, and parcel tests passed.**
- The original v26.8 four-test live-agent workflow passed separately (fake provider; no paid calls).
- An additional broader combined selection ran **90 passed, 1 xfailed, 1 failed**: the failure is a pre-existing shared test-state/collection-order issue (`test_04_live_does_not_approve_actions` encountered an already-approved proposal generated by a different test); when the live-agent workflow is executed alone, it passes. **A clean full-suite pass is not claimed.**
- Node JavaScript syntax checks passed.
- **12/12 frozen engine files** match `ENGINE_HASH_AUDIT_V30_3.json`, unchanged.
- Fresh-process CLI smoke test passed: disabled worker did nothing; enabled rules worker completed ten role reviews; ten reviews remained pending; audit hash-chain valid; migration rerun was idempotent.
- No browser visual acceptance or real model provider integration tests were performed. No unattended hosted operation was tested.

## Known gaps before any enterprise pilot

**P0:** Legacy SQLite schema still created/modified inside multiple application modules; only the new agent domain has a versioned migration. Consolidate versioned migrations and a persistence/data-access boundary before PostgreSQL/PostGIS migration.

**P0:** Local authentication is a preview, not production identity management or tenant-grade database isolation. Worker is a trusted local process and not cloud tenant-isolated. Production requires scoped service accounts, host secrets, deployment security audit, role enforcement and durable managed database.

**P0:** No cloud worker, supervised deployment, remote licensed data ingestion, monitoring/alerting or cost enforcement across multiple hosts. Local SQLite budget controls do not provide distributed quotas.

**P0:** Model responses are not independently verified, and the known financial/permit tranches integration limits still apply. Agent review does not change lender readiness or G4/G5 release gates.

**P1:** Limited per-role content, no sophisticated cross-agent task dependency graph, no event-driven task feed from real utility and permitting data providers. Approval is acknowledgment only; any proposed real-world action must go through a separate human-controlled workflow.

**P1:** Fix complete integrated test collection and add browser-driven and full cloud-runtime acceptance tests before customer use.

## Suggested next release

**v30.8:** finish canonical schema migration and data-access refactor, migrate to managed PostgreSQL/PostGIS (on staging first), add durable cloud worker + secrets management + health metrics, and integrate authorized source-monitoring events. Do **not** start by adding more agent tools or automatic external actions.
