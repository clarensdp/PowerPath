"""Independent basic fixed-note reference: intentionally does NOT import PowerPath JS.
The reference checks due coupon, OID and amortization for a controlled debt-only case.
Not a reference for issuer-specific indenture triggers or cross-collateralized waterfalls.
"""
import json,subprocess,random
from pathlib import Path
random.seed(259)
root=Path(__file__).parent/'source'/'workspace'
fixtures=[]
for i in range(40):
    face=random.uniform(10,300)
    issue_price=random.uniform(91,100)
    rate=random.uniform(1,15)
    amort=random.uniform(0,16)
    stub=random.choice([None,100,130,150,180])
    f={"id":"note", "type":"note","buildingNames":["A"],"faceM":face,"issuePricePct":issue_price,
       "couponPct":rate,"issueMonth":1,"firstCouponMonth":7,"couponIntervalMonths":6,"amortAnnualPct":amort,
       "amortStartMonth":7,"maturityMonth":19,"sourceId":"ASSUMPTION: test"}
    if stub is not None:f['firstCouponDayCount30_360']=stub
    project={"months":24,"initialCash":0,"sponsorCommitmentM":3000,"constructionCostMW":0,
             "exitValueM":0,"leaseExpiryPolicy":"vacate","minLiquidity":0,
             "buildings":[{"name":"A","itMW":10,"constructionStart":1,"constructionMonths":1,
                "powerMonth":24,"leaseMonth":24,"leaseTermMonths":12,"rentEscalatorPct":0}]}
    fixtures.append({"project":project,"facilities":[f]})
js="""require('./underwrite25.js');const f=require('./facility_waterfall259.js');let txt='';process.stdin.on('data',c=>txt+=c);process.stdin.on('end',()=>{const rows=JSON.parse(txt).map(x=>f.evaluate(x).rows.map(r=>({month:r.month,interest:r.interestDue,principal:r.principalDue,closing:r.closingDebt,draws:r.draws,oid:r.oid,debtResidual:r.debtResidual,cashResidual:r.cashResidual})));process.stdout.write(JSON.stringify(rows));});"""
proc=subprocess.run(['node','-e',js],input=json.dumps(fixtures),text=True,cwd=root,capture_output=True,check=True)
results=json.loads(proc.stdout)
count=0;maxdiff=0
for case, observed in zip(fixtures, results):
    f=case['facilities'][0]
    balance=0;face=f['faceM']
    for month in range(1,25):
        loan_cash=0;oid=0;interest=0;principal=0
        if month==1:
            balance=face;loan_cash=face*f['issuePricePct']/100;oid=face-loan_cash
        if month in (7,13,19):
            fraction=(f.get('firstCouponDayCount30_360',180)/360) if month==7 else 0.5
            interest=balance*f['couponPct']/100*fraction
            principal=min(balance,face*f['amortAnnualPct']/200)
        if month==19:principal=balance
        balance-=principal
        r=observed[month-1]
        for key,expected in [('closing',balance),('interest',interest),('principal',principal),('draws',loan_cash),('oid',oid),('debtResidual',0),('cashResidual',0)]:
            difference=abs(r[key]-expected);maxdiff=max(maxdiff,difference);count+=1
            if difference>1e-7:raise AssertionError(f"case {f}, month {month}, {key}: JS={r[key]} independent={expected} diff={difference}")
print(json.dumps({'cases':len(fixtures),'monthly_field_checks':count,'max_difference_M':maxdiff,'comparison':'independent Python fixed-note arithmetic, no shared JS financial helpers','limits':'synthetic notes; not indenture-level verification'},indent=2))
