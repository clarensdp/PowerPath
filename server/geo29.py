"""Local national geographic registry and versioned parcel store.
SQLite R*Tree is the local spatial index. No national parcel subscription is implied.
"""

import hashlib, json, math, re, sqlite3, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException, Query
from pydantic import BaseModel, Field

STATE_FIPS = {
    "01",
    "02",
    "04",
    "05",
    "06",
    "08",
    "09",
    "10",
    "11",
    "12",
    "13",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "23",
    "24",
    "25",
    "26",
    "27",
    "28",
    "29",
    "30",
    "31",
    "32",
    "33",
    "34",
    "35",
    "36",
    "37",
    "38",
    "39",
    "40",
    "41",
    "42",
    "44",
    "45",
    "46",
    "47",
    "48",
    "49",
    "50",
    "51",
    "53",
    "54",
    "55",
    "56",
}
SCHEMA = """CREATE TABLE IF NOT EXISTS geo30_latest(parcel_key TEXT PRIMARY KEY,record_id INTEGER NOT NULL REFERENCES geo29_parcels(rid));
CREATE TABLE IF NOT EXISTS geo29_sources(
 id TEXT PRIMARY KEY,name TEXT NOT NULL,state_fips TEXT NOT NULL,county_fips TEXT NOT NULL,
 source_url TEXT NOT NULL,license_note TEXT NOT NULL,coverage_scope TEXT NOT NULL,
 provenance TEXT NOT NULL,active_version TEXT);
CREATE TABLE IF NOT EXISTS geo29_versions(
 id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES geo29_sources(id),retrieved_at TEXT NOT NULL,
 content_hash TEXT NOT NULL,feature_count INTEGER NOT NULL,metadata_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS geo29_parcels(
 rid INTEGER PRIMARY KEY AUTOINCREMENT,parcel_key TEXT NOT NULL,workspace_id TEXT NOT NULL,
 source_id TEXT NOT NULL REFERENCES geo29_sources(id),version_id TEXT NOT NULL REFERENCES geo29_versions(id),
 local_pin TEXT NOT NULL,area_acres REAL,feature_json TEXT NOT NULL,
 UNIQUE(parcel_key,version_id));
CREATE INDEX IF NOT EXISTS geo29_key ON geo29_parcels(parcel_key);
CREATE INDEX IF NOT EXISTS geo29_workspace ON geo29_parcels(workspace_id);
CREATE VIRTUAL TABLE IF NOT EXISTS geo29_bounds USING rtree(rid,minx,maxx,miny,maxy);
CREATE TABLE IF NOT EXISTS geo29_saved_versions(
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 parcel_id TEXT NOT NULL,record_id INTEGER NOT NULL REFERENCES geo29_parcels(rid),
 PRIMARY KEY(project_id,parcel_id));
"""


def stamp():
    return datetime.now(timezone.utc).isoformat()


def safe_json(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False)


def geometry_bounds(geometry):
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        raise ValueError("Only Polygon/MultiPolygon geometry is supported")
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    if not polygons:
        raise ValueError("Empty geometry")
    points = []
    for polygon in polygons:
        if not polygon:
            raise ValueError("Empty polygon")
        for ring in polygon:
            if len(ring) < 4 or ring[0][:2] != ring[-1][:2]:
                raise ValueError("Polygon rings must be closed and contain at least four points")
            for pt in ring:
                if len(pt) < 2 or any(
                    isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in pt[:2]
                ):
                    raise ValueError("Non-finite coordinate")
                if not -180 <= pt[0] <= 180 or not -90 <= pt[1] <= 90:
                    raise ValueError("GeoJSON must use WGS84 longitude/latitude")
                points.append(pt[:2])
                if len(points) > 50000:
                    raise ValueError("Parcel geometry exceeds 50,000 vertices")
    xs, ys = zip(*points)
    return min(xs), max(xs), min(ys), max(ys)


