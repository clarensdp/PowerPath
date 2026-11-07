import sqlite3
from pathlib import Path
import pytest
from infrastructure.runtime_policies import compile_policies


def tables():
 c=sqlite3.connect(Path(__file__).resolve().parents[1]/'tests/fixtures/powerpath_synthetic.sqlite3')
 try:
  return {name:[r[1] for r in c.execute('PRAGMA table_info('+name+')')] for name, in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'geo29_bounds%'")}
 finally:c.close()


def test_schema_inventory_is_classified():
 inventory=tables();inventory['geo29_bounds']=['rid','minx','maxx','miny','maxy']
 sql=compile_policies('powerpath_runtime_candidate',inventory)
 assert sql.count(' FORCE ROW LEVEL SECURITY;')==len(inventory)
 assert 'SECURITY DEFINER' not in sql
 assert 'GRANT ALL' not in sql
 assert 'GRANT INSERT ON powerpath_runtime_candidate.v27_memberships' not in sql
 assert 'GRANT INSERT ON powerpath_runtime_candidate.geo29_parcels' not in sql
 assert 'owning_tenant' in sql
 assert 'user_metadata' not in sql


def test_unknown_table_fails_closed():
 with pytest.raises(ValueError,match='unclassified'):compile_policies('powerpath_runtime_x',{'surprise':['id']})


def test_identifier_injection_rejected():
 with pytest.raises(ValueError,match='unsafe'):compile_policies('x;DROP SCHEMA public',{})
