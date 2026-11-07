"""Explicit foreground worker for scheduled, bounded agent reviews.

Launch separately; no daemon, remote fetch, production deployment, or model
calls take place when merely starting the web application.
"""

from __future__ import annotations
import argparse, json, os, secrets, time
from server.app import db, project_exists
from agents.operations import config, schedule_daily, recover_interrupted, process_one


def tick(pid, max_jobs=10):
    with db() as con:
        project_exists(con, pid)
        cfg = config(con, pid)
    if not cfg["enabled"]:
        return {"status": "DISABLED", "project_id": pid, "message": "Enable schedule in Agent Operations first."}
    if cfg["mode"] == "live":
        from agents.run_live import live_available

        if not live_available():
            return {
                "status": "LIVE_DISABLED",
                "project_id": pid,
                "message": "Live opt-in/API configuration missing; no model calls sent",
            }
    recover_interrupted(db, pid)
    schedule_daily(db, pid)
    results = []
    worker_id = "foreground-" + secrets.token_hex(5)
    for _ in range(max_jobs):
        row = process_one(db, pid, worker_id)
        if row["status"] in ("IDLE", "LIVE_DISABLED", "BUDGET_BLOCKED"):
            if row["status"] != "IDLE":
                results.append(row)
            break
        results.append(row)
    return {
        "status": "TICK_COMPLETE",
        "project_id": pid,
        "jobs": results,
        "worker_id": worker_id,
        "background_process": False,
        "external_actions_performed": False,
    }


def main():
    p = argparse.ArgumentParser(description="PowerPath local, opt-in agent operations worker")
    p.add_argument("--project", required=True)
    p.add_argument("--once", action="store_true", help="Perform one schedule/dispatch tick and exit")
    p.add_argument("--watch", action="store_true", help="Keep polling in this foreground process")
    p.add_argument("--interval", type=int, default=600)
    p.add_argument("--max-jobs", type=int, default=10)
    a = p.parse_args()
    if a.once == a.watch:
        p.error("Select exactly one of --once or --watch")
    if not 60 <= a.interval <= 86400:
        p.error("Interval must be 60-86400 seconds")
    if not 1 <= a.max_jobs <= 10:
        p.error("Max jobs must be 1-10")
    while True:
        print(json.dumps(tick(a.project, a.max_jobs), sort_keys=True), flush=True)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
