"""v30.7 isolated, versioned SQLite migration for *agent operations only*.

Not a claim that the legacy PowerPath schema is fully migrated. The remaining
modules still own their preexisting SQLite DDL and must be consolidated before PG.
"""

from __future__ import annotations
import hashlib
from datetime import datetime, timezone

MIGRATION_ID = "agent_ops_0001"
MIGRATION_SQL = """
CREATE TABLE IF NOT EXISTS agent_ops_config (
 project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
 enabled INTEGER NOT NULL DEFAULT 0 CHECK(enabled IN (0,1)),
 mode TEXT NOT NULL DEFAULT 'rules' CHECK(mode IN ('rules','live')),
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_ops_jobs (
 id TEXT PRIMARY KEY,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 role TEXT NOT NULL, task_type TEXT NOT NULL, schedule_key TEXT NOT NULL,
 mode TEXT NOT NULL CHECK(mode IN ('rules','live')),
 status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','complete','failed','abandoned')),
 attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 2,
 created_at TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT '', completed_at TEXT NOT NULL DEFAULT '',
 worker_id TEXT NOT NULL DEFAULT '', lease_until TEXT NOT NULL DEFAULT '',
 source_hash TEXT NOT NULL DEFAULT '', result_json TEXT NOT NULL DEFAULT '{}', error_code TEXT NOT NULL DEFAULT '',
 UNIQUE(project_id,schedule_key)
);
CREATE INDEX IF NOT EXISTS agent_ops_jobs_queue ON agent_ops_jobs(status,created_at);
CREATE INDEX IF NOT EXISTS agent_ops_jobs_project ON agent_ops_jobs(project_id,created_at DESC);
CREATE TABLE IF NOT EXISTS agent_ops_calls (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 job_id TEXT NOT NULL REFERENCES agent_ops_jobs(id) ON DELETE CASCADE,
 attempt INTEGER NOT NULL CHECK(attempt>=1),
 state TEXT NOT NULL CHECK(state IN ('reserved','sent','ok','failed')),
 usage_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL, UNIQUE(job_id,attempt)
);
CREATE TABLE IF NOT EXISTS agent_ops_reviews (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 job_id TEXT NOT NULL REFERENCES agent_ops_jobs(id) ON DELETE CASCADE,
 artifact_hash TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
   CHECK(status IN ('pending','acknowledged','rejected')),
 reviewed_by TEXT NOT NULL DEFAULT '', reason TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL, decided_at TEXT NOT NULL DEFAULT '', UNIQUE(job_id)
);
CREATE INDEX IF NOT EXISTS agent_ops_reviews_pending ON agent_ops_reviews(project_id,status,created_at);
CREATE TABLE IF NOT EXISTS agent_ops_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 object_id TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS agent_ops_events_project ON agent_ops_events(project_id,id);
"""


def install_migrations(db):
    """Idempotent release-scoped migration with drift detection."""
    with db() as con:
        con.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
        digest = hashlib.sha256(MIGRATION_SQL.encode()).hexdigest()
        prior = con.execute("SELECT checksum FROM schema_migrations WHERE version=?", (MIGRATION_ID,)).fetchone()
        if prior:
            if prior["checksum"] != digest:
                raise RuntimeError("Agent migration checksum changed; refuse schema drift")
            return False
        con.executescript(MIGRATION_SQL)
        con.execute(
            "INSERT INTO schema_migrations(version,checksum,applied_at) VALUES(?,?,?)",
            (MIGRATION_ID, digest, datetime.now(timezone.utc).isoformat()),
        )
        return True
