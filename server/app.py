"""PowerPath v26 local-first API. No production auth or deployment is claimed.

All data stays in local SQLite and storage. Bind to 127.0.0.1 only.
Do not expose this service to a network without adding authorization, tenant isolation,
secure storage, audit controls and an operational deployment review.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from server import schedule27
from server.services.data_provenance import path_inputs, save_path_inputs

from server.database import ROOT, DATA, EVIDENCE, DB, sqlite_db as db

ENGINE = ROOT / "engine"
MAX_UPLOAD = 5 * 1024 * 1024
SAFE_SUFFIX = {".pdf", ".txt", ".csv", ".json", ".md", ".png", ".jpg", ".jpeg"}
DATA.mkdir(parents=True, exist_ok=True)
EVIDENCE.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="PowerPath v30.8.1 PostgreSQL Staging Preparation",
    version="30.8.1-postgres-staging",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

from server.schema_core import initialize_core_schema

initialize_core_schema(db)


class GeoAssetIn(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    asset_type: str = Field(pattern="^(generation_plant|substation|queue_project|transmission|other)$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    source_provider: str = Field(min_length=2, max_length=120)
    source_url: str = Field(min_length=8, max_length=700)
    source_record_id: str = Field(min_length=1, max_length=120)
    vintage: str = Field(min_length=4, max_length=70)
    evidence_level: str = Field(
        default="public_reference", pattern="^(public_reference|secondary_extract|user_supplied)$"
    )
    attributes: dict[str, Any] = Field(default_factory=dict)


class GeoBatchIn(BaseModel):
    csv_text: str = Field(min_length=10, max_length=600_000)
    source_provider: str = Field(min_length=2, max_length=120)
    source_url: str = Field(min_length=8, max_length=700)
    vintage: str = Field(min_length=4, max_length=70)
    evidence_level: str = Field(default="user_supplied", pattern="^(public_reference|secondary_extract|user_supplied)$")


class MilestoneIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    category: str = Field(pattern="^(interconnection|utility|permitting|construction|finance|equipment|tenant)$")
    status: str = Field(default="planned", pattern="^(planned|submitted|awaiting|completed|blocked)$")
    path_id: str
    permit_id: str | None = None
    planned_month: int | None = Field(default=None, ge=1, le=360)
    delay_months: int = Field(default=0, ge=0, le=120)
    predecessor_id: str | None = None
    source_url: str = Field(default="", max_length=700)
    source_note: str = Field(default="", max_length=1600)
    evidence_id: str | None = None
    float_months: int = Field(default=0, ge=0, le=120)  # v27.1: total float to COD (0 = assumed critical)


class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str = Field(default="", max_length=150)
    target_mw: float = Field(default=0, ge=0, le=100000)
    status: str = Field(default="Qualify", pattern="^(Originate|Qualify|Design|Permit|Interconnect|Finance|Deliver)$")
    description: str = Field(default="", max_length=2000)


class ScenarioIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    mode: str = Field(default="underwrite", pattern="^(underwrite|facilities|notes_v259)$")
    config: dict[str, Any]


class EvidenceIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(default="Other", max_length=60)
    evidence_status: str = Field(
        default="unverified", pattern="^(unverified|public_disclosure|executed_document|third_party_review)$"
    )
    citation: str = Field(default="", max_length=600)
    notes: str = Field(default="", max_length=2000)


class PowerPhase(BaseModel):
    month: int = Field(ge=1, le=600)
    mw: float = Field(ge=0, le=100000, allow_inf_nan=False)


class PathIn(BaseModel):
    parcel_id: str | None = None
    power_phases: list[PowerPhase] | None = Field(default=None, min_length=1, max_length=100)
    capacity_basis: str = Field(default='IT', pattern='^(IT|gross)$')
    name: str = Field(min_length=2, max_length=140)
    strategy: str = Field(pattern="^(grid|onsite|hybrid|colocation)$")
    status: str = Field(default="hypothesis", pattern="^(hypothesis|engagement|study|conditional)$")
    capacity_mw: float = Field(default=0, ge=0, le=100000)
    power_month: int | None = Field(default=None, ge=1, le=360)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    delay_months: int = Field(default=0, ge=0, le=120)
    capex_uplift_pct: float = Field(default=0, ge=0, le=500)
    energy_uplift_pct: float = Field(default=0, ge=0, le=500)
    source_note: str = Field(default="", max_length=1200)
    evidence_id: str | None = None


class PermitIn(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    kind: str = Field(pattern="^(permit|interconnection|utility|construction|finance)$")
    status: str = Field(default="not_started", pattern="^(not_started|working|awaiting_third_party|approved|blocked)$")
    path_id: str | None = None
    owner: str = Field(default="", max_length=120)
    due_month: int | None = Field(default=None, ge=1, le=360)
    delay_months: int = Field(default=0, ge=0, le=120)
    evidence_id: str | None = None
    detail: str = Field(default="", max_length=3000)


class StepIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)


class NoteIn(BaseModel):
    body: str = Field(min_length=2, max_length=3000)


class SensitivityIn(BaseModel):
    source_scenario_id: str
    include_open_permit_delay: bool = False


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def uid():
    return secrets.token_hex(12)


def as_json(x):
    return json.dumps(x, separators=(",", ":"), allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(con, project_id, action, object_id, details=None):
    con.execute(
        "INSERT INTO activity(project_id,action,object_id,details_json,created_at) VALUES (?,?,?,?,?)",
        (project_id, action, object_id, as_json(details or {}), now()),
    )
    if os.environ.get("POWERPATH_V27_AUTH_MODE", "local_only") == "required":
        from server.institutional import ACTOR, TENANT, append_audit

        append_audit(con, TENANT.get(), ACTOR.get(), action, object_id, details)


def record(row):
    return dict(row) if row is not None else None


def project_exists(con, pid):
    row = con.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "Project not found")
    return row


def scenario_exists(con, pid, sid):
    row = con.execute("SELECT * FROM scenarios WHERE id=? AND project_id=?", (sid, pid)).fetchone()
    if not row:
        raise HTTPException(404, "Scenario not found in this project")
    return row


def decode_scenario(row):
    d = record(row)
    d["config"] = json.loads(d.pop("config_json"))
    return d


# v27.1 engine versioning. An underwriting scenario names its engine in config.engineVersion. A missing field means the
# frozen v25.8.5 engine, so every scenario and run stored before v27.1 recalculates exactly as it did.
ENGINE_VERSIONS = {"25.8.5": ("underwrite", "underwrite25.js"), "27.1.0": ("underwrite27", "underwrite27.js")}
LEGACY_ENGINE_VERSION = "25.8.5"
CURRENT_ENGINE_VERSION = "27.1.0"


def engine_version_of(config):
    v = (config or {}).get("engineVersion", LEGACY_ENGINE_VERSION)
    if v not in ENGINE_VERSIONS:
        raise HTTPException(422, f"Unknown engineVersion {v!r}; supported: {sorted(ENGINE_VERSIONS)}")
    return v


def underwrite_engine_file(config):
    return ENGINE / ENGINE_VERSIONS[engine_version_of(config)][1]


def calculate(mode, data):
    if len(as_json(data)) > 450_000:
        raise HTTPException(413, "Scenario input is too large")
    if mode == "underwrite":
        mode = ENGINE_VERSIONS[engine_version_of(data)][0]
    try:
        result = subprocess.run(
            ["node", str(ENGINE / "bridge.cjs"), mode],
            input=as_json(data),
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(ROOT),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise HTTPException(503, "Financial engine unavailable") from exc
    if result.returncode:
        err = result.stderr.strip()[:450]
        try:
            msg = json.loads(err)["error"]
        except (ValueError, KeyError, TypeError):
            msg = "Calculation rejected; inspect scenario assumptions"
        raise HTTPException(422, msg)
    try:
        return json.loads(result.stdout)
    except ValueError as exc:
        raise HTTPException(503, "Invalid financial engine response") from exc


@app.middleware("http")
async def basic_hardening(request: Request, call_next):
    # Avoid cross-origin mutating requests against a loopback-only application.
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        origin = request.headers.get("origin")
        if origin:
            from urllib.parse import urlparse

            parsed = urlparse(origin)
            if parsed.hostname not in ("127.0.0.1", "localhost") or parsed.port != request.url.port:
                # RT-G01: an HTTPException raised in middleware bypasses handlers and surfaced as HTTP 500.
                from fastapi.responses import JSONResponse

                return JSONResponse({"detail": "Cross-origin write denied"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://tile.openstreetmap.org; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    )
    return response


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "release": "v30.8.3-local-alpha",
        "mode": "LOCAL_ONLY",
        "engine_hash": sha(ENGINE / "underwrite25.js"),
        "facility_engine_hash": sha(ENGINE / "facility_waterfall259.js"),
        "underwrite27_engine_hash": sha(ENGINE / "underwrite27.js"),
        "fixed_note27_engine_hash": sha(ENGINE / "fixed_note27.cjs"),
        "default_engine_version": CURRENT_ENGINE_VERSION,
        "notes_v259_engine_hash": sha(ENGINE / "v259_verified/src/underwrite.cjs"),
        "risk_v259_hash": sha(ENGINE / "v259_verified/src/assurance.cjs"),
        "authentication": (
            "V27_BEARER_LOCAL_PREVIEW" if os.environ.get("POWERPATH_V27_AUTH_MODE") == "required" else "NOT_IMPLEMENTED"
        ),
        "v27_auth_mode": os.environ.get("POWERPATH_V27_AUTH_MODE", "local_only"),
        "lender_grade": False,
    }


@app.get("/api/defaults")
def defaults():
    result = calculate("defaults", {})
    return {"config": result["project"], "facilities": result["facilities"], "notes": result["notes"]}


@app.get("/api/projects")
def list_projects(request: Request):
    with db() as con:
        res = []
        for row in con.execute("SELECT * FROM projects ORDER BY updated_at DESC"):
            if os.environ.get("POWERPATH_V27_AUTH_MODE", "local_only") == "required" and not any(
                m["tenant_id"]
                == (
                    con.execute("SELECT tenant_id FROM v27_project_tenants WHERE project_id=?", (row["id"],)).fetchone()
                    or {"tenant_id": None}
                )["tenant_id"]
                for m in request.state.members
            ):
                continue
            p = record(row)
            p["scenarios"] = con.execute("SELECT COUNT(*) FROM scenarios WHERE project_id=?", (p["id"],)).fetchone()[0]
            p["evidence_count"] = con.execute(
                "SELECT COUNT(*) FROM evidence WHERE project_id=?", (p["id"],)
            ).fetchone()[0]
            res.append(p)
        return res


@app.post("/api/projects", status_code=201)
def create_project(data: ProjectIn, request: Request, starter_scenario: bool = False):
    id = uid()
    ts = now()
    val = data.model_dump()
    starter = None
    if starter_scenario and val["target_mw"] > 0:
        # v30.8.2: explicit opt-in only. Engine defaults with buildings sized to the stated target MW.
        from server.starter import starter_config, STARTER_NAME

        starter = {
            **starter_config(calculate("defaults", {})["project"], val["target_mw"]),
            "engineVersion": CURRENT_ENGINE_VERSION,
        }
    with db() as con:
        con.execute(
            "INSERT INTO projects(id,name,location,target_mw,status,description,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (id, val["name"], val["location"], val["target_mw"], val["status"], val["description"], ts, ts),
        )
        if os.environ.get("POWERPATH_V27_AUTH_MODE", "local_only") == "required":
            con.execute("INSERT INTO v27_project_tenants VALUES(?,?)", (id, request.state.tenant_id))
        audit(con, id, "project.created", id, {"name": val["name"]})
        if starter:
            sid = uid()
            con.execute(
                "INSERT INTO scenarios VALUES (?,?,?,?,?,?,?,?)",
                (sid, id, STARTER_NAME, "underwrite", as_json(starter), 1, ts, ts),
            )
            audit(
                con,
                id,
                "scenario.created",
                sid,
                {"mode": "underwrite", "starter": True, "sized_to_target_mw": val["target_mw"]},
            )
    return {"id": id, **val, "created_at": ts, "updated_at": ts, "starter_scenario_id": starter and sid}


@app.post("/api/projects/{pid}/starter-scenario", status_code=201)
def create_starter_scenario(pid: str):
    """v30.8.2: explicit user action. Adds the illustrative working scenario (engine defaults, buildings sized to the
    project's target MW) to an existing project. Refuses if the project has no MW target."""
    from server.starter import starter_config, STARTER_NAME

    with db() as con:
        p = project_exists(con, pid)
        if not p["target_mw"] or p["target_mw"] <= 0:
            raise HTTPException(422, "Set a target MW in the project brief first")
        name = STARTER_NAME
        n = 1
        while con.execute("SELECT 1 FROM scenarios WHERE project_id=? AND name=?", (pid, name)).fetchone():
            n += 1
            name = f"{STARTER_NAME} {n}"
        cfg = {
            **starter_config(calculate("defaults", {})["project"], p["target_mw"]),
            "engineVersion": CURRENT_ENGINE_VERSION,
        }
        sid = uid()
        ts = now()
        con.execute(
            "INSERT INTO scenarios VALUES (?,?,?,?,?,?,?,?)", (sid, pid, name, "underwrite", as_json(cfg), 1, ts, ts)
        )
        audit(
            con,
            pid,
            "scenario.created",
            sid,
            {"mode": "underwrite", "starter": True, "sized_to_target_mw": p["target_mw"]},
        )
    return {"id": sid, "project_id": pid, "name": name, "mode": "underwrite", "config": cfg, "version": 1}


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    with db() as con:
        return record(project_exists(con, pid))


@app.patch("/api/projects/{pid}")
def patch_project(pid: str, data: ProjectIn):
    val = data.model_dump()
    ts = now()
    with db() as con:
        project_exists(con, pid)
        con.execute(
            "UPDATE projects SET name=?,location=?,target_mw=?,status=?,description=?,updated_at=? WHERE id=?",
            (val["name"], val["location"], val["target_mw"], val["status"], val["description"], ts, pid),
        )
        audit(con, pid, "project.updated", pid, {"status": val["status"]})
    return {"id": pid, **val, "updated_at": ts}


@app.get("/api/projects/{pid}/scenarios")
def list_scenarios(pid: str):
    with db() as con:
        project_exists(con, pid)
        return [
            decode_scenario(r)
            for r in con.execute("SELECT * FROM scenarios WHERE project_id=? ORDER BY updated_at DESC", (pid,))
        ]


@app.post("/api/projects/{pid}/scenarios", status_code=201)
def create_scenario(pid: str, data: ScenarioIn):
    id = uid()
    ts = now()
    if data.mode == "underwrite":
        if "engineVersion" not in data.config:
            data.config = {**data.config, "engineVersion": CURRENT_ENGINE_VERSION}
        engine_version_of(data.config)
    with db() as con:
        project_exists(con, pid)
        try:
            con.execute(
                "INSERT INTO scenarios VALUES (?,?,?,?,?,?,?,?)",
                (id, pid, data.name, data.mode, as_json(data.config), 1, ts, ts),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Scenario name already exists")
        audit(con, pid, "scenario.created", id, {"mode": data.mode})
    return {
        "id": id,
        "project_id": pid,
        "name": data.name,
        "mode": data.mode,
        "config": data.config,
        "version": 1,
        "created_at": ts,
        "updated_at": ts,
    }


@app.put("/api/projects/{pid}/scenarios/{sid}")
def update_scenario(pid: str, sid: str, data: ScenarioIn):
    with db() as con:
        row = scenario_exists(con, pid, sid)
        # RT-E03: a path-linked (derived) scenario keeps its lineage. Removing or rewriting powerPathLink would let it
        # be used as an "original" base and re-apply the same schedule delay (double counting).
        old_link = json.loads(row["config_json"]).get("powerPathLink")
        if old_link is not None and data.config.get("powerPathLink") != old_link:
            raise HTTPException(
                422,
                "powerPathLink lineage is immutable on a derived scenario; create a new scenario from the original base instead",
            )
        if old_link is None and data.config.get("powerPathLink") is not None:
            raise HTTPException(422, "powerPathLink can only be set by the server when a path sensitivity is created")
        # v30.8.2 audit: an update that omits engineVersion keeps the stored engine. Previously a client that dropped the
        # field silently re-ran a 27.1.0 scenario on the legacy 25.8.5 engine. Changing engines still requires naming it explicitly.
        old_engine = json.loads(row["config_json"]).get("engineVersion")
        if data.mode == "underwrite" and "engineVersion" not in data.config and old_engine is not None:
            data.config = {**data.config, "engineVersion": old_engine}
        if data.mode == "underwrite":
            engine_version_of(data.config)
        version = row["version"] + 1
        try:
            con.execute(
                "UPDATE scenarios SET name=?,mode=?,config_json=?,version=?,updated_at=? WHERE id=?",
                (data.name, data.mode, as_json(data.config), version, now(), sid),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Scenario name already exists")
        audit(con, pid, "scenario.updated", sid, {"version": version})
    return {"id": sid, "version": version}


@app.post("/api/projects/{pid}/scenarios/{sid}/runs", status_code=201)
def run_scenario(pid: str, sid: str):
    with db() as con:
        row = scenario_exists(con, pid, sid)
        scenario = decode_scenario(row)
    result = calculate(scenario["mode"], scenario["config"])
    summary = result["summary"]
    rows = result["rows"]
    id = uid()
    ts = now()
    # A local evidence room is not an authenticated transaction-approval system. No user-supplied
    # JSON, evidence metadata or model test count can change these server-enforced restrictions.
    if scenario["mode"] == "notes_v259":
        summary["risk"]["uses"]["transactionValuation"] = "BLOCKED"
        summary["risk"]["uses"]["lenderCertification"] = "BLOCKED"
        summary["assuranceStatus"] = summary["risk"]["uses"]["screening"]
    with db() as con:
        con.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                id,
                sid,
                scenario["version"],
                scenario["mode"],
                (
                    sha(ENGINE / "v259_verified/src/underwrite.cjs")
                    if scenario["mode"] == "notes_v259"
                    else (
                        sha(underwrite_engine_file(scenario["config"]))
                        if scenario["mode"] == "underwrite"
                        else sha(ENGINE / "underwrite25.js")
                    )
                ),
                (
                    sha(ENGINE / "v259_verified/src/facilities.cjs")
                    if scenario["mode"] == "notes_v259"
                    else sha(ENGINE / "facility_waterfall259.js")
                ),
                as_json(scenario["config"]),
                as_json(summary),
                as_json(rows),
                ts,
                "SCREENING / UNVERIFIED",
            ),
        )
        audit(
            con,
            pid,
            "run.completed",
            id,
            {
                "scenario": sid,
                "version": scenario["version"],
                "mode": scenario["mode"],
                "defaulted": bool(summary.get("defaulted") or summary.get("fundingDefault")),
            },
        )
    return {
        "id": id,
        "scenario_id": sid,
        "scenario_version": scenario["version"],
        "created_at": ts,
        "summary": summary,
        "rows": rows,
        "assurance": "SCREENING / UNVERIFIED",
        "engine_sha256": (
            sha(ENGINE / "v259_verified/src/underwrite.cjs")
            if scenario["mode"] == "notes_v259"
            else (
                sha(underwrite_engine_file(scenario["config"]))
                if scenario["mode"] == "underwrite"
                else sha(ENGINE / "underwrite25.js")
            )
        ),
        "engine_version": engine_version_of(scenario["config"]) if scenario["mode"] == "underwrite" else None,
    }


@app.get("/api/projects/{pid}/runs")
def list_runs(pid: str):
    with db() as con:
        project_exists(con, pid)
        return [
            dict(r)
            for r in con.execute(
                """SELECT r.id,r.scenario_id,r.scenario_version,r.mode,
          r.summary_json,r.created_at,r.label,s.name scenario_name FROM runs r
          JOIN scenarios s ON r.scenario_id=s.id WHERE s.project_id=? ORDER BY r.created_at DESC LIMIT 100""",
                (pid,),
            )
        ]


@app.get("/api/projects/{pid}/runs/{rid}")
def get_run(pid: str, rid: str):
    with db() as con:
        row = con.execute(
            """SELECT r.* FROM runs r JOIN scenarios s ON r.scenario_id=s.id WHERE r.id=? AND s.project_id=?""",
            (rid, pid),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Run not found")
        d = record(row)
        for k in ("input_json", "summary_json", "rows_json"):
            d[k[:-5]] = json.loads(d.pop(k))
        return d


@app.get("/api/projects/{pid}/runs/{rid}/csv")
def export_run(pid: str, rid: str):
    d = get_run(pid, rid)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["PowerPath v26", "SCREENING ONLY", "NOT CONTRACT VERIFIED"])
    writer.writerow(["Run id", rid, "Engine SHA256", d["engine_sha256"]])
    rows = d["rows"]
    keys = list(rows[0]) if rows else []
    writer.writerow(keys)
    for row in rows:
        writer.writerow(
            [json.dumps(row.get(k)) if isinstance(row.get(k), (dict, list)) else row.get(k, "") for k in keys]
        )
    out.seek(0)
    return StreamingResponse(
        iter([out.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="powerpath_{rid}_UNVERIFIED.csv"'},
    )


@app.get("/api/projects/{pid}/evidence")
def list_evidence(pid: str):
    with db() as con:
        project_exists(con, pid)
        return [
            record(r) for r in con.execute("SELECT * FROM evidence WHERE project_id=? ORDER BY created_at DESC", (pid,))
        ]


@app.post("/api/projects/{pid}/evidence", status_code=201)
def create_evidence(pid: str, data: EvidenceIn):
    id = uid()
    ts = now()
    val = data.model_dump()
    with db() as con:
        project_exists(con, pid)
        con.execute(
            """INSERT INTO evidence(id,project_id,title,category,evidence_status,citation,notes,created_at)
          VALUES (?,?,?,?,?,?,?,?)""",
            (id, pid, val["title"], val["category"], val["evidence_status"], val["citation"], val["notes"], ts),
        )
        audit(con, pid, "evidence.recorded", id, {"status": val["evidence_status"]})
    return {"id": id, "project_id": pid, **val, "created_at": ts}


@app.post("/api/projects/{pid}/evidence/{eid}/file")
async def upload_evidence(pid: str, eid: str, attachment: UploadFile = File(...)):
    suffix = Path(attachment.filename or "").suffix.lower()
    if suffix not in SAFE_SUFFIX:
        raise HTTPException(415, "Unsupported file type")
    with db() as con:
        project_exists(con, pid)
        item = con.execute("SELECT * FROM evidence WHERE id=? AND project_id=?", (eid, pid)).fetchone()
        if not item:
            raise HTTPException(404, "Evidence record not found")
        if item["stored_filename"]:
            raise HTTPException(409, "Evidence is immutable: create a new record for a new version")
    content = await attachment.read(MAX_UPLOAD + 1)
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "Maximum file size is 5 MB")
    name = eid + suffix
    file_path = EVIDENCE / name
    with file_path.open("xb") as f:
        f.write(content)
    digest = hashlib.sha256(content).hexdigest()
    with db() as con:
        con.execute(
            "UPDATE evidence SET filename=?,stored_filename=?,content_hash=?,bytes=? WHERE id=? AND project_id=?",
            (Path(attachment.filename or "document").name, name, digest, len(content), eid, pid),
        )
        audit(con, pid, "evidence.file_attached", eid, {"sha256": digest, "bytes": len(content)})
    return {"evidence_id": eid, "sha256": digest, "bytes": len(content)}


@app.get("/api/projects/{pid}/evidence/{eid}/download")
def download_evidence(pid: str, eid: str):
    with db() as con:
        item = con.execute("SELECT * FROM evidence WHERE id=? AND project_id=?", (eid, pid)).fetchone()
        if not item or not item["stored_filename"]:
            raise HTTPException(404, "Evidence file not found")
        path = EVIDENCE / item["stored_filename"]
        return FileResponse(path, filename=item["filename"], media_type="application/octet-stream")


@app.get("/api/projects/{pid}/activity")
def list_activity(pid: str):
    with db() as con:
        project_exists(con, pid)
        return [
            record(r)
            for r in con.execute("SELECT * FROM activity WHERE project_id=? ORDER BY id DESC LIMIT 100", (pid,))
        ]


# v26.2: Local-only, user-entered candidate paths and PermitIQ actions. No spatial or utility assertions.
def _link_exists(con, table, project_id, object_id, label):
    if object_id is None:
        return
    if not con.execute(f"SELECT id FROM {table} WHERE id=? AND project_id=?", (object_id, project_id)).fetchone():
        raise HTTPException(422, f"{label} does not belong to this project")


def _check_coords(data):
    if (data.latitude is None) != (data.longitude is None):
        raise HTTPException(422, "Latitude and longitude must be supplied together")


@app.get("/api/projects/{pid}/paths")
def get_paths(pid: str):
    with db() as con:
        project_exists(con, pid)
        return [
            path_inputs(con, record(x))
            for x in con.execute("SELECT * FROM power_paths WHERE project_id=? ORDER BY created_at,id", (pid,))
        ]


@contextmanager
def _write_path():
    with db() as con:
        if os.environ.get('POWERPATH_DATABASE_URL'):
            yield con
            return
        con.execute('BEGIN IMMEDIATE')
        try:
            yield con
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK')
            raise


@app.post("/api/projects/{pid}/paths", status_code=201)
def create_path(pid: str, data: PathIn):
    _check_coords(data)
    id = uid()
    ts = now()
    d = data.model_dump()
    if d['power_phases'] is not None:
        from server.services.power_capacity import tranches
        try:
            tranches(d['power_phases'], 1, d['capacity_basis'])
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    if d['power_phases']:
        d['capacity_mw'] = d['power_phases'][-1]['mw']
        d['power_month'] = next((p['month'] for p in d['power_phases'] if p['mw'] > 0), None)
    if os.environ.get('POWERPATH_DATABASE_URL') and (d['parcel_id'] or d['power_phases'] or d['capacity_basis'] != 'IT'):
        raise HTTPException(503, 'Parcel pathway settings require the local SQLite workspace')
    with _write_path() as con:
        project_exists(con, pid)
        _link_exists(con, "evidence", pid, d["evidence_id"], "Evidence")
        con.execute(
            "INSERT INTO power_paths VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                id,
                pid,
                d["name"],
                d["strategy"],
                d["status"],
                d["capacity_mw"],
                d["power_month"],
                d["latitude"],
                d["longitude"],
                d["delay_months"],
                d["capex_uplift_pct"],
                d["energy_uplift_pct"],
                d["source_note"],
                d["evidence_id"],
                ts,
                ts,
            ),
        )
        save_path_inputs(con, pid, id, d)
        audit(
            con,
            pid,
            "path.created",
            id,
            {"strategy": d["strategy"], "source_note": d["source_note"], "mode": "user_entered_screening"},
        )
    return {"id": id, "project_id": pid, **d, "created_at": ts, "updated_at": ts}


@app.put("/api/projects/{pid}/paths/{pathid}")
def update_path(pid: str, pathid: str, data: PathIn):
    _check_coords(data)
    d = data.model_dump()
    if d['power_phases'] is not None:
        from server.services.power_capacity import tranches
        try:
            tranches(d['power_phases'], 1, d['capacity_basis'])
        except ValueError as exc:
            raise HTTPException(422, str(exc))
    if d['power_phases']:
        d['capacity_mw'] = d['power_phases'][-1]['mw']
        d['power_month'] = next((p['month'] for p in d['power_phases'] if p['mw'] > 0), None)
    if os.environ.get('POWERPATH_DATABASE_URL') and (d['parcel_id'] or d['power_phases'] or d['capacity_basis'] != 'IT'):
        raise HTTPException(503, 'Parcel pathway settings require the local SQLite workspace')
    ts = now()
    with _write_path() as con:
        _link_exists(con, "power_paths", pid, pathid, "Path")
        _link_exists(con, "evidence", pid, d["evidence_id"], "Evidence")
        con.execute(
            "UPDATE power_paths SET name=?,strategy=?,status=?,capacity_mw=?,power_month=?,latitude=?,longitude=?,delay_months=?,capex_uplift_pct=?,energy_uplift_pct=?,source_note=?,evidence_id=?,updated_at=? WHERE id=?",
            (
                d["name"],
                d["strategy"],
                d["status"],
                d["capacity_mw"],
                d["power_month"],
                d["latitude"],
                d["longitude"],
                d["delay_months"],
                d["capex_uplift_pct"],
                d["energy_uplift_pct"],
                d["source_note"],
                d["evidence_id"],
                ts,
                pathid,
            ),
        )
        save_path_inputs(con, pid, pathid, d)
        audit(con, pid, "path.updated", pathid, {"status": d["status"], "delay_months": d["delay_months"]})
    return {"id": pathid, "project_id": pid, **d, "updated_at": ts}


def _permit_out(con, row):
    d = record(row)
    d["steps"] = [
        record(x)
        for x in con.execute("SELECT * FROM permit_steps WHERE permit_id=? ORDER BY sort_index,id", (d["id"],))
    ]
    d["notes"] = [
        record(x)
        for x in con.execute("SELECT * FROM permit_notes WHERE permit_id=? ORDER BY created_at,id", (d["id"],))
    ]
    return d


@app.get("/api/projects/{pid}/permits")
def get_permits(pid: str):
    with db() as con:
        project_exists(con, pid)
        return [
            _permit_out(con, x)
            for x in con.execute(
                "SELECT * FROM permit_items WHERE project_id=? ORDER BY due_month IS NULL, due_month,id", (pid,)
            )
        ]


@app.post("/api/projects/{pid}/permits", status_code=201)
def create_permit(pid: str, data: PermitIn):
    id = uid()
    ts = now()
    d = data.model_dump()
    with db() as con:
        project_exists(con, pid)
        _link_exists(con, "power_paths", pid, d["path_id"], "Path")
        _link_exists(con, "evidence", pid, d["evidence_id"], "Evidence")
        con.execute(
            "INSERT INTO permit_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                id,
                pid,
                d["path_id"],
                d["title"],
                d["kind"],
                d["status"],
                d["owner"],
                d["due_month"],
                d["delay_months"],
                d["evidence_id"],
                d["detail"],
                ts,
                ts,
            ),
        )
        audit(con, pid, "permit.created", id, {"title": d["title"], "status": d["status"]})
        return _permit_out(con, con.execute("SELECT * FROM permit_items WHERE id=?", (id,)).fetchone())


