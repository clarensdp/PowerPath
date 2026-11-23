import pytest
from server.services.power_capacity import constrain, period_capacity
from server.schedule27 import apply_to_config
from server.app import calculate


def config():
    c=calculate('defaults27',{})['project']
    c.update(months=120, sponsorCommitmentM=5000)
    c['buildings']=[dict(c['buildings'][0],itMW=75,constructionMonths=6,powerMonth=7,leaseMonth=7)]
    return c


def test_exact_audit_failure_and_dates():
    c=config();results=[]
    for mw,month,strategy in [(75,12,"grid"),(1,48,"onsite"),(75,48,"grid")]:
        p=dict(strategy=strategy,capacity_mw=mw,power_month=month,capex_uplift_pct=0,energy_uplift_pct=0)
        x=apply_to_config(c,p,{'effective_delay_months':0});r=calculate('underwrite',x)
        results.append(r)
        assert max(row['onlineMW'] for row in r['rows']) <= mw
        assert all(row['onlineMW']==0 for row in r['rows'] if row['month']<month)
    assert len({r['summary']['npvM'] for r in results})==3


def test_phases_pue_and_zero():
    c=config(); x=constrain(c,[{'month':20,'mw':32.5},{'month':30,'mw':65},{'month':36,'mw':97.5}],'gross')
    r=calculate('underwrite',x); periods={p['month']:p for p in period_capacity(x,r['rows'])}
    for m,mw in [(19,0),(20,25),(30,50),(36,75)]:
        assert periods[m]['operating_it_mw']==pytest.approx(mw)
    zero=calculate('underwrite',constrain(c,[{'month':1,'mw':0}]))
    assert max(r['onlineMW'] for r in zero['rows'])==0
    assert c==config()


def test_legacy_and_invalid():
    c=config();p=dict(capex_uplift_pct=0,energy_uplift_pct=0)
    assert apply_to_config(c,p,{'effective_delay_months':0})==c
    for phases in [[{'month':20,'mw':30},{'month':30,'mw':20}],[{'month':2.5,'mw':2}]]:
        with pytest.raises(ValueError):constrain(c,phases)
