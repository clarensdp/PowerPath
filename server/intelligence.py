"""Local-first public queue observations, snapshot diff, change review, and agent packets.
This is not utility capacity verification. Public generation queue positions are not load-service rights.
No automatic writes to underwriting scenarios or utility-facing services.
"""

from __future__ import annotations
import csv, io, json, hashlib, re, secrets
from datetime import datetime, timezone, date
from urllib.parse import urlparse
from typing import Any
from pydantic import BaseModel, Field
from fastapi import HTTPException

REGIONS = {
    "EIA860": {
        "name": "EIA Form 860 plant reference",
        "url": "https://www.eia.gov/electricity/data/eia860/",
        "record_type": "generation_reference",
        "domains": ("eia.gov",),
    },
    "ERCOT_GIS": {
        "name": "ERCOT Generator Interconnection Status",
        "url": "https://www.ercot.com/gridinfo/resource",
        "record_type": "generator_queue",
        "domains": ("ercot.com",),
    },
    "PJM_QUEUE": {
        "name": "PJM Interconnection Queue",
        "url": "https://www.pjm.com/planning/services-requests/interconnection-queues",
        "record_type": "generator_queue",
        "domains": ("pjm.com",),
    },
}
ALIASES = {
    "record_id": (
        "record_id",
        "project id",
        "project_id",
        "queue id",
        "queue_id",
        "interconnection request",
        "plant code",
        "plant_id",
        "plant id",
        "queue number",
    ),
    "name": ("name", "project name", "project_name", "plant name", "plant_name", "generator name"),
    # RT-B01: 'state' removed. PJM exports carry both 'State' (US state) and 'Status'; 'state' as a status alias
    # made the US state overwrite queue status whenever State preceded Status, hiding withdrawals.
    "status": ("status", "project status", "stage", "queue status"),
    "planned_date": (
        "planned_date",
        "projected in service date",
        "anticipated in service date",
        "in service date",
        "planned commercial operation date",
        "commercial operation date",
        "cod",
        "online date",
    ),
    "capacity_mw": (
        "capacity_mw",
        "capacity (mw)",
        "mw",
        "nameplate capacity",
        "nameplate capacity (mw)",
        "summer capacity (mw)",
    ),
    "latitude": ("latitude", "lat"),
    "longitude": ("longitude", "lon", "long"),
    "technology": ("technology", "fuel", "fuel type", "primary energy source"),
    "county": ("county",),
    "state": ("state",),
}
MAX_FIELD = 1000  # RT-B14: values are compared in full; longer values are rejected rather than silently truncated.
NUMERIC = re.compile(r"-?(\d+|\d{1,3}(,\d{3})+)(\.\d+)?")  # RT-B03: '1.234,5' and other locale forms are rejected.


def normalize_header(x):
    return re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", x.replace("﻿", "").strip().lower()))


def _column_for(headers, kind):
    alias = set(map(normalize_header, ALIASES[kind]))
    # Exact canonical name wins over any alias; otherwise first matching column. A column is used by one field only.
    exact = [h for h in headers if normalize_header(h) == normalize_header(kind)]
    return exact[0] if exact else next((h for h in headers if normalize_header(h) in alias), None)


