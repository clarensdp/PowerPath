"""Additive SQLite tables for the underwriting layer.

Records that support an investment decision are append-only (UPDATE/DELETE abort):
assumption versions, reviews, forecasts, outcomes, change events, decisions,
queue snapshots and imported forecasts. Mutable state is derived by reading the
latest append-only row, never by editing history.
"""
import hashlib
import json
import secrets
from datetime import datetime, timezone

SCHEMA = '''
CREATE TABLE IF NOT EXISTS uw_settings (
 project_id TEXT PRIMARY KEY REFERENCES projects(id), base_scenario_id TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS uw_assumptions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), scope TEXT NOT NULL,
 key TEXT NOT NULL, version INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(project_id,scope,key,version));
CREATE TABLE IF NOT EXISTS uw_reviews (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), assumption_id TEXT NOT NULL REFERENCES uw_assumptions(id),
 decision TEXT NOT NULL CHECK(decision IN ('accepted','rejected','superseded')), body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS uw_forecasts (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), kind TEXT NOT NULL, subject TEXT NOT NULL,
 fingerprint TEXT NOT NULL, body TEXT NOT NULL, issued_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS uw_outcomes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), forecast_id TEXT NOT NULL REFERENCES uw_forecasts(id),
 body TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(forecast_id));
CREATE TABLE IF NOT EXISTS uw_deliverability (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), version INTEGER NOT NULL,
 body TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(project_id,version));
CREATE TABLE IF NOT EXISTS uw_changes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), source TEXT NOT NULL,
 body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS uw_change_decisions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), change_id TEXT NOT NULL REFERENCES uw_changes(id),
 decision TEXT NOT NULL CHECK(decision IN ('accepted','rejected','acknowledged')), body TEXT NOT NULL, created_at TEXT NOT NULL,
 UNIQUE(change_id));
CREATE TABLE IF NOT EXISTS uw_queue_snapshots (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), source TEXT NOT NULL,
 body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS uw_price_forecasts (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), provider TEXT NOT NULL,
 body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS uw_assumption_scope ON uw_assumptions(project_id,scope,key,version);
CREATE INDEX IF NOT EXISTS uw_review_scope ON uw_reviews(project_id,assumption_id);
CREATE INDEX IF NOT EXISTS uw_forecast_scope ON uw_forecasts(project_id,kind);
CREATE INDEX IF NOT EXISTS uw_change_scope ON uw_changes(project_id);
'''

IMMUTABLE = ('uw_assumptions', 'uw_reviews', 'uw_forecasts', 'uw_outcomes', 'uw_deliverability',
             'uw_changes', 'uw_change_decisions', 'uw_queue_snapshots', 'uw_price_forecasts')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def uid():
    return secrets.token_hex(12)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(encode(value).encode()).hexdigest()


def initialize(db):
    with db() as con:
        con.executescript(SCHEMA)
        for table in IMMUTABLE:
            for op in ('UPDATE', 'DELETE'):
                con.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{op.lower()} BEFORE {op} ON {table} "
                            "BEGIN SELECT RAISE(ABORT,'Append-only underwriting record'); END")


def rows(con, sql, args=()):
    out = []
    for r in con.execute(sql, args):
        d = dict(r)
        if 'body' in d:
            d['body'] = json.loads(d['body'])
        out.append(d)
    return out


def one(con, sql, args=()):
    found = rows(con, sql, args)
    return found[0] if found else None


class transaction:
    """BEGIN IMMEDIATE on the shared SQLite connection (autocommit mode)."""

    def __init__(self, con):
        self.con = con

    def __enter__(self):
        self.con.execute('BEGIN IMMEDIATE')
        return self.con

    def __exit__(self, kind, exc, tb):
        self.con.execute('ROLLBACK' if kind else 'COMMIT')
        return False
