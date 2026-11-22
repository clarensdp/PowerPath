"""Additive SQLite storage for public snapshots and project-specific study entries."""
SCHEMA = '''
CREATE TABLE IF NOT EXISTS site_energy_cache (
 project_id TEXT NOT NULL REFERENCES projects(id), cache_key TEXT NOT NULL,
 body TEXT NOT NULL, retrieved_at TEXT NOT NULL, expires_at REAL NOT NULL, error TEXT,
 PRIMARY KEY(project_id,cache_key));
CREATE TABLE IF NOT EXISTS site_energy_contexts (
 project_id TEXT NOT NULL REFERENCES projects(id), parcel_id TEXT NOT NULL,
 source_version TEXT NOT NULL, body TEXT NOT NULL, updated_at TEXT NOT NULL,
 PRIMARY KEY(project_id,parcel_id));
CREATE TABLE IF NOT EXISTS site_energy_studies (
 project_id TEXT NOT NULL REFERENCES projects(id), parcel_id TEXT NOT NULL,
 body TEXT NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(project_id,parcel_id));
'''


def initialize(db):
    with db() as con:
        con.executescript(SCHEMA)


def assumptions(config):
    """Do not relabel arbitrary legacy scenario JSON as externally verified."""
    return {
        'powerCostMWh': {'value': config.get('powerCostMWh', 85), 'unit': 'USD/MWh',
                        'status': 'assumed', 'source_name': 'Saved scenario / engine default'},
        'constructionCostMW': {'value': config.get('constructionCostMW', 7), 'unit': 'million USD/MW',
                               'status': 'assumed', 'source_name': 'Saved scenario / engine default'},
        'other_inputs': 'Building capacity, schedules, PUE, leases, finance terms and construction costs retain the saved scenario assumptions.'
    }
