"""Excel add-in: served files, scoped security headers, manifest/metadata consistency, core mapping."""
import json, os, re, shutil, subprocess, tempfile, xml.dom.minidom
os.environ['POWERPATH_DATA_DIR'] = tempfile.mkdtemp(prefix='pp-excel-')
os.environ['POWERPATH_V27_AUTH_MODE'] = 'local_only'
os.environ.pop('POWERPATH_DATABASE_URL', None)
import pathlib, pytest
from fastapi.testclient import TestClient
from server.app import app

ROOT = pathlib.Path(__file__).resolve().parents[1]
C = TestClient(app, base_url='http://127.0.0.1')


def test_addin_files_get_office_scoped_headers_only():
    r = C.get('/excel/taskpane.html')
    assert r.status_code == 200
    csp = r.headers['content-security-policy']
    assert 'https://appsforoffice.microsoft.com' in csp and 'frame-ancestors' in csp and '*.officeapps.live.com' in csp
    assert 'x-frame-options' not in r.headers
    app_page = C.get('/')
    assert app_page.headers['x-frame-options'] == 'DENY' and "frame-ancestors 'none'" in app_page.headers['content-security-policy']
    assert 'appsforoffice' not in C.get('/api/health').headers['content-security-policy']
    for bad in ('/excel/../server/app.py', '/excel/secret.txt', '/excel/%2e%2e%2fapp.py'):
        assert C.get(bad).status_code == 404


def test_manifest_and_function_metadata_agree():
    xml.dom.minidom.parse(str(ROOT / 'web/excel/manifest.xml'))
    manifest = (ROOT / 'web/excel/manifest.xml').read_text()
    urls = re.findall(r'https://[^"<]+', manifest)
    assert urls and all(u.startswith('https://localhost:8768') or 'schemas.microsoft.com' in u for u in urls)
    meta = {f['id'] for f in json.loads((ROOT / 'web/excel/functions.json').read_text())['functions']}
    code = set(re.findall(r"CustomFunctions\.associate\('([A-Z]+)'", (ROOT / 'web/excel/functions.js').read_text()))
    assert meta == code == {'METRIC', 'EXPOSURE', 'SOURCE', 'PRIORITIES', 'BRIDGE', 'PATHBRIDGE', 'DELIVERABLE'}
    for f in (ROOT / 'web/excel').glob('*.js'):  # the add-in never calls the approval routes
        assert '/approvals' not in f.read_text(), f.name


def test_manifest_generator_requires_https():
    from scripts.excel_manifest import build
    assert 'https://pp.example.com/excel/taskpane.html' in build('https://pp.example.com')
    with pytest.raises(SystemExit):
        build('http://pp.example.com')


@pytest.mark.skipif(not shutil.which('node'), reason='node not installed')
def test_core_maps_real_api_responses(tmp_path):
    pid = C.post('/api/projects?starter_scenario=true', json={'name': 'Excel test', 'target_mw': 150}).json()['id']
    u = f'/api/projects/{pid}/underwriting'
    ch = C.post(u + '/assumptions', json={'key': 'construction_cost_mw', 'value': 8, 'source_kind': 'quote', 'source_name': 'EPC quote',
                'source_date': '2026-10-01', 'verification': 'estimated', 'rationale': 'Budget quote for test'}).json()['change']['id']
    C.post(u + f'/approvals/{ch}/accept', json={'note': 'ok'})
    C.post(u + '/deliverability', json={'target_month': 36, 'sources': [{'id': 'g', 'name': 'Utility', 'label': 'studied', 'mw': 150,
           'earliest_month': 24, 'likely_month': 30, 'latest_month': 40}]})
    case = C.get(u + '/approved-case').json()
    assert case['assignments'] == {'construction_cost_mw': 8} and case['result']['npvM'] is not None
    fx = {'case': case, 'priorities': C.get(u + '/priorities').json(),
          'bridge': C.post(u + '/bridge', json={'drivers': {'energization_delay_months': 6, 'power_capex_m': 50}}).json(),
          'deliverability': C.get(u + '/deliverability').json()}
    f = tmp_path / 'fx.json'
    f.write_text(json.dumps(fx))
    out = subprocess.run(['node', str(ROOT / 'tests/excel/core_check.cjs'), str(f)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert 'excel core ok' in out.stdout
