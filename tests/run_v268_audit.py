"""Single-command audit with honest partial/failure status. Saves a durable JSON run report.

RT patch: (1) the full inherited audit runs by default (use --focused for the old quick subset);
(2) engine integrity is checked against hashes recorded IN THIS TREE (docs/ENGINE_BASELINE_SHA256.txt,
docs/IMPORTED_V259_HASHES.json) instead of a v26.3 ZIP at an author-machine path that is not shipped;
(3) independent red-team suites (adversarial finance checks, reference parity against engine/underwrite25.js,
API/agent red-team tests) are included. Known-open issues are reported, never hidden.
"""
import subprocess, datetime, hashlib, json, os, sys, time, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
FOCUSED = '--focused' in sys.argv
ENV = {**os.environ, 'RT_ROOT': str(ROOT), 'PYTHONDONTWRITEBYTECODE': '1'}
CHECKS = [
 ('TypeScript build', ['tsc', '-p', 'tsconfig.json', '--pretty', 'false']),
 ('v26.4–26.8 APIs', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_v268_intelligence.py', '-v']),
 ('live agent mocked provider', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_v268_live_workflow.py', '-v']),
 ('red-team API (B/C/D/E/G)', [sys.executable, '-m', 'unittest', 'tests.redteam.test_redteam_api', '-v']),
 ('red-team agents (F)', [sys.executable, '-m', 'unittest', 'tests.redteam.test_redteam_agents', '-v']),
 ('red-team adversarial finance (engine/underwrite25.js)', ['node', 'tests/redteam/finance_adversarial.cjs', 'engine/underwrite25.js']),
 ('reference parity vs engine/underwrite25.js', ['node', 'tests/redteam/parity_underwrite25.cjs', str(ROOT), 'engine/underwrite25.js']),
 ('v27.0 security / transaction register (required auth, separate process)', [sys.executable, '-m', 'unittest', 'tests.test_v27_security_transaction', '-v']),
 ('v27.1 waterfall oracle (independent identities, hand cases, tests 1-10)', [sys.executable, '-m', 'unittest', 'tests.v271.oracle_waterfall', '-v']),
 ('v27.1 delay convention and interface parity (tests 11-13)', [sys.executable, '-m', 'unittest', 'tests.v271.test_schedule_parity', '-v']),
 ('v27.1 Core Scientific notes, evidence, immutability, gates (tests 14-17, 19, 20)', [sys.executable, '-m', 'unittest', 'tests.v271.test_core_scientific', '-v']),
 ('v27.1 required-auth tenancy and promotion (tests 17-18)', [sys.executable, '-m', 'unittest', 'tests.v271.test_v271_required_auth', '-v']),
 ('v27.1 adversarial finance (engine/underwrite27.js)', ['node', 'tests/redteam/finance_adversarial.cjs', 'engine/underwrite27.js']),
 ('v27.1 reference parity with changed-treatment localisation', ['node', 'tests/v271/reference_parity_v271.cjs']),
 ('v27.1 engine reproducible from frozen v25.8.5 source', [sys.executable, 'tools/build_underwrite27.py', '.', '--check']),
 ('desktop tablet mobile browser', [sys.executable, 'tests/browser_v268.py']),
]
if not FOCUSED:
    CHECKS.insert(-1, ('full inherited PowerPath audit', [sys.executable, 'tests/run_audit.py']))
report = {'release': 'v27.1.0-alpha', 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'checks': [], 'financial_engine_integrity': {},
          'live_model_calls_executed': 0, 'lender_certification': 'BLOCKED', 'source_delivery_verified': False, 'full_inherited_audit_rerun': not FOCUSED}
for name, cmd in CHECKS:
    t = time.monotonic()
    try:
        p = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=600, env=ENV); rc, out = p.returncode, p.stdout
    except Exception as exc:
        rc, out = 1, f'could not run: {exc!r}'
    report['checks'].append({'name': name, 'exit_code': rc, 'elapsed_seconds': round(time.monotonic() - t, 2), 'pass': rc == 0, 'tail': out[-1500:]})
    print(('PASS' if rc == 0 else 'FAIL') + ' ' + name, flush=True)
expected = {}
for line in (ROOT / 'docs/ENGINE_BASELINE_SHA256.txt').read_text().split('\n'):
    if line.strip(): h, rel = line.split(); expected[rel] = h
for name, h in json.loads((ROOT / 'docs/IMPORTED_V259_HASHES.json').read_text()).items():
    expected['engine/v259_verified/src/' + name] = h
for line in (ROOT / 'docs/v27_1/ENGINE_V271_SHA256.txt').read_text().split('\n'):
    if line.strip(): h, rel = line.split(); expected[rel] = h
for rel, h in sorted(expected.items()):
    actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    report['financial_engine_integrity'][rel] = {'unchanged': actual == h, 'sha256': actual, 'expected': h, 'reference': 'in-tree baseline file'}
z = os.environ.get('POWERPATH_V263_ZIP')
if z and Path(z).exists():
    with zipfile.ZipFile(z) as zz:
        for rel in list(expected):
            report['financial_engine_integrity'][rel]['matches_v26_3_zip'] = hashlib.sha256(zz.read('PowerPath_v26_3/' + rel)).hexdigest() == report['financial_engine_integrity'][rel]['sha256']
ok = all(v['unchanged'] for v in report['financial_engine_integrity'].values())
print(('PASS' if ok else 'FAIL') + ' financial engine hashes vs in-tree baseline', flush=True)
report['finished_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
report['pass'] = all(c['pass'] for c in report['checks']) and ok
(ROOT / 'docs' / 'V26_8_TEST_RESULTS.json').write_text(json.dumps(report, indent=2))
print('RESULT', report['pass'], 'checks', len(CHECKS) + 1)
if not report['pass']: sys.exit(1)
