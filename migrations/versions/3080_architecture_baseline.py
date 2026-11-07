"""Record an audited baseline of an EXISTING legacy PowerPath SQLite schema.

Revision ID: 3080_baseline
Revises:

This is NOT the migration that creates the pre-existing PowerPath tables.
"""
from alembic import op
import json
from pathlib import Path
import sqlalchemy as sa

revision = '3080_baseline'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        raise RuntimeError('PostgreSQL migration/cutover not released; baseline is SQLite-only')
    inspector = sa.inspect(bind)
    required = {'projects', 'scenarios', 'runs', 'evidence', 'permit_items', 'delivery_milestones'}
    missing = required - set(inspector.get_table_names())
    if missing:
        raise RuntimeError('Refusing to baseline incomplete legacy database: '+','.join(sorted(missing)))
    # Compare complete core column names, declared types, and primary keys
    # to the 30.7.1 contract BEFORE stamping the baseline.
    contract = json.loads((Path(__file__).resolve().parents[2] / 'architecture/schema_contract_v30_8.json').read_text())
    for table, columns in contract['required_columns'].items():
        if table not in inspector.get_table_names():
            raise RuntimeError(f'Refusing baseline: missing contract table {table}')
        actual = {c['name']: c for c in inspector.get_columns(table)}
        pk_columns = inspector.get_pk_constraint(table).get('constrained_columns') or []
        for col, expected in columns.items():
            observed = actual.get(col)
            if observed is None or str(observed['type']).upper() != expected['type'] or int(col in pk_columns) != int(bool(expected['primary_key'])):
                raise RuntimeError(f'Refusing baseline: contract drift at {table}.{col}')
    op.create_table('platform_migration_audit',
                    sa.Column('migration_key', sa.Text(), primary_key=True),
                    sa.Column('description',sa.Text(),nullable=False),
                    sa.Column('applied_at',sa.Text(),nullable=False))
    op.execute("INSERT INTO platform_migration_audit VALUES ('3080_baseline', "
               "'Audited legacy SQLite baseline, existing tables remain module-owned', "
               "strftime('%Y-%m-%dT%H:%M:%fZ','now'))")


def downgrade():
    # No drop of legacy data and no automatic rollback of a version baseline.
    raise RuntimeError('Baseline downgrade is prohibited; restore a verified pre-migration backup')
