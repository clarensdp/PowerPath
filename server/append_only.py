"""Append-only protection for financial outputs and their audit evidence (v30.8.2).

Closes the Nov 4 review finding that saved financial runs could be hard-deleted. SQLite enforces it here with
triggers; PostgreSQL enforces the same rule through infrastructure/runtime_policies.py (no UPDATE/DELETE grants).

Rules
- runs, feasibility_v82_runs, activity: insert-only. No UPDATE, no DELETE.
- evidence: no DELETE. A record may be updated exactly once, to attach its file (stored_filename '' -> value);
  descriptive fields can never change. A new version is a new record.

A database owner with raw file access can still drop triggers. This protects against application bugs and
accidental or role-level tampering; it is not a substitute for backups or WORM storage.
"""

APPEND_ONLY_TABLES = ('runs', 'feasibility_v82_runs', 'activity')

_TRIGGERS = [
    *[
        sql
        for table in APPEND_ONLY_TABLES
        for sql in (
            f"CREATE TRIGGER IF NOT EXISTS pp_append_only_{table}_no_update BEFORE UPDATE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only: create a new record instead'); END;",
            f"CREATE TRIGGER IF NOT EXISTS pp_append_only_{table}_no_delete BEFORE DELETE ON {table} "
            f"BEGIN SELECT RAISE(ABORT, '{table} is append-only: records cannot be deleted'); END;",
        )
    ],
    "CREATE TRIGGER IF NOT EXISTS pp_append_only_evidence_no_delete BEFORE DELETE ON evidence "
    "BEGIN SELECT RAISE(ABORT, 'evidence is append-only: records cannot be deleted'); END;",
    "CREATE TRIGGER IF NOT EXISTS pp_append_only_evidence_attach_once BEFORE UPDATE ON evidence "
    "WHEN OLD.stored_filename <> '' OR NEW.stored_filename = '' "
    "OR NEW.id IS NOT OLD.id OR NEW.project_id IS NOT OLD.project_id OR NEW.title IS NOT OLD.title "
    "OR NEW.category IS NOT OLD.category OR NEW.evidence_status IS NOT OLD.evidence_status "
    "OR NEW.citation IS NOT OLD.citation OR NEW.notes IS NOT OLD.notes OR NEW.created_at IS NOT OLD.created_at "
    "BEGIN SELECT RAISE(ABORT, 'evidence is immutable once its file is attached: create a new record'); END;",
]


def install(db):
    """Idempotently create the SQLite triggers. No-op for PostgreSQL connections (policies handle it there)."""
    with db() as con:
        if not hasattr(con, 'executescript'):
            return
        existing = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for sql in _TRIGGERS:
            table = sql.split(' ON ', 1)[1].split(' ', 1)[0]
            if table in existing:
                con.execute(sql)
