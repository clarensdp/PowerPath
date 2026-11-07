# Agent Operations v30.7: contract and boundaries

## Process model

- UI/REST schedules fixed tasks in `agent_ops_jobs` per project.
- Scheduler is not enabled until an operator explicitly enables it.
- CLI worker claims one queued job transactionally; for a live job it reserves a call budget slot before calling the provider. A provider response is analysis only.
- A completed job produces an immutable-by-convention output hash and a pending human-review record; the acknowledgment does not execute work.
- The event chain is useful as a local tampering diagnostic but **not** independent tamper-proof evidence (a privileged DB editor could rebuild the chain).

## Operational constraints

- The CSV watcher (`agents/watch.py`) is a separate opt-in process and only processes operator-provided files. The new worker does not itself poll government or utility websites.
- Worker timeout: 5-minute lease. If it expires, no automatic replay; the operator can retry once more if max attempts allow, and prior API slots remain charged against daily budget.
- Budget: the v30.7 worker and the legacy ten-role API runner reserve against the same local SQLite date-limited call ceiling. This is not a centralized multi-host spending limit.
- Source isolation: only up to 12 operator-imported queue changes; field names, change kinds, and dates. Original row data is withheld from the v30.7 role worker. No contract or source document is passed.
- Allowed outputs: review memo, issues, suggested diligence, proposed owners, unverified hypotheses. Forbidden automatic outcomes: enacted permits, project schedule modifications, financing approvals, lease signature, sending messages, code deployment, or any spending commitment.

## Repository-level debt

The original core server has feature tables initialized during import, a local SQLite connection helper, and a broad route module. `agent_ops_0001` is a new pattern to expand, not a declaration that this debt is repaid. Next engineering release should centralize persistence with tested migrations and clean API/service boundaries before any claim of national-scale enterprise readiness.
