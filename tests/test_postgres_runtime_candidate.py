"""Contract tests, not a substitute for live PostgreSQL application acceptance."""
import sqlite3
from contextlib import contextmanager
import pytest
from server.postgres_runtime import Row, Cursor, Connection, bind_sql, translate_sql, validate_config


def test_row_mapping_and_positions():
    row = Row(id=7, name='parcel')
    assert row['id'] == row[0] == 7
    assert row[-1] == 'parcel'
    assert dict(row) == {'id': 7, 'name': 'parcel'}


@pytest.mark.parametrize('sql,expected', [
    ('SELECT ? AS value', 'SELECT %s AS value'),
    ("SELECT '?' AS literal, ?", "SELECT '?' AS literal, %s"),
    ('SELECT "?", ?', 'SELECT "?", %s'),
    ("SELECT 'it''s ?' AS t, ?", "SELECT 'it''s ?' AS t, %s"),
    ('SELECT ? -- ?\n', 'SELECT %s -- ?\n'),
    ('SELECT /* ? */ ?', 'SELECT /* ? */ %s'),
    ("SELECT '50%', ?", "SELECT '50%%', %s"),
    ('SELECT 10 % 3, ?', 'SELECT 10 %% 3, %s'),
])
def test_bind_conversion_preserves_literals(sql, expected):
    assert bind_sql(sql) == expected


@pytest.mark.parametrize('sql', ["SELECT 'open", 'SELECT /* open', 'SELECT $$body$$'])
def test_unsupported_sql_rejected(sql):
    with pytest.raises(ValueError): bind_sql(sql)


def test_conflict_and_identity_translation():
    sql, identity, lock = translate_sql('INSERT OR IGNORE INTO geo29_saved_versions VALUES(?,?,?)')
    assert sql == 'INSERT INTO geo29_saved_versions VALUES(%s,%s,%s) ON CONFLICT DO NOTHING'
    assert identity is None and not lock
    sql, identity, _ = translate_sql('INSERT INTO geo29_parcels(parcel_key) VALUES(?)')
    assert sql.endswith('RETURNING rid') and identity == 'rid'
    assert translate_sql('INSERT INTO parcel_tasks28(project_id) VALUES(?)')[1] == 'id'
    assert translate_sql('BEGIN IMMEDIATE') == ('BEGIN', None, True)


def test_spatial_literal_search():
    assert translate_sql('SELECT instr(lower(p.local_pin),lower(?))>0')[0] == 'SELECT strpos(lower(p.local_pin),lower(%s))>0'


def test_candidate_disabled_by_default(monkeypatch):
    monkeypatch.delenv('POWERPATH_PG_RUNTIME_EXPERIMENTAL', raising=False)
    with pytest.raises(RuntimeError, match='NOT completed'):
        validate_config('postgresql://host/db')


@pytest.mark.parametrize('schema,auth,url,match', [
    ('powerpath_stage_v3081', 'required', 'postgresql://host/db?sslmode=verify-full', 'separately provisioned'),
    ('powerpath_runtime_test', 'local_only', 'postgresql://host/db?sslmode=verify-full', 'named authentication'),
    ('powerpath_runtime_test', 'required', 'postgresql://host/db?sslmode=require', 'verify-full'),
    ('powerpath_runtime_test', 'required', 'postgresql://host/db?sslmode=verify-full&sslmode=disable', 'verify-full'),
    ('powerpath_runtime_test;DROP', 'required', 'postgresql://host/db?sslmode=verify-full', 'separately provisioned'),
    ('powerpath_runtime_test', 'required', 'sqlite:///tmp/db', 'PostgreSQL connection'),
])
def test_invalid_config_rejected(monkeypatch, schema, auth, url, match):
    monkeypatch.setenv('POWERPATH_PG_RUNTIME_EXPERIMENTAL', '1')
    monkeypatch.setenv('POWERPATH_PG_SCHEMA', schema)
    monkeypatch.setenv('POWERPATH_V27_AUTH_MODE', auth)
    with pytest.raises(RuntimeError, match=match): validate_config(url)


def test_config_normalizes_driver_prefix(monkeypatch):
    monkeypatch.setenv('POWERPATH_PG_RUNTIME_EXPERIMENTAL', '1')
    monkeypatch.setenv('POWERPATH_PG_SCHEMA', 'powerpath_runtime_test')
    monkeypatch.setenv('POWERPATH_V27_AUTH_MODE', 'required')
    monkeypatch.setenv('POWERPATH_IDENTITY_PROVIDER', 'supabase')
    assert validate_config('postgresql+psycopg://host/db?sslmode=verify-full') == (
        'postgresql://host/db?sslmode=verify-full', 'powerpath_runtime_test')


def test_no_sqlite_fallback_on_postgres_failure(monkeypatch, tmp_path):
    from server import database, postgres_runtime
    monkeypatch.setenv('POWERPATH_DATABASE_URL', 'postgresql://host/db')
    @contextmanager
    def fail(_):
        raise ConnectionError('connection unavailable')
        yield
    monkeypatch.setattr(postgres_runtime, 'postgres_db', fail)
    def sqlite_forbidden(*args, **kwargs):
        raise AssertionError('SQLite must not open')
    monkeypatch.setattr(sqlite3, 'connect', sqlite_forbidden)
    with pytest.raises(ConnectionError):
        with database.sqlite_db(): pass


class FakeRaw:
    def __init__(self): self.calls = []
    def execute(self, sql, params=()):
        self.calls.append((sql, params))
        return Cursor(rows=[Row(cid=0, name='id', type='text', notnull=1, dflt_value=None)])


def test_bootstrap_checks_without_ddl():
    raw = FakeRaw(); con = Connection(raw, 'powerpath_runtime_test')
    con.executescript('CREATE TABLE IF NOT EXISTS projects(id TEXT); CREATE VIRTUAL TABLE IF NOT EXISTS geo29_bounds USING rtree(rid,minx,maxx,miny,maxy);')
    assert len(raw.calls) == 2
    assert all(sql.startswith('SELECT') for sql, _ in raw.calls)
    assert con.execute('PRAGMA table_info(projects)').fetchone()[1] == 'id'
    with pytest.raises(RuntimeError, match='Runtime DDL'):
        con.execute('ALTER TABLE projects ADD COLUMN unsafe TEXT')


def test_missing_migration_fails_boot():
    con = Connection(FakeRaw(), 'powerpath_runtime_test')
    con.columns = lambda _: []
    with pytest.raises(RuntimeError, match='missing required table'):
        con.executescript('CREATE TABLE IF NOT EXISTS projects(id TEXT);')