@app.put("/api/projects/{pid}/permits/{permitid}")
def update_permit(pid: str, permitid: str, data: PermitIn):
    d = data.model_dump()
    ts = now()
    with db() as con:
        _link_exists(con, "permit_items", pid, permitid, "Permit")
        _link_exists(con, "power_paths", pid, d["path_id"], "Path")
        _link_exists(con, "evidence", pid, d["evidence_id"], "Evidence")
        con.execute(
            "UPDATE permit_items SET path_id=?,title=?,kind=?,status=?,owner=?,due_month=?,delay_months=?,evidence_id=?,detail=?,updated_at=? WHERE id=?",
            (
                d["path_id"],
                d["title"],
                d["kind"],
                d["status"],
                d["owner"],
                d["due_month"],
                d["delay_months"],
                d["evidence_id"],
                d["detail"],
                ts,
                permitid,
            ),
        )
        audit(con, pid, "permit.updated", permitid, {"status": d["status"], "delay_months": d["delay_months"]})
        return _permit_out(con, con.execute("SELECT * FROM permit_items WHERE id=?", (permitid,)).fetchone())


@app.post("/api/projects/{pid}/permits/{permitid}/steps", status_code=201)
def add_step(pid: str, permitid: str, data: StepIn):
    id = uid()
    with db() as con:
        _link_exists(con, "permit_items", pid, permitid, "Permit")
        order = con.execute("SELECT COUNT(*) FROM permit_steps WHERE permit_id=?", (permitid,)).fetchone()[0]
        con.execute("INSERT INTO permit_steps VALUES (?,?,?,?,?)", (id, permitid, data.title, 0, order))
        audit(con, pid, "permit.checklist.added", permitid, {"step_id": id, "title": data.title})
    return {"id": id, "permit_id": permitid, "title": data.title, "is_done": 0, "sort_index": order}


