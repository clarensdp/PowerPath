"""Additive, versioned SQLite records. Existing project and engine tables are untouched."""
import hashlib
import json
import uuid
from server.providers.base import now

SCHEMA='''
CREATE TABLE IF NOT EXISTS parcel_analysis_versions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), parcel_id TEXT NOT NULL,
 kind TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(project_id,parcel_id,kind,version));
CREATE TABLE IF NOT EXISTS parcel_power_cases (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), parcel_id TEXT NOT NULL,
 version INTEGER NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS parcel_power_results (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), case_id TEXT NOT NULL REFERENCES parcel_power_cases(id),
 fingerprint TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS parcel_power_case_scope ON parcel_power_cases(project_id,parcel_id);
CREATE INDEX IF NOT EXISTS parcel_power_result_scope ON parcel_power_results(project_id,case_id);
CREATE TABLE IF NOT EXISTS feasibility_reports (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), version INTEGER NOT NULL,
 fingerprint TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(project_id,version));
'''


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def initialize(db):
    with db() as con:
        con.executescript(SCHEMA)
        for table in ('parcel_analysis_versions','parcel_power_results','feasibility_reports'):
            for op in ('UPDATE','DELETE'):
                con.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'Immutable analysis snapshot'); END")


def latest(con,pid,parcel,kind):
    row=con.execute('SELECT * FROM parcel_analysis_versions WHERE project_id=? AND parcel_id=? AND kind=? ORDER BY version DESC LIMIT 1',(pid,parcel,kind)).fetchone()
    return {**dict(row),'body':json.loads(row['body'])} if row else None


def save(con, pid, parcel, kind, body):
    con.execute('BEGIN IMMEDIATE')
    try:
        previous = latest(con, pid, parcel, kind)
        version = previous['version'] + 1 if previous else 1
        record_id, created_at = uuid.uuid4().hex, now()
        con.execute('INSERT INTO parcel_analysis_versions VALUES(?,?,?,?,?,?,?)',
                    (record_id, pid, parcel, kind, version, encode(body), created_at))
        con.execute('COMMIT')
    except Exception:
        con.execute('ROLLBACK')
        raise
    return {'id': record_id, 'version': version, 'body': body, 'created_at': created_at}
