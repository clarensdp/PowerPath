"""Readout and operator controls for v30.7 local-first agent orchestration."""

from __future__ import annotations
import json, os
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from agents import operations as ops
from server.agent_ops_store import install_migrations


class ConfigIn(BaseModel):
    enabled: bool
    mode: str = Field(pattern="^(rules|live)$")


class JobIn(BaseModel):
    role: str = Field(min_length=3, max_length=40)
    mode: str | None = Field(default=None, pattern="^(rules|live)$")


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(acknowledged|rejected)$")
    reason: str = Field(min_length=8, max_length=600)


def install(app, db, project_exists, audit, root):
    install_migrations(db)

    def require_approver(request):
        # In local-only mode no named, authenticated approver exists. Do not permit
        # self-attested approval via an unprotected API.
        if os.environ.get("POWERPATH_V27_AUTH_MODE", "local_only") != "required":
            raise HTTPException(
                403, "Named authenticated approver required; local preview cannot approve agent reviews"
            )
        from server.institutional import ROLE_RANK

        if ROLE_RANK.get(getattr(request.state, "role", ""), 0) < ROLE_RANK["approver"]:
            raise HTTPException(403, "Approver role required")

    @app.get("/agent-operations")
    def workspace():
        return FileResponse(root / "web" / "public" / "agent-operations.html", headers={"Cache-Control": "no-store"})

    @app.get("/api/projects/{pid}/agents/ops/overview")
    def status(pid: str):
        with db() as con:
            project_exists(con, pid)
        result = ops.overview(db, pid)
        return {**result, "roles": ops.ROLE_DESCRIPTIONS, "task_types": ops.TASKS}

    @app.post("/api/projects/{pid}/agents/ops/config")
    def set_config(pid: str, payload: ConfigIn, request: Request):
        # Enabling scheduled live calls can incur API charges. Require explicit
        # operator opt-in from this endpoint; in required-auth mode an approver.
        if os.environ.get("POWERPATH_V27_AUTH_MODE") == "required":
            require_approver(request)
        result = ops.configure(db, pid, payload.enabled, payload.mode)
        with db() as con:
            audit(con, pid, "agent_ops.configuration.changed", pid, {"enabled": payload.enabled, "mode": payload.mode})
        return {**result, "worker_started": False, "model_calls_made": 0}

    @app.post("/api/projects/{pid}/agents/ops/jobs", status_code=201)
    def create_job(pid: str, payload: JobIn):
        if payload.role not in ops.TASKS:
            raise HTTPException(422, "Role not allowlisted")
        try:
            item = ops.enqueue(db, pid, payload.role, payload.mode)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {**item, "worker_started": False, "external_actions": False}

    @app.get("/api/projects/{pid}/agents/ops/jobs")
    def list_jobs(pid: str):
        with db() as con:
            project_exists(con, pid)
            return [
                dict(r)
                for r in con.execute(
                    "SELECT * FROM agent_ops_jobs WHERE project_id=? ORDER BY created_at DESC,id DESC LIMIT 150", (pid,)
                )
            ]

    @app.get("/api/projects/{pid}/agents/ops/jobs/{job_id}")
    def get_job(pid: str, job_id: str):
        with db() as con:
            project_exists(con, pid)
            r = con.execute("SELECT * FROM agent_ops_jobs WHERE project_id=? AND id=?", (pid, job_id)).fetchone()
            if not r:
                raise HTTPException(404, "Job not found")
            result = dict(r)
            result["result"] = json.loads(result.pop("result_json"))
            return result

    @app.post("/api/projects/{pid}/agents/ops/jobs/{job_id}/retry")
    def retry_job(pid: str, job_id: str):
        with db() as con:
            project_exists(con, pid)
        try:
            return ops.retry(db, pid, job_id)
        except KeyError:
            raise HTTPException(404, "Job not found")
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/projects/{pid}/agents/ops/reviews")
    def list_reviews(pid: str):
        with db() as con:
            project_exists(con, pid)
            return [
                dict(r)
                for r in con.execute(
                    "SELECT r.*,j.role,j.task_type,j.mode FROM agent_ops_reviews r JOIN agent_ops_jobs j ON j.id=r.job_id WHERE r.project_id=? ORDER BY r.created_at DESC,r.id DESC LIMIT 150",
                    (pid,),
                )
            ]

    @app.post("/api/projects/{pid}/agents/ops/reviews/{rid}/decision")
    def decide(pid: str, rid: str, payload: DecisionIn, request: Request):
        require_approver(request)
        with db() as con:
            project_exists(con, pid)
        try:
            return ops.decide_review(db, pid, rid, payload.decision, request.state.user_id, payload.reason)
        except KeyError:
            raise HTTPException(404, "Review not found")
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.get("/api/projects/{pid}/agents/ops/audit-verify")
    def verify(pid: str):
        with db() as con:
            project_exists(con, pid)
            return ops.verify_events(con, pid)
