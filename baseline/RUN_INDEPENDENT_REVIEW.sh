#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
echo 'A. Red-team reproduction: patched engine'
node workspace/test_claude_audit.cjs
printf '\nB. All regression suites\n'
n=0
for t in workspace/test_*.cjs; do node "$t" >/dev/null; n=$((n+1)); echo "PASS $(basename "$t")"; done
printf 'PASSED %s JS scripts\n' "$n"
printf '\nC. Prior independent reference (method limited)\n'
python3 audit/verify_v258_cases.py
printf '\nD. New independently authored reference comparison\n'
python3 red_team/evidence/ca_reference.py red_team/evidence/cases.json red_team/validation/reference.json
node red_team/evidence/dump_js.cjs "$ROOT/workspace/underwrite25.js" "$ROOT/red_team/evidence/cases.json" "$ROOT/red_team/validation/actual.json"
python3 - <<'PY'
import json, pathlib
p=pathlib.Path('red_team/validation')
a=json.loads((p/'actual.json').read_text());b=json.loads((p/'reference.json').read_text())
F=['grossRevenue','energy','ebitda','cfads','capex','tenantCashReceipt','draw','mezzDraw','capitalizedInterest','cashInterest','principal','mezzPrincipal','debt','mezzDebt','reserve','cash','sponsorContribution','distribution','dscr']
n=0;worst=0
for key in b:
    assert 'error' not in a[key],(key,a[key])
    for x,y in zip(a[key]['rows'],b[key]['rows']):
        for k in F:
            lhs,rhs=x.get(k),y.get(k)
            if lhs is None or rhs is None: assert lhs is None and rhs is None,(key,k)
            else: worst=max(worst,abs(lhs-rhs));assert abs(lhs-rhs)<1e-7,(key,x['month'],k,lhs,rhs)
            n+=1
    assert abs(a[key]['npvM']-b[key]['npvM'])<1e-7,key
print(f'PASS from-scratch independent reference: {len(b)} cases, {n} checks, max gap {worst:.3g} $M')
PY
printf '\nE. Public-case simulation sanity (not contractual validation)\n'
node benchmarks/run_benchmarks_v258.cjs | tail -12
printf '\nF. Standalone HTML build\n'
python3 workspace/build_page.py
printf '\nPASS: computational screening tests; NOT approved for lender underwriting\n'
