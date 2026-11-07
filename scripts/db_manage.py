"""Database preflight / backup controls: no implicit migrations or cloud operations."""

from __future__ import annotations
import argparse, json, sys
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
    else:
        result = verify_backup(v.db, contract)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok", True) and result.get("verified", True) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError, RuntimeError, FileExistsError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
