"""Offline browser acceptance. Requires optional Playwright and Chrome/Chromium.

python -m tests.browser_site_energy
No production routes, external data or user's database are modified.
"""
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit, parse_qs

os.environ['POWERPATH_DATA_DIR'] = tempfile.mkdtemp(prefix='pp-energy-browser-')
os.environ['POWERPATH_V27_AUTH_MODE'] = 'local_only'
for name in ('EIA','NREL'):
    os.environ[f'POWERPATH_{name}_API_KEY'] = 'SYNTHETIC_TEST_KEY'
os.environ.pop('POWERPATH_DATABASE_URL', None)
os.environ.pop('POWERPATH_IDENTITY_PROVIDER', None)
os.environ.pop('POWERPATH_TERRITORY_LAYER_URL', None)
os.environ.pop('POWERPATH_SUBSTATION_LAYER_URL', None)

from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from server.app import app
from tests.site_energy_samples import MockTransport


def main():
    c = TestClient(app,base_url='http://127.0.0.1')
    app.state.site_energy.http.transport = MockTransport()
    pid = c.post('/api/projects?starter_scenario=true',json={'name':'Browser acceptance — synthetic inputs','target_mw':50}).json()['id']
    c.post(f'/api/projects/{pid}/paths',json={'name':'Test grid hypothesis','strategy':'grid','capacity_mw':50,'power_month':19})
    catalog = c.get('/api/parcels28/catalog').json()
    catalog['messages'] = ['Offline browser test: genuine bundled VA parcel geometry; energy responses are synthetic test fixtures.']
    out = Path(os.environ.get('POWERPATH_BROWSER_OUTPUT','/tmp/powerpath-energy-browser'))
    out.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        executable = os.environ.get('POWERPATH_CHROMIUM')
        mac = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        if not executable and Path(mac).exists():
            executable = mac
        browser = p.chromium.launch(headless=True,executable_path=executable)
        page = browser.new_page(viewport={'width':1500,'height':1000})
        errors = []
        acreage_requests = []
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(request):
            url = urlsplit(request.request.url)
            if url.hostname != '127.0.0.1':
                request.abort()
                return
            if url.path == '/api/geo30/parcels':
                minimum = float(parse_qs(url.query).get('min_acres',['50'])[0])
                acreage_requests.append(minimum)
                filtered = {**catalog,'features':[f for f in catalog['features']
                    if f['properties'].get('PA_LEGAL_SQFT') is not None
                    and f['properties']['PA_LEGAL_SQFT']/43560 >= minimum]}
                request.fulfill(status=200,content_type='application/json',body=json.dumps(filtered))
                return
            response = c.request(request.request.method,url.path+('?' + url.query if url.query else ''),
                content=request.request.post_data,headers={'Content-Type':'application/json'} if request.request.post_data else {})
            body = response.content
            if url.path == '/assets/vendor/leaflet.js':
                body += b'\nL.Map.addInitHook(function(){window.parcelTestMap=this;});\n'
            request.fulfill(status=response.status_code,body=body,
                headers={k:v for k,v in response.headers.items() if k.lower() not in ('content-length','content-encoding')})
        page.route('**/*',route)
        page.goto('http://127.0.0.1/')
        page.locator('[data-parcel]').first.wait_for()
        def assert_parcel_filter(minimum):
            expected = sorted(str(f['properties']['PA_MCPI']) for f in catalog['features']
                if f['properties'].get('PA_LEGAL_SQFT') is not None and f['properties']['PA_LEGAL_SQFT']/43560 >= minimum)
            page.wait_for_function('(count) => document.querySelectorAll("[data-parcel]").length === count',arg=len(expected))
            listed = sorted(page.locator('[data-parcel]').evaluate_all('(els) => els.map(e => e.dataset.parcel)'))
            mapped = sorted(page.evaluate('''() => {
                const ids=[]; window.parcelTestMap.eachLayer(layer => {
                    const props=layer.feature?.properties;
                    if (props?.PA_MCPI) ids.push(String(props.workspace_id || props.PA_MCPI));
                }); return ids;
            }'''))
            assert listed == mapped == expected
            assert page.locator('#min-area').input_value() == str(minimum)
            assert acreage_requests[-1] == minimum
        assert_parcel_filter(50)
        for minimum in (0,100):
            with page.expect_response(lambda r: '/api/geo30/parcels?' in r.url and f'min_acres={minimum}' in r.url):
                page.locator('#min-area').select_option(str(minimum))
            assert_parcel_filter(minimum)
        with page.expect_response(lambda r: '/api/geo30/parcels?' in r.url and 'min_acres=50' in r.url):
            page.locator('#reset-filters').click()
        assert_parcel_filter(50)
        page.locator('[data-parcel]').first.click()
        page.locator('#energy-apply').wait_for(timeout=30000)
        assert 'PJM' not in page.locator('#site-energy').inner_text()
        assert page.locator('#energy-node, #energy-pjm, [name=delivery_adjustment_mwh]').count() == 0
        assert '82.5 USD/MWh' in page.locator('#site-energy').inner_text()
        assert 'SYNTHETIC TEST LINE' in page.locator('#site-energy').inner_text()
        page.locator('[data-energy-asset]').first.click()
        page.locator('.leaflet-popup-content').wait_for()
        assert 'Capacity and energization unknown' in page.locator('.leaflet-popup-content').inner_text()
        page.locator('.leaflet-popup-close-button').click()
        page.locator('#energy-solar [name=capacity_kw]').fill('1000')
        page.locator('#energy-solar button').click()
        page.get_by_text('1,500 MWh/year',exact=True).wait_for()
        page.locator('#energy-basis').select_option('eia_reference:0')
        page.locator('#energy-apply [name=rationale]').fill('Offline test: explicitly use state retail average as a scenario assumption.')
        page.locator('#energy-apply [name=include_solar]').check()
        page.locator('#energy-apply button').click()
        page.locator('#energy-run-result').wait_for(timeout=30000)
        assert '$82.50/MWh' in page.locator('#energy-run-result').inner_text()
        assert 'Saved scenario v2' in page.locator('#energy-run-result').inner_text()
        page.screenshot(path=str(out/'parcel-energy-desktop.png'),full_page=True)
        page.locator('.nav [data-step="3"]').click()
        page.get_by_role('heading',name='Energy input provenance').wait_for(timeout=30000)
        assert '$82.5/MWh' in page.locator('#econ').inner_text()
        page.screenshot(path=str(out/'economics-desktop.png'),full_page=True)
        page.locator('.nav [data-step="1"]').click()
        page.locator('#energy-apply').wait_for()
        page.set_viewport_size({'width':390,'height':844})
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), 'Mobile horizontal overflow'
        page.screenshot(path=str(out/'parcel-energy-mobile.png'),full_page=True)
        assert not errors, errors
        runs = c.get(f'/api/projects/{pid}/runs').json()
        assert runs
        print(json.dumps({'browser':'Chromium','offline':True,'flow':'VA parcel → context → map popup → solar estimate → EIA selection → saved financial run → Economics',
                          'acreage_filters_verified':[50,0,100,50], 'map_list_parity':True,
                          'mobile_overflow':False,'page_errors':errors,'screenshots':str(out)},indent=2))
        browser.close()


if __name__ == '__main__':
    main()
