"""Independent monthly reference ledger for PowerPath (v25.8-CA review).

Written from the documented intended mechanics, not ported from underwrite25.js. It consumes only
input assumptions (cases.json) and never reads model-generated monthly outputs.
Policy choices encoded here (and asserted in the review): annuity repayment of refinanced debt,
sticky shared-supply allocation, gross tranche units converted by PUE, construction halt after a
funding default, additive base reserve + DSRA, lagged tenant reimbursement cash.
"""
import calendar, json, sys, math

DEFAULTS = dict(months=120, calendarStartYear=2026, calendarStartMonth=1, discount=10, rate=8, ltc=65, debtFee=1,
    termMonths=60, dscrCovenant=1.20, minLiquidity=10, initialCash=50, reserveTargetM=10, rentPerKwMonth=170, pue=1.3,
    powerCostMWh=85, otherOpexPct=12, fixedOpexM=0.4, constructionCostMW=7, delayMonths=0, overrunPct=0, rateShockPct=0,
    energyShockPct=0, refinanceLtvPct=60, refinanceValueM=1400, refinanceRatePct=7, refinanceFeePct=1, exitValueM=1800,
    exitCostPct=2, loanMaturityMode='refinance', capacityBasis='IT', tenantCapexPct=0, tenantFundingLagMonths=0,
    tenantRentCreditPct=0, tenantCreditMonths=0, debtYieldMinPct=8, refinanceDscrMin=1.25, refinanceAmortMonths=240,
    mezzLtcPct=0, mezzRatePct=13, mezzFeePct=2, cashSweepPct=0, distributionDscrMin=1.20, dsraMonths=0,
    sponsorCommitmentM=None, cashTaxRatePct=0, maintenanceCapexMWYearM=0, workingCapitalDays=0,
    buildings=[dict(name='Building A', itMW=50, constructionStart=1, constructionMonths=18, powerMonth=19, leaseMonth=19),
               dict(name='Building B', itMW=50, constructionStart=10, constructionMonths=18, powerMonth=28, leaseMonth=28),
               dict(name='Building C', itMW=50, constructionStart=19, constructionMonths=18, powerMonth=37, leaseMonth=37)],
    powerTranches=[])

def annuity(balance, monthly_rate, n):
    n = max(1, n)
    return balance / n if monthly_rate == 0 else balance * monthly_rate / (1 - (1 + monthly_rate) ** -n)

