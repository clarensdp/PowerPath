"""Alembic can manage new migrations; legacy feature DDL remains app-bootstrapped.

DO NOT call this a PostgreSQL cutover or stamp an empty DB as migrated.
"""
from __future__ import annotations
import os
from logging.config import fileConfig
from pathlib import Path
from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
root = Path(__file__).resolve().parent.parent
path = Path(os.getenv('POWERPATH_DATA_DIR', str(root/'data'))).resolve() / 'powerpath.sqlite3'
# SQLite-only baseline. PostgreSQL target will have its own explicit migration sequence.
backend = os.getenv('POWERPATH_DATABASE_URL','')
if backend:
    raise RuntimeError('v30.8 migration has no database-URL routing or PostgreSQL cutover; use POWERPATH_DATA_DIR')
if not path.is_file() and not context.is_offline_mode():
    raise FileNotFoundError(f'Refusing to create an empty database as a migration side effect: {path}')
config.set_main_option('sqlalchemy.url', 'sqlite:///' + str(path).replace('%','%%'))

def run_migrations_offline():
    context.configure(url=config.get_main_option('sqlalchemy.url'), literal_binds=True, dialect_opts={'paramstyle':'named'})
    with context.begin_transaction():context.run_migrations()

def run_migrations_online():
    engine = engine_from_config(config.get_section(config.config_ini_section), prefix='sqlalchemy.', poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():context.run_migrations()
    engine.dispose()

if context.is_offline_mode():run_migrations_offline()
else:run_migrations_online()
