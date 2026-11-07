"""Independently authored Python *forecast* reference for PowerPath v25.7.
Inputs shared as JSON; does NOT use JavaScript ledger lines to calculate its outputs.
This is a synthetic-contract arithmetic comparison, NOT an external lender model audit.
"""
from __future__ import annotations
import json, math, pathlib, subprocess, calendar

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE = str(ROOT/'workspace'/'underwrite25.js')


def reference(spec: dict):
    c = dict(spec)
    horizon = int(c['months'])
    buildings = c['buildings']
    power_blocks = c.get('powerTranches', [])
    rent_base = float(c['rentPerKwMonth'])
    pue = float(c['pue'])
    mw_basis = c.get('capacityBasis','IT')
    delay = c['delayMonths']

    # Independently forecast each commissioned power cohort, with its own lease age.
    # Input ordering determines allocation priority for shared power. Contract evidence
    # for that allocation is NOT implied by this deterministic screening convention.
    commissioned={b['name']:0. for b in buildings}
    cohorts={b['name']:[] for b in buildings}
    props=[]
    for month in range(horizon + 13):
        build_spend=tenant=total_rent=rebates=served_mw=0.
        shared=sum(q['mw'] for q in power_blocks if not q.get('building') and q['month']+delay<=month)
        for b in buildings:
            mw=b['itMW']/(pue if b.get('capacityBasis',mw_basis)=='gross' else 1)
            start=b['constructionStart']; end=start+b['constructionMonths']-1
            spending=mw*c['constructionCostMW']*(1+c['overrunPct']/100)/b['constructionMonths'] if start<=month<=end else 0.
            build_spend+=spending;tenant+=spending*b.get('tenantCapexPct',c['tenantCapexPct'])/100
            ready=max(end+1,b['powerMonth']+delay,b['leaseMonth']+delay)
            available=0.
            if month>=ready:
                if power_blocks:
                    assigned=sum(q['mw'] for q in power_blocks if q.get('building')==b['name'] and q['month']+delay<=month)
                    portion=min(max(0,mw-assigned),shared)
                    shared-=portion
                    available=min(mw,assigned+portion)
                else:
                    available=mw
            delta=available-commissioned[b['name']]
            if delta < -1e-8:raise ValueError('Nonmonotone shared supply for '+b['name'])
            if delta > 1e-9:cohorts[b['name']].append((delta,month))
            commissioned[b['name']]=available
            term=b.get('leaseTermMonths',180)
            mode=b.get('rentInputMode','starting')
            step=b.get('rentEscalatorPct',2.5)/100
            contract_factors=sum((1+step)**(i//12) for i in range(term)) if mode=='total' else None
            pay_schedule=b.get('annualRentM',[])
            if isinstance(pay_schedule,str):pay_schedule=[float(x) for x in pay_schedule.split(',')]
            for portion,commissioned_month in cohorts[b['name']]:
                age=month-commissioned_month
                if age<0 or age>=term:continue
                served_mw+=portion
                if mode=='total':
                    payment=b['contractedRentM'] * (1+step)**(age//12) / contract_factors
                elif mode=='schedule':
                    payment=pay_schedule[age//12]/12
                else:
                    payment=mw*1000*b.get('rentPerKwMonth',rent_base)*(1+step)**(age//12)/1e6
                paid=payment*portion/mw
                total_rent+=paid
                if age<b.get('tenantCreditMonths',c['tenantCreditMonths']):
                    rebates+=paid*b.get('tenantRentCreditPct',c['tenantRentCreditPct'])/100
        rev=total_rent-rebates
        month_index=c['calendarStartMonth']-1+month-1
        cal_year=c['calendarStartYear']+month_index//12
        cal_month=month_index%12+1
        energy_hours=calendar.monthrange(cal_year,cal_month)[1]*24
        energy=served_mw*pue*energy_hours*c['powerCostMWh']*(1+c['energyShockPct']/100)/1e6
        ebitda=rev-energy-rev*c['otherOpexPct']/100-(c['fixedOpexM'] if served_mw else 0.)
        taxes=max(0,ebitda)*c['cashTaxRatePct']/100
        maintenance=served_mw*c['maintenanceCapexMWYearM']/12
        wc=max(0,rev)*c['workingCapitalDays']/30
        props.append(dict(capex=build_spend,tenantFundedCapex=tenant,grossRevenue=total_rent,rentCredits=rebates,onlineMW=served_mw,revenue=rev,energy=energy,ebitda=ebitda,cashTaxes=taxes,maintenanceCapex=maintenance,workingCapitalBalance=wc))
    cashflow = lambda n: props[n]['ebitda']-props[n]['cashTaxes']-props[n]['maintenanceCapex']-(props[n]['workingCapitalBalance']-props[n-1]['workingCapitalBalance'])
    balance = float(c['initialCash']); escrow = 0.; senior = 0.; junior = 0.; equity = balance
    first_draw = maturity = None; term_issued = False; facility_closed = False; impaired = False; outcome=[]
    commit = c.get('sponsorCommitmentM')
    def credit():return float('inf') if commit is None else max(0.,commit-equity)
    def inject(amount):
        nonlocal equity
        supplied = min(max(0.,amount),credit())
        equity += supplied
        return supplied
    for t in range(1,horizon+1):
        p = props[t]; initial_cash=balance
        spend = p['capex']-p['tenantFundedCapex']
        reimbursement=props[t-c['tenantFundingLagMonths']]['tenantFundedCapex'] if t>c['tenantFundingLagMonths'] else 0.
        a = spend*c['ltc']/100 if not facility_closed and not impaired else 0
        b = spend*c['mezzLtcPct']/100 if not facility_closed and not impaired else 0
        if a+b and first_draw is None:first_draw=t; maturity=t+round(c['termMonths'])-1
        upfront_fee = a*c['debtFee']/100+b*c['mezzFeePct']/100
        senior += a; junior += b
        si = senior*(c['refinanceRatePct'] if term_issued else c['rate']+c['rateShockPct'])/1200
        ji = junior*c['mezzRatePct']/1200
        building = any(x['constructionStart']<=t<x['constructionStart']+x['constructionMonths'] for x in buildings)
        rolled = si+ji if building and not term_issued else 0.
        csi = (rolled*si/(si+ji)) if rolled else 0.
        cji = rolled-csi
        senior+=csi; junior+=cji
        interest_cash=si+ji-rolled
        principal_s = principal_j = refinancing = fee_refi = 0.
        if t==maturity and not term_issued:
            senior_old, junior_old = senior, junior
            if impaired:
                pass
            elif c['loanMaturityMode']=='refinance':
                forward_cfads = sum(cashflow(t+k) for k in range(1,13))
                forward_noi = sum(props[t+k]['ebitda']-props[t+k]['maintenanceCapex'] for k in range(1,13))
                mr = c['refinanceRatePct']/1200
                amort = round(c['refinanceAmortMonths'])
                factor = 1/amort if mr==0 else mr/(1-(1+mr)**(-amort))
                lv = c['refinanceValueM']*c['refinanceLtvPct']/100
                ds = max(0.,forward_cfads)/max(.01,c['refinanceDscrMin'])/(12*factor)
                dy = max(0.,forward_noi)/(c['debtYieldMinPct']/100) if c['debtYieldMinPct'] else float('inf')
                proposed=max(0.,min(lv,ds,dy))
                fee_proposed=proposed*c['refinanceFeePct']/100
                available = max(0.,balance+cashflow(t)+a+b+reimbursement-p['capex']-upfront_fee-interest_cash-c['minLiquidity'])+credit()
                if senior_old+junior_old+fee_proposed-proposed > available+1e-8:impaired=True
                else:
                    refinancing=proposed;fee_refi=fee_proposed
                    principal_s=senior_old;principal_j=junior_old;senior=proposed;junior=0;term_issued=True;facility_closed=True
            elif c['loanMaturityMode']=='equity':
                available=max(0.,balance+cashflow(t)+a+b+reimbursement-p['capex']-upfront_fee-interest_cash-c['minLiquidity'])+credit()
                if senior_old+junior_old>available+1e-8:impaired=True
                else:principal_s=senior_old;principal_j=junior_old;senior=junior=0.;facility_closed=True
            else:impaired=True
        elif term_issued and t>maturity:
            count=max(1,c['refinanceAmortMonths']-(t-maturity-1))
            rr=c['refinanceRatePct']/1200  # v25.8-CA P1: annuity repayment consistent with sizing
            pmt=senior/count if rr==0 else senior*rr/(1-(1+rr)**-count)
            principal_s=min(senior,max(0.,pmt-senior*rr))
            senior-=principal_s
        ds=interest_cash+(0 if t==maturity else principal_s+principal_j)
        cf=cashflow(t)
        ratio=cf/ds if ds>0 else None
        owed=p['capex']+upfront_fee+fee_refi+interest_cash+principal_s+principal_j
        balance += cf+a+b+refinancing+reimbursement-owed
        funded=inject(max(0,c['minLiquidity']-balance)); balance+=funded
        if balance < c['minLiquidity']-1e-8:impaired=True
        if term_issued and senior>0:
            left=max(1,c['refinanceAmortMonths']-(t-maturity))
            rr=c['refinanceRatePct']/1200
            pay=senior/left if rr==0 else senior*rr/(1-(1+rr)**(-left))
            target=c['reserveTargetM']+c['dsraMonths']*pay
        else:target=c['reserveTargetM']
        shift=0
        if escrow<target:
            transfer=min(target-escrow,max(0.,balance-c['minLiquidity']))
            escrow+=transfer;balance-=transfer;shift+=transfer
        else:
            transfer=escrow-target
            escrow-=transfer;balance+=transfer;shift-=transfer
        if escrow<target:
            additional=inject(target-escrow)
            funded+=additional
            escrow+=additional;shift+=additional
        blocked=impaired or escrow<target-1e-8 or (ratio is not None and ratio<c['dscrCovenant'] and c['lockDistributionsOnBreach']) or (senior+junior>1e-9 and (ratio is None or ratio<c['distributionDscrMin']))
        swept=0.
        if senior+junior>1e-9 and not impaired and c['cashSweepPct']>0:
            swept=min(senior,max(0.,balance-c['minLiquidity'])*c['cashSweepPct']/100)
            senior-=swept;balance-=swept
        payout=0.
        if not blocked and c['distributionPolicy']=='excess' and t<horizon:
            payout=max(0.,balance-c['minLiquidity']);balance-=payout
        sale=terminal_paid=0.
        if t==horizon:
            sale=c['exitValueM']*(1-c['exitCostPct']/100)
            terminal_paid=min(senior+junior,max(0.,balance+sale+escrow))
            pay_s=min(senior,terminal_paid);pay_j=terminal_paid-pay_s
            senior-=pay_s;junior-=pay_j
            balance+=sale-terminal_paid+escrow
            escrow=0.
            if senior+junior>1e-8:impaired=True
            if not impaired and balance>0:payout+=balance;balance=0.
        outcome.append(dict(month=t,onlineMW=p['onlineMW'],revenue=p['revenue'],ebitda=p['ebitda'],cfads=cf,cashTaxes=p['cashTaxes'],maintenanceCapex=p['maintenanceCapex'],workingCapitalBalance=p['workingCapitalBalance'],capex=p['capex'],tenantFundedCapex=p['tenantFundedCapex'],tenantCashReceipt=reimbursement,draw=a,mezzDraw=b,cashInterest=interest_cash,capitalizedInterest=rolled,principal=principal_s+swept,sweepPrincipal=swept,debt=senior,mezzDebt=junior,dscr=ratio,refinanceProceeds=refinancing,reserve=escrow,cash=balance,sponsorContribution=funded,distribution=payout,terminalProceeds=sale,exitDebtPayoff=terminal_paid))
    return outcome


def js_run(assumptions):
    source="let p=require("+json.dumps(MODULE)+");console.log(JSON.stringify(p.evaluate("+json.dumps(assumptions)+")))"
    return json.loads(subprocess.check_output(['node','-e',source],text=True))


def compare(cases):
    all_cases=[]; assertions=0; maximum=0.
    fields=['onlineMW','revenue','ebitda','cfads','cashTaxes','maintenanceCapex','workingCapitalBalance','capex','tenantFundedCapex','tenantCashReceipt','draw','mezzDraw','cashInterest','capitalizedInterest','sweepPrincipal','debt','mezzDebt','refinanceProceeds','reserve','cash','sponsorContribution','distribution','terminalProceeds','exitDebtPayoff']
    for title,settings in cases:
        j=js_run(settings)
        inp=j['assumptions'] # independent implementation uses defaults finalized by source input spec, NOT source output lines
        py=reference(inp)
        for yr,jr in zip(py,j['rows']):
            for key in fields:
                gap=abs(yr[key]-jr[key]);maximum=max(maximum,gap);assert gap<1e-6,(title,yr['month'],key,yr[key],jr[key],gap)
                assertions+=1
            if yr['dscr'] is None:assert jr['dscr'] is None
            else:assert abs(yr['dscr']-jr['dscr'])<1e-6,(title,yr['month'],'DSCR')
            assertions+=1
        assert len(py)==len(j['rows'])
        reference_flows=[-inp['initialCash']]+[x['distribution']-x['sponsorContribution'] for x in py]
        independent_npv=sum(v/(1+inp['discount']/100)**(i/12) for i,v in enumerate(reference_flows))
        assert abs(independent_npv-j['summary']['npvM'])<1e-6,(title,'NPV',independent_npv,j['summary']['npvM'])
        assert abs(sum(x['sponsorContribution'] for x in py)+inp['initialCash']-j['summary']['equityInvestedM'])<1e-6
        assert abs(sum(x['distribution'] for x in py)-j['summary']['equityDistributionsM'])<1e-6
        assertions+=3
        all_cases.append(dict(name=title,months=len(py),sponsor_equity_m=j['summary']['equityInvestedM'],defaulted=j['summary']['defaulted'],npv_m=j['summary']['npvM'],max_reference_gap_m=maximum))
    return {'cases':all_cases,'assertions':assertions,'max_gap_m':maximum,'note':'Independent Python implementation of monthly property and credit arithmetic under synthetic assumptions. Not validation against an executed lender model.'}

if __name__=='__main__':
    from copy import deepcopy
    default=js_run({})['assumptions']
    def case(name,**updates):
        spec=deepcopy(default);spec.update(updates);return name,spec
    checks=[
      case('reference baseline',months=120),
      case('CFADS / maintenance / WC / tax',months=120,cashTaxRatePct=18,maintenanceCapexMWYearM=.06,workingCapitalDays=20),
      case('mezzanine and tenant funding',months=120,ltc=50,mezzLtcPct=15,tenantCapexPct=35,tenantRentCreditPct=20,tenantCreditMonths=10),
      case('DSRA and cash sweep',months=120,termMonths=24,dsraMonths=6,cashSweepPct=30),
      case('capped sponsor',months=120,sponsorCommitmentM=75,termMonths=24,fundingDefaultPolicy='continue'),
      case('zero borrowing',months=120,ltc=0,mezzLtcPct=0,sponsorCommitmentM=800,fundingDefaultPolicy='continue'),
      case('maturity equity',months=120,loanMaturityMode='equity',cashTaxRatePct=5),
      case('maturity default',months=120,loanMaturityMode='default'),
    ]
    res=compare(checks)
    (ROOT/'audit'/'reference257_results.json').write_text(json.dumps(res,indent=2))
    print(json.dumps(res,indent=2))