class GeoStore:
    def __init__(self, db, root):
        self.db = db
        self.root = Path(root)

    def initialize(self):
        with self.db() as con:
            con.executescript(SCHEMA)
        # PostgreSQL source imports are operator migrations, never app bootstrap writes.
        import os

        if os.environ.get("POWERPATH_DATABASE_URL"):
            return
        data = json.loads((self.root / "data_sources/loudoun_parcels.geojson").read_text())
        src = data["powerpath_source"]
        self.ingest(
            {
                "id": "loudoun-county",
                "name": "Loudoun County parcel pilot",
                "state_fips": "51",
                "county_fips": "107",
                "source_url": src["layer_url"],
                "license_note": "Public county GIS; retain source attribution and county limitations. Not a survey or listing.",
                "coverage_scope": src["scope"],
                "provenance": "official_public_snapshot",
                "retrieved_at": src["retrieved_at"],
            },
            data,
            "PA_MCPI",
            "PA_LEGAL_SQFT",
            legacy=True,
        )
        # Existing v28 shortlists acquire an immutable link on first migration.
        with self.db() as con:
            for row in con.execute("SELECT project_id,parcel_id FROM parcel_shortlist28"):
                r = con.execute(
                    "SELECT p.rid FROM geo29_parcels p JOIN geo29_sources s ON s.id=p.source_id AND s.active_version=p.version_id WHERE p.workspace_id=?",
                    (row["parcel_id"],),
                ).fetchone()
                if r:
                    con.execute(
                        "INSERT OR IGNORE INTO geo29_saved_versions VALUES(?,?,?)",
                        (row["project_id"], row["parcel_id"], r["rid"]),
                    )

    def ingest(self, source, collection, id_field, area_field=None, legacy=False):
        required = [
            "id",
            "name",
            "state_fips",
            "county_fips",
            "source_url",
            "license_note",
            "coverage_scope",
            "retrieved_at",
        ]
        if any(not isinstance(source.get(k), str) or not source[k].strip() for k in required):
            raise ValueError("Complete source identity, retrieval date, attribution and coverage scope are required")
        if not re.fullmatch("[a-z0-9-]{2,24}", source["id"]):
            raise ValueError("Source ID must be a 2–24 character lowercase slug")
        if source["state_fips"] not in STATE_FIPS or not re.fullmatch(r"\d{3}", source["county_fips"]):
            raise ValueError("Use a supported state FIPS and three-digit county code")
        url = urllib.parse.urlsplit(source["source_url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Source must have a credential-free HTTPS citation")
        retrieved = datetime.fromisoformat(source["retrieved_at"].replace("Z", "+00:00"))
        if not retrieved.tzinfo or retrieved > datetime.now(timezone.utc):
            raise ValueError("Retrieval time must be timezone-aware and not in the future")
        fs = collection.get("features", [])
        if collection.get("type") != "FeatureCollection" or not 1 <= len(fs) <= 100000:
            raise ValueError("Import requires 1–100,000 parcel features per batch")
        digest = hashlib.sha256(
            safe_json(
                {"source": source, "collection": collection, "id_field": id_field, "area_field": area_field}
            ).encode()
        ).hexdigest()
        version = source["id"] + ":" + digest[:24]
        prepared = []
        seen = set()
        for f in fs:
            pin = str(f.get("properties", {}).get(id_field, ""))
            if not re.fullmatch(r"[A-Za-z0-9_. -]{1,40}", pin):
                raise ValueError("Parcel IDs must be 1–40 safe identifier characters")
            if pin in seen:
                raise ValueError("Duplicate parcel ID within source batch")
            seen.add(pin)
            bounds = geometry_bounds(f["geometry"])
            key = f"{source['state_fips']}{source['county_fips']}:{source['id']}:{pin}"
            workspace_id = pin if legacy else key
            raw = f["properties"].get(area_field) if area_field else None
            if raw is not None and (
                isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(raw) or raw < 0
            ):
                raise ValueError("Area must be a finite nonnegative square-foot value")
            area = raw / 43560 if raw is not None else None
            # Preserve native properties and canonical aliases for the v28 inspector.
            props = {
                **f["properties"],
                "PA_MCPI": pin,
                "PA_LEGAL_SQFT": raw,
                "powerpath_id": key,
                "workspace_id": workspace_id,
                "state_fips": source["state_fips"],
                "county_fips": source["county_fips"],
                "source_id": source["id"],
                "version_id": version,
                "source_url": source["source_url"],
                "retrieved_at": source["retrieved_at"],
                "source_provenance": source.get("provenance", "user_supplied"),
            }
            prepared.append(
                (
                    key,
                    workspace_id,
                    source["id"],
                    version,
                    pin,
                    area,
                    safe_json({"type": "Feature", "properties": props, "geometry": f["geometry"]}),
                    bounds,
                )
            )
        with self.db() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                old = con.execute("SELECT * FROM geo29_sources WHERE id=?", (source["id"],)).fetchone()
                if old and (old["state_fips"] != source["state_fips"] or old["county_fips"] != source["county_fips"]):
                    raise ValueError("A source ID cannot move between jurisdictions")
                if con.execute("SELECT 1 FROM geo29_versions WHERE id=?", (version,)).fetchone():
                    con.execute("COMMIT")
                    return {"version_id": version, "count": len(fs), "idempotent": True}
                con.execute(
                    "INSERT INTO geo29_sources VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,source_url=excluded.source_url,license_note=excluded.license_note,coverage_scope=excluded.coverage_scope,provenance=excluded.provenance",
                    (
                        source["id"],
                        source["name"],
                        source["state_fips"],
                        source["county_fips"],
                        source["source_url"],
                        source["license_note"],
                        source["coverage_scope"],
                        source.get("provenance", "user_supplied"),
                        None,
                    ),
                )
                con.execute(
                    "INSERT INTO geo29_versions VALUES(?,?,?,?,?,?)",
                    (version, source["id"], source["retrieved_at"], digest, len(fs), safe_json(source)),
                )
                for key, wid, src, ver, pin, area, body, b in prepared:
                    rid = con.execute(
                        "INSERT INTO geo29_parcels(parcel_key,workspace_id,source_id,version_id,local_pin,area_acres,feature_json) VALUES(?,?,?,?,?,?,?)",
                        (key, wid, src, ver, pin, area, body),
                    ).lastrowid
                    con.execute("INSERT INTO geo29_bounds VALUES(?,?,?,?,?)", (rid, *b))
                con.execute("UPDATE geo29_sources SET active_version=? WHERE id=?", (version, source["id"]))
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
        return {"version_id": version, "count": len(fs), "idempotent": False}

    def get(self, identifier, project=None):
        with self.db() as con:
            row = None
            if project:
                row = con.execute(
                    "SELECT p.* FROM geo29_parcels p JOIN geo29_saved_versions v ON v.record_id=p.rid WHERE v.project_id=? AND v.parcel_id=?",
                    (project, identifier),
                ).fetchone()
            if not row:
                row = con.execute(
                    "SELECT p.* FROM geo29_parcels p JOIN geo29_sources s ON s.id=p.source_id WHERE ((s.provenance!='public_live_viewport' AND s.active_version=p.version_id) OR p.rid IN (SELECT record_id FROM geo30_latest)) AND (p.workspace_id=? OR p.parcel_key=?)",
                    (identifier, identifier),
                ).fetchone()
            return dict(row) if row else None

    def pin(self, project, identifier):
        record = self.get(identifier, project)
        if not record:
            raise HTTPException(404, "Parcel not in a connected source")
        with self.db() as con:
            con.execute(
                "INSERT OR IGNORE INTO geo29_saved_versions VALUES(?,?,?)", (project, identifier, record["rid"])
            )
        return record

    def query(self, bbox=None, state=None, min_acres=0, pin="", limit=200, offset=0):
        where = [
            "((s.provenance!='public_live_viewport' AND s.active_version=p.version_id) OR p.rid IN (SELECT record_id FROM geo30_latest))"
        ]
        args = []
        join = ""
        if bbox:
            west, south, east, north = bbox
            join = " JOIN geo29_bounds b ON b.rid=p.rid"
            where += ["b.maxx>=? AND b.minx<=? AND b.maxy>=? AND b.miny<=?"]
            args += [west, east, south, north]
        if state:
            where += ["s.state_fips=?"]
            args += [state]
        if min_acres:
            where += ["p.area_acres>=?"]
            args += [min_acres]
        if pin:
            # Literal substring matching; SQL wildcard characters have no special meaning.
            where += ["instr(lower(p.local_pin),lower(?))>0"]
            args += [pin]
        sql = " FROM geo29_parcels p JOIN geo29_sources s ON s.id=p.source_id" + join + " WHERE " + " AND ".join(where)
        with self.db() as con:
            count = con.execute("SELECT COUNT(*)" + sql, args).fetchone()[0]
            rows = con.execute(
                "SELECT p.feature_json" + sql + " ORDER BY p.parcel_key LIMIT ? OFFSET ?", args + [limit, offset]
            ).fetchall()
        return {
            "type": "FeatureCollection",
            "features": [json.loads(r["feature_json"]) for r in rows],
            "total_matches": count,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(rows) < count,
            "selection": "parcel bounding-box overlap, not engineering eligibility",
        }

    def registry(self):
        with self.db() as con:
            return [
                dict(r)
                for r in con.execute(
                    """SELECT s.*,v.retrieved_at,CASE WHEN s.provenance='public_live_viewport' THEN (SELECT count(*) FROM geo30_latest l JOIN geo29_parcels p ON p.rid=l.record_id WHERE p.source_id=s.id) ELSE v.feature_count END AS feature_count,v.content_hash,
    (SELECT count(*) FROM geo29_versions WHERE source_id=s.id) AS retained_versions
    FROM geo29_sources s JOIN geo29_versions v ON v.id=s.active_version ORDER BY s.state_fips,s.id"""
                )
            ]


def parse_bbox(value):
    try:
        b = [float(x) for x in value.split(",")]
        if len(b) != 4 or not all(math.isfinite(x) for x in b):
            raise ValueError()
        w, s, e, n = b
        if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
            raise ValueError()
        return b
    except (ValueError, TypeError):
        raise HTTPException(422, "bbox must be west,south,east,north in WGS84; split antimeridian viewports")


def install(app, store, root):
    from server.public_parcels30 import install as install_public

    install_public(app, store)
    states = json.loads((root / "data_sources/us_states.geojson").read_text())
    states["features"] = [f for f in states["features"] if f["properties"]["STATE"] in STATE_FIPS]
    counties = json.loads((root / "data_sources/us_county_locations.json").read_text())
    state_index = {f["properties"]["STATE"]: f["properties"] for f in states["features"]}
    locations = []
    for f in states["features"]:
        p = f["properties"]
        locations.append(
            {
                "kind": "state",
                "label": p["NAME"],
                "state_fips": p["STATE"],
                "abbreviation": p["STUSAB"],
                "latitude": float(p["INTPTLAT"]),
                "longitude": float(p["INTPTLON"]),
            }
        )
    for p in counties["records"]:
        if p["STATE"] not in state_index:
            continue
        locations.append(
            {
                "kind": "county",
                "label": p["NAME"] + ", " + state_index[p["STATE"]]["STUSAB"],
                "state_fips": p["STATE"],
                "county_fips": p["COUNTY"],
                "latitude": float(p["INTPTLAT"]),
                "longitude": float(p["INTPTLON"]),
            }
        )

    @app.get("/api/geo29/states")
    def get_states():
        return states

    @app.get("/api/geo29/coverage")
    def coverage():
        sources = store.registry()
        return {
            "state_count": 50,
            "district_of_columbia": True,
            "states": [
                {
                    "fips": p["STATE"],
                    "name": p["NAME"],
                    "abbreviation": p["STUSAB"],
                    "status": (
                        "partial_parcel_snapshot"
                        if any(s["state_fips"] == p["STATE"] for s in sources)
                        else "navigation_only"
                    ),
                    "parcel_records": sum(s["feature_count"] for s in sources if s["state_fips"] == p["STATE"]),
                }
                for p in state_index.values()
            ],
            "sources": sources,
            "parcel_coverage": "Only registered source footprints; state navigation does not imply statewide parcel coverage.",
            "state_boundary_source": states["powerpath_source"],
            "county_location_source": counties["powerpath_source"],
        }

    @app.get("/api/geo29/locations")
    def search(q: str = Query(min_length=2, max_length=150), state: str | None = None):
        if state and state not in STATE_FIPS:
            raise HTTPException(422, "Unknown state FIPS")
        words = q.casefold().strip().split()
        hits = [
            l
            for l in locations
            if (not state or l["state_fips"] == state)
            and all(w in (l["label"] + " " + l.get("abbreviation", "")).casefold() for w in words)
        ]
        hits.sort(key=lambda l: (l["kind"] != "state", l["label"].casefold() != q.casefold(), l["label"]))
        return {
            "results": hits[:20],
            "total_matches": len(hits),
            "source": "U.S. Census Bureau TIGERweb; state/county navigation only",
        }

    @app.get("/api/geo29/parcels")
    def parcels(
        bbox: str | None = None,
        state: str | None = None,
        min_acres: float = Query(default=0, ge=0, le=1000000),
        pin: str = Query(default="", max_length=80),
        limit: int = Query(default=200, ge=1, le=500),
        offset: int = Query(default=0, ge=0, le=1000000),
    ):
        if state and state not in STATE_FIPS:
            raise HTTPException(422, "Unknown state FIPS")
        return store.query(parse_bbox(bbox) if bbox else None, state, min_acres, pin, limit, offset)

    @app.get("/api/geo29/geocode")
    def geocode(address: str = Query(min_length=5, max_length=300), consent: bool = False):
        if not consent:
            raise HTTPException(422, "Explicit consent is required to send the address to Census")
        params = {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
        url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urllib.parse.urlencode(params)
        try:
            with urllib.request.urlopen(url, timeout=12) as r:
                raw = r.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("Oversized response")
            data = json.loads(raw)
            results = []
            for match in data.get("result", {}).get("addressMatches", [])[:5]:
                x, y = float(match["coordinates"]["x"]), float(match["coordinates"]["y"])
                if math.isfinite(x) and math.isfinite(y) and -180 <= x <= 180 and -90 <= y <= 90:
                    results.append(
                        {"label": str(match["matchedAddress"])[:500], "longitude": x, "latitude": y, "kind": "address"}
                    )
            return {
                "results": results,
                "source": "U.S. Census Bureau Geocoder",
                "meaning": "Address interpolation/location match, not a parcel, ownership record or power-service commitment",
            }
        except Exception as exc:
            raise HTTPException(
                503, "Census address lookup unavailable; state/county navigation and connected parcels remain available"
            ) from exc
