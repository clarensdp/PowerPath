"""v30.8 first extraction: the original core SQLite schema (identical DDL).

Other feature modules still self-initialize their own legacy schemas.
Do not use this as a PostgreSQL migration or claim that all DDL is centralized.
"""
SCHEMA = '''
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, location TEXT NOT NULL DEFAULT '',
 target_mw REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'Qualify',
 description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scenarios (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'underwrite', config_json TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(project_id,name)
);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
 scenario_version INTEGER NOT NULL, mode TEXT NOT NULL, engine_sha256 TEXT NOT NULL,
 finance_sha256 TEXT NOT NULL, input_json TEXT NOT NULL, summary_json TEXT NOT NULL,
 rows_json TEXT NOT NULL, created_at TEXT NOT NULL, label TEXT NOT NULL DEFAULT 'SCREENING / UNVERIFIED'
);
CREATE TABLE IF NOT EXISTS evidence (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 title TEXT NOT NULL, category TEXT NOT NULL, evidence_status TEXT NOT NULL DEFAULT 'unverified',
 citation TEXT NOT NULL DEFAULT '', filename TEXT NOT NULL DEFAULT '', stored_filename TEXT NOT NULL DEFAULT '',
 content_hash TEXT NOT NULL DEFAULT '', bytes INTEGER NOT NULL DEFAULT 0,
 notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS activity (
 id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, action TEXT NOT NULL,
 object_id TEXT NOT NULL, details_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_scenario ON runs(scenario_id,created_at DESC);
CREATE INDEX IF NOT EXISTS scenarios_project ON scenarios(project_id);
CREATE INDEX IF NOT EXISTS evidence_project ON evidence(project_id);
CREATE TABLE IF NOT EXISTS power_paths (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, strategy TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'hypothesis',
 capacity_mw REAL NOT NULL DEFAULT 0, power_month INTEGER, latitude REAL, longitude REAL,
 delay_months INTEGER NOT NULL DEFAULT 0, capex_uplift_pct REAL NOT NULL DEFAULT 0,
 energy_uplift_pct REAL NOT NULL DEFAULT 0, source_note TEXT NOT NULL DEFAULT '',
 evidence_id TEXT REFERENCES evidence(id) ON DELETE SET NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS permit_items (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 path_id TEXT REFERENCES power_paths(id) ON DELETE SET NULL,
 title TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'not_started',
 owner TEXT NOT NULL DEFAULT '', due_month INTEGER,
 delay_months INTEGER NOT NULL DEFAULT 0, evidence_id TEXT REFERENCES evidence(id) ON DELETE SET NULL,
 detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS permit_steps (
 id TEXT PRIMARY KEY, permit_id TEXT NOT NULL REFERENCES permit_items(id) ON DELETE CASCADE,
 title TEXT NOT NULL, is_done INTEGER NOT NULL DEFAULT 0, sort_index INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS permit_notes (
 id TEXT PRIMARY KEY, permit_id TEXT NOT NULL REFERENCES permit_items(id) ON DELETE CASCADE,
 body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS geographic_assets (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, asset_type TEXT NOT NULL, latitude REAL NOT NULL, longitude REAL NOT NULL,
 source_provider TEXT NOT NULL, source_url TEXT NOT NULL, source_record_id TEXT NOT NULL,
 vintage TEXT NOT NULL, evidence_level TEXT NOT NULL, attributes_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL, UNIQUE(project_id,source_provider,source_record_id));
CREATE INDEX IF NOT EXISTS geographic_assets_project ON geographic_assets(project_id);
CREATE TABLE IF NOT EXISTS delivery_milestones (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 path_id TEXT NOT NULL REFERENCES power_paths(id) ON DELETE CASCADE,
 permit_id TEXT REFERENCES permit_items(id) ON DELETE SET NULL,
 title TEXT NOT NULL, category TEXT NOT NULL, status TEXT NOT NULL,
 planned_month INTEGER, delay_months INTEGER NOT NULL DEFAULT 0,
 predecessor_id TEXT REFERENCES delivery_milestones(id) ON DELETE SET NULL,
 source_url TEXT NOT NULL DEFAULT '', source_note TEXT NOT NULL DEFAULT '',
 evidence_id TEXT REFERENCES evidence(id) ON DELETE SET NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS delivery_milestones_path ON delivery_milestones(path_id);
CREATE INDEX IF NOT EXISTS power_paths_project ON power_paths(project_id);
CREATE INDEX IF NOT EXISTS permits_project ON permit_items(project_id);
'''

def initialize_core_schema(db):
    """Legacy-compatible bootstrap; Alembic is not yet sole DDL authority."""
    with db() as con:
        con.executescript(SCHEMA)
        if 'float_months' not in {r[1] for r in con.execute('PRAGMA table_info(delivery_milestones)')}:
            con.execute('ALTER TABLE delivery_milestones ADD COLUMN float_months INTEGER NOT NULL DEFAULT 0')
