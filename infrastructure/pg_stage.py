"""PowerPath v30.8.1 PostgreSQL staging migration (never a live application cutover).

Safety properties:
- Read-only source inspection plus SQLite online backup to a private temporary file.
- Requires a fresh, dedicated PostgreSQL schema; never drops/overwrites an existing schema.
- Uses PostgreSQL DOUBLE PRECISION for SQLite REAL to preserve financial precision.
- Copies values/IDs as-is, reconciles every row and material financial fingerprints.
- Excludes SQLite RTree internal tables; creates PostGIS polygon geometry from source GeoJSON.
- Does not enable app-side PostgreSQL writes or claim tenant isolation for legacy tables.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, create_engine, text, insert, select, inspect
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.sqltypes import REAL, Float

from infrastructure.db_audit import assess

STAGING_SCHEMA = "powerpath_stage_v3081"
SKIP_PREFIXES = ("sqlite_", "geo29_bounds")
REQUIRED = (
    "projects",
    "scenarios",
    "runs",
    "evidence",
    "geo29_parcels",
    "geo29_versions",
    "geo29_sources",
    "v27_project_tenants",
)
FINANCIAL_COLUMNS = (
    "id",
    "scenario_id",
    "scenario_version",
    "mode",
    "engine_sha256",
    "finance_sha256",
    "input_json",
    "summary_json",
    "rows_json",
    "created_at",
    "label",
)


def sha(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def quoted_identifier(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Unsafe identifier in database snapshot")
    return '"' + name + '"'


def canonical_row(row: dict) -> dict:
    return {key: (val.hex() if isinstance(val, bytes) else val) for key, val in sorted(row.items())}


def data_digest(rows: list[dict]) -> str:
    return sha(
        sorted((canonical_row(r) for r in rows), key=lambda r: json.dumps(r, sort_keys=True, separators=(",", ":")))
    )


def source_snapshot(source: Path, destination: Path) -> None:
    """Use online backup API, never dump a live SQLite DB with shutil.copy()."""
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source does not exist: {source}")
    uri = "file:" + str(source.resolve()) + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as reader:
        with sqlite3.connect(destination) as target:
            reader.backup(target)
    os.chmod(destination, 0o600)


def install_snapshot_only_schemas(snapshot: Path) -> None:
    """Complete legacy agent schema on disposable snapshot; never modify source."""
    from contextlib import contextmanager
    from server.agent_ops_store import install_migrations

    @contextmanager
    def isolated_db():
        con = sqlite3.connect(snapshot, isolation_level=None)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
        finally:
            con.close()

    install_migrations(isolated_db)


def tables_in_snapshot(con: sqlite3.Connection) -> list[str]:
    names = []
    for name, ddl in con.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name"):
        if name.startswith(SKIP_PREFIXES) or not ddl or "CREATE VIRTUAL TABLE" in ddl.upper():
            continue
        quoted_identifier(name)
        names.append(name)
    if set(REQUIRED) - set(names):
        raise ValueError("Snapshot missing required canonical tables: " + ", ".join(sorted(set(REQUIRED) - set(names))))
    return names


def row_dicts(con: sqlite3.Connection, table: str) -> list[dict]:
    con.row_factory = sqlite3.Row
    return [dict(r) for r in con.execute("SELECT * FROM " + quoted_identifier(table))]


def manifest_from_connection(con: sqlite3.Connection, names: list[str]) -> dict:
    tables = {name: {"count": len(rows := row_dicts(con, name)), "sha256": data_digest(rows)} for name in names}
    financial_rows = row_dicts(con, "runs")
    financial = [{col: row[col] for col in FINANCIAL_COLUMNS} for row in financial_rows]
    geometry_rows = row_dicts(con, "geo29_parcels")
    geom_sources = [
        {"rid": row["rid"], "feature_json_sha256": hashlib.sha256(row["feature_json"].encode()).hexdigest()}
        for row in geometry_rows
    ]
    return {
        "format": "PP-STAGE-MANIFEST-1",
        "tables": tables,
        "financial_output_sha256": data_digest(financial),
        "geometry_source_sha256": data_digest(geom_sources),
        "row_count": sum(t["count"] for t in tables.values()),
        "source_table_count": len(names),
    }


def reflected_metadata(db_path: Path, names: list[str]):
    src = create_engine("sqlite:///" + str(db_path), future=True)
    metadata = MetaData()
    metadata.reflect(bind=src, only=names)
    # SQLite REAL is binary64; PostgreSQL REAL is binary32. Preserve exact model outputs.
    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, REAL) or (isinstance(col.type, Float) and col.type.precision is None):
                col.type = Float(precision=53)
    return src, metadata


def make_pg_ddl(metadata: MetaData) -> str:
    dialect = postgresql.dialect()
    lines = [f"CREATE SCHEMA {STAGING_SCHEMA};", f"CREATE EXTENSION IF NOT EXISTS postgis;"]
    # DDL is explicit about target schema; SQLAlchemy's table keys stay unqualified.
    from sqlalchemy.schema import CreateTable, AddConstraint

    for t in metadata.sorted_tables:
        lines.append(
            str(
                CreateTable(t).compile(
                    dialect=dialect, schema_translate_map={None: STAGING_SCHEMA}, render_schema_translate=True
                )
            ).strip()
            + ";"
        )
    for t in metadata.sorted_tables:
        for idx in t.indexes:
            stmt = str(
                CreateIndex(idx).compile(
                    dialect=dialect, schema_translate_map={None: STAGING_SCHEMA}, render_schema_translate=True
                )
            )
            lines.append(stmt + ";")
    # Preview only. Actual install uses SQLAlchemy schema_translate_map to correctly qualify FKs.
    return "\n\n".join(lines) + "\n"


def stage_extensions_sql() -> list[str]:
    s = STAGING_SCHEMA
    return [
        f"""CREATE TABLE {s}.pp_import_audit_v1 (
            id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            source_row_count INTEGER NOT NULL,
            source_finance_sha256 TEXT NOT NULL,
            manifest_sha256 TEXT NOT NULL,
            table_counts_json JSONB NOT NULL,
            success BOOLEAN NOT NULL DEFAULT true
        )""",
        f"""CREATE TABLE {s}.pp_parcel_geometry_v1 (
            record_id INTEGER PRIMARY KEY REFERENCES {s}.geo29_parcels(rid) ON DELETE RESTRICT,
            source_version_id TEXT NOT NULL REFERENCES {s}.geo29_versions(id),
            geometry_fingerprint_md5 TEXT NOT NULL,
            geom geometry(Geometry,4326) NOT NULL,
            CONSTRAINT pp_geometry_polygon CHECK (ST_GeometryType(geom) IN ('ST_Polygon','ST_MultiPolygon')),
            CONSTRAINT pp_geometry_valid CHECK (ST_IsValid(geom))
        )""",
        f"CREATE INDEX pp_parcel_geometry_gix ON {s}.pp_parcel_geometry_v1 USING GIST (geom)",
        f"""CREATE TABLE {s}.pp_overlay_sources_v1 (
            id TEXT PRIMARY KEY, label TEXT NOT NULL, source_url TEXT NOT NULL,
            source_sha256 TEXT NOT NULL, source_version TEXT NOT NULL,
            complete_coverage BOOLEAN NOT NULL DEFAULT false,
            verified_at TIMESTAMPTZ, retrieved_at TIMESTAMPTZ NOT NULL,
            review_state TEXT NOT NULL DEFAULT 'unverified'
              CHECK (review_state IN ('unverified','reviewed','rejected'))
        )""",
        f"""CREATE TABLE {s}.pp_overlay_features_v1 (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES {s}.pp_overlay_sources_v1(id),
            constraint_kind TEXT NOT NULL, source_feature_id TEXT NOT NULL,
            geom geometry(Geometry,4326) NOT NULL,
            CONSTRAINT pp_overlay_polygon CHECK (ST_GeometryType(geom) IN ('ST_Polygon','ST_MultiPolygon')),
            CONSTRAINT pp_overlay_valid CHECK (ST_IsValid(geom)),
            UNIQUE(source_id,source_feature_id)
        )""",
        f"CREATE INDEX pp_overlay_geom_gix ON {s}.pp_overlay_features_v1 USING GIST (geom)",
        f"""CREATE OR REPLACE VIEW {s}.pp_parcel_overlay_coverage_v1 AS
            SELECT p.record_id, o.id AS source_id,
                   (o.complete_coverage AND o.review_state='reviewed') AS known_complete,
                   o.review_state, o.source_version, o.retrieved_at
            FROM {s}.pp_parcel_geometry_v1 p CROSS JOIN {s}.pp_overlay_sources_v1 o""",
        f"""CREATE OR REPLACE VIEW {s}.pp_parcel_constraint_intersections_v1 AS
            SELECT p.record_id, f.source_id, f.constraint_kind,
              ST_Area(ST_UnaryUnion(ST_Collect(ST_CollectionExtract(ST_Intersection(p.geom,f.geom),3)))::geography)/4046.8564224 AS affected_acres,
              ST_Area(p.geom::geography)/4046.8564224 AS parcel_acres,
              bool_and(o.complete_coverage AND o.review_state='reviewed') AS layer_coverage_verified
            FROM {s}.pp_parcel_geometry_v1 p
            JOIN {s}.pp_overlay_features_v1 f ON ST_Intersects(p.geom,f.geom)
            JOIN {s}.pp_overlay_sources_v1 o ON o.id=f.source_id
            GROUP BY p.record_id,f.source_id,f.constraint_kind,p.geom""",
        # v30.8.2: invalid source geometries are quarantined with their PostGIS reason instead of aborting the whole
        # import (the archived importer failed on one self-intersecting Loudoun ring; the live DB was loaded by an
        # uncommitted variant). Nothing is repaired or dropped silently: every parcel is either valid or quarantined.
        f"""CREATE TABLE {s}.pp_parcel_geometry_quarantine_v1 (
            record_id INTEGER PRIMARY KEY REFERENCES {s}.geo29_parcels(rid) ON DELETE RESTRICT,
            source_version_id TEXT NOT NULL REFERENCES {s}.geo29_versions(id),
            geometry_fingerprint_md5 TEXT NOT NULL,
            reason TEXT NOT NULL,
            quarantined_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
        f"""INSERT INTO {s}.pp_parcel_geometry_quarantine_v1(record_id,source_version_id,geometry_fingerprint_md5,reason)
            SELECT rid,version_id,md5(feature_json),
                   coalesce(ST_IsValidReason(g),'not a valid polygon') || CASE WHEN ST_GeometryType(g) IN ('ST_Polygon','ST_MultiPolygon') THEN '' ELSE ' / type '||ST_GeometryType(g) END
            FROM (SELECT rid,version_id,feature_json,ST_SetSRID(ST_GeomFromGeoJSON((feature_json::jsonb->'geometry')::text),4326) g FROM {s}.geo29_parcels) x
            WHERE NOT ST_IsValid(g) OR ST_GeometryType(g) NOT IN ('ST_Polygon','ST_MultiPolygon')""",
        f"""INSERT INTO {s}.pp_parcel_geometry_v1(record_id,source_version_id,geometry_fingerprint_md5,geom)
            SELECT rid,version_id,md5(feature_json),
                   ST_SetSRID(ST_GeomFromGeoJSON((feature_json::jsonb->'geometry')::text),4326)
            FROM {s}.geo29_parcels
            WHERE rid NOT IN (SELECT record_id FROM {s}.pp_parcel_geometry_quarantine_v1)""",
        f"""CREATE TABLE {s}.pp_footprint_assessments_v1 (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL REFERENCES {s}.projects(id) ON DELETE RESTRICT,
            record_id INTEGER NOT NULL REFERENCES {s}.pp_parcel_geometry_v1(record_id) ON DELETE RESTRICT,
            source_hash TEXT NOT NULL, assessment_sha256 TEXT NOT NULL UNIQUE,
            results_json JSONB NOT NULL, source_evidence_json JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
        f"CREATE INDEX pp_footprint_project_idx ON {s}.pp_footprint_assessments_v1(project_id)",
        f"""CREATE TABLE {s}.pp_footprint_review_events_v1 (
            id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL REFERENCES {s}.pp_footprint_assessments_v1(id) ON DELETE RESTRICT,
            actor_id TEXT NOT NULL, decision TEXT NOT NULL CHECK (decision IN ('acknowledged','rejected')),
            reason TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )""",
        # Strict append-only: even reviewers cannot mutate source results; review separate later.
        f"""CREATE OR REPLACE FUNCTION {s}.refuse_footprint_mutation() RETURNS trigger
           LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Immutable footprint assessment'; END $$""",
        f"""CREATE TRIGGER pp_footprint_immutable BEFORE UPDATE OR DELETE ON {s}.pp_footprint_assessments_v1
           FOR EACH ROW EXECUTE FUNCTION {s}.refuse_footprint_mutation()""",
        f"""CREATE TRIGGER pp_footprint_review_immutable BEFORE UPDATE OR DELETE ON {s}.pp_footprint_review_events_v1
           FOR EACH ROW EXECUTE FUNCTION {s}.refuse_footprint_mutation()""",
        f"""ALTER TABLE {s}.pp_footprint_assessments_v1 ENABLE ROW LEVEL SECURITY""",
        f"""ALTER TABLE {s}.pp_footprint_assessments_v1 FORCE ROW LEVEL SECURITY""",
        f"""CREATE POLICY pp_footprint_by_tenant ON {s}.pp_footprint_assessments_v1
           FOR ALL USING (
              EXISTS (SELECT 1 FROM {s}.v27_project_tenants pt
                      WHERE pt.project_id=pp_footprint_assessments_v1.project_id
                        AND pt.tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
           ) WITH CHECK (
              EXISTS (SELECT 1 FROM {s}.v27_project_tenants pt
                      WHERE pt.project_id=pp_footprint_assessments_v1.project_id
                        AND pt.tenant_id = NULLIF(current_setting('app.tenant_id', true), ''))
           )""",
        # The imported legacy tables are *not* tenant safe. Explicitly deny runtime roles access.
        f"REVOKE ALL ON SCHEMA {s} FROM PUBLIC",
        f"REVOKE ALL ON ALL TABLES IN SCHEMA {s} FROM PUBLIC",
    ]


