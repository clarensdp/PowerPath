"""Join the existing versioned parcel store with independent public data providers."""
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
from server.providers.base import PublicHTTP, now, unavailable
from server.providers.electricity import eia
from server.providers.infrastructure import public_grid
from server.providers.renewables import nrel


def record_county(parcel):
    props = parcel['feature']['properties']
    # Public parcels use five-digit GEOIDs. Source catalogs store a separate county suffix.
    geoid = props.get('geoid') or props.get('county_geoid')
    if geoid:
        return str(geoid)
    source = parcel['source']
    return str(source.get('state_fips') or '') + str(source.get('county_fips') or '')


class SiteEnergyService:
    def __init__(self, db, store, root):
        self.db, self.store = db, store
        self.http = PublicHTTP(db)
        states = json.loads((root / 'data_sources/us_states.geojson').read_text())
        self.states = {f['properties']['STATE']: f['properties']['STUSAB'] for f in states['features']}

    def parcel(self, pid, parcel_id):
        record = self.store.get(parcel_id, pid)
        if not record:
            raise HTTPException(404, 'Parcel not found in a connected source or this project snapshot')
        feature = json.loads(record['feature_json'])
        try:
            point = public_grid.valid_geometry(feature['geometry']).representative_point()
        except (ValueError, KeyError, TypeError):
            raise HTTPException(422, 'Parcel has no valid WGS84 geometry') from None
        with self.db() as con:
            source = dict(con.execute('SELECT * FROM geo29_sources WHERE id=?', (record['source_id'],)).fetchone())
        return {'parcel_id': parcel_id, 'source_version': record['version_id'], 'feature': feature,
                'latitude': point.y, 'longitude': point.x, 'state': self.states.get(source['state_fips']),
                'location_method': 'Point on parcel surface in WGS84; not a surveyed service point', 'source': source}

    def context(self, pid, parcel_id, category=None):
        parcel = self.parcel(pid, parcel_id)
        jobs = {}
        if category in (None, 'electricity'):
            jobs['eia'] = lambda: eia.fetch(self.http, pid, parcel['state'])
        if category in (None, 'infrastructure'):
            for kind in ('transmission_line', 'substation', 'service_territory'):
                jobs[kind] = lambda kind=kind: public_grid.fetch(self.http, pid, parcel['feature']['geometry'], kind,
                    record_county(parcel))
        if category in (None, 'renewables'):
            jobs['solar'] = lambda: nrel.fetch(self.http, pid, parcel['latitude'], parcel['longitude'])
        def safe(job):
            try:
                return job()
            except (ValueError, KeyError, TypeError, AttributeError):
                # A changed upstream schema cannot break parcel selection or other providers.
                return unavailable('Public provider', '', 'Source response did not match the documented schema')
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = dict(zip(jobs, pool.map(safe, jobs.values())))
        result = {'parcel': parcel, 'retrieved_at': now(),
                  'electricity': {k: results[k] for k in ('eia',) if k in results},
                  'grid_infrastructure': {k: results[k] for k in ('transmission_line', 'substation', 'service_territory') if k in results},
                  'renewable_resources': {k: results[k] for k in ('solar',) if k in results},
                  'delivered_price': {'value': None, 'unit': 'USD/MWh', 'status': 'unavailable'},
                  'grid_capacity': {'value': None, 'unit': 'MW', 'status': 'unavailable'},
                  'data_quality': {k: {'status': v['status'], 'error': v['error']} for k, v in results.items()},
                  'limitations': ['No utility-confirmed capacity, tariff, connection cost or energization date.',
                                  'Wind resource is not connected in this MVP. Solar acreage/buildability is not inferred.']}
        with self.db() as con:
            study = con.execute('SELECT body FROM site_energy_studies WHERE project_id=? AND parcel_id=?',
                                (pid, parcel_id)).fetchone()
            result['utility_study'] = json.loads(study['body']) if study else None
            if category is None:
                con.execute('''INSERT INTO site_energy_contexts VALUES(?,?,?,?,?)
                    ON CONFLICT(project_id,parcel_id) DO UPDATE SET source_version=excluded.source_version,
                    body=excluded.body,updated_at=excluded.updated_at''',
                    (pid, parcel_id, parcel['source_version'], json.dumps(result), result['retrieved_at']))
        return result

    def generation(self, pid, parcel_id, system):
        parcel = self.parcel(pid, parcel_id)
        return nrel.fetch(self.http, pid, parcel['latitude'], parcel['longitude'], system)