@app.post("/api/projects/{pid}/permits/{permitid}/steps/{stepid}/toggle")
def toggle_step(pid: str, permitid: str, stepid: str):
    with db() as con:
        _link_exists(con, "permit_items", pid, permitid, "Permit")
        step = con.execute("SELECT * FROM permit_steps WHERE id=? AND permit_id=?", (stepid, permitid)).fetchone()
        if not step:
            raise HTTPException(404, "Checklist item not found in permit")
        state = 1 - int(step["is_done"])
        con.execute("UPDATE permit_steps SET is_done=? WHERE id=?", (state, stepid))
        audit(con, pid, "permit.checklist.updated", permitid, {"step_id": stepid, "done": bool(state)})
    return {"id": stepid, "is_done": state}


@app.post("/api/projects/{pid}/permits/{permitid}/notes", status_code=201)
def add_note(pid: str, permitid: str, data: NoteIn):
    id = uid()
    ts = now()
    with db() as con:
        _link_exists(con, "permit_items", pid, permitid, "Permit")
        con.execute("INSERT INTO permit_notes VALUES (?,?,?,?)", (id, permitid, data.body, ts))
        audit(con, pid, "permit.note.added", permitid, {"note_id": id})
    return {"id": id, "permit_id": permitid, "body": data.body, "created_at": ts}