def parse_data(raw, warnings=None):
    raw = raw.lstrip("﻿")  # RT-B11: UTF-8 BOM from spreadsheet exports
    reader = csv.DictReader(io.StringIO(raw))
    csvrows = list(reader)
    if not csvrows or len(csvrows) > 2500:
        raise HTTPException(422, "CSV must have 1–2500 records")
    headers = [h for h in (reader.fieldnames or []) if h is not None]
    cols = {k: _column_for(headers, k) for k in ALIASES}
    used = {c for c in cols.values() if c}
    if warnings is not None:
        warnings["mapped_columns"] = {k: v for k, v in cols.items() if v}
        warnings["unmapped_columns"] = [h for h in headers if h not in used]  # RT-B04: dropped columns are reported

    def textfield(row, kind):
        c = cols[kind]
        v = str(row.get(c) or "").strip() if c else ""
        if len(v) > MAX_FIELD:
            raise HTTPException(422, f"{kind} longer than {MAX_FIELD} characters")
        return v

    ids = set()
    out = []
    for i, row in enumerate(csvrows, 2):
        rid = textfield(row, "record_id")
        if not rid or len(rid) > 120 or rid in ids:
            raise HTTPException(422, f"Missing or duplicate record ID on row {i}")
        ids.add(rid)
        item = {"record_id": rid}
        for fld in ("name", "status", "planned_date", "technology", "state", "county"):
            item[fld] = textfield(row, fld)
        ds = item["planned_date"]
        if ds and re.fullmatch(r"\d{4}-\d{2}-\d{2}", ds):
            try:
                date.fromisoformat(ds)
            except ValueError:
                raise HTTPException(422, f"Invalid date on row {i}")
        elif ds:
            # Exact dates are not guessed from month/quarter strings.
            item["date_note"] = ds
            item["planned_date"] = ""
        for fld in ("capacity_mw", "latitude", "longitude"):
            s = textfield(row, fld)
            if s:
                if not NUMERIC.fullmatch(s):
                    raise HTTPException(422, f"Non-numeric or locale-formatted {fld} on row {i}: {s[:30]!r}")
                v = float(s.replace(",", ""))
                if not (
                    -90 <= v <= 90
                    if fld == "latitude"
                    else -180 <= v <= 180 if fld == "longitude" else 0 <= v <= 100000
                ):
                    raise HTTPException(422, f"Out-of-range {fld} on row {i}")
                item[fld] = v
            else:
                item[fld] = None
        out.append(item)
    return out


def now():
    return datetime.now(timezone.utc).isoformat()


def uid():
    return secrets.token_hex(12)


