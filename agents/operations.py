"""PowerPath v30.7 bounded, local-first agent task orchestrator.

No unrestricted tools, code changes, emails, permit filings or model edits. Scheduler
runs only in an operator-started worker. Live requests require explicit API consent.
"""

from __future__ import annotations
import hashlib, json, os, secrets, sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from agents.council import ROLES, DUTIES
from agents import run_live

TASKS = {
    "Chief of Staff": "executive_brief",
    "CFO": "finance_risks",
    "CTO": "engineering_health",
    "CPO": "product_priorities",
    "Head of Product Design": "ux_findings",
    "CDO": "source_freshness",
    "COO": "permitting_dependencies",
    "CRO": "customer_hypotheses",
    "CMO": "positioning_review",
    "Chief Risk Officer": "controls_review",
}
assert set(TASKS) == set(ROLES)
ROLE_DESCRIPTIONS = {role: DUTIES[role] for role in ROLES}


def utc():
    return datetime.now(timezone.utc).isoformat()


def stamp():
    return secrets.token_hex(12)


def dumps(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(dumps(value).encode("utf-8")).hexdigest()


def event(con, pid, oid, kind, data):
    """Append-only chained local diagnostic log. Not independently secured or notarized."""
    prev = con.execute(
        "SELECT event_hash FROM agent_ops_events WHERE project_id=? ORDER BY id DESC LIMIT 1", (pid,)
    ).fetchone()
    before = prev["event_hash"] if prev else "GENESIS"
    ts = utc()
    body = dumps(data)
    h = hashlib.sha256(dumps([pid, oid, kind, body, ts, before]).encode()).hexdigest()
    con.execute(
        "INSERT INTO agent_ops_events(project_id,object_id,event_type,payload_json,created_at,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)",
        (pid, oid, kind, body, ts, before, h),
    )


def verify_events(con, pid):
    prev = "GENESIS"
    num = 0
    for r in con.execute("SELECT * FROM agent_ops_events WHERE project_id=? ORDER BY id", (pid,)):
        expected = hashlib.sha256(
            dumps([pid, r["object_id"], r["event_type"], r["payload_json"], r["created_at"], prev]).encode()
        ).hexdigest()
        if r["previous_hash"] != prev or r["event_hash"] != expected:
            return {"valid": False, "checked": num, "invalid_id": r["id"]}
        prev = r["event_hash"]
        num += 1
    return {"valid": True, "checked": num, "head": prev}


def config(con, pid):
    r = con.execute("SELECT enabled,mode,updated_at FROM agent_ops_config WHERE project_id=?", (pid,)).fetchone()
    return dict(r) if r else {"enabled": 0, "mode": "rules", "updated_at": None}


def configure(db, pid, enabled, mode):
    if mode not in ("rules", "live"):
        raise ValueError("Invalid mode")
    from server.app import project_exists

    with db() as con:
        project_exists(con, pid)
        con.execute("BEGIN IMMEDIATE")
        now = utc()
        con.execute(
            "INSERT INTO agent_ops_config(project_id,enabled,mode,updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(project_id) DO UPDATE SET enabled=excluded.enabled,mode=excluded.mode,updated_at=excluded.updated_at",
            (pid, int(enabled), mode, now),
        )
        event(con, pid, pid, "agent_ops.schedule.configured", {"enabled": bool(enabled), "mode": mode})
        con.execute("COMMIT")
        return config(con, pid)


def enqueue(db, pid, role, mode=None, schedule_key=None):
    if role not in TASKS:
        raise ValueError("Role not allowlisted")
    from server.app import project_exists

    with db() as con:
        project_exists(con, pid)
        cfg = config(con, pid)
        requested_mode = mode or cfg["mode"]
        if requested_mode not in ("rules", "live"):
            raise ValueError("Mode must be rules or live")
        key = schedule_key or "manual:" + stamp()
        if len(key) > 90:
            raise ValueError("Schedule key too long")
        con.execute("BEGIN IMMEDIATE")
        jid = stamp()
        created = utc()
        cur = con.execute(
            "INSERT OR IGNORE INTO agent_ops_jobs(id,project_id,role,task_type,schedule_key,mode,status,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (jid, pid, role, TASKS[role], key, requested_mode, "queued", created),
        )
        if cur.rowcount:
            event(
                con,
                pid,
                jid,
                "agent_ops.job.queued",
                {"role": role, "task_type": TASKS[role], "mode": requested_mode, "schedule_key": key},
            )
        else:
            jid = con.execute(
                "SELECT id FROM agent_ops_jobs WHERE project_id=? AND schedule_key=?", (pid, key)
            ).fetchone()["id"]
        con.execute("COMMIT")
        return dict(con.execute("SELECT * FROM agent_ops_jobs WHERE id=?", (jid,)).fetchone())


def schedule_daily(db, pid, day=None):
    """Ten idempotent job records per enabled project per UTC day; no LLM call here."""
    from server.app import project_exists

    with db() as con:
        project_exists(con, pid)
        cfg = config(con, pid)
    if not cfg["enabled"]:
        return {"scheduled": 0, "reason": "DISABLED"}
    day = day or datetime.now(timezone.utc).date().isoformat()
    count = 0
    for role in ROLES:
        enqueue(db, pid, role, cfg["mode"], f"daily:{day}:{TASKS[role]}")
        count += 1
    return {"scheduled_or_existing": count, "date": day, "mode": cfg["mode"]}


def _source_meta(con, pid):
    """Only public-queue field NAMES and change counts are shared; never row values."""
    rows = con.execute(
        "SELECT source_key,change_type,delta_json,created_at FROM intel_changes WHERE project_id=? ORDER BY created_at DESC LIMIT 12",
        (pid,),
    ).fetchall()
    data = []
    for row in rows:
        try:
            fields = sorted(str(k)[:80] for k in json.loads(row["delta_json"]))[:20]
        except (ValueError, TypeError):
            fields = []
        data.append(
            {
                "source": row["source_key"],
                "change_type": row["change_type"],
                "changed_columns": fields,
                "observed_at": row["created_at"],
            }
        )
    return {
        "source_changes": data,
        "count": len(rows),
        "verified_utility_service": False,
        "executed_contracts_supplied": False,
        "data_basis": "operator-imported public queue row-change metadata; raw values withheld",
    }


def recover_interrupted(db, pid=None):
    """Stale jobs become abandoned, not automatically replayed (a provider call may have occurred)."""
    cutoff = utc()
    recovered = []
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        query = "SELECT id,project_id FROM agent_ops_jobs WHERE status='running' AND lease_until<?"
        args = [cutoff]
        if pid is not None:
            query += " AND project_id=?"
            args.append(pid)
        for row in con.execute(query, tuple(args)).fetchall():
            con.execute(
                "UPDATE agent_ops_jobs SET status='abandoned',completed_at=?,error_code='WORKER_INTERRUPTED' WHERE id=?",
                (utc(), row["id"]),
            )
            event(
                con,
                row["project_id"],
                row["id"],
                "agent_ops.job.abandoned",
                {"reason": "lease expired; no automatic replay"},
            )
            recovered.append(row["id"])
        con.execute("COMMIT")
    return recovered


def _daily_used(con):
    today = datetime.now(timezone.utc).date().isoformat()
    old = con.execute("SELECT COUNT(*) FROM agent_call_log WHERE created_at>=?", (today,)).fetchone()[0]
    new = con.execute("SELECT COUNT(*) FROM agent_ops_calls WHERE created_at>=?", (today,)).fetchone()[0]
    return old + new


def claim(db, pid, worker_id):
    """Atomic single-worker claim and LIVE budget reservation; no provider request in transaction."""
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT * FROM agent_ops_jobs WHERE project_id=? AND status='queued' ORDER BY created_at,id LIMIT 1", (pid,)
        ).fetchone()
        if not row:
            return None
        if row["mode"] == "live":
            if not run_live.live_available():
                return {"status": "LIVE_DISABLED", "id": row["id"]}
            cap = int(os.getenv("POWERPATH_MAX_CALLS_PER_DAY", "20"))
            if cap < 1 or _daily_used(con) + 1 > cap:
                return {"status": "BUDGET_BLOCKED", "id": row["id"]}
        now = utc()
        end = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
        con.execute(
            "UPDATE agent_ops_jobs SET status='running',attempts=attempts+1,started_at=?,completed_at='',worker_id=?,lease_until=?,error_code='' WHERE id=?",
            (now, worker_id, end, row["id"]),
        )
        if row["mode"] == "live":
            con.execute(
                "INSERT INTO agent_ops_calls(id,project_id,job_id,attempt,state,created_at) VALUES(?,?,?,?,?,?)",
                (stamp(), pid, row["id"], row["attempts"] + 1, "reserved", now),
            )
        event(con, pid, row["id"], "agent_ops.job.claimed", {"worker_id": worker_id, "mode": row["mode"]})
        con.execute("COMMIT")
        return dict(con.execute("SELECT * FROM agent_ops_jobs WHERE id=?", (row["id"],)).fetchone())


