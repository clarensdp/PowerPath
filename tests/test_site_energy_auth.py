"""Run separately: imports the repository's required-auth test harness."""
import os
os.environ.pop('POWERPATH_DATABASE_URL', None)
os.environ.pop('POWERPATH_IDENTITY_PROVIDER', None)
from tests.v271.test_v271_required_auth import C, H


def test_new_routes_preserve_tenant_and_role_boundaries():
    pid = C.post('/api/projects',headers=H('analyst','a'),json={'name':'Energy authorization'}).json()['id']
    parcel = str(C.get('/api/parcels28/catalog',headers=H('analyst')).json()['features'][0]['properties']['PA_MCPI'])
    base = f'/api/projects/{pid}/parcels28/{parcel}/energy'
    for path in ('-context','/electricity-prices','/infrastructure','/renewables'):
        assert C.get(base+path).status_code == 401
        assert C.get(base+path,headers=H('other')).status_code == 403
    for method, path in ((C.post,'/scenario-inputs'),(C.post,'/solar-estimate'),(C.put,'/utility-study')):
        assert method(base+path,headers=H('other'),json={}).status_code == 403
        assert method(base+path,headers=H('viewer'),json={}).status_code == 403