def dump(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


SCHEMA = """
CREATE TABLE IF NOT EXISTS intel_snapshots (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 source_key TEXT NOT NULL, source_url TEXT NOT NULL, observed_at TEXT NOT NULL,
 source_published_date TEXT NOT NULL DEFAULT '', data_sha256 TEXT NOT NULL,
 record_count INTEGER NOT NULL, import_label TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intel_records (
 snapshot_id TEXT NOT NULL REFERENCES intel_snapshots(id) ON DELETE CASCADE,
 record_id TEXT NOT NULL, record_json TEXT NOT NULL, PRIMARY KEY(snapshot_id,record_id)
);
CREATE TABLE IF NOT EXISTS intel_changes (
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 snapshot_id TEXT NOT NULL REFERENCES intel_snapshots(id) ON DELETE CASCADE,
 source_key TEXT NOT NULL,record_id TEXT NOT NULL,change_type TEXT NOT NULL,
 old_json TEXT,new_json TEXT,delta_json TEXT NOT NULL,review_state TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS intel_proposals (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 change_id TEXT NOT NULL REFERENCES intel_changes(id) ON DELETE CASCADE,
 milestone_id TEXT NOT NULL REFERENCES delivery_milestones(id) ON DELETE CASCADE,
 proposed_delay_months INTEGER NOT NULL,reason TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',
 created_at TEXT NOT NULL,decided_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS agent_meetings (
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 mode TEXT NOT NULL,status TEXT NOT NULL,mission TEXT NOT NULL,source_digest TEXT NOT NULL,
 model TEXT NOT NULL DEFAULT '',result_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,completed_at TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS agent_messages (
 id TEXT PRIMARY KEY,meeting_id TEXT NOT NULL REFERENCES agent_meetings(id) ON DELETE CASCADE,
 role TEXT NOT NULL,content TEXT NOT NULL,mode TEXT NOT NULL,created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS intel_changes_project ON intel_changes(project_id,created_at DESC);
CREATE INDEX IF NOT EXISTS intel_snapshots_project ON intel_snapshots(project_id,source_key,created_at DESC);
CREATE TABLE IF NOT EXISTS intel_snapshot_raw (
 snapshot_id TEXT PRIMARY KEY REFERENCES intel_snapshots(id) ON DELETE CASCADE,
 csv_text TEXT NOT NULL, text_sha256 TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_call_log (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL, meeting_id TEXT NOT NULL, role TEXT NOT NULL,
 outcome TEXT NOT NULL DEFAULT 'reserved', usage_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
"""
# RT-D01/D02: proposals remember the milestone state they were drafted against (additive migration).
PROPOSAL_COLUMNS = {"base_delay_months": "INTEGER", "base_status": "TEXT NOT NULL DEFAULT ''"}


def migrate(con):
    have = {r[1] for r in con.execute("PRAGMA table_info(intel_proposals)")}
    for c, t in PROPOSAL_COLUMNS.items():
        if c not in have:
            con.execute(f"ALTER TABLE intel_proposals ADD COLUMN {c} {t}")


class SnapshotIn(BaseModel):
    source_key: str = Field(pattern="^(EIA860|ERCOT_GIS|PJM_QUEUE)$")
    csv_text: str = Field(min_length=15, max_length=1_200_000)
    source_url: str = Field(min_length=12, max_length=750)
    # RT-B06/B07: the provider's publication vintage is required; ordering and diffs depend on it.
    source_published_date: str = Field(min_length=10, max_length=10)
    import_label: str = Field(default="analyst_upload", pattern="^(analyst_upload|operator_inbox_file)$")


class ProposalIn(BaseModel):
    change_id: str
    milestone_id: str
    proposed_delay_months: int = Field(ge=0, le=120)
    reason: str = Field(min_length=10, max_length=1000)


class MeetingIn(BaseModel):
    mission: str = Field(
        default="Review changes and propose due diligence, engineering and risk actions.",
        min_length=15,
        max_length=1000,
    )


def official_source(source_key, url):
    u = urlparse(url)
    if (
        u.scheme != "https"
        or not u.hostname
        or not any(u.hostname == d or u.hostname.endswith("." + d) for d in REGIONS[source_key]["domains"])
    ):
        raise HTTPException(422, "Source URL must be HTTPS under the declared EIA/ISO provider domain")
    # Provenance URL is a reference ONLY; there is no server-side network fetch from this field.


def install(app, db, project_exists, link_exists, audit, calculate):
    from fastapi import HTTPException

    with db() as con:
        con.executescript(SCHEMA)
        migrate(con)

    @app.get("/api/intelligence/sources")
    def sources():
        return [
            {
                **{"key": k},
                **v,
                "provenance": "declared URL; uploaded bytes are not independently authenticated",
                "utility_available_mw": None,
            }
            for k, v in REGIONS.items()
        ]

    @app.get("/api/projects/{pid}/intelligence/snapshots")
    def snapshots(pid: str):
        with db() as con:
            project_exists(con, pid)
            return [
                dict(r)
                for r in con.execute(
                    "SELECT * FROM intel_snapshots WHERE project_id=? ORDER BY created_at DESC", (pid,)
                )
            ]

    @app.post("/api/projects/{pid}/intelligence/snapshots", status_code=201)
    def ingest(pid: str, payload: SnapshotIn):
        official_source(payload.source_key, payload.source_url)
        warnings = {}
        data = parse_data(payload.csv_text, warnings)
        # RT-B05/W02: hash of the exact UTF-8 text received (a BOM, if present, is part of it); the text itself is retained.
        digest = hashlib.sha256(payload.csv_text.encode("utf-8")).hexdigest()
        try:
            published = date.fromisoformat(payload.source_published_date)
        except ValueError:
            raise HTTPException(422, "Publication date must be YYYY-MM-DD")
        if published > datetime.now(timezone.utc).date():
            raise HTTPException(
                422, "Publication date is in the future; record the provider vintage, not a planned date"
            )
        with db() as con:
            project_exists(con, pid)
            snapshot_id = uid()
            changed = 0
            try:
                # RT-B15: predecessor selection, duplicate test, diff AND the created_at stamp happen inside one write
                # transaction, so timestamp order equals commit order.
                con.execute("BEGIN IMMEDIATE")
                ts = now()
                # RT-B07: the predecessor is the latest snapshot by provider vintage, then import order.
                previous = con.execute(
                    "SELECT id,data_sha256,source_published_date FROM intel_snapshots WHERE project_id=? AND source_key=? ORDER BY source_published_date DESC,created_at DESC,rowid DESC LIMIT 1",
                    (pid, payload.source_key),
                ).fetchone()
                if (
                    previous
                    and previous["source_published_date"]
                    and payload.source_published_date < previous["source_published_date"]
                ):
                    raise HTTPException(
                        409,
                        f"Out-of-order vintage: {payload.source_published_date} is older than the latest imported {previous['source_published_date']}; diffs would report reversed changes",
                    )
                # RT-B08: only an exact repeat of the immediate predecessor is a duplicate; reverting to older bytes is a real change.
                if previous and previous["data_sha256"] == digest:
                    raise HTTPException(
                        409, "Identical bytes to the latest snapshot for this source; no new snapshot created"
                    )
                prior = {}
                if previous:
                    prior = {
                        r["record_id"]: json.loads(r["record_json"])
                        for r in con.execute("SELECT * FROM intel_records WHERE snapshot_id=?", (previous["id"],))
                    }
                con.execute(
                    "INSERT INTO intel_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (
                        snapshot_id,
                        pid,
                        payload.source_key,
                        payload.source_url,
                        ts,
                        payload.source_published_date,
                        digest,
                        len(data),
                        payload.import_label,
                        ts,
                    ),
                )
                con.execute("INSERT INTO intel_snapshot_raw VALUES(?,?,?)", (snapshot_id, payload.csv_text, digest))
                incoming = {r["record_id"]: r for r in data}
                for r in data:
                    con.execute("INSERT INTO intel_records VALUES(?,?,?)", (snapshot_id, r["record_id"], dump(r)))
                if previous:
                    for rid in sorted(set(prior) | set(incoming)):
                        old = prior.get(rid)
                        new = incoming.get(rid)
                        if old == new:
                            continue
                        kind = "added" if old is None else "removed" if new is None else "updated"
                        delta = {
                            k: {"before": old.get(k) if old else None, "after": new.get(k) if new else None}
                            for k in sorted(set(old or {}) | set(new or {}))
                            if (old or {}).get(k) != (new or {}).get(k)
                        }
                        con.execute(
                            "INSERT INTO intel_changes VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                uid(),
                                pid,
                                snapshot_id,
                                payload.source_key,
                                rid,
                                kind,
                                dump(old) if old else None,
                                dump(new) if new else None,
                                dump(delta),
                                "open",
                                ts,
                            ),
                        )
                        changed += 1
                audit(
                    con,
                    pid,
                    "intelligence.snapshot.imported",
                    snapshot_id,
                    {
                        "provider": payload.source_key,
                        "records": len(data),
                        "changes": changed,
                        "sha256": digest,
                        "source_published_date": payload.source_published_date,
                        "available_mw_verified": False,
                    },
                )
                con.execute("COMMIT")
            except Exception:
                if con.in_transaction:
                    con.execute("ROLLBACK")
                raise
        # RT-B10: the bytes are operator-supplied; only the declared provider domain was checked.
        return {
            "id": snapshot_id,
            "source_key": payload.source_key,
            "sha256": digest,
            "count": len(data),
            "changes": changed,
            "compared_to": previous["id"] if previous else None,
            "available_mw_verified": False,
            "bytes_authenticated_against_provider": False,
            "import_label": payload.import_label,
            "mapped_columns": warnings.get("mapped_columns", {}),
            "unmapped_columns": warnings.get("unmapped_columns", []),
            "status": "OPERATOR-SUPPLIED CSV — PROVIDER DOMAIN DECLARED, BYTES NOT AUTHENTICATED; NOT A SERVICE COMMITMENT",
        }

    @app.get("/api/projects/{pid}/intelligence/snapshots/{sid}/raw")
    def snapshot_raw(pid: str, sid: str):
        from fastapi.responses import PlainTextResponse

        with db() as con:
            project_exists(con, pid)
            r = con.execute(
                "SELECT r.csv_text,r.text_sha256 FROM intel_snapshot_raw r JOIN intel_snapshots s ON s.id=r.snapshot_id WHERE s.id=? AND s.project_id=?",
                (sid, pid),
            ).fetchone()
            if not r:
                raise HTTPException(404, "No retained source text for this snapshot")
            return PlainTextResponse(
                r["csv_text"],
                media_type="text/csv",
                headers={
                    "X-Content-SHA256": r["text_sha256"],
                    "Content-Disposition": f'attachment; filename="snapshot_{sid}_OPERATOR_SUPPLIED.csv"',
                },
            )

    @app.get("/api/projects/{pid}/intelligence/changes")
    def changes(pid: str):
        with db() as con:
            project_exists(con, pid)
            return [
                {
                    **dict(r),
                    "before": json.loads(r["old_json"]) if r["old_json"] else None,
                    "after": json.loads(r["new_json"]) if r["new_json"] else None,
                    "delta": json.loads(r["delta_json"]),
                }
                for r in con.execute(
                    "SELECT * FROM intel_changes WHERE project_id=? ORDER BY created_at DESC,rowid DESC LIMIT 300",
                    (pid,),
                )
            ]

    @app.post("/api/projects/{pid}/intelligence/proposals", status_code=201)
    def propose(pid: str, payload: ProposalIn):
        ts = now()
        ident = uid()
        with db() as con:
            project_exists(con, pid)
            change = con.execute(
                "SELECT * FROM intel_changes WHERE id=? AND project_id=?", (payload.change_id, pid)
            ).fetchone()
            if not change:
                raise HTTPException(422, "Change does not belong to this project")
            milestone = con.execute(
                "SELECT * FROM delivery_milestones WHERE id=? AND project_id=?", (payload.milestone_id, pid)
            ).fetchone()
            if not milestone:
                raise HTTPException(422, "Milestone does not belong to this project")
            if not con.execute(
                "SELECT id FROM power_paths WHERE id=? AND project_id=?", (milestone["path_id"], pid)
            ).fetchone():
                raise HTTPException(422, "Invalid milestone path")
            # RT-D05: completed milestones contribute zero modeled delay; a delay proposal would be approved with no effect.
            if milestone["status"] == "completed":
                raise HTTPException(422, "Milestone is completed; reopen it before proposing a delay")
            con.execute(
                "INSERT INTO intel_proposals(id,project_id,change_id,milestone_id,proposed_delay_months,reason,status,created_at,decided_at,base_delay_months,base_status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ident,
                    pid,
                    payload.change_id,
                    payload.milestone_id,
                    payload.proposed_delay_months,
                    payload.reason,
                    "pending",
                    ts,
                    "",
                    milestone["delay_months"],
                    milestone["status"],
                ),
            )
            audit(
                con,
                pid,
                "intelligence.milestone.proposed",
                ident,
                {
                    "change_id": payload.change_id,
                    "milestone_id": payload.milestone_id,
                    "delay_months": payload.proposed_delay_months,
                    "not_automatic": True,
                },
            )
        return {"id": ident, "status": "pending", "writes_to_financial_model": False, "writes_to_milestone": False}

    @app.get("/api/projects/{pid}/intelligence/proposals")
    def list_proposals(pid: str):
        with db() as con:
            project_exists(con, pid)
            return [
                dict(x)
                for x in con.execute(
                    "SELECT * FROM intel_proposals WHERE project_id=? ORDER BY created_at DESC", (pid,)
                )
            ]

    @app.post("/api/projects/{pid}/intelligence/proposals/{proposal_id}/{decision}")
    def decide(pid: str, proposal_id: str, decision: str):
        if decision not in ("approve", "reject"):
            raise HTTPException(422, "Only approve or reject")
        with db() as con:
            project_exists(con, pid)
            con.execute("BEGIN IMMEDIATE")
            p = con.execute("SELECT * FROM intel_proposals WHERE id=? AND project_id=?", (proposal_id, pid)).fetchone()
            if not p:
                raise HTTPException(404, "Proposal not found")
            if p["status"] != "pending":
                raise HTTPException(409, "Decision already recorded")
            newstate = "approved" if decision == "approve" else "rejected"
            if decision == "approve":
                # RT-D01/D02: refuse to apply a proposal drafted against a milestone state that has since changed
                # (another approval or a manual edit). The analyst must re-draft against the current estimate.
                m = con.execute(
                    "SELECT delay_months,status FROM delivery_milestones WHERE id=? AND project_id=?",
                    (p["milestone_id"], pid),
                ).fetchone()
                if not m:
                    raise HTTPException(422, "Milestone no longer available")
                if p["base_delay_months"] is not None and (
                    m["delay_months"] != p["base_delay_months"] or m["status"] != p["base_status"]
                ):
                    raise HTTPException(
                        409,
                        f"Stale proposal: milestone is now {m['delay_months']} months/{m['status']} (drafted against {p['base_delay_months']} months/{p['base_status']}); re-draft",
                    )
            con.execute("UPDATE intel_proposals SET status=?,decided_at=? WHERE id=?", (newstate, now(), proposal_id))
            # RT-D04: the originating source change records the review outcome.
            con.execute(
                "UPDATE intel_changes SET review_state=? WHERE id=? AND project_id=?",
                ("proposal_" + newstate, p["change_id"], pid),
            )
            if decision == "approve":
                con.execute(
                    "UPDATE delivery_milestones SET delay_months=?,source_note=?,updated_at=? WHERE id=? AND project_id=?",
                    (
                        p["proposed_delay_months"],
                        "Analyst-approved change proposal " + proposal_id + "; source remains unverified",
                        now(),
                        p["milestone_id"],
                        pid,
                    ),
                )
            audit(
                con,
                pid,
                "intelligence.proposal." + newstate,
                proposal_id,
                {
                    "source_change": p["change_id"],
                    "milestone_id": p["milestone_id"],
                    "delay_months": p["proposed_delay_months"],
                },
            )
            con.execute("COMMIT")
        return {
            "id": proposal_id,
            "decision": newstate,
            "requires_new_financial_scenario": True,
            "utility_confirmed": False,
        }

    @app.get("/api/projects/{pid}/intelligence/proposals/{proposal_id}/impact")
    def proposed_finance_impact(pid: str, proposal_id: str, source_scenario_id: str | None = None):
        """Read-only, never changes a milestone, creates a financial run, or unlocks Risk gates."""
        with db() as con:
            project_exists(con, pid)
            p = con.execute("SELECT * FROM intel_proposals WHERE id=? AND project_id=?", (proposal_id, pid)).fetchone()
            if not p:
                raise HTTPException(404, "Proposal not found")
            if p["status"] != "pending":
                raise HTTPException(
                    409, "Preview only applies before approval; rerun an approved milestone through v26.3 sensitivity"
                )
            milestone = con.execute(
                "SELECT * FROM delivery_milestones WHERE id=? AND project_id=?", (p["milestone_id"], pid)
            ).fetchone()
            if not milestone:
                raise HTTPException(422, "Milestone no longer available")
            path = con.execute(
                "SELECT * FROM power_paths WHERE id=? AND project_id=?", (milestone["path_id"], pid)
            ).fetchone()
            if not path:
                raise HTTPException(422, "Power path unavailable")
            # v27.1: the canonical schedule engine (server/schedule27.py) - the same function every interface uses.
            from server import schedule27

            try:
                before_sched = schedule27.schedule_for(con, pid, path["id"])
                after_sched = schedule27.schedule_for(
                    con, pid, path["id"], {p["milestone_id"]: p["proposed_delay_months"]}
                )
            except schedule27.ScheduleError as exc:
                raise HTTPException(422, str(exc))
            before_delay = before_sched["effective_delay_months"]
            after_delay = after_sched["effective_delay_months"]
            # RT-E05: the analyst may name the base; the default is deterministic (insertion order), never a random-id tie-break.
            if source_scenario_id:
                base = con.execute(
                    "SELECT * FROM scenarios WHERE id=? AND project_id=? AND mode='underwrite'",
                    (source_scenario_id, pid),
                ).fetchone()
                if base is None:
                    raise HTTPException(404, "Underwriting scenario not found in this project")
                if json.loads(base["config_json"]).get("powerPathLink"):
                    raise HTTPException(422, "Preview requires an original unlinked base scenario")
                selection = "analyst_selected"
            else:
                rows_ = con.execute(
                    "SELECT * FROM scenarios WHERE project_id=? AND mode='underwrite' ORDER BY created_at,rowid", (pid,)
                ).fetchall()
                base = next((r for r in rows_ if not json.loads(r["config_json"]).get("powerPathLink")), None)
                selection = "default_oldest_unlinked"
            if base is None:
                raise HTTPException(422, "No original underwriting scenario available")
            config = json.loads(base["config_json"])
        outputs = []
        for delay, sched in ((before_delay, before_sched), (after_delay, after_sched)):
            x = schedule27.apply_to_config(config, dict(path), sched)
            try:
                r = calculate("underwrite", x)
                v = r.get("summary", {})
                outputs.append(
                    {
                        "delay_months": delay,
                        "schedule_version": sched["schedule_version"],
                        "revised_cod_month": sched["revised_cod_month"],
                        "critical_path": sched["critical_path"],
                        "npvM": v.get("npvM"),
                        "minDSCR": v.get("minDSCR"),
                        "defaulted": v.get("defaulted"),
                        "breach_months": len(v.get("breachMonths") or []),
                        "assumptions_hash": hashlib.sha256(dump(x).encode()).hexdigest(),
                    }
                )
            except HTTPException as exc:
                outputs.append(
                    {
                        "delay_months": delay,
                        "schedule_version": sched["schedule_version"],
                        "calculation_blocked": exc.detail,
                    }
                )
        b, a = outputs
        d = (
            (a["npvM"] - b["npvM"])
            if isinstance(b.get("npvM"), (float, int)) and isinstance(a.get("npvM"), (float, int))
            else None
        )
        return {
            "proposal_id": proposal_id,
            "source_record_change_id": p["change_id"],
            "before": b,
            "proposed": a,
            "npv_deltaM": d,
            "schedule_method": before_sched["method"],
            "source_scenario_id": base["id"],
            "source_scenario_name": base["name"],
            "base_selection": selection,
            "source_version": base["version"],
            "valuation_allowed": False,
            "utility_delivery_verified": False,
            "persisted_changes": False,
            "warning": "Synthetic comparison, not a project valuation. Public generation queue changes do NOT imply large-load service impact; this linkage is analyst-proposed and unverified.",
        }

    @app.get("/api/projects/{pid}/agents/meetings")
    def meetings(pid: str):
        with db() as con:
            project_exists(con, pid)
            return [
                {**dict(r), "result": json.loads(r["result_json"])}
                for r in con.execute("SELECT * FROM agent_meetings WHERE project_id=? ORDER BY created_at DESC", (pid,))
            ]

    @app.get("/api/projects/{pid}/agents/meetings/{mid}")
    def meeting(pid: str, mid: str):
        with db() as con:
            project_exists(con, pid)
            r = con.execute("SELECT * FROM agent_meetings WHERE id=? AND project_id=?", (mid, pid)).fetchone()
            if not r:
                raise HTTPException(404, "No such meeting")
            return {
                **dict(r),
                "result": json.loads(r["result_json"]),
                "messages": [
                    dict(m)
                    for m in con.execute("SELECT * FROM agent_messages WHERE meeting_id=? ORDER BY rowid", (mid,))
                ],
            }

    @app.post("/api/projects/{pid}/agents/meetings", status_code=201)
    def plan_meeting(pid: str, payload: MeetingIn):
        from agents.council import offline_council, ROLES

        with db() as con:
            project_exists(con, pid)
            openchanges = [
                dict(x)
                for x in con.execute(
                    "SELECT source_key,record_id,delta_json FROM intel_changes WHERE project_id=? ORDER BY created_at DESC LIMIT 15",
                    (pid,),
                )
            ]
            openproposals = con.execute(
                "SELECT COUNT(*) FROM intel_proposals WHERE project_id=? AND status='pending'", (pid,)
            ).fetchone()[0]
            digest = hashlib.sha256(dump(openchanges).encode()).hexdigest()
            result = offline_council(payload.mission, openchanges, openproposals)
            mid = uid()
            ts = now()
            con.execute(
                "INSERT INTO agent_meetings VALUES(?,?,?,?,?,?,?,?,?,?)",
                (mid, pid, "OFFLINE_RULES", "complete", payload.mission, digest, "", dump(result), ts, ts),
            )
            for r in result["messages"]:
                con.execute(
                    "INSERT INTO agent_messages VALUES(?,?,?,?,?,?)",
                    (uid(), mid, r["role"], r["content"], "OFFLINE_RULES", ts),
                )
            audit(
                con,
                pid,
                "agents.offline_review",
                mid,
                {"source_changes": len(openchanges), "mode": "OFFLINE_RULES", "api_calls": 0},
            )
        return {
            "id": mid,
            "status": "complete",
            "mode": "OFFLINE_RULES",
            "roles": ROLES,
            "api_calls": 0,
            "external_actions": 0,
            "report": result,
        }
