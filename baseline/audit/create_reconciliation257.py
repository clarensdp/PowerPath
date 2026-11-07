import sys,json,csv,pathlib
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from reference257 import reference,js_run
ROOT=pathlib.Path(__file__).resolve().parents[1]
case={'months':120,'ltc':50,'mezzLtcPct':15,'termMonths':24,'cashTaxRatePct':18,'maintenanceCapexMWYearM':.08,'workingCapitalDays':20,'tenantCapexPct':20,'cashSweepPct':30,'dsraMonths':6,'sponsorCommitmentM':1500}
j=js_run(case)
independent=reference(j['assumptions'])
fields=['revenue','ebitda','cfads','cashTaxes','maintenanceCapex','workingCapitalBalance','capex','tenantFundedCapex','draw','mezzDraw','cashInterest','capitalizedInterest','sweepPrincipal','debt','mezzDebt','refinanceProceeds','reserve','cash','sponsorContribution','distribution','terminalProceeds','exitDebtPayoff']
with (ROOT/'audit'/'monthly_reconciliation_257.csv').open('w',newline='') as fp:
 w=csv.writer(fp);w.writerow(['month','metric','javascript_$M','python_reference_$M','difference_$M'])
 for py,js in zip(independent,j['rows']):
  for f in fields:w.writerow([py['month'],f,f'{js[f]:.12f}',f'{py[f]:.12f}',f'{(js[f]-py[f]):.12f}'])
print('Wrote',len(independent),'monthly rows x',len(fields),'independent metrics')
