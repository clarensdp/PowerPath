"""Generate an additive private runtime-schema migration from a source snapshot.

Source/target financial values are reconciled inside the transaction. This
module does not connect, apply DDL, provision credentials or switch a writer.
"""

from pathlib import Path
import argparse
import sqlite3
from sqlalchemy import Column, Text, text
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from infrastructure.pg_stage import reflected_metadata, tables_in_snapshot
from infrastructure.runtime_policies import compile_policies

SCHEMA = "powerpath_runtime_v3090"
SOURCE = "powerpath_stage_v3081"
ROLE = "powerpath_app"


def generate(snapshot):
    with sqlite3.connect(snapshot) as c:
        names = tables_in_snapshot(c)
    engine, metadata = reflected_metadata(Path(snapshot), names)
    try:
        dialect = postgresql.dialect()
        statements = [f"CREATE SCHEMA {SCHEMA};", f"CREATE ROLE {ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT;"]
        project = metadata.tables["projects"]
        project.append_column(
            Column("created_by", Text, server_default=text("nullif(current_setting('powerpath.actor_id',true),'')"))
        )
        project.append_column(
            Column("owning_tenant", Text, server_default=text("nullif(current_setting('powerpath.tenant_id',true),'')"))
        )
        tables = {}
        for table in metadata.sorted_tables:
            statement = (
                str(
                    CreateTable(table).compile(
                        dialect=dialect, schema_translate_map={None: SCHEMA}, render_schema_translate=True
                    )
                )
                + ";"
            )
            statements.append(statement)
            for index in table.indexes:
                statements.append(
                    str(
                        CreateIndex(index).compile(
                            dialect=dialect, schema_translate_map={None: SCHEMA}, render_schema_translate=True
                        )
                    )
                    + ";"
                )
            tables[table.name] = [c.name for c in table.columns]
        for table in metadata.sorted_tables:
            cols = [c.name for c in table.columns if c.name not in ("created_by", "owning_tenant")]
            columns = ",".join('"' + c + '"' for c in cols)
            statements.append(
                f'INSERT INTO {SCHEMA}."{table.name}" ({columns}) SELECT {columns} FROM {SOURCE}."{table.name}";'
            )
            for col in table.columns:
                if col.primary_key and col.type.python_type is int and len(table.primary_key.columns) == 1:
                    statements.append(
                        f'SELECT setval(pg_get_serial_sequence(\'{SCHEMA}.{table.name}\',\'{col.name}\'),COALESCE(MAX("{col.name}"),1),MAX("{col.name}") IS NOT NULL) FROM {SCHEMA}."{table.name}";'
                    )
            # Exact typed multiset parity. New runtime metadata is excluded.
            statements.append(
                f"""DO $verify$ BEGIN
 IF EXISTS((SELECT {columns} FROM {SCHEMA}."{table.name}" EXCEPT ALL SELECT {columns} FROM {SOURCE}."{table.name}") UNION ALL
 (SELECT {columns} FROM {SOURCE}."{table.name}" EXCEPT ALL SELECT {columns} FROM {SCHEMA}."{table.name}")) THEN
 RAISE EXCEPTION 'Source parity failed: {table.name}'; END IF; END $verify$;"""
            )
        statements.append(
            f"UPDATE {SCHEMA}.projects p SET owning_tenant=t.tenant_id FROM {SCHEMA}.v27_project_tenants t WHERE t.project_id=p.id;"
        )
        statements += [
            f"CREATE TABLE {SCHEMA}.geo29_bounds(rid integer PRIMARY KEY REFERENCES {SCHEMA}.geo29_parcels(rid),minx double precision NOT NULL,maxx double precision NOT NULL,miny double precision NOT NULL,maxy double precision NOT NULL);",
            f"INSERT INTO {SCHEMA}.geo29_bounds SELECT record_id,extensions.ST_XMin(geom::extensions.box3d),extensions.ST_XMax(geom::extensions.box3d),extensions.ST_YMin(geom::extensions.box3d),extensions.ST_YMax(geom::extensions.box3d) FROM {SOURCE}.pp_parcel_geometry_v1;",
            f"CREATE INDEX geo29_bounds_x ON {SCHEMA}.geo29_bounds(minx,maxx);",
            f"CREATE INDEX geo29_bounds_y ON {SCHEMA}.geo29_bounds(miny,maxy);",
        ]
        tables["geo29_bounds"] = ["rid", "minx", "maxx", "miny", "maxy"]
        statements.append(compile_policies(SCHEMA, tables, ROLE))
        # New schema is closed to API/browser/service roles. No application login,
        # ownership assignments or network exposure are created implicitly.
        return "\n".join(statements) + "\n"
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    Path(args.out).write_text(generate(args.snapshot))
