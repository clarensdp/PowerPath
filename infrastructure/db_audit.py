"""Read-only SQLite inventory and verified, consistent backups.

Not a PostgreSQL migration, schema owner, or tenant-security implementation.
Inspection never imports the application, initializes schemas, or creates a DB.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

CORE_TABLES = (
    "projects",
    "scenarios",
    "runs",
    "evidence",
    "activity",
    "power_paths",
    "permit_items",
    "permit_steps",
    "permit_notes",
    "geographic_assets",
    "delivery_milestones",
)


def owner(table: str) -> str:
    if table.startswith("site_energy_"):
        return "site_energy_integration"
    if table in CORE_TABLES:
        return "core_application"
    if table.startswith("agent_ops_") or table == "schema_migrations":
        return "agent_operations"
    if table.startswith("geo29_") or table.startswith("geo30_"):
        return "geographic_registry"
    if table.startswith("parcel_"):
        return "parcel_shortlist"
    if table.startswith("intel_") or table.startswith("agent_"):
        return "intelligence"
    if table.startswith("v27_") or table.startswith("v271_"):
        return "institutional_transaction"
    if table.startswith("feasibility_"):
        return "feasibility"
    if table == "platform_migration_audit" or table == "alembic_version":
        return "architecture_migrations"
    if table.startswith("sqlite_"):
        return "sqlite_internal"
    return "unassigned"


def connect_readonly(path: Path):
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Database does not exist: {path}")
    # URI read-only, no accidental new database on mistyped path
    conn = sqlite3.connect(f'file:{quote(str(path), safe="/")}?mode=ro', uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def fingerprint(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def schema_inventory(con):
    """Stable DDL shape, excluding SQLite implementation-maintained RTree shadow tables."""
    tables = []
    for (name,) in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ):
        fields = [
            dict(
                name=r["name"],
                type=(r["type"] or "").upper(),
                nullable=not bool(r["notnull"]),
                primary_key=int(r["pk"]),
                default=r["dflt_value"],
            )
            for r in con.execute('PRAGMA table_info("' + name.replace('"', '""') + '")')
        ]
        foreign_keys = [
            dict(table=r["table"], from_column=r["from"], to_column=r["to"], on_delete=r["on_delete"])
            for r in con.execute('PRAGMA foreign_key_list("' + name.replace('"', '""') + '")')
        ]
        tables.append(
            {
                "name": name,
                "owner": owner(name),
                "columns": fields,
                "foreign_keys": sorted(foreign_keys, key=lambda v: (v["table"], v["from_column"])),
            }
        )
    return {"tables": tables, "schema_sha256": fingerprint(tables)}


def assess(path: Path, contract: dict | None = None):
    with connect_readonly(path) as con:
        integrity = [r[0] for r in con.execute("PRAGMA quick_check")]
        fk = [tuple(r) for r in con.execute("PRAGMA foreign_key_check")]
        inv = schema_inventory(con)
        tables = {t["name"]: t for t in inv["tables"]}
        results = {
            "path": str(Path(path).resolve()),
            "integrity_ok": integrity == ["ok"],
            "integrity_details": integrity[:20] if integrity != ["ok"] else [],
            "foreign_key_violations": len(fk),
            "foreign_key_examples": fk[:10],
            "table_count": len(tables),
            "schema_sha256": inv["schema_sha256"],
            "table_owners": {t["name"]: t["owner"] for t in inv["tables"]},
            "unassigned": [t["name"] for t in inv["tables"] if t["owner"] == "unassigned"],
        }
        if contract is not None:
            issues = []
            for name, required_columns in contract["required_columns"].items():
                if name not in tables:
                    issues.append(f"MISSING_TABLE:{name}")
                    continue
                actual = {c["name"]: c for c in tables[name]["columns"]}
                for col, expected in required_columns.items():
                    if col not in actual:
                        issues.append(f"MISSING_COLUMN:{name}.{col}")
                    elif (
                        actual[col]["type"] != expected["type"] or actual[col]["primary_key"] != expected["primary_key"]
                    ):
                        issues.append(f"COLUMN_INCOMPATIBLE:{name}.{col}")
            results["contract_version"] = contract["contract_version"]
            results["contract_issues"] = issues
        results["ok"] = results["integrity_ok"] and not fk and not results.get("contract_issues")
        return results


def verified_backup(source: Path, destination: Path, contract: dict | None = None):
    """SQLite online backup API, atomic publish, no overwrite, verified schema and FK integrity."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError("Backup cannot overwrite the source")
    before = assess(source, contract)
    if not before["ok"]:
        raise ValueError(f"Source preflight failed: {before}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.with_suffix(destination.suffix + ".json").exists():
        raise FileExistsError(f"Backup or manifest already exists: {destination}")
    handle = tempfile.NamedTemporaryFile(prefix=destination.name + ".part-", dir=destination.parent, delete=False)
    tmp = Path(handle.name)
    handle.close()
    tmp.chmod(0o600)
    try:
        with connect_readonly(source) as live:
            with sqlite3.connect(tmp) as target:
                live.backup(target)
        check = assess(tmp, contract)
        if not check["ok"] or before["schema_sha256"] != check["schema_sha256"]:
            raise RuntimeError("Backup verification failed; refusing to publish")
        digest = sha256_file(tmp)
        # Never expose unverified backup on error
        os.replace(tmp, destination)
        manifest = {
            "version": "PP-BACKUP-30.8.0",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "filename": destination.name,
            "sha256": digest,
            "schema_sha256": check["schema_sha256"],
            "foreign_key_violations": 0,
            "integrity_ok": True,
            "contract_version": check.get("contract_version"),
        }
        manifest_path = destination.with_suffix(destination.suffix + ".json")
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest
    finally:
        tmp.unlink(missing_ok=True)


def verify_backup(path: Path, contract: dict | None = None):
    p = Path(path).resolve()
    manifest = json.loads(p.with_suffix(p.suffix + ".json").read_text())
    actual = assess(p, contract)
    integrity = actual["ok"] and actual["schema_sha256"] == manifest["schema_sha256"]
    checksum = sha256_file(p) == manifest["sha256"]
    return {
        "verified": bool(integrity and checksum),
        "sha256_matches": checksum,
        "integrity_matches": integrity,
        "schema_sha256": actual["schema_sha256"],
    }