def stage_postgres(snapshot: Path, dsn: str, allow_execute: bool = False) -> dict:
    """One-time import into fresh schema; operator must pass --execute and --confirm-stage.

    No PG connection is attempted in default preview mode. Existing staging schema
    or any failed/partial migration is NEVER dropped or silently re-used.
    """
    if not allow_execute:
        raise PermissionError("A live PostgreSQL connection requires explicit --execute --confirm-stage")
    with sqlite3.connect(snapshot) as sqlite:
        sqlite.execute("PRAGMA foreign_keys=ON")
        if sqlite.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("SQLite snapshot failed quick_check")
        if sqlite.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("SQLite snapshot contains foreign-key violations")
        names = tables_in_snapshot(sqlite)
        expected = manifest_from_connection(sqlite, names)
        source_engine, metadata = reflected_metadata(snapshot, names)
        # SQLAlchemy dialect chooses driver according to the DSN, e.g. postgresql+psycopg://.
        pg_engine = create_engine(dsn, future=True)
        try:
            with pg_engine.begin() as root:
                exists = root.execute(
                    text("SELECT 1 FROM pg_namespace WHERE nspname=:s"), {"s": STAGING_SCHEMA}
                ).first()
                if exists:
                    raise FileExistsError(f"Refusing to modify existing staging schema: {STAGING_SCHEMA}")
                root.execute(text(f"CREATE SCHEMA {STAGING_SCHEMA}"))
                root.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
                conn = root.execution_options(schema_translate_map={None: STAGING_SCHEMA})
                metadata.create_all(conn)
                for table in metadata.sorted_tables:
                    rows = row_dicts(sqlite, table.name)
                    for offset in range(0, len(rows), 100):
                        conn.execute(insert(table), rows[offset : offset + 100])
                # Rebase serial sequences after explicit SQLite integer IDs are imported.
                for table in metadata.sorted_tables:
                    for col in table.columns:
                        if (
                            col.primary_key
                            and len(table.primary_key.columns) == 1
                            and col.autoincrement in (True, "auto")
                            and isinstance(col.type, __import__("sqlalchemy").Integer)
                        ):
                            # PG default SERIAL sequence name from pg_get_serial_sequence; can be NULL.
                            seq = root.execute(
                                text("SELECT pg_get_serial_sequence(:table,:column)"),
                                {"table": f"{STAGING_SCHEMA}.{table.name}", "column": col.name},
                            ).scalar()
                            if seq:
                                max_id = root.execute(
                                    text(
                                        f"SELECT max({quoted_identifier(col.name)}) FROM {STAGING_SCHEMA}.{quoted_identifier(table.name)}"
                                    )
                                ).scalar()
                                if max_id is not None:
                                    root.execute(
                                        text("SELECT setval(CAST(:seq AS regclass), :value, true)"),
                                        {"seq": seq, "value": max_id},
                                    )
                for statement in stage_extensions_sql():
                    root.execute(text(statement))
                actual = {}
                for table in metadata.sorted_tables:
                    result = conn.execute(select(table)).mappings().all()
                    actual[table.name] = {"count": len(result), "sha256": data_digest([dict(r) for r in result])}
                if actual != expected["tables"]:
                    bad = [name for name in actual if actual[name] != expected["tables"][name]]
                    raise ValueError("PostgreSQL reconciliation failed: " + ",".join(bad))
                full_geom = root.execute(text(f"SELECT count(*) FROM {STAGING_SCHEMA}.pp_parcel_geometry_v1")).scalar()
                quarantined = root.execute(
                    text(f"SELECT count(*) FROM {STAGING_SCHEMA}.pp_parcel_geometry_quarantine_v1")
                ).scalar()
                if full_geom + quarantined != expected["tables"]["geo29_parcels"]["count"]:
                    raise ValueError("Geometry derivation lost records")
                from_pg = conn.execute(select(metadata.tables["runs"])).mappings().all()
                financial = [{col: r[col] for col in FINANCIAL_COLUMNS} for r in from_pg]
                if data_digest(financial) != expected["financial_output_sha256"]:
                    raise ValueError("Financial source/target fingerprints mismatch")
                root.execute(
                    text(
                        f"""INSERT INTO {STAGING_SCHEMA}.pp_import_audit_v1
                    (source_row_count,source_finance_sha256,manifest_sha256,table_counts_json)
                    VALUES (:count,:financial,:digest,CAST(:tables AS jsonb))"""
                    ),
                    {
                        "count": expected["row_count"],
                        "financial": expected["financial_output_sha256"],
                        "digest": sha(expected),
                        "tables": json.dumps(expected["tables"], sort_keys=True),
                    },
                )
                # The transaction commits ONLY after successful table-by-table reconciliation.
                return {
                    "status": "staging_loaded",
                    "schema": STAGING_SCHEMA,
                    "financial_output_sha256": expected["financial_output_sha256"],
                    "tables_reconciled": len(actual),
                    "rows_reconciled": expected["row_count"],
                    "parcel_geometries": full_geom,
                    "parcel_geometries_quarantined": quarantined,
                    "production_cutover": False,
                    "application_backend": "sqlite",
                }
        finally:
            pg_engine.dispose()
            source_engine.dispose()