@app.post("/api/projects/{pid}/paths/{pathid}/sensitivity", status_code=201)
def create_path_sensitivity(pid: str, pathid: str, data: SensitivityIn):
    # v27.1 (RT-E04b): the v26.2 route is now an alias of the canonical schedule sensitivity. It previously ADDED the path
    # estimate and the largest open-permit delay (16 months for the demo grid path) while the v26.3 route took the max
    # (9 months). include_open_permit_delay can no longer change the result: unlinked open permits are always parallel drivers.
    return _schedule_sensitivity(pid, pathid, data, "v26.2 /sensitivity (canonical alias)", "path.sensitivity.created")


# v26.3 — Real-coordinate source records. These are geographic observations, NEVER confirmed available MW.
def _url(u):
    from urllib.parse import urlparse

    x = urlparse(u)
    if x.scheme != "https" or not x.hostname or x.username or x.password:
        raise HTTPException(422, "A public HTTPS source URL is required")
    if x.hostname in ("localhost", "127.0.0.1") or x.hostname.endswith(".local"):
        raise HTTPException(422, "Local/private source URLs are not accepted")


def _geo_out(row):
    d = record(row)
    d["attributes"] = json.loads(d.pop("attributes_json"))
    d["capacity_available_mw"] = None
    d["available_power_verified"] = False
    return d


