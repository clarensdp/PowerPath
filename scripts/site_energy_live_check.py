"""Opt-in, read-only external requests using an isolated temporary local workspace.

Run: python -m scripts.site_energy_live_check [--demo-keys]
DEMO_KEY is an explicit opt-in for published EIA/NREL examples, never a runtime fallback.
"""
import argparse
import json
import os
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo-keys', action='store_true')
    args = parser.parse_args()
    if os.environ.get('POWERPATH_DATABASE_URL'):
        raise SystemExit('Live check refuses a configured external database')
    if args.demo_keys:
        os.environ.setdefault('POWERPATH_EIA_API_KEY', 'DEMO_KEY')
        os.environ.setdefault('POWERPATH_NREL_API_KEY', 'DEMO_KEY')
    with tempfile.TemporaryDirectory(prefix='pp-energy-live-') as directory:
        os.environ['POWERPATH_DATA_DIR'] = directory
        os.environ['POWERPATH_V27_AUTH_MODE'] = 'local_only'
        from fastapi.testclient import TestClient
        from server.app import app
        c = TestClient(app, base_url='http://127.0.0.1')
        pid = c.post('/api/projects', json={'name':'Temporary live source check'}).json()['id']
        # Genuine county parcel snapshot already versioned by this repository.
        parcel = str(c.get('/api/parcels28/catalog').json()['features'][0]['properties']['PA_MCPI'])
        base = f'/api/projects/{pid}/parcels28/{parcel}/energy'
        response = c.get(base+'-context')
        response.raise_for_status()
        context = response.json()
        print(json.dumps({'parcel_id':parcel, 'state':context['parcel']['state'],
                          'latitude':context['parcel']['latitude'],'longitude':context['parcel']['longitude'],
                          'source_version':context['parcel']['source_version'],'checked_at':context['retrieved_at']}, indent=2))
        for group in ('electricity','grid_infrastructure','renewable_resources'):
            for name, result in context[group].items():
                print(json.dumps({'provider':name,'status':result['status'],'error':result['error'],
                    'source_url':result['source_url'],'features':len(result['features']),
                    'sample_points':result['points'][:2]},indent=2))
        generation = c.post(base+'/solar-estimate',json={'capacity_kw':1000})
        generation.raise_for_status()
        print(json.dumps({'solar_generation':generation.json()},indent=2))


if __name__ == '__main__':
    main()