def preview(source: Path, output: Path | None = None) -> dict:
    # Consistent temporary snapshot is never bundled with the source release.
    with tempfile.TemporaryDirectory(prefix="powerpath-stage-") as d:
        snap = Path(d) / "snapshot.sqlite3"
        source_snapshot(source, snap)
        install_snapshot_only_schemas(snap)
        inspection = assess(snap)
        if not inspection["ok"]:
            raise ValueError(f"SQLite preflight failed: {inspection}")
        with sqlite3.connect(snap) as con:
            tables = tables_in_snapshot(con)
            manifest = manifest_from_connection(con, tables)
        engine, meta = reflected_metadata(snap, tables)
        try:
            if output:
                output.mkdir(parents=True, exist_ok=True)
                (output / "pg_ddl_preview.sql").write_text(make_pg_ddl(meta))
                (output / "migration_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
            return {
                "status": "staging_plan_ready",
                "tables": len(tables),
                "rows": manifest["row_count"],
                "financial_output_sha256": manifest["financial_output_sha256"],
                "schema_sha256": inspection["schema_sha256"],
                "source_integrity_ok": True,
                "requires": "Fresh PostgreSQL with PostGIS; credentials; optional psycopg driver",
                "application_backend": "sqlite",
                "live_cutover": False,
            }
        finally:
            engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="PowerPath PostgreSQL staging import and full row-by-row reconciliation"
    )
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "data/powerpath.sqlite3")
    parser.add_argument("--out", type=Path, help="Directory for NON-SENSITIVE DDL and digest-only manifest")
    parser.add_argument("--execute", action="store_true", help="Connect to a staging PostgreSQL instance")
    parser.add_argument(
        "--confirm-stage", action="store_true", help="Required second confirmation that DSN is staging only"
    )
    args = parser.parse_args(argv)
    if not args.execute:
        result = preview(args.source, args.out)
    else:
        if not args.confirm_stage:
            parser.error("Live PostgreSQL requires both --execute and --confirm-stage")
        dsn = os.environ.get("POWERPATH_PG_STAGE_DSN", "")
        if not dsn.startswith(("postgresql+psycopg://", "postgresql+psycopg2://", "postgresql+pg8000://")):
            parser.error("Set POWERPATH_PG_STAGE_DSN to a PostgreSQL SQLAlchemy driver URL")
        # Do not make environment-specific assumptions from DSN hostname (no magical prod detection).
        with tempfile.TemporaryDirectory(prefix="powerpath-stage-") as d:
            snap = Path(d) / "snapshot.sqlite3"
            source_snapshot(args.source, snap)
            install_snapshot_only_schemas(snap)
            result = stage_postgres(snap, dsn, allow_execute=True)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
