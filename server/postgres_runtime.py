"""PostgreSQL repository compatibility boundary, pending live acceptance.

Only handles SQL forms used by the current application. It is not a general
SQLite translator. Runtime DDL is replaced by schema checks; migrations belong
to an operator connection, never to the application role.
"""
from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from urllib.parse import urlsplit, parse_qs


class Row(dict):
    """Keep SQLite's mapping and positional access contract."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def row_factory(cursor):
    names = [c.name for c in (cursor.description or ())]
    return lambda values: Row(zip(names, values))


def bind_sql(sql):
    """Convert qmark binds outside quoted literals/identifiers/comments.

    Escape literal percent signs for psycopg when a bind tuple is supplied.
    Dollar-quoted SQL is intentionally unsupported at the runtime boundary.
    """
    if re.search(r'\$[A-Za-z_0-9]*\$', sql):
        raise ValueError('Dollar-quoted SQL is migration-only')
    out = []; i = 0; state = None
    while i < len(sql):
        c = sql[i]; pair = sql[i:i+2]
        if state in ("'", '"'):
            out.append('%%' if c == '%' else c)
            if c == state:
                if i+1 < len(sql) and sql[i+1] == state:
                    out.append(sql[i+1]); i += 1
                else:
                    state = None
        elif state == '--':
            out.append('%%' if c == '%' else c)
            if c == '\n': state = None
        elif state == '/*':
            if pair == '*/': out.append(pair); i += 1; state = None
            else: out.append('%%' if c == '%' else c)
        elif pair in ('--', '/*'):
            state = pair; out.append(pair); i += 1
        elif c in ("'", '"'):
            state = c; out.append(c)
        elif c == '?': out.append('%s')
        elif c == '%': out.append('%%')
        else: out.append(c)
        i += 1
    if state in ("'", '"', '/*'):
        raise ValueError('Unterminated SQL literal or comment')
    return ''.join(out)


def translate_sql(sql):
    sql = sql.strip().rstrip(';')
    if re.fullmatch(r'BEGIN\s+IMMEDIATE', sql, re.I):
        return 'BEGIN', None, True
    ignore = bool(re.match(r'INSERT\s+OR\s+IGNORE\s+INTO\b', sql, re.I))
    if ignore:
        sql = re.sub(r'^INSERT\s+OR\s+IGNORE', 'INSERT', sql, flags=re.I)
        sql += ' ON CONFLICT DO NOTHING'
    # The sole runtime instr form, deliberately exact rather than broad rewriting.
    sql = sql.replace('instr(lower(p.local_pin),lower(?))', 'strpos(lower(p.local_pin),lower(?))')
    insert = re.match(r'INSERT\s+INTO\s+(\w+)\b', sql, re.I)
    identity = {'geo29_parcels': 'rid', 'parcel_tasks28': 'id'}
    returning = identity.get(insert[1].lower()) if insert else None
    if returning:
        sql += ' RETURNING ' + returning
    return bind_sql(sql), returning, False


class Cursor:
    def __init__(self, cursor=None, rows=None, lastrowid=None):
        self.cursor = cursor
        self.rows = iter(rows) if rows is not None else None
        self.lastrowid = lastrowid
        self.rowcount = cursor.rowcount if cursor is not None else len(rows or [])

    def fetchone(self):
        return next(self.rows, None) if self.rows is not None else self.cursor.fetchone()

    def fetchall(self):
        return list(self.rows) if self.rows is not None else self.cursor.fetchall()

    def __iter__(self):
        return iter(self.rows) if self.rows is not None else iter(self.cursor)


class Connection:
    def __init__(self, raw, schema):
        self.raw = raw; self.schema = schema

    def columns(self, table):
        return self.raw.execute('SELECT ordinal_position-1 AS cid,column_name AS name,'
            'data_type AS type,(is_nullable=\'NO\')::int AS notnull,column_default AS dflt_value '
            'FROM information_schema.columns WHERE table_schema=%s AND table_name=%s '
            'ORDER BY ordinal_position', (self.schema, table)).fetchall()

    def require_table(self, table):
        if not self.columns(table):
            raise RuntimeError('PostgreSQL migration missing required table: ' + table)

    def execute(self, sql, parameters=()):
        pragma = re.fullmatch(r'PRAGMA\s+table_info\((\w+)\)\s*;?', sql.strip(), re.I)
        if pragma:
            return Cursor(rows=self.columns(pragma[1]))
        ddl = re.match(r'CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)', sql.strip(), re.I)
        if ddl:
            self.require_table(ddl[1]); return Cursor(rows=[])
        if re.match(r'(CREATE|ALTER|DROP|PRAGMA|ATTACH|DETACH|VACUUM)\b', sql.strip(), re.I):
            raise RuntimeError('Runtime DDL is disabled; apply the PostgreSQL migration first')
        translated, returning, immediate = translate_sql(sql)
        import psycopg
        try:
            cur = self.raw.execute(translated, tuple(parameters))
            if immediate:
                # SQLite BEGIN IMMEDIATE serializes writers. Keep that guarantee
                # for legacy job claiming and hash-chain appends across processes.
                self.raw.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',
                                 ('powerpath-runtime-writer:' + self.schema,))
            if returning:
                row = cur.fetchone()
                return Cursor(cur, rows=[], lastrowid=row[0] if row else None)
            return Cursor(cur)
        except psycopg.IntegrityError as exc:
            # Existing routes convert duplicate/constraint errors to HTTP 409.
            # Keep explicit transactions aborted until their ROLLBACK path runs.
            raise sqlite3.IntegrityError('PostgreSQL constraint rejected operation') from exc

    def executescript(self, script):
        # Bootstrap calls verify pre-provisioned relations; they never mutate DDL.
        tables = re.findall(r'CREATE\s+(?:VIRTUAL\s+)?TABLE\s+IF\s+NOT\s+EXISTS\s+(\w+)', script, re.I)
        if not tables:
            raise RuntimeError('Unsupported PostgreSQL bootstrap script')
        for table in tables:
            self.require_table(table)


def validate_config(url):
    if os.environ.get('POWERPATH_PG_RUNTIME_EXPERIMENTAL') != '1':
        raise RuntimeError('PostgreSQL cutover has NOT completed live acceptance; experimental adapter is disabled')
    normalized = url.replace('postgresql+psycopg://', 'postgresql://', 1)
    parsed = urlsplit(normalized)
    if parsed.scheme not in ('postgresql', 'postgres') or not parsed.hostname:
        raise RuntimeError('A PostgreSQL connection URL is required')
    if parse_qs(parsed.query).get('sslmode', []) != ['verify-full']:
        raise RuntimeError('PostgreSQL requires sslmode=verify-full and a trusted CA')
    schema = os.environ.get('POWERPATH_PG_SCHEMA', '')
    if not re.fullmatch(r'powerpath_runtime_[a-z0-9_]+', schema):
        raise RuntimeError('Set a separately provisioned POWERPATH_PG_SCHEMA; staging snapshots are read-only')
    if os.environ.get('POWERPATH_V27_AUTH_MODE') != 'required':
        raise RuntimeError('PostgreSQL runtime requires named authentication')
    if os.environ.get('POWERPATH_IDENTITY_PROVIDER') != 'supabase':
        raise RuntimeError('PostgreSQL runtime requires managed Supabase identity')
    return normalized, schema


@contextmanager
def postgres_db(url):
    normalized, schema = validate_config(url)
    import psycopg
    # No exception path opens SQLite. Never log the URL or driver exception text.
    raw = psycopg.connect(normalized, autocommit=True, row_factory=row_factory,
                          connect_timeout=10, prepare_threshold=None)
    try:
        role = raw.execute('SELECT r.rolsuper,r.rolbypassrls FROM pg_roles r '
                           'WHERE r.rolname=current_user').fetchone()
        if role['rolsuper'] or role['rolbypassrls']:
            raise RuntimeError('Application database role must not bypass row security')
        unsafe = raw.execute('SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
            'WHERE n.nspname=%s AND c.relkind=\'r\' AND '
            '(NOT c.relrowsecurity OR c.relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user))',
            (schema,)).fetchall()
        if unsafe:
            raise RuntimeError('Runtime tables require RLS and a non-owner application role')
        from psycopg import sql
        raw.execute(sql.SQL('SET search_path TO {}, pg_catalog').format(sql.Identifier(schema)))
        raw.execute("SET statement_timeout='20s'")
        raw.execute("SET lock_timeout='10s'")
        from server.institutional import ACTOR, TENANT
        raw.execute("SELECT set_config('powerpath.actor_id',%s,false),set_config('powerpath.tenant_id',%s,false)",
                    (ACTOR.get() or '',TENANT.get() or ''))
        yield Connection(raw, schema)
    finally:
        # close() rolls back any abandoned explicit transaction, including errors.
        raw.close()
