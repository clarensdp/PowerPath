"""Additive SQLite storage for public snapshots and project-specific study entries."""
SCHEMA = '''
CREATE TABLE IF NOT EXISTS power_path_inputs (path_id TEXT PRIMARY KEY REFERENCES power_paths(id), body TEXT NOT NULL);

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


def path_inputs(con, path):
    import json
    # Legacy PostgreSQL runtime has no new SQLite tables.
    import os
    if os.environ.get('POWERPATH_DATABASE_URL'):
        return path
    row = con.execute('SELECT body FROM power_path_inputs WHERE path_id=?',(path['id'],)).fetchone()
    return {**path, **json.loads(row['body'])} if row else path


def save_path_inputs(con, pid, path_id, data):
    import os
    if os.environ.get("POWERPATH_DATABASE_URL"):
        return
    import json
    from fastapi import HTTPException
    from server.services.power_capacity import tranches
    values={k:data.get(k) for k in ('parcel_id','power_phases','capacity_basis')}
    if values['parcel_id'] and not con.execute('SELECT 1 FROM parcel_shortlist28 WHERE project_id=? AND parcel_id=?',(pid,values['parcel_id'])).fetchone():
        raise HTTPException(422,'Shortlist the selected parcel in this project first')
    if values['power_phases'] is not None:
        tranches(values['power_phases'],1,values['capacity_basis'])
    con.execute('INSERT INTO power_path_inputs VALUES(?,?) ON CONFLICT(path_id) DO UPDATE SET body=excluded.body',(path_id,json.dumps(values)))