class Campus:
    def __init__(self, c):
        self.c = c
        self.halt_from = None          # first month in which abandoned buildings incur no capex
        self.abandoned = set()
        for t in c['powerTranches']:
            basis = t.get('basis', c.get('trancheCapacityBasis', c['capacityBasis']))
            t['it'] = t['mw'] / (c['pue'] if basis == 'gross' else 1)
        self.build()

    def it(self, b):
        return b['itMW'] / (self.c['pue'] if b.get('capacityBasis', self.c['capacityBasis']) == 'gross' else 1)

    def finish(self, b):
        return b['constructionStart'] + b['constructionMonths'] - 1

    def build(self):
        """Physical energization and lease cohorts, month 0..months+12."""
        c = self.c; d = c['delayMonths']; T = c['powerTranches']
        held = {b['name']: 0.0 for b in c['buildings']}
        prev = {b['name']: 0.0 for b in c['buildings']}
        cohorts = {b['name']: [] for b in c['buildings']}
        self.phys = []
        for m in range(c['months'] + 13):
            ded = {b['name']: sum(t['it'] for t in T if t.get('building') == b['name'] and t['month'] + d <= m) for b in c['buildings']}
            for b in c['buildings']:
                held[b['name']] = min(held[b['name']], max(0.0, self.it(b) - ded[b['name']]))
            pool = sum(t['it'] for t in T if not t.get('building') and t['month'] + d <= m) - sum(held.values())
            gross = credit = rented = 0.0
            for b in c['buildings']:
                n, cap = b['name'], self.it(b)
                ready = math.inf if n in self.abandoned else max(self.finish(b) + 1, b['leaseMonth'] + d, b['powerMonth'] + d)
                live = 0.0
                if m >= ready:
                    if T:
                        take = min(max(0.0, cap - ded[n] - held[n]), max(0.0, pool)); pool -= take; held[n] += take
                        live = min(cap, ded[n] + held[n])
                    else:
                        live = cap
                if live > prev[n] + 1e-9:
                    cohorts[n].append((m, live - prev[n]))
                prev[n] = live
                term = b.get('leaseTermMonths', 180); esc = b.get('rentEscalatorPct', 2.5) / 100
                for start, mw in cohorts[n]:
                    age = m - start
                    if 0 <= age < term:
                        rent = self.rent(b, cap, age) * mw / cap
                        gross += rent; rented += mw
                        if age < b.get('tenantCreditMonths', c['tenantCreditMonths']):
                            credit += rent * b.get('tenantRentCreditPct', c['tenantRentCreditPct']) / 100
            self.phys.append((gross, credit, rented))

    def rent(self, b, cap, age):
        term = b.get('leaseTermMonths', 180); esc = b.get('rentEscalatorPct', 2.5) / 100
        mode = b.get('rentInputMode', 'starting')
        if mode == 'total':
            weight = sum((1 + esc) ** (i // 12) for i in range(term))
            return b['contractedRentM'] / weight * (1 + esc) ** (age // 12)
        if mode == 'schedule':
            return b['annualRentM'][age // 12] / 12
        return cap * 1000 * b.get('rentPerKwMonth', self.c['rentPerKwMonth']) * (1 + esc) ** (age // 12) / 1e6

    def hours(self, m):
        k = self.c['calendarStartMonth'] - 1 + m - 1
        y, mo = self.c['calendarStartYear'] + k // 12, k % 12 + 1
        return calendar.monthrange(y, mo)[1] * 24

    def ops(self, m):
        c = self.c; capex = tenant = 0.0
        for b in c['buildings']:
            if b['constructionStart'] <= m <= self.finish(b) and not (b['name'] in self.abandoned and m >= self.halt_from):
                g = self.it(b) * c['constructionCostMW'] * (1 + c['overrunPct'] / 100) / b['constructionMonths']
                capex += g; tenant += g * b.get('tenantCapexPct', c['tenantCapexPct']) / 100
        gross, credit, rented = self.phys[max(0, min(len(self.phys) - 1, m))]
        rev = gross - credit
        energy = rented * c['pue'] * self.hours(m) * c['powerCostMWh'] * (1 + c['energyShockPct'] / 100) / 1e6
        opex = rev * c['otherOpexPct'] / 100 + (c['fixedOpexM'] if rented else 0)
        ebitda = rev - energy - opex
        tax = max(0.0, ebitda) * c['cashTaxRatePct'] / 100
        mcap = rented * c['maintenanceCapexMWYearM'] / 12
        wc = max(0.0, rev) * c['workingCapitalDays'] / 30
        return dict(capex=capex, tenant=tenant, gross=gross, credit=credit, rented=rented, rev=rev, energy=energy,
                    ebitda=ebitda, tax=tax, mcap=mcap, wc=wc)

    def cfads(self, m):
        x, p = self.ops(m), self.ops(m - 1)
        return x['ebitda'] - x['tax'] - x['mcap'] - (x['wc'] - p['wc'])

    def constructing(self, m):
        return any(b['constructionStart'] <= m <= self.finish(b) and not (b['name'] in self.abandoned and m >= self.halt_from)
                   for b in self.c['buildings'])

def run(case):
    c = json.loads(json.dumps(DEFAULTS)); c.update(json.loads(json.dumps(case)))
    P = Campus(c)
    cap = math.inf if c['sponsorCommitmentM'] is None else c['sponsorCommitmentM']
    sponsor_in = c['initialCash']
    cash, reserve, senior, mezz = c['initialCash'], 0.0, 0.0, 0.0
    first_draw = maturity = None
    refi = closed = default = fdefault = False
    rows, flows = [], [-c['initialCash']]
    r0 = (c['rate'] + c['rateShockPct']) / 1200; rr = c['refinanceRatePct'] / 1200; mr = c['mezzRatePct'] / 1200
    def fund(x):
        nonlocal sponsor_in
        got = min(max(0.0, x), max(0.0, cap - sponsor_in)); sponsor_in += got; return got
    for m in range(1, c['months'] + 1):
        o = P.ops(m)
        cf = P.cfads(m)
        receipt = P.ops(m - c['tenantFundingLagMonths'])['tenant'] if m > c['tenantFundingLagMonths'] else 0.0
        elig = o['capex'] - o['tenant']
        ds_ = 0.0 if (closed or default) else elig * c['ltc'] / 100
        dm_ = 0.0 if (closed or default) else elig * c['mezzLtcPct'] / 100
        fee = ds_ * c['debtFee'] / 100 + dm_ * c['mezzFeePct'] / 100
        senior += ds_; mezz += dm_
        if ds_ + dm_ > 0 and first_draw is None:
            first_draw = m; maturity = m + round(c['termMonths']) - 1
        i_s = senior * (rr if refi else r0); i_m = mezz * mr
        capi = (i_s + i_m) if (not refi and P.constructing(m)) else 0.0
        cash_int = i_s + i_m - capi
        if capi:
            senior += i_s; mezz += i_m
        prin = mprin = refi_in = refi_fee = 0.0
        if maturity is not None and m == maturity and not refi:
            pre = cash + cf + ds_ + dm_ + receipt - o['capex'] - fee - cash_int
            room = max(0.0, pre - c['minLiquidity']) + max(0.0, cap - sponsor_in)
            if default:
                fdefault = True
            elif c['loanMaturityMode'] == 'refinance':
                f12 = sum(P.cfads(m + j) for j in range(1, 13))
                noi = sum(P.ops(m + j)['ebitda'] - P.ops(m + j)['mcap'] for j in range(1, 13))
                n = max(1, round(c['refinanceAmortMonths']))
                ppd = 1 / n if rr == 0 else rr / (1 - (1 + rr) ** -n)
                lim = [c['refinanceValueM'] * c['refinanceLtvPct'] / 100, max(0.0, f12) / max(.01, c['refinanceDscrMin']) / (12 * ppd)]
                lim.append(max(0.0, noi) / (c['debtYieldMinPct'] / 100) if c['debtYieldMinPct'] > 0 else math.inf)
                new = max(0.0, min(lim)); feeR = new * c['refinanceFeePct'] / 100
                if senior + mezz + feeR - new - room > 1e-8:
                    default = fdefault = True
                else:
                    refi_in, refi_fee, prin, mprin = new, feeR, senior, mezz
                    senior, mezz, refi, closed = new, 0.0, True, True
            elif c['loanMaturityMode'] == 'equity':
                if senior + mezz - room > 1e-8:
                    default = fdefault = True
                else:
                    prin, mprin, senior, mezz, closed = senior, mezz, 0.0, 0.0, True
            else:
                default = True
        elif refi and m > maturity:
            left = max(1, c['refinanceAmortMonths'] - (m - maturity - 1))
            prin = min(senior, max(0.0, annuity(senior, rr, left) - i_s)); senior -= prin
        sched = cash_int + (0.0 if m == maturity else prin + mprin)
        dscr = cf / sched if sched > 0 else None
        uses = o['capex'] + fee + refi_fee + cash_int + prin + mprin
        pre_fund = cash + cf + ds_ + dm_ + refi_in + receipt - uses
        contrib = fund(c['minLiquidity'] - pre_fund)
        cash = pre_fund + contrib
        if c['minLiquidity'] - cash > 1e-8:
            default = fdefault = True
        dsra = c['dsraMonths'] * annuity(senior, rr, c['refinanceAmortMonths'] - (m - maturity)) if (refi and senior > 0) else 0.0
        target = c['reserveTargetM'] + dsra
        if reserve < target:
            mv = min(target - reserve, max(0.0, cash - c['minLiquidity'])); cash -= mv; reserve += mv
        elif reserve > target:
            cash += reserve - target; reserve = target
        short = max(0.0, target - reserve)
        if short > 1e-8:
            t = fund(short); contrib += t; reserve += t
        outstanding = senior + mezz > 1e-9
        locked = (target - reserve > 1e-8) or default or (dscr is not None and dscr < c['dscrCovenant']) or \
                 (outstanding and (dscr is None or dscr < c['distributionDscrMin']))
        if outstanding and not default and c['cashSweepPct'] > 0:
            sw = min(senior, max(0.0, cash - c['minLiquidity']) * c['cashSweepPct'] / 100); cash -= sw; senior -= sw; prin += sw
        dist = 0.0
        if not locked and m < c['months']:
            dist = max(0.0, cash - c['minLiquidity']); cash -= dist
        if m == c['months']:
            tot = sum(P.it(b) for b in c['buildings']); live = sum(P.it(b) for b in c['buildings'] if b['name'] not in P.abandoned)
            term = c['exitValueM'] * (1 - c['exitCostPct'] / 100) * (live / tot if P.abandoned else 1)
            pot = max(0.0, cash + term + reserve); pay = min(senior + mezz, pot)
            ps = min(senior, pay); senior -= ps; mezz -= pay - ps; prin += ps; mprin += pay - ps
            cash += term - pay + reserve; reserve = 0.0
            if senior + mezz > 1e-8:
                default = True
            if cash > 0 and senior + mezz < 1e-8 and not default:
                dist += cash; cash = 0.0
        if fdefault and P.halt_from is None:
            P.halt_from = m + 1
            P.abandoned = {b['name'] for b in c['buildings'] if P.finish(b) > m}
            if P.abandoned:
                P.build()
        flows.append(dist - contrib)
        rows.append(dict(month=m, grossRevenue=o['gross'], energy=o['energy'], ebitda=o['ebitda'], cfads=cf, capex=o['capex'],
                         tenantCashReceipt=receipt, draw=ds_, mezzDraw=dm_, capitalizedInterest=capi, cashInterest=cash_int,
                         principal=prin, mezzPrincipal=mprin, debt=senior, mezzDebt=mezz, reserve=reserve, cash=cash,
                         sponsorContribution=contrib, distribution=dist, dscr=dscr))
    npv = sum(v / (1 + c['discount'] / 100) ** (i / 12) for i, v in enumerate(flows))
    return dict(rows=rows, npvM=npv, defaulted=default)

if __name__ == '__main__':
    cases = json.load(open(sys.argv[1]))
    json.dump({k: run(v) for k, v in cases.items()}, open(sys.argv[2], 'w'))
