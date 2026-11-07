"""Database preflight / backup controls: no implicit migrations or cloud operations."""

from __future__ import annotations
import argparse, hashlib, json, shutil, sys
from pathlib import Path
from server.database import DB, ROOT
from infrastructure.db_audit import assess, verified_backup, verify_backup


def main(args=None):
    parser = argparse.ArgumentParser(description="PowerPath v30.8 local SQLite migration preflight")
    parser.add_argument("action", choices=["inspect", "backup", "verify-backup"])
    parser.add_argument("--db", type=Path, default=DB, help="Existing SQLite source file")
    parser.add_argument("--output", type=Path, help="Backup output file; never overwritten")
    parser.add_argument("--contract", type=Path, default=ROOT / "architecture/schema_contract_v30_8.json")
    v = parser.parse_args(args)
    contract = json.loads(v.contract.read_text())
    if v.action == "inspect":
        result = assess(v.db, contract)
    elif v.action == "backup":
        if not v.output:
            parser.error("backup requires --output")
        result = verified_backup(v.db, v.output, contract)
        # v30.8.2: uploaded evidence lives outside SQLite. Copy it next to the backup with a hash manifest so a
        # restore cannot silently lose attached documents.
        evidence_src = Path(v.db).resolve().parent / "evidence"
        if evidence_src.is_dir():
            dest = Path(str(v.output) + ".evidence")
            shutil.copytree(evidence_src, dest)
            files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.iterdir() if p.is_file()}
            (dest / "EVIDENCE_MANIFEST.json").write_text(json.dumps(files, indent=2, sort_keys=True) + "\n")
            result["evidence_files"] = len(files)
            result["evidence_dir"] = str(dest)
    else:
        result = verify_backup(v.db, contract)
        ev = Path(str(v.db) + ".evidence")
        if (ev / "EVIDENCE_MANIFEST.json").exists():
            expected = json.loads((ev / "EVIDENCE_MANIFEST.json").read_text())
            actual = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in ev.iterdir()
                if p.is_file() and p.name != "EVIDENCE_MANIFEST.json"
            }
            result["evidence_verified"] = expected == actual
            result["verified"] = result["verified"] and result["evidence_verified"]
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok", True) and result.get("verified", True) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, RuntimeError, FileExistsError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
