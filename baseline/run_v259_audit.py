"""Reproducible one-command alpha software QA; no lender assurance is implied."""
import concurrent.futures,hashlib,json,subprocess,sys,datetime
from pathlib import Path
root=Path(__file__).resolve().parent
ws=root/'source'/'workspace'

def run(cmd,cwd,timeout=100):
 try:
  p=subprocess.run(cmd,cwd=cwd,timeout=timeout,capture_output=True,text=True)
  return {'pass':p.returncode==0,'exit':p.returncode,'command':' '.join(map(str,cmd)),'output_tail':p.stdout[-800:]+p.stderr[-500:]}
 except Exception as e:return {'pass':False,'exit':-1,'command':' '.join(map(str,cmd)),'error':str(e)}
scripts=sorted(ws.glob('test_*.cjs'))
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    checks=list(pool.map(lambda p:(p.name,run(['node',str(p)],ws)),scripts))
fixed=run([sys.executable,str(root/'independent_notes_reference.py')],root)
bench=run(['node','benchmarks/run_power_cost_2584.cjs'],root/'source',timeout=120)
browser=run([sys.executable,str(root/'browser_qa.py')],root,timeout=120)
baseline=Path('/mnt/data/PowerPath_v25_8_5_release/PowerPath_v25_8_5/workspace/underwrite25.js')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source_unchanged=sha(baseline)==sha(ws/'underwrite25.js')
report={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'suite_pass':sum(v['pass'] for _,v in checks),'suite_total':len(checks),'tests':dict(checks),'independent_fixed_note_reference':fixed,'public_case_stress':bench,'browser':browser,'legacy_underwrite_engine_sha256':sha(ws/'underwrite25.js'),'prior_release_underwrite_engine_sha256':sha(baseline),'legacy_engine_unchanged':source_unchanged,'screening_only':True,'contract_verified_transaction_count':0,'independent_human_audit':False}
(root/'AUDIT_RUN.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k not in ('tests','timestamp_utc')},indent=2))
if not(all(x['pass'] for _,x in checks) and fixed['pass'] and bench['pass'] and browser['pass'] and source_unchanged):sys.exit(1)
