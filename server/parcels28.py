"""Public parcel screening: evidence completeness is not electrical reliability."""

import json, math, os
from datetime import date, datetime, timezone
from urllib.parse import urlparse
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator

FACTORS = {"power": 30, "permitting": 20, "land": 15, "environment": 15, "delivery": 10, "connectivity": 10}
CRITICAL = {"power", "permitting"}


class Assessment(BaseModel):
    factor: str
    rating: int | None = Field(default=None, ge=0, le=5)
    gate: str = Field(default="unknown", pattern="^(unknown|pass|flag|fail)$")
    source_url: str = Field(default="", max_length=1000)
    source_date: date | None = None
    notes: str = Field(default="", max_length=3000)

    @model_validator(mode="after")
    def validate_evidence(self):
        if self.factor not in FACTORS:
            raise ValueError("Unknown factor")
        if self.source_date and self.source_date > date.today():
            raise ValueError("Source date cannot be in the future")
        if self.gate != "unknown":
            u = urlparse(self.source_url)
            if (
                u.scheme not in ("http", "https")
                or not u.hostname
                or not self.source_date
                or len(self.notes.strip()) < 10
            ):
                raise ValueError(
                    "Assessed factors need an HTTP source, source date, and at least 10 characters of rationale"
                )
            if self.rating is None:
                raise ValueError("Assessed factors need a 0–5 rating")
        elif self.rating is not None:
            raise ValueError("Unknown factors cannot carry ratings")
        return self


class SaveParcel(BaseModel):
    parcel_id: str = Field(min_length=1, max_length=80)


