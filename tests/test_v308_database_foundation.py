"""v30.8 database foundation release controls; isolated, no external DB needed."""
from __future__ import annotations
import json, os, shutil, sqlite3, subprocess, sys, tempfile
from pathlib import Path
import pytest
from infrastructure.db_audit import assess, schema_inventory, verified_backup, verify_backup, fingerprint
from server.schema_core import initialize_core_schema
from contextlib import contextmanager

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=json.loads((ROOT/'architecture/schema_contract_v30_8.json').read_text())


def seeded_db(path):
    @contextmanager
    def db():
        con=sqlite3.connect(path,isolation_level=None)
        con.row_factory=sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:yield con
        finally:con.close()
    initialize_core_schema(db)
    return path


def test_core_contract_accepts_original_schema(tmp_path):
    a=assess(seeded_db(tmp_path/'fresh.sqlite3'),CONTRACT)
    assert a['ok'], a
    assert a['table_count']==11
    assert not a['contract_issues']


def test_schema_hash_does_not_depend_on_record_values(tmp_path):
    p=seeded_db(tmp_path/'fresh.sqlite3')
    before=assess(p,CONTRACT)['schema_sha256']
    with sqlite3.connect(p) as con:
        con.execute("INSERT INTO projects(id,name,created_at,updated_at) VALUES('a','test','2026','2026')")
    assert assess(p,CONTRACT)['schema_sha256']==before


def test_missing_column_fails_contract(tmp_path):
    p=seeded_db(tmp_path/'fresh.sqlite3')
    with sqlite3.connect(p) as con:
        con.execute('ALTER TABLE projects RENAME COLUMN name TO renamed_name')
    a=assess(p,CONTRACT)
    assert not a['ok']
    assert 'MISSING_COLUMN:projects.name' in a['contract_issues']


def test_no_implicit_creation_on_missing_db(tmp_path):
    p=tmp_path/'missing.sqlite3'
    with pytest.raises(FileNotFoundError):assess(p,CONTRACT)
    assert not p.exists()


def test_backup_integrity_manifest_and_no_overwrite(tmp_path):
    source=seeded_db(tmp_path/'source.sqlite3')
    with sqlite3.connect(source) as con:
        con.execute("INSERT INTO projects(id,name,created_at,updated_at) VALUES('a','test','2026','2026')")
    out=tmp_path/'snap.sqlite3'
    m=verified_backup(source,out,CONTRACT)
    assert m['integrity_ok']
    assert verify_backup(out,CONTRACT)['verified']
    assert sqlite3.connect(out).execute('SELECT count(*) FROM projects').fetchone()[0]==1
    with pytest.raises(FileExistsError):verified_backup(source,out,CONTRACT)


def test_backup_tamper_fails_verification(tmp_path):
    source=seeded_db(tmp_path/'source.sqlite3')
    out=tmp_path/'snap.sqlite3'
    verified_backup(source,out,CONTRACT)
    with sqlite3.connect(out) as con:
        con.execute("INSERT INTO projects(id,name,created_at,updated_at) VALUES('a','test','2026','2026')")
    assert not verify_backup(out,CONTRACT)['verified']


def test_unresolved_foreign_key_rejected(tmp_path):
    p=seeded_db(tmp_path/'source.sqlite3')
    with sqlite3.connect(p) as con:
        con.execute('PRAGMA foreign_keys=OFF')
        con.execute("INSERT INTO scenarios(id,project_id,name,config_json,created_at,updated_at) VALUES ('s','missing','base','{}','2026','2026')")
    report=assess(p,CONTRACT)
    assert not report['ok']
    assert report['foreign_key_violations'] > 0
    with pytest.raises(ValueError):verified_backup(p,tmp_path/'unsafe.sqlite3',CONTRACT)


def test_alembic_baseline_is_idempotent_and_additive(tmp_path):
    p=seeded_db(tmp_path/'powerpath.sqlite3')
    with sqlite3.connect(p) as con:
        con.execute("INSERT INTO projects(id,name,created_at,updated_at) VALUES('demo','test','2026','2026')")
    env={**os.environ,'POWERPATH_DATA_DIR':str(tmp_path)}
    def migrate():
        return subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env,
                              capture_output=True,text=True,timeout=25)
    result=migrate()
    assert result.returncode==0,result.stderr
    again=migrate()
    assert again.returncode==0,again.stderr
    with sqlite3.connect(p) as con:
        assert con.execute('SELECT count(*) FROM projects').fetchone()[0]==1
        assert con.execute('SELECT count(*) FROM platform_migration_audit').fetchone()[0]==1
        assert con.execute('SELECT version_num FROM alembic_version').fetchone()[0]=='3080_baseline'
    assert assess(p,CONTRACT)['ok']


def test_refuse_alembic_baseline_on_empty_db(tmp_path):
    p=tmp_path/'powerpath.sqlite3'
    sqlite3.connect(p).close()
    env={**os.environ,'POWERPATH_DATA_DIR':str(tmp_path)}
    result=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env,
                          capture_output=True,text=True,timeout=25)
    assert result.returncode!=0
    assert 'incomplete legacy database' in result.stderr


def test_pg_env_fails_closed(tmp_path,monkeypatch):
    from server.database import sqlite_db
    monkeypatch.setenv('POWERPATH_DATABASE_URL','postgresql+psycopg://host/db')
    with pytest.raises(RuntimeError,match='NOT completed'):
        with sqlite_db():pass