@app.get("/api/projects/{pid}/geo-assets")
def list_geo(pid: str):
    with db() as con:
        project_exists(con, pid)
        return [
            _geo_out(x) for x in con.execute("SELECT * FROM geographic_assets WHERE project_id=? ORDER BY name", (pid,))
        ]


def _insert_geo(con, pid, data: GeoAssetIn):
    _url(data.source_url)
    d = data.model_dump()
    if len(as_json(d["attributes"])) > 15_000:
        raise HTTPException(422, "Geographic attributes too large")
    if d["latitude"] == 0 and d["longitude"] == 0:
        raise HTTPException(422, "Null-Island placeholder coordinates not allowed")
    id = uid()
    try:
        con.execute(
            "INSERT INTO geographic_assets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                id,
                pid,
                d["name"],
                d["asset_type"],
                d["latitude"],
                d["longitude"],
                d["source_provider"],
                d["source_url"],
                d["source_record_id"],
                d["vintage"],
                d["evidence_level"],
                as_json(d["attributes"]),
                now(),
            ),
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Duplicate provider record in this project")
    audit(
        con,
        pid,
        "geo.source.added",
        id,
        {"record": d["source_record_id"], "provider": d["source_provider"], "claim": "location_only_no_available_mw"},
    )
    return {"id": id, "project_id": pid, **d, "available_power_verified": False, "capacity_available_mw": None}


