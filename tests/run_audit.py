"""Reproducible v26 platform & frozen-engine acceptance log."""
import hashlib,json,subprocess,sys,time,os,tempfile,socket,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
LEGACY=ROOT/'baseline'/'workspace'
results=[]

def run(name,args,timeout=90,cwd=None):
 t=time.perf_counter()
 try:
  p=subprocess.run(args,cwd=cwd or ROOT,capture_output=True,text=True,timeout=timeout)
  okay=p.returncode==0
  info=(p.stderr+'\n'+p.stdout)[-450:]
 except subprocess.TimeoutExpired:
  okay=False;info='TIMEOUT'
 results.append({'name':name,'passed':okay,'seconds':round(time.perf_counter()-t,3),'details':info})
 print(('PASS' if okay else 'FAIL'), name, flush=True)

run('Typescript static compilation',['tsc','-p','tsconfig.json'])
for path in sorted(LEGACY.glob('test_*.cjs')):
 run('legacy.'+path.stem,['node',str(path)])
run('v26 API acceptance',['python','-m','unittest','tests.test_api','-v'])
run('v26.1 notes Risk/API integration',['python','-m','unittest','tests.test_notes_integration','-v'])
run('v26.2 persistent paths PermitIQ sensitivity API',['python','-m','unittest','tests.test_v262_workflows','-v'])
run('v26.3 geographic source and critical path API',['python','-m','unittest','tests.test_v263_geo','-v'])
run('imported v25.9 red-team regressions',['node','--test','test/**/*.test.cjs'] if False else ['node','--test',*list(map(str, sorted((ROOT/'review/engine-v259/test').rglob('*.test.cjs'))))],timeout=120)
run('imported v25.9 independent reference parity',['node','scripts/reference_parity.cjs'],timeout=120,cwd=ROOT/'review/engine-v259')
# End-to-end browser acceptance launches its own clean local server and database.
with tempfile.TemporaryDirectory(prefix='powerpath26_e2e_') as tmp:
  with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as sock:
    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  env=os.environ.copy();env['POWERPATH_DATA_DIR']=tmp;env['PORT']=str(port)
  proc=subprocess.Popen(['bash',str(ROOT/'run_local.sh')],cwd=ROOT,env=env,
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  try:
    health=False
    for _ in range(80):
      try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health',timeout=1) as r:
          health=r.status==200;break
      except Exception:time.sleep(.15)
    if not health:results.append({'name':'v26 Chromium browser acceptance','passed':False,'seconds':0,'details':'Test server failed to start'})
    else:
      os.environ['POWERPATH_BROWSER_BASE']=f'http://127.0.0.1:{port}'
      # The v26.1 visual-script navigation assumptions are superseded by v26.2 project-first views.
      # The script is retained for backward-compatibility troubleshooting but not counted as the release gate.
      run('v26.2 Decision Center / PermitIQ browser acceptance',['python','tests/browser_v262.py'])
      run('v26.3 source map / milestone browser acceptance',['python','tests/browser_v263.py'])
      del os.environ['POWERPATH_BROWSER_BASE']
  finally:
    proc.terminate()
    try:proc.wait(timeout=3)
    except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=2)
from_sha=hashlib.sha256((LEGACY/'underwrite25.js').read_bytes()).hexdigest()
to_sha=hashlib.sha256((ROOT/'engine/underwrite25.js').read_bytes()).hexdigest()
old_fac=hashlib.sha256((LEGACY/'facility_waterfall259.js').read_bytes()).hexdigest()
new_fac=hashlib.sha256((ROOT/'engine/facility_waterfall259.js').read_bytes()).hexdigest()
new_origin=hashlib.sha256((ROOT/'review/engine-v259/src/underwrite.cjs').read_bytes()).hexdigest()
new_engine=hashlib.sha256((ROOT/'engine/v259_verified/src/underwrite.cjs').read_bytes()).hexdigest()
new_risk_origin=hashlib.sha256((ROOT/'review/engine-v259/src/assurance.cjs').read_bytes()).hexdigest()
new_risk=hashlib.sha256((ROOT/'engine/v259_verified/src/assurance.cjs').read_bytes()).hexdigest()
same=from_sha==to_sha and old_fac==new_fac and new_origin==new_engine and new_risk_origin==new_risk
results.append({'name':'Frozen financial-engine integrity','passed':same,'seconds':0,'details':{'underwrite_sha256':to_sha,'facility_sha256':new_fac,'imported_notes_sha256':new_engine,'imported_risk_sha256':new_risk}})
print(('PASS' if same else 'FAIL'),'financial module hashes')
report={'release':'PowerPath v26.3.0 Geographic Intelligence / Critical Path alpha','scope':'local web foundation and regression; not contractual validation',
  'passed':sum(x['passed'] for x in results),'failed':sum(not x['passed'] for x in results),
  'checks':results,'assurance':{'G4':'BLOCKED','G5':'NOT STARTED','production_authentication':'NOT IMPLEMENTED'}}
(ROOT/'V26_AUDIT.json').write_text(json.dumps(report,indent=2))
print(f"{report['passed']} PASSED, {report['failed']} FAILED")
if report['failed']:sys.exit(1)