def process_one(db, pid, worker_id="local-worker", responder=None):
    work = claim(db, pid, worker_id)
    if not work:
        return {"status": "IDLE"}
    if work["status"] != "running":
        return work
    role = work["role"]
    mode = work["mode"]
    try:
        with db() as con:
            source = _source_meta(con, pid)
        source_hash = digest(source)
        mission = "Review operator-imported public queue metadata for PowerPath. " + DUTIES[role]
        if mode == "live":
            with db() as con:
                con.execute(
                    "UPDATE agent_ops_calls SET state='sent' WHERE job_id=? AND attempt=?",
                    (work["id"], work["attempts"]),
                )
            reply = (responder or run_live.response)(role, mission, dumps(source), "")
            body, usage = reply if isinstance(reply, tuple) else (reply, {})
            if not isinstance(body, str) or not body.strip():
                raise ValueError("No model response")
            flags = run_live.policy_flags(body)
        else:
            body = (
                f"OFFLINE_RULES (not AI): {DUTIES[role]} "
                f'Observed {source["count"]} operator-imported source changes. '
                "Verify evidence vintages and source identity. Do not update underwriting, permits or approvals automatically."
            )
            usage = {}
            flags = []
        body = body[:6000]
        result = {
            "role": role,
            "task_type": work["task_type"],
            "mode": mode,
            "memo": body,
            "source_provenance": source,
            "policy_flags": flags,
            "no_actions_performed": True,
            "underwriting_certified": False,
            "utility_capacity_confirmed": False,
            "usage": usage,
        }
        artifact_hash = digest(result)
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            current = con.execute("SELECT status,worker_id FROM agent_ops_jobs WHERE id=?", (work["id"],)).fetchone()
            if current["status"] != "running" or current["worker_id"] != worker_id:
                raise RuntimeError("Job lease owner changed; refusing to finalize")
            con.execute(
                "UPDATE agent_ops_jobs SET status='complete',source_hash=?,result_json=?,completed_at=?,lease_until='' WHERE id=?",
                (source_hash, dumps(result), utc(), work["id"]),
            )
            if mode == "live":
                con.execute(
                    "UPDATE agent_ops_calls SET state=?,usage_json=? WHERE job_id=? AND attempt=?",
                    ("ok", dumps(usage), work["id"], work["attempts"]),
                )
            review_id = stamp()
            con.execute(
                "INSERT INTO agent_ops_reviews(id,project_id,job_id,artifact_hash,created_at) VALUES(?,?,?,?,?)",
                (review_id, pid, work["id"], artifact_hash, utc()),
            )
            event(
                con,
                pid,
                work["id"],
                "agent_ops.job.completed",
                {
                    "result_sha256": artifact_hash,
                    "source_sha256": source_hash,
                    "policy_flags": flags,
                    "review_id": review_id,
                    "no_actions_performed": True,
                },
            )
            con.execute("COMMIT")
        return {
            "status": "complete",
            "job_id": work["id"],
            "role": role,
            "mode": mode,
            "review_id": review_id,
            "policy_flags": flags,
        }
    except Exception as exc:
        # Do not persist arbitrary exception text: errors might contain provider secrets.
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                "UPDATE agent_ops_jobs SET status='failed',completed_at=?,lease_until='',error_code=? WHERE id=? AND status='running'",
                (utc(), type(exc).__name__[:60], work["id"]),
            )
            if mode == "live":
                con.execute(
                    "UPDATE agent_ops_calls SET state='failed' WHERE job_id=? AND attempt=?",
                    (work["id"], work["attempts"]),
                )
            event(con, pid, work["id"], "agent_ops.job.failed", {"error_type": type(exc).__name__})
            con.execute("COMMIT")
        return {"status": "failed", "job_id": work["id"], "error_code": type(exc).__name__}


