"""Read-only repository handoff smoke tests."""
from pathlib import Path
import sqlite3
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_november_adapter_cursor_guard():
    src=(ROOT/'server/postgres_runtime.py').read_text()
    assert 'cursor.description or ()' in src
    assert 'names = [c.name for c in cursor.description]' not in src

def test_detailed_login_route_and_types():
    assert (ROOT/'web/public/advanced-session.js').exists()
    assert (ROOT/'web/src/advanced-session.d.ts').exists()
    for f in ('web/public/app.js','web/src/app.ts'):
        text=(ROOT/f).read_text()
        assert "import { workspaceFetch as fetch, enterWorkspace } from './advanced-session.js';" in text
        assert 'enterWorkspace(init);' in text

def test_curated_fixture_is_demo_only():
    con=sqlite3.connect(f'file:{ROOT / "tests/fixtures/powerpath_synthetic.sqlite3"}?mode=ro', uri=True)
    try:
        assert con.execute('SELECT id FROM projects').fetchall()==[('demo-campus-001',)]
        assert con.execute('SELECT COUNT(*) FROM v27_users').fetchone()[0]==0
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    finally:
        con.close()

def test_local_launcher_never_targets_postgres(monkeypatch):
    from scripts.prepare_local import prepare
    monkeypatch.setenv('POWERPATH_DATABASE_URL','postgresql://example.test/demo')
    with pytest.raises(SystemExit,match='refuses a configured PostgreSQL'):
        prepare()