class Task(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    owner: str = Field(default="", max_length=100)
    due: date | None = None
    done: bool = False


def score(assessments, today=None):
    today = today or date.today()
    valid = {}
    stale = []
    for a in assessments:
        d = a.get("source_date")
        fresh = bool(d) and 0 <= (today - date.fromisoformat(d)).days <= 180
        if a["gate"] != "unknown" and not fresh:
            stale.append(a["factor"])
        if fresh and a["gate"] != "unknown" and a.get("rating") is not None:
            valid[a["factor"]] = a
    coverage = sum(FACTORS[k] for k in valid)
    # A recorded adverse gate remains active even if its evidence has aged.
    failed = [a["factor"] for a in assessments if a["gate"] == "fail"]
    unknown = [k for k in FACTORS if k not in valid]
    raw = round(sum(FACTORS[k] * a["rating"] / 5 for k, a in valid.items()) / coverage * 100) if coverage else None
    ready = coverage >= 60 and CRITICAL.issubset(valid) and not failed
    return {
        "version": "PP-SITE-1.0",
        "score": raw if ready else None,
        "coverage_pct": coverage,
        "status": "blocked" if failed else ("provisional" if ready else "insufficient_evidence"),
        "failed_gates": failed,
        "missing_factors": unknown,
        "stale_factors": stale,
        "electrical_reliability": "not_assessed",
        "probability_of_completion": None,
        "meaning": "Analyst-rated screening index; not a probability, utility commitment, or engineering reliability assessment.",
    }


def install(app, db, project_exists, audit, root):
    path = root / "data_sources/loudoun_parcels.geojson"
    collection = json.loads(path.read_text())
    features = {str(f["properties"]["PA_MCPI"]): f for f in collection["features"]}
    with db() as con:
        con.executescript(
            """CREATE TABLE IF NOT EXISTS parcel_shortlist28 (
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, parcel_id TEXT NOT NULL,
        created_at TEXT NOT NULL, PRIMARY KEY(project_id,parcel_id));
        CREATE TABLE IF NOT EXISTS parcel_assessments28 (
        project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, parcel_id TEXT NOT NULL,
        factor TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(project_id,parcel_id,factor));
        CREATE TABLE IF NOT EXISTS parcel_tasks28 (
        id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
        parcel_id TEXT NOT NULL, title TEXT NOT NULL, owner TEXT NOT NULL, due TEXT, done INTEGER NOT NULL DEFAULT 0);"""
        )

    from server.geo29 import GeoStore, install as install_geo29

    store = GeoStore(db, root)
    store.initialize()
    install_geo29(app, store, root)

    def check_parcel(parcel, pid=None):
        record = store.get(parcel, pid)
        if not record:
            raise HTTPException(404, "Parcel not in a connected source or saved snapshot")
        return record

    def rows(con, pid, parcel):
        return [
            json.loads(r["body"])
            for r in con.execute(
                "SELECT body FROM parcel_assessments28 WHERE project_id=? AND parcel_id=?", (pid, parcel)
            )
        ]

    @app.get("/api/parcels28/catalog")
    def catalog():
        return {
            **collection,
            "factors": FACTORS,
            "score_policy": {"minimum_coverage": 60, "critical_factors": sorted(CRITICAL), "freshness_days": 180},
        }

    @app.get("/api/projects/{pid}/parcels28")
    def shortlist(pid: str):
        with db() as con:
            project_exists(con, pid)
            result = []
            for row in con.execute(
                "SELECT parcel_id FROM parcel_shortlist28 WHERE project_id=? ORDER BY created_at DESC", (pid,)
            ):
                parcel = row["parcel_id"]
                aa = rows(con, pid, parcel)
                record = store.get(parcel, pid)
                from server.services.feasibility_store import latest
                land = latest(con, pid, parcel, 'land') if not os.environ.get('POWERPATH_DATABASE_URL') else None
                usable = None
                if land and record and land['body']['parcel_source_version'] == record['version_id']:
                    summary = land['body']['summary']
                    if summary['assessment_complete']:
                        usable = summary['potentially_usable_acres']
                result.append(
                    {
                        "parcel_id": parcel,
                        "usable_acres": usable,
                        "assessment": score(aa),
                        "factors": aa,
                        "feature": json.loads(record["feature_json"]) if record else None,
                        "source_version": record["version_id"] if record else None,
                    }
                )
            return result

    @app.post("/api/projects/{pid}/parcels28", status_code=201)
    def save(pid: str, data: SaveParcel):
        record = check_parcel(data.parcel_id, pid)
        with db() as con:
            project_exists(con, pid)
            con.execute(
                "INSERT OR IGNORE INTO parcel_shortlist28 VALUES (?,?,?)",
                (pid, data.parcel_id, datetime.now(timezone.utc).isoformat()),
            )
            con.execute(
                "INSERT OR IGNORE INTO geo29_saved_versions VALUES(?,?,?)", (pid, data.parcel_id, record["rid"])
            )
            audit(
                con,
                pid,
                "parcel.shortlisted",
                data.parcel_id,
                {
                    "parcel_key": record["parcel_key"],
                    "source_id": record["source_id"],
                    "version_id": record["version_id"],
                },
            )
        return {"parcel_id": data.parcel_id}

    @app.delete("/api/projects/{pid}/parcels28/{parcel}")
    def remove(pid: str, parcel: str):
        with db() as con:
            project_exists(con, pid)
            con.execute("DELETE FROM parcel_shortlist28 WHERE project_id=? AND parcel_id=?", (pid, parcel))
            audit(con, pid, "parcel.removed", parcel)
        return {"removed": True}

    @app.get("/api/projects/{pid}/parcels28/{parcel}")
    def detail(pid: str, parcel: str):
        record = check_parcel(parcel, pid)
        with db() as con:
            project_exists(con, pid)
            aa = rows(con, pid, parcel)
            tasks = [
                dict(r)
                for r in con.execute(
                    "SELECT * FROM parcel_tasks28 WHERE project_id=? AND parcel_id=? ORDER BY id", (pid, parcel)
                )
            ]
        return {
            "parcel_id": parcel,
            "factors": aa,
            "assessment": score(aa),
            "tasks": tasks,
            "feature": json.loads(record["feature_json"]),
            "source_version": record["version_id"],
        }

    @app.put("/api/projects/{pid}/parcels28/{parcel}/assessment")
    def assess(pid: str, parcel: str, data: Assessment):
        record = check_parcel(parcel, pid)
        body = data.model_dump(mode="json")
        with db() as con:
            project_exists(con, pid)
            if not con.execute(
                "SELECT 1 FROM parcel_shortlist28 WHERE project_id=? AND parcel_id=?", (pid, parcel)
            ).fetchone():
                raise HTTPException(422, "Shortlist the parcel first")
            prior = con.execute(
                "SELECT body FROM parcel_assessments28 WHERE project_id=? AND parcel_id=? AND factor=?",
                (pid, parcel, data.factor),
            ).fetchone()
            if prior and json.loads(prior["body"])["gate"] == "fail" and data.gate != "fail":
                if data.gate == "unknown" or not data.source_date or (date.today() - data.source_date).days > 180:
                    raise HTTPException(422, "Clearing a failed gate requires a current, sourced reassessment")
            con.execute(
                "INSERT INTO parcel_assessments28 VALUES (?,?,?,?,?) ON CONFLICT(project_id,parcel_id,factor) DO UPDATE SET body=excluded.body,updated_at=excluded.updated_at",
                (pid, parcel, data.factor, json.dumps(body), datetime.now(timezone.utc).isoformat()),
            )
            audit(con, pid, "parcel.assessment.updated", parcel, body)
            return score(rows(con, pid, parcel))

    @app.post("/api/projects/{pid}/parcels28/{parcel}/tasks", status_code=201)
    def addtask(pid: str, parcel: str, data: Task):
        record = check_parcel(parcel, pid)
        with db() as con:
            project_exists(con, pid)
            cur = con.execute(
                "INSERT INTO parcel_tasks28(project_id,parcel_id,title,owner,due,done) VALUES (?,?,?,?,?,?)",
                (pid, parcel, data.title, data.owner, str(data.due) if data.due else None, int(data.done)),
            )
            audit(con, pid, "parcel.task.created", parcel, data.model_dump(mode="json"))
            return {"id": cur.lastrowid}

    @app.patch("/api/projects/{pid}/parcels28/{parcel}/tasks/{tid}")
    def edit_task(pid: str, parcel: str, tid: int, data: Task):
        with db() as con:
            project_exists(con, pid)
            cur = con.execute(
                "UPDATE parcel_tasks28 SET title=?,owner=?,due=?,done=? WHERE id=? AND project_id=? AND parcel_id=?",
                (data.title, data.owner, str(data.due) if data.due else None, int(data.done), tid, pid, parcel),
            )
            if not cur.rowcount:
                raise HTTPException(404, "Task not found")
            audit(con, pid, "parcel.task.updated", parcel, data.model_dump(mode="json"))
        return {"updated": True}

    return store
