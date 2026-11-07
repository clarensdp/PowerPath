#!/usr/bin/env python3
"""Single-command auditable v25.8.3 phase1A. Runs full JS test inventory and 16x45 stresses.
Captures hash and timestamps. Does not purport to verify contractual data or independent economics.
"""
from pathlib import Path
from datetime import datetime,timezone
import subprocess, hashlib, json, sys, os
root=Path(__file__).resolve().parent
work=root/'workspace'
out=root/'audit_runs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
out.mkdir(parents=True,exist_ok=True)
report={'version':'PowerPath v25.8.3 Phase 1A','timestamp_utc':datetime.now(timezone.utc).isoformat(), 'source_sha256':{}, 'tests':[], 'notes':'Arithmetic/regression assurance only; does not validate real project returns or executed loan agreements.'}
for file in ['underwrite25.js','engine2.js','contract_notes258.js','test_roadmap_phase1a.cjs']:
    report['source_sha256'][file]=hashlib.sha256((work/file).read_bytes()).hexdigest()
for f in sorted(work.glob('test_*.cjs')):
    run=subprocess.run(['node',f.name],cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=120)
    (out/(f.stem+'.log')).write_text(run.stdout)
    report['tests'].append({'script':f.name,'passed':run.returncode==0,'log':f.stem+'.log'})
    if run.returncode:
        report['passed']=False
        (out/'audit_summary.json').write_text(json.dumps(report,indent=2))
        print('FAIL',f.name,run.stdout[-1500:]);sys.exit(1)
# 16 public projects x 45 stress assumptions (reusing frozen case inputs; NOT transaction verification).
js = r'''
const fs=require('fs'),{evaluate}=require('./underwrite25');
const specs=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const out=[];
for(const p of specs)for(const delay of [0,3,6,12,18])for(const overrun of [0,10,20])for(const shock of [0,200,400]){
const a={...p.assumptions,delayMonths:delay,overrunPct:overrun,rateShockPct:shock/100};
const z=evaluate(a),s=z.summary;
const residual=Math.max(s.sourcesUsesMaxResidual,s.debtMaxResidual,s.reserveMaxResidual);
if(!Number.isFinite(s.npvM)||residual>1e-6)throw Error(p.name+' invalid NPV/residual '+residual);
out.push({project:p.name,delay,overrun,shockBps:shock,npvM:s.npvM,defaulted:s.defaulted,breachMonths:s.breachMonths.length,residual});
}
console.log(JSON.stringify({cases:specs.length,scenarios:out.length,maxResidual:Math.max(...out.map(r=>r.residual)),results:out}));
'''
run=subprocess.run(['node','-e',js,str(root/'benchmarks'/'v258_results'/'frozen_inputs_16.json')],cwd=work,capture_output=True,text=True,timeout=120)
if run.returncode:print(run.stderr);raise RuntimeError('Stress run failed')
stress=json.loads(run.stdout)
(out/'stress_results.json').write_text(json.dumps(stress['results'],indent=1))
report['stress']={'projects':stress['cases'],'scenarios':stress['scenarios'],'max_identity_residual_millions':stress['maxResidual'],'source':'Previously frozen, assumption-driven public-project cases'}
report['passed']=all(x['passed'] for x in report['tests']) and stress['scenarios']==720
(out/'audit_summary.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'passed':report['passed'],'test_suites':len(report['tests']),'stress':report['stress'],'audit_output':str(out)},indent=2))
if not report['passed']:sys.exit(1)