@app.post("/api/projects/{pid}/geo-assets", status_code=201)
def create_geo(pid: str, data: GeoAssetIn):
    with db() as con:
        project_exists(con, pid)
        return _insert_geo(con, pid, data)


@app.post("/api/projects/{pid}/geo-assets/import", status_code=201)
def import_geo(pid: str, data: GeoBatchIn):
    _url(data.source_url)
    rows = list(csv.DictReader(io.StringIO(data.csv_text)))
    if not rows or len(rows) > 250:
        raise HTTPException(422, "CSV must contain 1–250 rows per batch")

    def val(row, *keys):
        lower = {str(k).strip().lower(): v for k, v in row.items()}
        for k in keys:
            x = lower.get(k.lower())
            if x is not None and str(x).strip():
                return str(x).strip()
        return ""

    items = []
    seen = set()
    for ix, r in enumerate(rows):
        try:
            lat = float(val(r, "Latitude", "lat"))
            lon = float(val(r, "Longitude", "lon", "long"))
            label = val(r, "Plant Name", "name", "asset_name")
            rid = val(r, "Plant Code", "plant_id", "source_record_id", "id")
            kind = val(r, "asset_type") or "generation_plant"
            asset = GeoAssetIn(
                name=label,
                asset_type=kind,
                latitude=lat,
                longitude=lon,
                source_provider=data.source_provider,
                source_url=data.source_url,
                source_record_id=rid,
                vintage=data.vintage,
                evidence_level=data.evidence_level,
                attributes={
                    "state": val(r, "State", "state"),
                    "county": val(r, "County", "county"),
                    "grid_voltage_kv": val(r, "Grid Voltage (kV)", "grid_voltage_kv"),
                    "balancing_authority": val(r, "Balancing Authority Code", "balancing_authority"),
                    "display_capacity_mw": val(r, "Nameplate MW", "nameplate_mw"),
                },
            )
        except (ValueError, TypeError, Exception) as exc:
            raise HTTPException(422, f"Invalid CSV row {ix+2}: {str(exc)[:200]}")
        if rid in seen:
            raise HTTPException(422, "Duplicate record ID inside imported CSV")
        seen.add(rid)
        items.append(asset)
    with db() as con:
        project_exists(con, pid)
        # Full-batch atomicity: do not retain a partial import if any row conflicts.
        con.execute("BEGIN")
        try:
            out = [_insert_geo(con, pid, x) for x in items]
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        return {
            "count": len(out),
            "records": out,
            "warning": "Geographic records do not establish grid access or available MW",
        }


