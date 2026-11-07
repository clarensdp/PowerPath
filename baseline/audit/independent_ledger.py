"""Independent Python verification of accounting identities and refinance sizing.
It does not reproduce the entire cash flow engine or a lender credit agreement.
"""
import json, subprocess, pathlib, math
ROOT=pathlib.Path(__file__).resolve().parents[1]
JS=ROOT/'workspace'/'underwrite25.js'
cases=[{}, {'dsraMonths':6}, {'termMonths':24,'dsraMonths':12,'cashSweepPct':30}, {'ltc':55,'mezzLtcPct':15,'tenantCapexPct':30,'dsraMonths':9,'cashSweepPct':40}, {'termMonths':24,'loanMaturityMode':'default'}]
assertions=0; maxres=0; results=[]
for idx,c in enumerate(cases):
    cmd=['node','-e',f"let x=require({json.dumps(str(JS))}).evaluate({json.dumps(c)}); console.log(JSON.stringify({{rows:x.rows,summary:x.summary,assumptions:x.assumptions}}))"]
    x=json.loads(subprocess.check_output(cmd,text=True)); a=x['assumptions']; rows=x['rows']; s=x['summary']
    for r in rows:
        cash_in=r['openingCash']+r['operatingCash']+r['loanSources']+r['tenantFundedCapex']+r['sponsorContribution']+r['terminalProceeds']
        cash_out=r['uses']+r['exitDebtPayoff']+r['distribution']+r['reserveMovement']+r['cash']
        cap_interest=r['capitalizedInterest']
        senior_interest=r['interest']-r['mezzDebt']*a['mezzRatePct']/1200 # unsuitable at refinance/sweep; avoid independent split
        residual=cash_in-cash_out
        reserve_res=r['reserve']-(r['openingReserve']+r['reserveMovement'])
        maxres=max(maxres,abs(residual),abs(reserve_res))
        assert abs(residual)<1e-7,(idx,r['month'],'cash',residual)
        assert abs(reserve_res)<1e-7,(idx,r['month'],'reserve',reserve_res)
        assert r['reserveDeficiency']<1e-8 or r['distribution']==0
        assert r['reserve']>=-1e-8 and r['debt']>=-1e-8 and r['mezzDebt']>=-1e-8
        assertions+=4
    for r in rows:
        if r['refinanceProceeds']>0:
            rate=a['refinanceRatePct']/1200; n=round(a['refinanceAmortMonths']); p=1/n if rate==0 else rate/(1-(1+rate)**(-n))
            capacity=max(0,r['forward12CfadsM']/max(.01,a['refinanceDscrMin']))
            ltv=a['refinanceValueM']*a['refinanceLtvPct']/100
            dscr=capacity/12/p
            dy=max(0,r['forward12NoiM'])/(a['debtYieldMinPct']/100) if a['debtYieldMinPct']>0 else float('inf')
            assert abs(min(ltv,dscr,dy)-r['refinanceProceeds'])<1e-7
            assertions+=1
    results.append({'case':idx,'months':len(rows),'financing_status':s['financeabilityStatus'],'max_cash_residual':s['sourcesUsesMaxResidual'],'max_debt_residual':s['debtMaxResidual'],'dsra_deficiency_months':len(s['dsraDeficiencyMonths'])})
res={'cases':results,'assertions':assertions,'max_independent_cash_residual_millions':maxres,'scope':'Independent arithmetic identities using JS ledger facts; see audit/reference257.py for separate Python property and finance forecast.'}
(ROOT/'audit'/'results.json').write_text(json.dumps(res,indent=2))
print(json.dumps(res,indent=2))
