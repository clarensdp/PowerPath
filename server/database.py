"""Explicit backend routing. PostgreSQL errors never fall back to SQLite.

PostgreSQL runtime remains gated on a separately provisioned private schema,
least-privilege credentials and required authentication. See integration report.
"""
from __future__ import annotations
import os, sqlite3
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('POWERPATH_DATA_DIR', str(ROOT / 'data'))).resolve()
EVIDENCE = DATA / 'evidence'
DB = DATA / 'powerpath.sqlite3'

@contextmanager
def sqlite_db():
    url = os.environ.get('POWERPATH_DATABASE_URL', '').strip()
    if url:
        from server.postgres_runtime import postgres_db
        with postgres_db(url) as con:
            yield con
        return
    DATA.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB, timeout=20, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=10000')
    try:
        yield con
    finally:
        con.close()