def retry(db, pid, jid):
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        item = con.execute("SELECT * FROM agent_ops_jobs WHERE id=? AND project_id=?", (jid, pid)).fetchone()
        if not item:
            raise KeyError("No job")
        if item["status"] not in ("failed", "abandoned"):
            raise ValueError("Only failed/abandoned jobs can be retried")
        if item["attempts"] >= item["max_attempts"]:
            raise ValueError("Maximum attempts reached")
        con.execute(
            "UPDATE agent_ops_jobs SET status='queued',error_code='',lease_until='',worker_id='' WHERE id=?", (jid,)
        )
        event(
            con,
            pid,
            jid,
            "agent_ops.job.retried",
            {"attempts_already_used": item["attempts"], "replay_may_incur_cost": True},
        )
        con.execute("COMMIT")
        return {"id": jid, "status": "queued"}


def decide_review(db, pid, review_id, decision, actor, reason):
    """Records human evaluation ONLY; never executes the recommended action."""
    if decision not in ("acknowledged", "rejected"):
        raise ValueError("Invalid decision")
    if not actor or len(reason.strip()) < 8:
        raise ValueError("Named approver and reason required")
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM agent_ops_reviews WHERE id=? AND project_id=?", (review_id, pid)).fetchone()
        if not row:
            raise KeyError("No review")
        if row["status"] != "pending":
            raise ValueError("Already reviewed")
        item = con.execute("SELECT result_json FROM agent_ops_jobs WHERE id=?", (row["job_id"],)).fetchone()
        if digest(json.loads(item["result_json"])) != row["artifact_hash"]:
            raise ValueError("Underlying output changed; refuse review")
        con.execute(
            "UPDATE agent_ops_reviews SET status=?,reviewed_by=?,reason=?,decided_at=? WHERE id=?",
            (decision, actor, reason.strip(), utc(), review_id),
        )
        event(
            con,
            pid,
            review_id,
            "agent_ops.review." + decision,
            {"actor": actor, "reason": reason[:300], "no_action_executed": True},
        )
        con.execute("COMMIT")
        return {"id": review_id, "status": decision, "action_executed": False}


def overview(db, pid):
    with db() as con:
        cfg = config(con, pid)
        jobs = Counter(
            {
                r["status"]: r["n"]
                for r in con.execute(
                    "SELECT status,COUNT(*) n FROM agent_ops_jobs WHERE project_id=? GROUP BY status", (pid,)
                )
            }
        )
        pending = con.execute(
            "SELECT COUNT(*) FROM agent_ops_reviews WHERE project_id=? AND status='pending'", (pid,)
        ).fetchone()[0]
        last = [
            dict(x)
            for x in con.execute(
                "SELECT id,role,task_type,mode,status,created_at,completed_at,error_code FROM agent_ops_jobs WHERE project_id=? ORDER BY created_at DESC,id DESC LIMIT 30",
                (pid,),
            )
        ]
        return {
            "configuration": cfg,
            "jobs_by_status": dict(jobs),
            "pending_reviews": pending,
            "last_jobs": last,
            "live_api_ready": run_live.live_available(),
            "autonomous_cloud_worker_running": False,
            "no_automatic_external_actions": True,
            "security_classification": "LOCAL_ALPHA",
        }
