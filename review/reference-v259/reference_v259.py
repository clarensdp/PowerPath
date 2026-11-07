"""Independent monthly reference ledger for PowerPath (v25.8-CA review), extended with v25.9 debt facilities.

v25.9 extension (fixed-rate notes, FACILITY_SPEC_v259.md) was written from the spec text only; every
interpretation of an ambiguous clause is listed in REFERENCE_V259_NOTES.md (tags [Axx] in comments).

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
    sponsorCommitmentM=None, refinanceTenorPolicy='fixed', leaseTailBufferMonths=12, minRefinanceAmortMonths=24,
    powerResponsibility='landlord', powerPassThroughPct=100, rateShockAllFacilities=False, exitTenantReceivableRecoveryPct=0, exitWorkingCapitalRecoveryPct=0, leaseExpiryPolicy='vacate', renewalProbabilityPct=75, renewalRentPct=100, renewalTermMonths=60, exitValuePolicy='fixed', vacantValuePct=40, cashTaxRatePct=0, maintenanceCapexMWYearM=0, workingCapitalDays=0,
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
        self.bphys = []                # v25.9: per-building (gross rent, credits) for facility triggers / DSCR allocation
        for m in range(c['months'] + 13):
            ded = {b['name']: sum(t['it'] for t in T if t.get('building') == b['name'] and t['month'] + d <= m) for b in c['buildings']}
            for b in c['buildings']:
                held[b['name']] = min(held[b['name']], max(0.0, self.it(b) - ded[b['name']]))
            pool = sum(t['it'] for t in T if not t.get('building') and t['month'] + d <= m) - sum(held.values())
            gross = credit = rented = 0.0; by_b = {}
            bg = {b['name']: 0.0 for b in c['buildings']}; bc = {b['name']: 0.0 for b in c['buildings']}
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
                    if age >= term and c['leaseExpiryPolicy'] == 'renew' and age < term + c['renewalTermMonths']:
                        share = c['renewalProbabilityPct'] / 100
                        last = self.rent(b, cap, term - 1) * mw / cap
                        gross += last * c['renewalRentPct'] / 100 * (1 + esc) ** ((age - term) // 12) * share
                        bg[n] += last * c['renewalRentPct'] / 100 * (1 + esc) ** ((age - term) // 12) * share
                        rented += mw * share; by_b[n] = by_b.get(n, 0.0) + mw * share
                    if 0 <= age < term:
                        rent = self.rent(b, cap, age) * mw / cap
                        gross += rent; rented += mw; by_b[n] = by_b.get(n, 0.0) + mw
                        bg[n] += rent
                        if age < b.get('tenantCreditMonths', c['tenantCreditMonths']):
                            credit += rent * b.get('tenantRentCreditPct', c['tenantRentCreditPct']) / 100
                            bc[n] += rent * b.get('tenantRentCreditPct', c['tenantRentCreditPct']) / 100
            self.phys.append((gross, credit, rented, by_b))
            self.bphys.append((bg, bc))
        self.cohorts = cohorts

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
        gross, credit, rented, by_b = self.phys[max(0, min(len(self.phys) - 1, m))]
        lease_rev = gross - credit
        landlord_cost = reimb = 0.0
        unit = c['pue'] * self.hours(m) * c['powerCostMWh'] * (1 + c['energyShockPct'] / 100) / 1e6
        for b in c['buildings']:
            cost = by_b.get(b['name'], 0.0) * unit
            mode = b.get('powerResponsibility', c['powerResponsibility']); pt = b.get('powerPassThroughPct', c['powerPassThroughPct']) / 100
            if mode == 'tenant_direct': landlord_cost += cost * (1 - pt)
            elif mode == 'reimbursed': landlord_cost += cost; reimb += cost * pt
            else: landlord_cost += cost
        rev = lease_rev + reimb
        energy = landlord_cost
        opex = lease_rev * c['otherOpexPct'] / 100 + (c['fixedOpexM'] if rented else 0)
        ebitda = rev - energy - opex
        tax = max(0.0, ebitda) * c['cashTaxRatePct'] / 100
        mcap = rented * c['maintenanceCapexMWYearM'] / 12
        wc = max(0.0, lease_rev) * c['workingCapitalDays'] / 30  # spec: reimbursements collected in billing month
        return dict(capex=capex, tenant=tenant, gross=gross, credit=credit, rented=rented, rev=rev, energy=energy, reimb=reimb,
                    ebitda=ebitda, tax=tax, mcap=mcap, wc=wc)

    def cfads(self, m):
        x, p = self.ops(m), self.ops(m - 1)
        return x['ebitda'] - x['tax'] - x['mcap'] - (x['wc'] - p['wc'])

    def constructing(self, m):
        return any(b['constructionStart'] <= m <= self.finish(b) and not (b['name'] in self.abandoned and m >= self.halt_from)
                   for b in self.c['buildings'])


# ---------------------------------------------------------------------------------------------
# v25.9 facilities
# ---------------------------------------------------------------------------------------------
import re as _re
EPS = 1e-8
LABELS = ('Executed', 'Public approximate', 'Management expectation', 'Assumption', 'Unknown')

def _finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)

def _int(x):
    return _finite(x) and float(x).is_integer()

def date_to_month(c, v, what):
    if not isinstance(v, str) or not _re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
        raise ValueError(f'{what}: invalid ISO date {v!r}')
    y, mo = int(v[0:4]), int(v[5:7])
    if not 1 <= mo <= 12:
        raise ValueError(f'{what}: invalid ISO date {v!r}')
    return (y - c['calendarStartYear']) * 12 + (mo - c['calendarStartMonth']) + 1

def pick_month(c, obj, mkey, dkey, what):
    """Integer month field takes precedence over date field [A02]."""
    if obj.get(mkey) is not None:
        if not _int(obj[mkey]):
            raise ValueError(f'{what}: {mkey} must be an integer')
        return int(obj[mkey])
    if obj.get(dkey) is not None:
        return date_to_month(c, obj[dkey], what)
    raise ValueError(f'{what}: {mkey} or {dkey} is required')

class Facility:
    def __init__(self, c, x, idx):
        fid = x.get('id')
        if not isinstance(fid, str) or not fid:
            raise ValueError('Facility id must be a non-empty string')
        w = f'Facility {fid}'
        self.id, self.name, self.idx, self.spec = fid, x.get('name', fid), idx, x
        if x.get('type') != 'fixed_note':
            raise ValueError(f"{w}: type must be 'fixed_note'")
        self.face = x.get('faceM'); self.cpn = x.get('couponPct'); self.price = x.get('issuePricePct')
        self.feep = x.get('feePct', 0) if x.get('feePct') is not None else 0
        if not (_finite(self.face) and self.face > 0): raise ValueError(f'{w}: faceM must be > 0')
        if not (_finite(self.cpn) and 0 <= self.cpn <= 100): raise ValueError(f'{w}: couponPct must be in 0..100')
        if not (_finite(self.price) and 0 <= self.price <= 200): raise ValueError(f'{w}: issuePricePct must be in 0..200')
        if not (_finite(self.feep) and 0 <= self.feep <= 100): raise ValueError(f'{w}: feePct must be in 0..100')
        self.issue = pick_month(c, x, 'issueMonth', 'issueDate', w)
        self.first = pick_month(c, x, 'firstPaymentMonth', 'firstPaymentDate', w)
        self.mat = pick_month(c, x, 'maturityMonth', 'maturityDate', w)
        if self.issue < 1: raise ValueError(f'{w}: issueMonth must be >= 1')
        if not self.issue < self.first: raise ValueError(f'{w}: issueMonth must be < firstPaymentMonth')
        if not self.first <= self.mat: raise ValueError(f'{w}: firstPaymentMonth must be <= maturityMonth')
        if not self.mat <= c['months']: raise ValueError(f'{w}: maturityMonth must be <= months')
        if (self.mat - self.first) % 6 != 0: raise ValueError(f'{w}: (maturityMonth - firstPaymentMonth) must be a multiple of 6')
        bl = x.get('buildings')
        names = [b['name'] for b in c['buildings']]
        if not isinstance(bl, list) or not bl: raise ValueError(f'{w}: buildings must be a non-empty list')
        for n in bl:
            if n not in names: raise ValueError(f'{w}: unknown building {n!r}')
        self.blds = list(dict.fromkeys(bl))      # [A03] duplicate names in the list count once
        pr = x.get('priority', 1)
        pr = 1 if pr is None else pr
        if not _int(pr): raise ValueError(f'{w}: priority must be an integer')
        self.prio = int(pr)
        am = x.get('amortization')
        if not isinstance(am, dict) or am.get('type') not in ('none', 'unknown', 'pctOriginalPerYear', 'explicit'):
            raise ValueError(f'{w}: invalid amortization')
        if am['type'] == 'pctOriginalPerYear' and not (_finite(am.get('annualPct')) and 0 <= am['annualPct'] <= 100):
            raise ValueError(f'{w}: pctOriginalPerYear needs a finite annualPct in 0..100')
        if am['type'] == 'explicit':
            a_ = am.get('amountsM')
            if not isinstance(a_, list) or not all(_finite(v) and v >= 0 for v in a_):
                raise ValueError(f'{w}: explicit amortization amounts must be finite and >= 0')
        self.am = am
        ast = x.get('amortStart')
        if ast is None:
            if am['type'] not in ('none', 'unknown'):
                raise ValueError(f'{w}: amortStart is required for amortization {am["type"]}')
            self.ast_month = None
        else:
            t = ast.get('type') if isinstance(ast, dict) else None
            if t == 'fixedMonth':
                self.ast_month = pick_month(c, ast, 'month', 'date', f'{w} amortStart')
            elif t in ('afterFirstRent', 'afterFinalCommencement'):
                off = ast.get('offsetMonths')
                if not (_int(off) and off >= 0): raise ValueError(f'{w}: amortStart.offsetMonths must be an integer >= 0')
                self.off = int(off)
            else:
                raise ValueError(f'{w}: invalid amortStart')
        self.ast = ast
        ds = x.get('dsra') or {'type': 'none'}
        dt = ds.get('type')
        if dt == 'fixed':
            if not (_finite(ds.get('amountM')) and ds['amountM'] >= 0): raise ValueError(f'{w}: dsra.amountM must be finite and >= 0')
        elif dt == 'constructionThenNextPeriod':
            if not (_finite(ds.get('constructionAmountM')) and ds['constructionAmountM'] >= 0):
                raise ValueError(f'{w}: dsra.constructionAmountM must be finite and >= 0')
        elif dt not in ('none', 'nextPeriod'):
            raise ValueError(f'{w}: invalid dsra type')
        self.dsra_spec = ds
        lk = x.get('lockupDscr', 1.20)
        self.lockup = 1.20 if lk is None else lk
        if not _finite(self.lockup): raise ValueError(f'{w}: lockupDscr must be finite')
        self.evidence = x.get('evidence') or {}
        self.P = list(range(self.first, self.mat + 1, 6))
        self.Pset = set(self.P)
        # state
        self.bal = self.acc = self.dsra = 0.0
        self.A = None; self.A_resolved_in = None
        self.E = None                                # AM1 construction-end event month
        self.L = None                                # AM3 construction lock-up end month
        self.issued = False
        self.tests = []; self.last_test = None       # (month, dscr)
        self.share = {}                              # month -> cfadsShare
        self.schedule = []; self.lock_months = []; self.def_months = []
        self.int_paid = self.prin_paid = self.balloon = 0.0
        self.unpaid_exit = 0.0

    # ---- §4 amortization start ------------------------------------------------------------
    def resolve(self, P, m):
        """Evaluated at the start of month m on the current physical schedule [A05]."""
        c = P.c
        bl = [b for b in c['buildings'] if b['name'] in self.blds]
        if self.L is None:                                        # AM3: every collateral building has gross rent > 0 (k <= m)
            self.L = next((k for k in range(1, m + 1) if all(P.bphys[k][0][b['name']] > 0 for b in bl)), None)
        if self.E is not None or self.ast is None:
            return
        t = self.ast['type']
        if t == 'fixedMonth':
            self.A, self.E, self.A_resolved_in = self.ast_month, self.ast_month, m   # AM1: known from month 1
            return
        if t == 'afterFirstRent':
            R = next((k for k in range(1, m + 1) if any(P.bphys[k][0][b['name']] > 0 for b in bl)), None)
            if R is None: return
            self.E = R
            cand = [p for p in self.P if p > R + self.off]
        else:
            C = next((k for k in range(1, m + 1)
                      if all(P.phys[k][3].get(b['name'], 0.0) >= P.it(b) - 1e-9 for b in bl)), None)
            if C is None: return
            K = 0
            for b in bl:
                cm = b.get('tenantCreditMonths')
                cm = c.get('tenantCreditMonths') if cm is None else cm
                cm = 0 if cm is None else cm
                starts = [s for s, _ in P.cohorts[b['name']] if s <= C]
                K = max(K, (max(starts) if starts else 0) + cm)          # [A08]
            T = max(C, K)
            if T > m: return                                      # AM1: event E = T must have occurred
            self.E = T
            cand = [p for p in self.P if p >= T + self.off]
        if cand:
            self.A, self.A_resolved_in = min(cand), m
        # [A07] no payment month satisfies the rule -> stays unresolved (re-evaluated every month)

    def amortizing(self):
        return self.am['type'] in ('pctOriginalPerYear', 'explicit')

    def installment(self, p, bal_open):
        """Scheduled installment at payment month p given opening balance (also used at maturity) [A09]."""
        if self.A is None or p not in self.Pset or p < self.A or bal_open <= 0:
            return 0.0
        t = self.am['type']
        if t == 'pctOriginalPerYear':
            return min(bal_open, self.face * self.am['annualPct'] / 200)
        if t == 'explicit':
            j = sum(1 for q in self.P if self.A <= q < p)
            a = self.am['amountsM']
            return min(bal_open, a[j]) if j < len(a) else 0.0
        return 0.0

    def requirement(self, m):
        """§6 Q(m) at end of month m (on the balance after this month's waterfall payments)."""
        t = self.dsra_spec['type']
        if self.bal <= 0 or t == 'none':
            return 0.0
        if t == 'fixed':
            return self.dsra_spec['amountM']
        if t == 'constructionThenNextPeriod' and (self.E is None or m < self.E):     # AM2
            return self.dsra_spec['constructionAmountM']
        q = next((p for p in self.P if p > m), None)
        if q is None:
            return 0.0
        return self.acc + self.bal * self.cpn / 1200 * (q - m) + self.installment(q, self.bal)

    def warnings(self):
        w = []
        if self.ast is not None and self.ast['type'] in ('afterFirstRent', 'afterFinalCommencement'):
            w.append(f'FACILITY {self.id}: amortization start derived from modeled commencement, not contractual confirmation')
        if self.am['type'] == 'unknown':
            w.append(f'FACILITY {self.id}: amortization unknown — bullet assumed; debt service understated')
        if self.ast is not None and self.A is None:                       # [A16]
            w.append(f'FACILITY {self.id}: amortization start never resolved within horizon')
        for term, ev in self.evidence.items():
            lab = (ev or {}).get('label')
            if lab != 'Executed':
                w.append(f"FACILITY {self.id}: term '{term}' is {lab}, not Executed")
        return w

def build_facilities(c):
    fl = c.get('facilities') or []
    if not fl:
        return []
    if c['ltc'] != 0 or c['mezzLtcPct'] != 0:
        raise ValueError('Generic construction debt must be disabled (ltc=0, mezzLtcPct=0) when facilities are modeled')
    F, seen = [], set()
    for i, x in enumerate(fl):
        f = Facility(c, x, i)
        if f.id in seen:
            raise ValueError(f'Duplicate facility id {f.id!r}')
        seen.add(f.id); F.append(f)
    return sorted(F, key=lambda f: (f.prio, f.idx))      # stable: ties keep input order

def cfads_share(P, f, cf, m):
    k = max(0, min(len(P.bphys) - 1, m))
    bg, bc = P.bphys[k]
    den = sum(bg[n] - bc[n] for n in bg)
    num = sum(bg[n] - bc[n] for n in f.blds)
    return cf * num / den if abs(den) > 1e-12 else 0.0                    # [A12]


def run(case):
    c = json.loads(json.dumps(DEFAULTS)); c.update(json.loads(json.dumps(case)))
    F = build_facilities(c)
    P = Campus(c)
    cap = math.inf if c['sponsorCommitmentM'] is None else c['sponsorCommitmentM']
    sponsor_in = c['initialCash']
    cash, reserve, senior, mezz = c['initialCash'], 0.0, 0.0, 0.0
    first_draw = maturity = None
    refi = closed = default = fdefault = False
    rows, flows = [], [-c['initialCash']]
    amort_n = max(1, round(c['refinanceAmortMonths']))
    shock_all = c['rateShockPct'] if c['rateShockAllFacilities'] else 0
    r0 = (c['rate'] + c['rateShockPct']) / 1200; rr = (c['refinanceRatePct'] + shock_all) / 1200; mr = (c['mezzRatePct'] + shock_all) / 1200
    receivable = 0.0
    shortfall_months = []; unpaid_exit_total = 0.0
    def fund(x):
        nonlocal sponsor_in
        got = min(max(0.0, x), max(0.0, cap - sponsor_in)); sponsor_in += got; return got
    for m in range(1, c['months'] + 1):
        if F:
            open_pool = cash + reserve + sum(f.dsra for f in F)
        o = P.ops(m)
        cf = P.cfads(m)
        receipt = P.ops(m - c['tenantFundingLagMonths'])['tenant'] if m > c['tenantFundingLagMonths'] else 0.0
        receivable += o['tenant'] - receipt
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
                if c['refinanceTenorPolicy'] == 'leaseTail':
                    live = [b for b in c['buildings'] if b['name'] not in P.abandoned]
                    ends = [(P.it(b), max(b['constructionStart'] + b['constructionMonths'], b['leaseMonth'] + c['delayMonths'], b['powerMonth'] + c['delayMonths']) + b.get('leaseTermMonths', 180)) for b in live]
                    walt = sum(w * max(0, e - m) for w, e in ends) / sum(w for w, _ in ends)
                    n = max(round(c['minRefinanceAmortMonths']), min(n, math.floor(walt - c['leaseTailBufferMonths'])))
                amort_n = n
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
            left = max(1, amort_n - (m - maturity - 1))
            prin = senior if left == 1 else min(senior, max(0.0, annuity(senior, rr, left) - i_s)); senior -= prin
        sched = cash_int + (0.0 if m == maturity else prin + mprin)
        dscr = cf / sched if sched > 0 else None
        uses = o['capex'] + fee + refi_fee + cash_int + prin + mprin
        pre_fund = cash + cf + ds_ + dm_ + refi_in + receipt - uses
        if F:
            # ---- §2-§4: issuance, accrual, payments (step 1-3) --------------------------------
            n_proc = n_fee = n_acc = n_int = n_prin = 0.0
            for f in F:
                f.resolve(P, m)
                f.m = dict(month=m, opening=f.bal, accruedStart=f.acc, issued=0.0, accrual=0.0, interestPaid=0.0,
                           principalPaid=0.0, scheduledPrincipal=0.0, exitInterestPaid=0.0, exitPrincipalPaid=0.0,
                           dsraOpening=f.dsra, dsraDeposit=0.0, dsraSponsorDeposit=0.0, dsraRelease=0.0, dsraDraw=0.0,
                           dsraRequired=0.0, dscr=None, dsraDeficiency=0.0, interestDue=0.0, deferredToExit=False)
                if m == f.issue:
                    f.issued = True
                    proc = f.face * f.price / 100; fe = f.face * f.feep / 100
                    f.bal = f.face; f.m['issued'] = f.face; f.m['opening'] = f.face      # [A04]
                    f.m['proceeds'] = proc; f.m['fees'] = fe
                    n_proc += proc; n_fee += fe
                if f.issue < m <= f.mat and f.bal > 0:
                    a = f.bal * f.cpn / 1200
                    f.acc += a; f.m['accrual'] = a; n_acc += a
                if m in f.Pset and f.issued and m == f.mat == c['months']:
                    # AM4: maturity in the horizon month -> whole maturity payment settled in the exit waterfall
                    inst = f.installment(m, f.bal)
                    f.m['scheduledPrincipal'] = inst; f.m['interestDue'] = f.acc; f.m['deferredToExit'] = True
                    f.m['_num_partial'] = sum(f.share.get(k, 0.0) for k in range(max(1, m - 5), m))
                elif m in f.Pset and f.issued:
                    ip = f.acc; f.acc = 0.0
                    inst = f.installment(m, f.bal)
                    pp = f.bal if m == f.mat else inst
                    f.bal -= pp
                    f.m['interestPaid'] = ip; f.m['principalPaid'] = pp; f.m['scheduledPrincipal'] = inst
                    f.m['interestDue'] = ip
                    f.int_paid += ip; f.prin_paid += pp
                    if m == f.mat:
                        f.balloon = pp - inst                                          # [A10]
                    n_int += ip; n_prin += pp
                    # §7 DSCR test
                    num = sum(f.share.get(k, 0.0) for k in range(max(1, m - 5), m + 1) if k != m)
                    f.m['_num_partial'] = num
            # cfadsShare for this month (all facilities, also pre-issue months for the DSCR look-back [A13])
            for f in F:
                f.share[m] = cfads_share(P, f, cf, m)
                f.m['cfadsShare'] = f.share[m]
                if m in f.Pset and f.issued:
                    den = f.m['interestDue'] + f.m['scheduledPrincipal']
                    num = f.m.pop('_num_partial') + f.share[m]
                    v = num / den if den > 0 else None
                    f.m['dscr'] = v; f.tests.append(dict(month=m, dscr=v)); f.last_test = (m, v)
            fac_ds = n_int + n_prin
            pre_fund = pre_fund + n_proc - n_fee - fac_ds
            pre_funding_cash = pre_fund
            # ---- step 4: DSRA draw before sponsor ---------------------------------------------
            n_draw = 0.0
            if pre_fund < c['minLiquidity']:
                need = c['minLiquidity'] - pre_fund
                for f in F:
                    if need <= 0: break
                    d_ = min(f.dsra, f.m['interestPaid'] + f.m['principalPaid'], need)
                    if d_ > 0:
                        f.dsra -= d_; f.m['dsraDraw'] = d_; need -= d_; n_draw += d_
                pre_fund = pre_fund + n_draw
        contrib = fund(c['minLiquidity'] - pre_fund)
        cash = pre_fund + contrib
        if c['minLiquidity'] - cash > 1e-8:
            default = fdefault = True
        if F:
            gap = c['minLiquidity'] - cash if c['minLiquidity'] - cash > 1e-8 else 0.0
            if gap > 0 and fac_ds > 0:
                shortfall_months.append(m)
            # ---- step 6: facility DSRA funding / release (priority order) ---------------------
            fac_def = False
            for f in F:
                Q = f.requirement(m) if f.issued else 0.0
                f.m['dsraRequired'] = Q
                if f.dsra < Q:
                    mv = min(Q - f.dsra, max(0.0, cash - c['minLiquidity'])); cash -= mv; f.dsra += mv
                    t = fund(Q - f.dsra); contrib += t; f.dsra += t
                    f.m['dsraDeposit'] = mv + t; f.m['dsraSponsorDeposit'] = t
                    if Q - f.dsra > 1e-8:
                        f.m['dsraDeficiency'] = Q - f.dsra; f.def_months.append(m); fac_def = True
                elif f.dsra > Q:
                    r_ = f.dsra - Q; cash += r_; f.dsra = Q; f.m['dsraRelease'] = r_
        dsra = c['dsraMonths'] * annuity(senior, rr, amort_n - (m - maturity)) if (refi and senior > 0) else 0.0
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
        if F:
            # ---- step 8: facility lock-up --------------------------------------------------------
            constr_lock = False
            for f in F:
                own = f.m['dsraDeficiency'] > 1e-8
                if f.bal > 0 and (f.L is None or m < f.L):                     # AM3 construction lock-up
                    own = True; constr_lock = True
                if f.last_test is not None:
                    tm, v = f.last_test
                    nxt = next((p for p in f.P if p > tm), f.mat + 1)          # [A14]
                    if tm <= m < nxt and v is not None and v < f.lockup:
                        own = True
                if own:
                    f.lock_months.append(m)
                locked = locked or own
            locked = locked or fac_def or gap > 0
        if outstanding and not default and c['cashSweepPct'] > 0:
            sw = min(senior, max(0.0, cash - c['minLiquidity']) * c['cashSweepPct'] / 100); cash -= sw; senior -= sw; prin += sw
        dist = 0.0
        if not locked and m < c['months']:
            dist = max(0.0, cash - c['minLiquidity']); cash -= dist
        exit_in = 0.0
        if m == c['months'] and not F:
            tot = sum(P.it(b) for b in c['buildings']); live = sum(P.it(b) for b in c['buildings'] if b['name'] not in P.abandoned)
            share = live / tot if P.abandoned else 1
            if c['exitValuePolicy'] == 'contracted':
                leased = min(live, P.phys[m][2]); share = (leased + (live - leased) * c['vacantValuePct'] / 100) / tot
            term = c['exitValueM'] * (1 - c['exitCostPct'] / 100) * share
            coll = receivable * c['exitTenantReceivableRecoveryPct'] / 100 + max(0.0, o['wc']) * c['exitWorkingCapitalRecoveryPct'] / 100
            pot = max(0.0, cash + term + coll + reserve); pay = min(senior + mezz, pot)
            ps = min(senior, pay); senior -= ps; mezz -= pay - ps; prin += ps; mprin += pay - ps
            cash += term + coll - pay + reserve; reserve = 0.0
            if senior + mezz > 1e-8:
                default = True
            if cash > 0 and senior + mezz < 1e-8 and not default:
                dist += cash; cash = 0.0
        elif m == c['months']:
            # ---- step 10: exit with facilities -------------------------------------------------
            tot = sum(P.it(b) for b in c['buildings']); live = sum(P.it(b) for b in c['buildings'] if b['name'] not in P.abandoned)
            share = live / tot if P.abandoned else 1
            if c['exitValuePolicy'] == 'contracted':
                leased = min(live, P.phys[m][2]); share = (leased + (live - leased) * c['vacantValuePct'] / 100) / tot
            term = c['exitValueM'] * (1 - c['exitCostPct'] / 100) * share
            coll = receivable * c['exitTenantReceivableRecoveryPct'] / 100 + max(0.0, o['wc']) * c['exitWorkingCapitalRecoveryPct'] / 100
            exit_in = term + coll
            dsra_all = 0.0
            for f in F:
                f.m['dsraRelease'] += f.dsra; dsra_all += f.dsra; f.dsra = 0.0
            avail = max(0.0, cash + term + coll + reserve + dsra_all)
            fac_exit = 0.0
            for f in F:
                ip = min(f.acc, avail); avail -= ip; f.acc -= ip
                pp = min(f.bal, avail); avail -= pp; f.bal -= pp
                f.m['exitInterestPaid'] = ip; f.m['exitPrincipalPaid'] = pp
                f.m['interestPaid'] += ip; f.m['principalPaid'] += pp
                f.int_paid += ip; f.prin_paid += pp; fac_exit += ip + pp
                if f.mat == m:
                    f.balloon = max(0.0, pp - f.m['scheduledPrincipal'])               # AM4 / [A10]
                f.unpaid_exit = f.bal + f.acc
                unpaid_exit_total += f.unpaid_exit
            pay = min(senior + mezz, avail)
            ps = min(senior, pay); senior -= ps; mezz -= pay - ps; prin += ps; mprin += pay - ps
            cash += term + coll - pay + reserve + dsra_all - fac_exit; reserve = 0.0
            n_int += sum(f.m['exitInterestPaid'] for f in F); n_prin += sum(f.m['exitPrincipalPaid'] for f in F)
            fac_ds += fac_exit
            if senior + mezz > 1e-8 or unpaid_exit_total > 1e-8:
                default = True
            if cash > 0 and senior + mezz < 1e-8 and not default:
                dist += cash; cash = 0.0
        if fdefault and P.halt_from is None:
            P.halt_from = m + 1
            P.abandoned = {b['name'] for b in c['buildings'] if P.finish(b) > m}
            if P.abandoned:
                P.build()
        flows.append(dist - contrib)
        row = dict(month=m, grossRevenue=o['gross'], energy=o['energy'], powerReimbursement=o['reimb'], ebitda=o['ebitda'], cfads=cf, capex=o['capex'],
                         tenantCashReceipt=receipt, draw=ds_, mezzDraw=dm_, capitalizedInterest=capi, cashInterest=cash_int,
                         principal=prin, mezzPrincipal=mprin, debt=senior, mezzDebt=mezz, reserve=reserve, cash=cash,
                         sponsorContribution=contrib, distribution=dist, dscr=dscr)
        if F:
            for f in F:
                f.m.update(closing=f.bal, accruedEnd=f.acc, dsraBalance=f.dsra)
                if m >= f.issue:
                    f.schedule.append(f.m)
            dep = sum(f.m['dsraDeposit'] for f in F); rel = sum(f.m['dsraRelease'] for f in F)
            dsra_close = sum(f.dsra for f in F)
            close_pool = cash + reserve + dsra_close
            resid = (open_pool + cf + receipt + ds_ + dm_ + refi_in + n_proc + contrib + exit_in
                     - o['capex'] - fee - refi_fee - cash_int - prin - mprin - n_fee - fac_ds - dist - close_pool)
            row.update(notesProceeds=n_proc, notesFees=n_fee, facilityInterestAccrued=n_acc, facilityInterestPaid=n_int,
                       facilityPrincipalPaid=n_prin, facilityDebtService=fac_ds,
                       facilityBalance=sum(f.bal for f in F), facilityAccruedInterest=sum(f.acc for f in F),
                       facilityDsra=dsra_close, facilityDsraMovement=dep - rel - n_draw, facilityDsraDraw=n_draw,
                       facilityDsraDeposit=dep, facilityDsraRelease=rel,
                       facilityExitPaid=sum(f.m['exitInterestPaid'] + f.m['exitPrincipalPaid'] for f in F),
                       preFundingCash=pre_funding_cash, unfundedGapM=gap, exitProceeds=exit_in,
                       distributionLocked=bool(locked), facilityConstructionLockup=bool(constr_lock),
                       sourcesUsesResidual=resid)
        rows.append(row)
    npv = sum(v / (1 + c['discount'] / 100) ** (i / 12) for i, v in enumerate(flows))
    out = dict(rows=rows, npvM=npv, defaulted=default)
    if F:
        facs, cw = [], []
        for f in sorted(F, key=lambda f: f.idx):                                  # [A17] input order in outputs
            w = f.warnings(); cw += w
            vals = [t['dscr'] for t in f.tests if t['dscr'] is not None]
            facs.append(dict(id=f.id, name=f.name, faceM=f.face, couponPct=f.cpn, issuePricePct=f.price,
                proceedsM=f.face * f.price / 100, oidM=f.face - f.face * f.price / 100, feesM=f.face * f.feep / 100,
                issueMonth=f.issue, firstPaymentMonth=f.first, maturityMonth=f.mat, priority=f.prio, buildings=f.blds,
                amortStartMonth=f.A, amortStartResolvedInMonth=f.A_resolved_in, constructionEndMonth=f.E,
                constructionLockupEndMonth=f.L,
                amortStartBasis=(f.ast['type'] if f.ast else 'none'),
                amortizationType=f.am['type'], dsraType=f.dsra_spec['type'], lockupDscr=f.lockup,
                totalInterestPaidM=f.int_paid, totalPrincipalPaidM=f.prin_paid, balloonM=f.balloon,
                endingBalanceM=f.bal, unpaidAtExitM=f.unpaid_exit, minDscr=(min(vals) if vals else None),
                dscrTests=f.tests, lockupMonths=f.lock_months, dsraDeficiencyMonths=f.def_months,
                schedule=f.schedule, evidence=f.evidence, warnings=w))
        cw += ['FACILITIES: single project cash pool; facility ring-fencing, cash sweeps and excess-cash-flow offers not modeled',
               'FACILITIES: payment shortfalls are shown as unfunded cash, not as facility arrears']
        out['facilities'] = facs
        out['summary'] = dict(facilities=facs, creditWarnings=cw, facilityPaymentShortfallMonths=shortfall_months,
                              unpaidDebtAtExitM=unpaid_exit_total)
    return out

if __name__ == '__main__':
    args = sys.argv[1:]
    cases = json.load(open(args[0]))
    res = {}
    for k, v in cases.items():
        if v.get('facilities'):
            try:
                res[k] = run(v)
            except ValueError as e:
                res[k] = dict(error=str(e))
        else:
            res[k] = run(v)
    json.dump(res, open(args[1], 'w'))
