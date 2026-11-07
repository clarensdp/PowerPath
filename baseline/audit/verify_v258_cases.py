"""Independent property/financing calculation tests for v25.8 change cases.
No historical disclosure is treated as full project-level contract verification.
"""
import json, pathlib, sys
from copy import deepcopy
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
from reference257 import compare, js_run
root=pathlib.Path(__file__).resolve().parents[1]
base=js_run({})['assumptions']
def case(name,**changes):
  s=deepcopy(base);s.update(changes);return name,s
one=[dict(name='A',itMW=100,constructionStart=1,constructionMonths=2,powerMonth=3,leaseMonth=3,leaseTermMonths=24,rentEscalatorPct=12,rentPerKwMonth=100)]
late=[dict(name='A',itMW=20,constructionStart=1,constructionMonths=5,powerMonth=6,leaseMonth=6,leaseTermMonths=24),dict(name='B',itMW=30,constructionStart=20,constructionMonths=6,powerMonth=26,leaseMonth=26,leaseTermMonths=24)]
checks=[
 case('partially energized separate cohorts',months=72,initialCash=1000,ltc=0,mezzLtcPct=0,minLiquidity=0,reserveTargetM=0,buildings=one,powerTranches=[{'building':'A','mw':50,'month':3},{'building':'A','mw':50,'month':15}]),
 case('power gate despite early dedicated tranche',months=72,initialCash=1000,ltc=0,mezzLtcPct=0,minLiquidity=0,reserveTargetM=0,buildings=[dict(one[0],powerMonth=10)],powerTranches=[{'building':'A','mw':100,'month':3}]),
 case('equity maturity with late development',months=70,initialCash=4000,ltc=65,mezzLtcPct=5,minLiquidity=0,reserveTargetM=0,loanMaturityMode='equity',termMonths=10,buildings=late),
 case('simultaneous reserve and DSRA',months=120,initialCash=3000,termMonths=24,dsraMonths=6,reserveTargetM=12),
 case('leap year energy month',months=72,calendarStartYear=2028,calendarStartMonth=1,pue=1,powerCostMWh=100,initialCash=1000,ltc=0,mezzLtcPct=0,minLiquidity=0,reserveTargetM=0,buildings=[dict(one[0],constructionMonths=1,powerMonth=2,leaseMonth=2)]),
 case('tenant funding collection delay',months=72,initialCash=50,sponsorCommitmentM=50,ltc=0,mezzLtcPct=0,minLiquidity=0,reserveTargetM=0,tenantCapexPct=100,tenantFundingLagMonths=3,buildings=one,fundingDefaultPolicy='continue'),
 case('staggered all-in contracted rent',months=80,initialCash=1000,ltc=0,mezzLtcPct=0,minLiquidity=0,reserveTargetM=0,buildings=[dict(one[0],rentInputMode='total',contractedRentM=240)],powerTranches=[{'building':'A','mw':50,'month':3},{'building':'A','mw':50,'month':15}]),
]
results=compare(checks)
(root/'audit'/'reference258_results.json').write_text(json.dumps(results,indent=2))
print(json.dumps({'cases':len(checks),'assertions':results['assertions'],'max_gap_m':results['max_gap_m']},indent=2))
