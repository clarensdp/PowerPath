"""Independent arithmetic spot-check of v25.8.4 gross power expense and P&L.
No reuse of the PowerPath JS calculation code. Only one-building deterministic cases.
"""
import json,subprocess,calendar,math
from pathlib import Path
root=Path(__file__).resolve().parent
script="""
const {evaluate,defaults}=require('./workspace/underwrite25.js');
const base={...defaults(),months:24,calendarStartYear:2026,calendarStartMonth:1,ltc:0,mezzLtcPct:0,loanMaturityMode:'equity',initialCash:100,minLiquidity:0,reserveTargetM:0,exitValueM:100,constructionCostMW:1,otherOpexPct:0,fixedOpexM:0,cashTaxRatePct:0,maintenanceCapexMWYearM:0,workingCapitalDays:0,buildings:[{name:'Example',itMW:8,constructionStart:1,constructionMonths:1,powerMonth:2,leaseMonth:2,leaseTermMonths:20,rentEscalatorPct:0,rentPerKwMonth:100}]};
const results=[];for(const mode of ['landlord','tenant_direct','reimbursed'])for(const pct of [35,100]){
 const x=evaluate({...base,powerResponsibility:mode,powerPassThroughPct:pct});results.push({mode,pct,rows:x.rows.map(r=>({month:r.month,gross:r.grossEnergy,cost:r.energy,invoice:r.powerReimbursement,direct:r.tenantDirectPower,ebitda:r.ebitda,revenue:r.revenue,lease:r.leaseRevenue,cfads:r.cfads}))});
}process.stdout.write(JSON.stringify(results));
"""
p=subprocess.run(['node','-e',script],cwd=root,check=True,capture_output=True,text=True)
actual=json.loads(p.stdout);count=0;max_diff=0
for case in actual:
 for r in case['rows']:
  month=r['month'];days=calendar.monthrange(2026+(month-1)//12,1+(month-1)%12)[1]
  active=2<=month<=21
  mw=8 if active else 0
  gross=mw*1.3*days*24*85/1_000_000
  share=case['pct']/100
  if case['mode']=='landlord':energy=gross;invoice=direct=0
  elif case['mode']=='tenant_direct':energy=gross*(1-share);invoice=0;direct=gross*share
  else:energy=gross;invoice=gross*share;direct=0
  rent=mw*1000*100/1_000_000
  ebitda=rent+invoice-energy
  expected={'gross':gross,'cost':energy,'invoice':invoice,'direct':direct,'lease':rent,'revenue':rent+invoice,'ebitda':ebitda,'cfads':ebitda}
  for field,value in expected.items():
   delta=abs(r[field]-value);max_diff=max(max_diff,delta);assert delta<1e-8,(case['mode'],month,field,r[field],value)
   count+=1
print(json.dumps({'status':'PASS','checks':count,'months':24,'scenarios':len(actual),'maxDifferenceM':max_diff},indent=2))