@app.get("/api/projects/{pid}/milestones")
def list_milestones(pid: str, path_id: str | None = None):
    with db() as con:
        project_exists(con, pid)
        if path_id:
            _link_exists(con, "power_paths", pid, path_id, "Path")
            rows = con.execute(
                "SELECT * FROM delivery_milestones WHERE project_id=? AND path_id=? ORDER BY planned_month,id",
                (pid, path_id),
            )
        else:
            rows = con.execute("SELECT * FROM delivery_milestones WHERE project_id=? ORDER BY planned_month,id", (pid,))
        return [record(x) for x in rows]


def _validate_milestone_links(con, pid, d, mid=None):
    _link_exists(con, "power_paths", pid, d["path_id"], "Path")
    _link_exists(con, "evidence", pid, d["evidence_id"], "Evidence")
    _link_exists(con, "permit_items", pid, d["permit_id"], "Permit")
    if d["permit_id"]:
        permit = con.execute("SELECT path_id FROM permit_items WHERE id=?", (d["permit_id"],)).fetchone()
        if permit["path_id"] != d["path_id"]:
            raise HTTPException(422, "Permit must relate to the same path")
    pred = d["predecessor_id"]
    if pred:
        row = con.execute(
            "SELECT id,path_id,predecessor_id FROM delivery_milestones WHERE id=? AND project_id=?", (pred, pid)
        ).fetchone()
        if not row or row["path_id"] != d["path_id"]:
            raise HTTPException(422, "Predecessor must be within this power path")
        if pred == mid:
            raise HTTPException(422, "Milestone cannot depend on itself")
        seen = {mid}
        cur = row
        while cur:
            if cur["id"] in seen:
                raise HTTPException(422, "Milestone dependency cycle")
            seen.add(cur["id"])
            cur = (
                con.execute(
                    "SELECT id,path_id,predecessor_id FROM delivery_milestones WHERE id=?", (cur["predecessor_id"],)
                ).fetchone()
                if cur["predecessor_id"]
                else None
            )
    if d["source_url"]:
        _url(d["source_url"])


@app.post("/api/projects/{pid}/milestones", status_code=201)
def add_milestone(pid: str, data: MilestoneIn):
    d = data.model_dump()
    id = uid()
    ts = now()
    with db() as con:
        project_exists(con, pid)
        _validate_milestone_links(con, pid, d, id)
        con.execute(
            "INSERT INTO delivery_milestones(id,project_id,path_id,permit_id,title,category,status,planned_month,delay_months,predecessor_id,source_url,source_note,evidence_id,created_at,updated_at,float_months) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                id,
                pid,
                d["path_id"],
                d["permit_id"],
                d["title"],
                d["category"],
                d["status"],
                d["planned_month"],
                d["delay_months"],
                d["predecessor_id"],
                d["source_url"],
                d["source_note"],
                d["evidence_id"],
                ts,
                ts,
                d["float_months"],
            ),
        )
        audit(
            con, pid, "milestone.created", id, {"path_id": d["path_id"], "incremental_delay_months": d["delay_months"]}
        )
    return {"id": id, "project_id": pid, **d}


@app.put("/api/projects/{pid}/milestones/{mid}")
def edit_milestone(pid: str, mid: str, data: MilestoneIn):
    d = data.model_dump()
    ts = now()
    with db() as con:
        project_exists(con, pid)
        _link_exists(con, "delivery_milestones", pid, mid, "Milestone")
        current = con.execute("SELECT path_id FROM delivery_milestones WHERE id=?", (mid,)).fetchone()
        if current["path_id"] != d["path_id"]:
            raise HTTPException(422, "Milestone may not switch paths")
        _validate_milestone_links(con, pid, d, mid)
        con.execute(
            "UPDATE delivery_milestones SET permit_id=?,title=?,category=?,status=?,planned_month=?,delay_months=?,predecessor_id=?,source_url=?,source_note=?,evidence_id=?,updated_at=?,float_months=? WHERE id=?",
            (
                d["permit_id"],
                d["title"],
                d["category"],
                d["status"],
                d["planned_month"],
                d["delay_months"],
                d["predecessor_id"],
                d["source_url"],
                d["source_note"],
                d["evidence_id"],
                ts,
                d["float_months"],
                mid,
            ),
        )
        audit(con, pid, "milestone.updated", mid, {"status": d["status"], "delay_months": d["delay_months"]})
    return {"id": mid, "project_id": pid, **d, "updated_at": ts}


def _schedule(con, pid, pathid, overrides=None):
    """v27.1: delegates to the canonical schedule engine (server/schedule27.py)."""
    _link_exists(con, "power_paths", pid, pathid, "Path")
    try:
        return schedule27.schedule_for(con, pid, pathid, overrides)
    except schedule27.ScheduleError as exc:
        raise HTTPException(422, str(exc))


@app.get("/api/projects/{pid}/paths/{pathid}/schedule")
def get_path_schedule(pid: str, pathid: str):
    with db() as con:
        project_exists(con, pid)
        return _schedule(con, pid, pathid)


