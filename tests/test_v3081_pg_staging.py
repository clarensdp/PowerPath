"""Cross-dialect staging tests; no live PG or cloud connection is implied."""
import json
import sqlite3
import re
from pathlib import Path
import pytest
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import postgresql
from infrastructure.pg_stage import (source_snapshot, install_snapshot_only_schemas,
    tables_in_snapshot, manifest_from_connection, reflected_metadata, make_pg_ddl,
    preview, stage_extensions_sql, data_digest, stage_postgres, quoted_identifier,
    STAGING_SCHEMA)

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tests'/'fixtures'/'powerpath_synthetic.sqlite3'

@pytest.fixture
def source_copy(tmp_path):
    dest=tmp_path/'snap.sqlite3'
    source_snapshot(SRC,dest)
    install_snapshot_only_schemas(dest)
    return dest

def test_snapshot_never_updates_original(source_copy):
    with sqlite3.connect(SRC) as con:
        assert con.execute("SELECT count(*) FROM sqlite_master WHERE name='agent_ops_jobs'").fetchone()[0]==0
    with sqlite3.connect(source_copy) as con:
        assert con.execute("SELECT count(*) FROM sqlite_master WHERE name='agent_ops_jobs'").fetchone()[0]==1

def test_includes_every_relational_module_without_rtree(source_copy):
    with sqlite3.connect(source_copy) as con:
        names=tables_in_snapshot(con)
    assert len(names)>=45
    assert 'agent_ops_jobs' in names and 'geo29_parcels' in names
    assert 'geo29_bounds' not in names
    assert not any(n.startswith('geo29_bounds_') for n in names)

def test_manifest_is_deterministic_and_complete(source_copy):
    with sqlite3.connect(source_copy) as con:
        names=tables_in_snapshot(con)
        first=manifest_from_connection(con,names)
        assert first==manifest_from_connection(con,names)
    assert first['tables']['projects']['count']>0
    assert first['tables']['geo29_parcels']['count']>0
    assert first['tables']['agent_ops_jobs']['count']==0
    assert len(first['financial_output_sha256'])==64

def test_postgres_reflection_preserves_double_precision(source_copy):
    eng,metadata=reflected_metadata(source_copy,['projects','geo29_parcels','scenarios'])
    try:
        t=metadata.tables['projects']
        compiled=str(CreateTable(t).compile(dialect=postgresql.dialect()))
        assert 'target_mw FLOAT(53)' in compiled
        assert 'target_mw REAL' not in compiled
    finally:eng.dispose()

def test_schema_qualified_pg_foreign_keys_and_indexes(source_copy):
    with sqlite3.connect(source_copy) as con:names=tables_in_snapshot(con)
    eng,meta=reflected_metadata(source_copy,names)
    try:
        ddl=make_pg_ddl(meta)
        assert 'FOREIGN KEY(project_id) REFERENCES '+STAGING_SCHEMA+'.projects' in ddl
        assert f'CREATE TABLE {STAGING_SCHEMA}.agent_ops_jobs' in ddl
        assert 'geo29_bounds' not in ddl
        assert 'FOREIGN KEY' in ddl
        assert '__[SCHEMA__none]' not in ddl
    finally: eng.dispose()

def test_postgis_and_auth_protection_contracts():
    statements='\n'.join(stage_extensions_sql())
    assert 'ST_GeomFromGeoJSON' in statements
    assert 'ST_Intersects' in statements
    assert 'ST_UnaryUnion' in statements
    assert '::geography' in statements
    assert 'layer_coverage_verified' in statements
    assert 'FORCE ROW LEVEL SECURITY' in statements
    assert "current_setting('app.tenant_id', true)" in statements
    assert 'pp_footprint_assessments_v1.project_id' in statements
    assert 'REVOKE ALL ON ALL TABLES' in statements
    assert 'refuse_footprint_mutation' in statements

def test_reject_unsafe_sql_identifier():
    with pytest.raises(ValueError):quoted_identifier('projects; DROP TABLE projects;')

def test_source_integrity_and_report_no_credentials(source_copy,tmp_path):
    result=preview(source_copy,tmp_path/'report')
    assert result['live_cutover'] is False
    assert result['source_integrity_ok'] is True
    assert result['application_backend']=='sqlite'
    assert (tmp_path/'report'/'pg_ddl_preview.sql').is_file()
    text=(tmp_path/'report'/'migration_manifest.json').read_text()
    assert 'finance_sha256' not in text # digests of entire tables only, no sensitive raw rows

def test_live_pg_import_requires_explicit_gate(source_copy):
    with pytest.raises(PermissionError):stage_postgres(source_copy,'invalid-url',False)

def test_corrupt_snapshot_blocks_manifest(tmp_path):
    src=tmp_path/'bad.sqlite3'
    sqlite3.connect(src).close()
    with sqlite3.connect(src) as con:
        with pytest.raises(ValueError,match='missing required'):
            tables_in_snapshot(con)

def test_digest_detects_changed_financial_row():
    a=[{'id':'a','rows_json':'{"cash":100.0}'}]
    b=[{'id':'a','rows_json':'{"cash":99.999}'}]
    assert data_digest(a)!=data_digest(b)
