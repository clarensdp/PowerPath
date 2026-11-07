"""Explicit local-only demo bootstrap. Never touches a configured PostgreSQL backend."""

from pathlib import Path
import os
import shutil
import sqlite3

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "powerpath_synthetic.sqlite3"
TARGET = ROOT / "data" / "powerpath.sqlite3"


def prepare():
    if os.environ.get("POWERPATH_DATABASE_URL", "").strip():
        raise SystemExit(
            "Local demo launcher refuses a configured PostgreSQL URL. Use the reviewed runtime runbook instead."
        )
    if os.environ.get("POWERPATH_DATA_DIR", "").strip():
        raise SystemExit(
            "Local demo launcher will not modify a custom POWERPATH_DATA_DIR. Launch the dedicated environment explicitly."
        )
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        try:
            with sqlite3.connect(f"file:{TARGET}?mode=ro", uri=True) as con:
                names = {x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not {"projects", "scenarios", "runs"}.issubset(names):
                    raise ValueError("missing required local database tables")
        except (sqlite3.DatabaseError, ValueError) as exc:
            raise SystemExit(
                f"Existing local database cannot be used: {exc}. Back it up and repair it manually; nothing was overwritten."
            ) from exc
        print("Using existing local SQLite workspace; no reset performed.")
        return
    if not FIXTURE.is_file():
        raise SystemExit("Synthetic local fixture missing; cannot create workspace.")
    # Exclusive creation ensures a pre-existing local database is never overwritten.
    with FIXTURE.open("rb") as source, TARGET.open("xb") as output:
        shutil.copyfileobj(source, output)
    print("Created local synthetic demo database (not real project data).")


if __name__ == "__main__":
    prepare()