def _schedule_sensitivity(pid, pathid, data, route, action="milestone.sensitivity.created"):
    with db() as con:
        project_exists(con, pid)
        scheduled = _schedule(con, pid, pathid)
        path = path_inputs(con, dict(con.execute("SELECT * FROM power_paths WHERE id=?", (pathid,)).fetchone()))
        base = scenario_exists(con, pid, data.source_scenario_id)
        if base["mode"] != "underwrite":
            raise HTTPException(422, "Use an underwriting base scenario")
        config = json.loads(base["config_json"])
        if config.get("powerPathLink"):
            raise HTTPException(
                422,
                "Start critical-path sensitivities from an original unlinked base case to avoid double-counting delays",
            )
        config = schedule27.apply_to_config(config, path, scheduled)
        applied = int(scheduled["effective_delay_months"])
        config["powerPathLink"] = {
            "pathId": pathid,
            "pathName": path["name"],
            "sourceScenarioId": base["id"],
            "sourceScenarioVersion": base["version"],
            "scheduleVersion": scheduled["schedule_version"],
            "scheduleMethod": scheduled["method"],
            "appliedDelayMonths": applied,
            "criticalPath": scheduled["critical_path"],
            "synthetic": True,
            "sourceEvidenceId": path["evidence_id"],
            "route": route,
            "provenance": "analyst-entered milestones / unconfirmed utility service",
        }
        id = uid()
        ts = now()
        name = ("Critical path / " + path["name"] + " / " + id[:5])[:100]
        con.execute(
            "INSERT INTO scenarios VALUES (?,?,?,?,?,?,?,?)", (id, pid, name, "underwrite", as_json(config), 1, ts, ts)
        )
        audit(
            con,
            pid,
            action,
            id,
            {
                "path_id": pathid,
                "schedule_version": scheduled["schedule_version"],
                "applied_delay_months": applied,
                "source_scenario_id": base["id"],
                "route": route,
            },
        )
        return {
            "id": id,
            "name": name,
            "mode": "underwrite",
            "config": config,
            "schedule": scheduled,
            "schedule_version": scheduled["schedule_version"],
            "incremental_delay_months": applied,
            "delay_months": config["delayMonths"],
            "source_version": base["version"],
            "path_id": pathid,
            "permit_delay_months": scheduled["unlinked_permit_delay_months"],
            "include_open_permit_delay_superseded": not data.include_open_permit_delay,
            "delay_convention": scheduled["method"],
            "valuation_allowed": False,
        }


@app.post("/api/projects/{pid}/paths/{pathid}/sensitivity-v263", status_code=201)
def milestone_sensitivity(pid: str, pathid: str, data: SensitivityIn):
    return _schedule_sensitivity(pid, pathid, data, "v26.3 /sensitivity-v263")


@app.get("/api/projects/{pid}/paths/{pathid}/schedule-impact")
def schedule_impact(pid: str, pathid: str, source_scenario_id: str | None = None):
    """Read-only: canonical schedule plus baseline-vs-revised financial effect. Persists nothing."""
    with db() as con:
        project_exists(con, pid)
        scheduled = _schedule(con, pid, pathid)
        path = path_inputs(con, dict(con.execute("SELECT * FROM power_paths WHERE id=?", (pathid,)).fetchone()))
        if source_scenario_id:
            base = scenario_exists(con, pid, source_scenario_id)
        else:
            base = next(
                (
                    r
                    for r in con.execute(
                        "SELECT * FROM scenarios WHERE project_id=? AND mode='underwrite' ORDER BY created_at,rowid",
                        (pid,),
                    )
                    if not json.loads(r["config_json"]).get("powerPathLink")
                ),
                None,
            )
            if base is None:
                raise HTTPException(422, "No original underwriting scenario available")
        if base["mode"] != "underwrite":
            raise HTTPException(422, "Use an underwriting base scenario")
        config = json.loads(base["config_json"])
        if config.get("powerPathLink"):
            raise HTTPException(422, "Use an original unlinked base scenario")
    impact = schedule27.financial_impact(calculate, config, path, scheduled)
    return {
        "schedule": scheduled,
        "schedule_version": scheduled["schedule_version"],
        "source_scenario_id": base["id"],
        "source_scenario_name": base["name"],
        "source_version": base["version"],
        **impact,
        "persisted_changes": False,
    }


from server.institutional import install as install_institutional
from server.transaction27 import install as install_transaction27

install_institutional(app, db)
install_transaction27(app, db)
from server.transaction271 import install as install_transaction271

install_transaction271(app, db, calculate)

from server.intelligence import install as install_intelligence

install_intelligence(app, db, project_exists, _link_exists, audit, calculate)

from server.parcels28 import install as install_parcels28

parcel_store = install_parcels28(app, db, project_exists, audit, ROOT)

from server.site_energy_api import install as install_site_energy

install_site_energy(app, db, parcel_store, project_exists, audit, ROOT, calculate)

from server.site_feasibility_api import install as install_site_feasibility
install_site_feasibility(app, db, parcel_store, project_exists, calculate)


@app.get("/advanced")
def advanced_workspace():
    return FileResponse(ROOT / "web" / "public" / "advanced.html")


app.mount("/assets", StaticFiles(directory=ROOT / "web" / "public"), name="assets")


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "public" / "index.html")


@app.get("/power-deliverability")
def power_deliverability_workspace():
    return FileResponse(
        ROOT / "web" / "public" / "power-deliverability.html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.get("/transaction-workspace")
def transaction_workspace():
    return FileResponse(
        ROOT / "web" / "public" / "transaction-workspace.html",
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


# v30.2 additive PowerPath feasibility API. No frozen calculation engines are changed.
from server.feasibility_api import install as install_feasibility_v82

install_feasibility_v82(app, db)

# v30.4-alpha additive permitting API (read-only rule engine; no frozen engine or DB change).
from server.permitting_api import install as install_permitting

install_permitting(app)

# v30.5 read-only nationwide state navigation and truth-labelled screening.
from server.national_permitting_api import install as install_national_permitting

install_national_permitting(app)

# v30.7 additive, scoped and versioned agent operating state (no financial changes).
from server.agent_ops_api import install as install_agent_ops

install_agent_ops(app, db, project_exists, audit, ROOT)

# v30.7.1: read-only footprint intersections; no model/financial mutation.
from server.footprint_api import install as install_footprint

install_footprint(app, db, ROOT)

# v30.8.2: financial outputs and their audit evidence are append-only (Nov 4 review P0). Installed last so every table exists.
from server.append_only import install as install_append_only

install_append_only(db)
