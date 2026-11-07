"""Self-checks for the v25.9 Python reference (reference_v259.py).

Run:  python3 -I self_checks.py [path/to/reference_module.py]
      (paths resolve relative to this file; the optional argument checks another build of the reference,
       e.g. the pre-Amendment-1 version, to show the AM1-AM5 checks fail there)
Checks
  A. no-facility equality: reference_v259.run == powerpath_reference.run, byte-identical JSON, on
     cases.json, cases_v2583.json, cases_v2584.json (and with facilities: [] injected).
  B. per facility case / per facility / per month identities (balance roll, accrued roll, accrual formula,
     DSRA roll, row aggregation, debt service, DSRA movement, sources/uses residual recomputed from row
     fields, DSCR recomputation, nextPeriod DSRA requirement recomputation, balloon, totals, exit).
  C. scenario coverage expectations for cases_v259.json.
  D. validation: invalid inputs throw.
  E. Amendment 1 (AM1-AM5): event month E, construction DSRA switch at E, construction lock-up L,
     horizon-month maturity settled at exit, required output field names.
"""
import importlib.util, json, math, os, copy, sys, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
def load(name, fn):
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn)); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); return m
base = load('powerpath_reference', 'powerpath_reference.py')
ref = load('reference_v259', sys.argv[1] if len(sys.argv) > 1 else 'reference_v259.py')

TOL = 1e-9
fails, counts = [], dict(A=0, B=0, C=0, D=0, E=0)
def chk(group, cond, msg):
    counts[group] += 1
    if not cond: fails.append(f'[{group}] {msg}')
def close(a, b, tol=TOL):
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))

# ---- A. no-facility equality --------------------------------------------------------------
for fn in ('cases.json', 'cases_v2583.json', 'cases_v2584.json'):
    cases = json.load(open(os.path.join(HERE, fn)))
    for k, v in cases.items():
        o = json.dumps(base.run(copy.deepcopy(v)))
        chk('A', json.dumps(ref.run(copy.deepcopy(v))) == o, f'{fn}:{k} differs from base reference')
        chk('A', json.dumps(ref.run(dict(copy.deepcopy(v), facilities=[]))) == o, f'{fn}:{k} facilities=[] differs')

# ---- B. identities --------------------------------------------------------------------------
fcases = json.load(open(os.path.join(HERE, 'cases_v259.json')))
outs = {}
def check_case(name, case):
    out = ref.run(copy.deepcopy(case)); outs[name] = out
    c = dict(ref.DEFAULTS); c.update(case); months = c['months']; minliq = c['minLiquidity']
    rows = out['rows']; facs = out['facilities']
    chk('B', len(rows) == months, f'{name}: row count')
    sched = {f['id']: {s['month']: s for s in f['schedule']} for f in facs}
    for f in facs:
        S = sched[f['id']]; spec = next(x for x in case['facilities'] if x['id'] == f['id'])
        P = list(range(f['firstPaymentMonth'], f['maturityMonth'] + 1, 6))
        chk('B', sorted(S) == list(range(f['issueMonth'], months + 1)), f'{name}/{f["id"]}: schedule months')
        prev = None
        for m in sorted(S):
            s = S[m]; tag = f'{name}/{f["id"]}/m{m}'
            if m == f['issueMonth']:
                chk('B', close(s['opening'], f['faceM']) and s['accruedStart'] == 0 and s['dsraOpening'] == 0, f'{tag}: issue opening')
            else:
                chk('B', close(s['opening'], prev['closing']), f'{tag}: opening = prior closing')
                chk('B', close(s['accruedStart'], prev['accruedEnd']), f'{tag}: accruedStart = prior accruedEnd')
                chk('B', close(s['dsraOpening'], prev['dsraBalance']), f'{tag}: dsraOpening = prior balance')
            chk('B', close(s['closing'], s['opening'] - s['principalPaid']), f'{tag}: balance roll')
            chk('B', close(s['accruedEnd'], s['accruedStart'] + s['accrual'] - s['interestPaid']), f'{tag}: accrued roll')
            exp_acc = s['opening'] * f['couponPct'] / 1200 if (f['issueMonth'] < m <= f['maturityMonth'] and s['opening'] > 0) else 0.0
            chk('B', close(s['accrual'], exp_acc), f'{tag}: accrual formula')
            chk('B', close(s['dsraBalance'], s['dsraOpening'] + s['dsraDeposit'] - s['dsraRelease'] - s['dsraDraw']), f'{tag}: DSRA roll')
            chk('B', s['dsraBalance'] >= -TOL and s['closing'] >= -TOL, f'{tag}: non-negative balances')
            regular_paid = s['interestPaid'] - s['exitInterestPaid'] + s['principalPaid'] - s['exitPrincipalPaid']
            chk('B', s['dsraDraw'] <= min(s['dsraOpening'], regular_paid) + TOL, f'{tag}: draw bounded by DSRA and debt service')
            if m not in P and m != months:
                chk('B', s['interestPaid'] == 0 and s['principalPaid'] == 0, f'{tag}: payment only on payment months')
            deferred = (m == f['maturityMonth'] == months)                     # AM4
            if m in P:
                due = s['accruedStart'] + s['accrual']
                chk('B', close(s['interestPaid'] - s['exitInterestPaid'], 0.0 if deferred else due), f'{tag}: pays all accrued (or defers, AM4)')
                if s['dscr'] is not None and m - 5 >= f['issueMonth']:
                    num = sum(S[k]['cfadsShare'] for k in range(m - 5, m + 1))
                    chk('B', close(s['dscr'], num / (due + s['scheduledPrincipal'])), f'{tag}: DSCR recompute (interest due + installment)')
            if m < months and m >= f['issueMonth']:
                dt = spec.get('dsra', {'type': 'none'})['type']
                A, Ares, E = f['amortStartMonth'], f['amortStartResolvedInMonth'], f['constructionEndMonth']
                if s['closing'] <= 0: chk('B', s['dsraRequired'] == 0, f'{tag}: Q=0 once repaid')
                elif dt == 'fixed': chk('B', s['dsraRequired'] == spec['dsra']['amountM'], f'{tag}: fixed Q')
                elif dt == 'constructionThenNextPeriod' and (E is None or m < E):          # AM2
                    chk('B', s['dsraRequired'] == spec['dsra']['constructionAmountM'], f'{tag}: construction Q')
                elif dt in ('nextPeriod', 'constructionThenNextPeriod'):
                    q = next((p for p in P if p > m), None)
                    if q is None: chk('B', s['dsraRequired'] == 0, f'{tag}: no next period -> Q=0')
                    elif Ares is not None and Ares <= m and q < months:
                        exp = s['accruedEnd'] + s['closing'] * f['couponPct'] / 1200 * (q - m) + S[q]['scheduledPrincipal']
                        chk('B', close(s['dsraRequired'], exp), f'{tag}: nextPeriod Q recompute')
                    elif Ares is None:
                        chk('B', close(s['dsraRequired'], s['accruedEnd'] + s['closing'] * f['couponPct'] / 1200 * (q - m)), f'{tag}: nextPeriod Q (A unresolved)')
                deficient = s['dsraRequired'] - s['dsraBalance'] > 1e-8
                chk('B', deficient == (m in f['dsraDeficiencyMonths']), f'{tag}: deficiency listing')
            prev = s
        last = S[months]
        chk('B', close(f['endingBalanceM'], last['closing']), f'{name}/{f["id"]}: ending balance')
        chk('B', close(f['unpaidAtExitM'], last['closing'] + last['accruedEnd']), f'{name}/{f["id"]}: unpaid at exit')
        chk('B', last['dsraBalance'] == 0, f'{name}/{f["id"]}: DSRA released at exit')
        chk('B', close(f['totalInterestPaidM'], sum(s['interestPaid'] for s in S.values())), f'{name}/{f["id"]}: interest total')
        chk('B', close(f['totalPrincipalPaidM'], sum(s['principalPaid'] for s in S.values())), f'{name}/{f["id"]}: principal total')
        chk('B', close(f['totalPrincipalPaidM'] + f['endingBalanceM'], f['faceM']), f'{name}/{f["id"]}: principal + ending = face')
        mat = S[f['maturityMonth']]
        chk('B', close(f['balloonM'], max(0.0, mat['principalPaid'] - mat['scheduledPrincipal'])), f'{name}/{f["id"]}: balloon')
        chk('B', close(f['proceedsM'], f['faceM'] * f['issuePricePct'] / 100) and close(f['oidM'], f['faceM'] - f['proceedsM']), f'{name}/{f["id"]}: proceeds/OID')
        vals = [t['dscr'] for t in f['dscrTests'] if t['dscr'] is not None]
        chk('B', f['minDscr'] == (min(vals) if vals else None), f'{name}/{f["id"]}: minDscr')
        chk('B', [t['month'] for t in f['dscrTests']] == [p for p in P if p <= months], f'{name}/{f["id"]}: one DSCR test per payment month')
    prev_r = None
    for r in rows:
        m = r['month']; tag = f'{name}/m{m}'
        g = lambda k: sum(sched[f['id']][m][k] for f in facs if m in sched[f['id']])
        for rk, sk in (('facilityInterestAccrued', 'accrual'), ('facilityInterestPaid', 'interestPaid'), ('facilityPrincipalPaid', 'principalPaid'),
                       ('facilityBalance', 'closing'), ('facilityAccruedInterest', 'accruedEnd'), ('facilityDsra', 'dsraBalance'),
                       ('facilityDsraDraw', 'dsraDraw'), ('facilityDsraDeposit', 'dsraDeposit'), ('facilityDsraRelease', 'dsraRelease')):
            chk('B', close(r[rk], g(sk)), f'{tag}: row {rk} = sum of schedules')
        chk('B', close(r['notesProceeds'], sum(f['proceedsM'] for f in facs if f['issueMonth'] == m)), f'{tag}: proceeds')
        chk('B', close(r['notesFees'], sum(f['feesM'] for f in facs if f['issueMonth'] == m)), f'{tag}: fees')
        chk('B', close(r['facilityDebtService'], r['facilityInterestPaid'] + r['facilityPrincipalPaid']), f'{tag}: debt service')
        chk('B', close(r['facilityDsraMovement'], r['facilityDsraDeposit'] - r['facilityDsraRelease'] - r['facilityDsraDraw']), f'{tag}: DSRA movement')
        o_cash = prev_r['cash'] if prev_r else c['initialCash']; o_res = prev_r['reserve'] if prev_r else 0.0
        o_dsra = prev_r['facilityDsra'] if prev_r else 0.0
        resid = (o_cash + o_res + o_dsra + r['cfads'] + r['tenantCashReceipt'] + r['draw'] + r['mezzDraw'] + r['notesProceeds']
                 + r['sponsorContribution'] + r['exitProceeds'] - r['capex'] - r['cashInterest'] - r['principal'] - r['mezzPrincipal']
                 - r['notesFees'] - r['facilityDebtService'] - r['distribution'] - (r['cash'] + r['reserve'] + r['facilityDsra']))
        chk('B', abs(resid) < 1e-6 and abs(r['sourcesUsesResidual']) < 1e-6, f'{tag}: sources/uses residual {resid:.3e}')
        chk('B', r['draw'] == 0 and r['mezzDraw'] == 0 and r['debt'] == 0 and r['cashInterest'] == 0, f'{tag}: generic debt inert')
        chk('B', (r['unfundedGapM'] > 0) == (minliq - r['cash'] > 1e-8) or m == months, f'{tag}: unfunded gap consistent')
        if r['distribution'] > 0 and m < months:
            chk('B', not r['distributionLocked'], f'{tag}: distribution while locked')
        prev_r = r
    sm = out['summary']
    chk('B', close(sm['unpaidDebtAtExitM'], sum(f['unpaidAtExitM'] for f in facs)), f'{name}: unpaidDebtAtExitM')
    if sm['unpaidDebtAtExitM'] > 1e-8: chk('B', out['defaulted'], f'{name}: unpaid at exit must set defaulted')
    exp_sf = [r['month'] for r in rows if r['unfundedGapM'] > 0 and r['facilityDebtService'] - r['facilityExitPaid'] > 0]
    chk('B', sm['facilityPaymentShortfallMonths'] == exp_sf, f'{name}: facilityPaymentShortfallMonths')
    cw = sm['creditWarnings']
    chk('B', cw.count('FACILITIES: single project cash pool; facility ring-fencing, cash sweeps and excess-cash-flow offers not modeled') == 1
        and cw.count('FACILITIES: payment shortfalls are shown as unfunded cash, not as facility arrears') == 1, f'{name}: global warnings once')
    for f in facs: chk('B', all(w in cw for w in f['warnings']), f'{name}: facility warnings in creditWarnings')

    # ---- E. Amendment 1 per-case checks --------------------------------------------------------
    ROW_REQ = ['notesProceeds', 'notesFees', 'facilityInterestAccrued', 'facilityInterestPaid', 'facilityPrincipalPaid', 'facilityDebtService',
               'facilityBalance', 'facilityAccruedInterest', 'facilityDsra', 'facilityDsraMovement', 'facilityDsraDraw', 'facilityConstructionLockup']
    FAC_REQ = ['id', 'name', 'faceM', 'couponPct', 'issuePricePct', 'proceedsM', 'oidM', 'feesM', 'issueMonth', 'firstPaymentMonth', 'maturityMonth',
               'amortStartMonth', 'amortStartBasis', 'totalInterestPaidM', 'totalPrincipalPaidM', 'balloonM', 'endingBalanceM', 'unpaidAtExitM',
               'minDscr', 'dscrTests', 'lockupMonths', 'dsraDeficiencyMonths', 'schedule', 'evidence', 'warnings',
               'constructionEndMonth', 'constructionLockupEndMonth']
    SCH_REQ = ['month', 'opening', 'accrual', 'interestPaid', 'principalPaid', 'closing', 'accruedEnd', 'dsraRequired', 'dsraBalance', 'cfadsShare']
    chk('E', all(k in r for r in rows for k in ROW_REQ), f'{name}: AM5 row fields')
    chk('E', all(k in f for f in facs for k in FAC_REQ) and 'facilities' in out['summary'], f'{name}: AM5 facility fields')
    chk('E', all(k in s for f in facs for s in f['schedule'] for k in SCH_REQ), f'{name}: AM5 schedule fields')
    chk('E', all(set(t) >= {'month', 'dscr'} for f in facs for t in f['dscrTests']), f'{name}: AM5 dscrTests fields')
    for f in facs:
        spec = next(x for x in case['facilities'] if x['id'] == f['id']); ast = spec.get('amortStart'); E = f['constructionEndMonth']
        tag = f'{name}/{f["id"]}'
        if ast is None:
            chk('E', E is None and f['amortStartMonth'] is None, f'{tag}: AM1 omitted amortStart -> E undefined')
        elif ast['type'] == 'fixedMonth':
            chk('E', E == f['amortStartMonth'] == (ast.get('month') if ast.get('month') is not None else E), f'{tag}: AM1 fixedMonth E = A = given month')
        else:
            # event-based, no look-ahead: evaluated monthly from month 1, so it resolves exactly in month E
            if E is not None:
                chk('E', f['amortStartResolvedInMonth'] in (None, E), f'{tag}: AM1 resolution happens in event month E')
                if f['amortStartMonth'] is not None:
                    P = list(range(f['firstPaymentMonth'], f['maturityMonth'] + 1, 6))
                    want = min(p for p in P if (p > E + ast['offsetMonths'] if ast['type'] == 'afterFirstRent' else p >= E + ast['offsetMonths']))
                    chk('E', f['amortStartMonth'] == want, f'{tag}: AM1 A from E')
            else:
                chk('E', f['amortStartMonth'] is None and any('never resolved' in w for w in f['warnings']), f'{tag}: AM1 unresolved -> warning')
        Sm = {s['month']: s for s in f['schedule']}
        if f['maturityMonth'] == months:                                           # AM4
            s = Sm[months]
            chk('E', s['interestPaid'] == s['exitInterestPaid'] and s['principalPaid'] == s['exitPrincipalPaid'], f'{tag}: AM4 nothing paid in step 2')
            chk('E', s['dsraDraw'] == 0, f'{tag}: AM4 DSRA not drawn for deferred amount')
            chk('E', close(f['unpaidAtExitM'], s['opening'] - s['exitPrincipalPaid'] + s['accruedStart'] + s['accrual'] - s['exitInterestPaid']), f'{tag}: AM4 unpaid = due - paid at exit')
            chk('E', any(t['month'] == months for t in f['dscrTests']), f'{tag}: AM4 DSCR test still runs')
    L = {f['id']: f['constructionLockupEndMonth'] for f in facs}
    for r in rows:
        m = r['month']
        want = any(m in sched[f['id']] and sched[f['id']][m]['closing'] > 0 and (L[f['id']] is None or m < L[f['id']]) for f in facs)
        chk('E', r['facilityConstructionLockup'] == want, f'{name}/m{m}: AM3 construction lock-up flag')
        if want:
            chk('E', r['distributionLocked'] and (r['distribution'] == 0 or m == months), f'{name}/m{m}: AM3 no distribution while locked')
    for f in facs:
        if f['constructionLockupEndMonth'] is not None:
            chk('E', f['constructionLockupEndMonth'] <= months, f'{name}: AM3 L within horizon')

for name, case in fcases.items():
    try:
        check_case(name, case)
    except Exception as e:
        chk('B', False, f'{name}: crashed {type(e).__name__}: {e}')

# ---- C. coverage expectations ----------------------------------------------------------------
def F(name, i=0): return outs[name]['facilities'][i]
def R(name): return outs[name]['rows']
exp = [
 ('F01 bullet none: balloon = face, no amortStart', F('F01_bullet_none')['balloonM'] == 1500 and F('F01_bullet_none')['amortStartMonth'] is None),
 ('F02 dates mapped (issue 11, first 18, mat 60, A 24)', (F('F02_unknown_dates_fixed_dsra_evidence')['issueMonth'], F('F02_unknown_dates_fixed_dsra_evidence')['firstPaymentMonth'],
     F('F02_unknown_dates_fixed_dsra_evidence')['maturityMonth'], F('F02_unknown_dates_fixed_dsra_evidence')['amortStartMonth']) == (11, 18, 60, 24)),
 ('F02 unknown-amortization + 3 evidence warnings', sum('not Executed' in w for w in F('F02_unknown_dates_fixed_dsra_evidence')['warnings']) == 3
     and any('amortization unknown' in w for w in F('F02_unknown_dates_fixed_dsra_evidence')['warnings'])),
 ('F02 fixed DSRA 177 held then released at maturity', F('F02_unknown_dates_fixed_dsra_evidence')['schedule'][1]['dsraBalance'] == 177.0
     and F('F02_unknown_dates_fixed_dsra_evidence')['schedule'][60 - 11]['dsraRequired'] == 0),
 ('F03 fixedMonth: month field beats date (A=33)', F('F03_pct_fixedMonth_nextPeriod')['amortStartMonth'] == 33),
 ('F03 pct installments = 60/payment', all(s['scheduledPrincipal'] in (0, 60) for s in F('F03_pct_fixedMonth_nextPeriod')['schedule'])),
 ('F04 afterFirstRent: R=25, offset 6 -> A=37', F('F04_explicit_afterFirstRent_ctnp')['amortStartMonth'] == 37),
 ('F05 afterFinalCommencement with credits: C=31, K=43, A=47', F('F05_pct_afterFinalCommencement_credits')['amortStartMonth'] == 47),
 ('F06 DSRA drawn before sponsor in operating period', any(r['facilityDsraDraw'] > 0 and r['cfads'] > 0 and r['facilityDebtService'] > r['cfads'] for r in R('F06_dsra_draw_before_sponsor'))),
 ('F07 capped sponsor -> default, halt, amortStart never resolved, DSRA deficiency, shortfall months',
     outs['F07_capped_sponsor_halt']['defaulted'] and F('F07_capped_sponsor_halt')['amortStartMonth'] is None
     and any('never resolved' in w for w in F('F07_capped_sponsor_halt')['warnings']) and F('F07_capped_sponsor_halt')['dsraDeficiencyMonths']
     and outs['F07_capped_sponsor_halt']['summary']['facilityPaymentShortfallMonths']),
 ('F08 priority sort: senior (listed 2nd) draws DSRA first', True),
 ('F08 collateral shares differ', any(abs(a['cfadsShare'] - b['cfadsShare']) > 1 for a, b in zip(F('F08_two_facilities_priority_collateral', 0)['schedule'], F('F08_two_facilities_priority_collateral', 1)['schedule'][2:]))),
 ('F09 tranches delay full commencement (A=32 resolved m30)', F('F09_shared_power_tranches')['amortStartMonth'] == 32),
 ('F10 renewal: rent drops after 48m lease expiry', R('F10_lease_renewal')[70]['grossRevenue'] < R('F10_lease_renewal')[60]['grossRevenue']),
 ('F11 tenant_direct lifts DSCR above landlord-power case', F('F11_tenant_direct_power')['dscrTests'][-2]['dscr'] > F('F15_balloon_before_horizon')['dscrTests'][-2]['dscr']),
 ('F12 delay: first rent 25 (19+6) -> A=26', F('F12_delay_months')['amortStartMonth'] == 26),
 ('F13 exit insufficient: unpaid > 0, defaulted', F('F13_exit_unpaid')['unpaidAtExitM'] > 100 and outs['F13_exit_unpaid']['defaulted']),
 ('F14 ties keep input order & short explicit list', F('F14_ties_fee_oid_short_explicit', 0)['id'] == 'tie_a_b1'
     and sum(s['scheduledPrincipal'] for s in F('F14_ties_fee_oid_short_explicit', 0)['schedule']) == 80),
 ('F15 balloon paid in waterfall before horizon', F('F15_balloon_before_horizon')['balloonM'] > 0 and F('F15_balloon_before_horizon')['schedule'][96 - 2]['closing'] == 0),
 ('F16 ctnp switches to nextPeriod when A resolves (no amortization)', F('F16_none_with_trigger_ctnp')['amortStartMonth'] == 38
     and F('F16_none_with_trigger_ctnp')['schedule'][29 - 2]['dsraRequired'] == 90 and F('F16_none_with_trigger_ctnp')['schedule'][31 - 2]['dsraRequired'] != 90),
]
# F08: in a month where both draw, senior (priority 1) must be drawn before junior gets anything unless senior exhausted
f8 = outs['F08_two_facilities_priority_collateral']['facilities']
jun, sen = {s['month']: s for s in f8[0]['schedule']}, {s['month']: s for s in f8[1]['schedule']}
ok = all(not (jun[m]['dsraDraw'] > 0 and sen[m]['dsraDraw'] < min(sen[m]['dsraOpening'], sen[m]['interestPaid'] + sen[m]['principalPaid']) - 1e-9) for m in jun)
exp[10] = ('F08 priority order: junior drawn only after senior draw capacity used', ok and f8[1]['id'] == 'senior_b1b2')
for label, cond in exp: chk('C', bool(cond), label)
def am_scenarios():
    f5 = F('F05_pct_afterFinalCommencement_credits')
    chk('E', f5['constructionEndMonth'] == 43 and f5['amortStartResolvedInMonth'] == 43, 'AM1 F05: T = max(C=31, K=43) = 43, resolved at 43 not at C')
    s5 = {s['month']: s for s in f5['schedule']}
    chk('E', s5[42]['dsraRequired'] == 250 and s5[43]['dsraRequired'] != 250, 'AM2 F05: construction DSRA until E=43')
    f17 = F('F17_AM2_ctnp_fixedMonth'); s17 = {s['month']: s for s in f17['schedule']}
    chk('E', f17['constructionEndMonth'] == 40 and s17[39]['dsraRequired'] == 140 and s17[40]['dsraRequired'] != 140, 'AM2 F17: fixedMonth -> construction DSRA until month 40')
    exp40 = s17[40]['accruedEnd'] + s17[40]['closing'] * 8.5 / 1200 * (44 - 40) + s17[44]['scheduledPrincipal']
    chk('E', close(s17[40]['dsraRequired'], exp40), 'AM2 F17: nextPeriod from month 40 uses installment at q=44')
    f18 = F('F18_AM3_construction_lockup_ends'); r18 = R('F18_AM3_construction_lockup_ends')
    chk('E', f18['constructionLockupEndMonth'] == 31, 'AM3 F18: L = 31 (B3 first rent; B1 from 19)')
    chk('E', all(r['facilityConstructionLockup'] for r in r18[:30]) and not any(r['facilityConstructionLockup'] for r in r18[30:]), 'AM3 F18: lock-up months 1..30 only')
    chk('E', r18[0]['sponsorContribution'] == 0 and r18[0]['cash'] > 1000 and sum(r['distribution'] for r in r18[:30]) == 0, 'AM3 F18: unspent proceeds retained and fund capex before sponsor')
    chk('E', any(r['distribution'] > 0 for r in r18[30:]), 'AM3 F18: distributions resume after lock-up ends')
    f07 = F('F07_capped_sponsor_halt')
    chk('E', f07['constructionLockupEndMonth'] is None and f07['constructionEndMonth'] is None, 'AM1/AM3 F07: halt abandons B3 -> E and L never occur')
    f19 = outs['F19_AM4_partial_exit_recovery']
    jun, sen = f19['facilities']
    chk('E', sen['unpaidAtExitM'] == 0 and 0 < jun['unpaidAtExitM'] < jun['faceM'] and jun['schedule'][-1]['exitPrincipalPaid'] > 0, 'AM4 F19: senior fully repaid, junior partially recovered at exit')
    chk('E', f19['defaulted'] and close(f19['summary']['unpaidDebtAtExitM'], jun['unpaidAtExitM']), 'AM4 F19: defaulted, unpaidDebtAtExitM = junior unpaid')
    f13 = F('F13_exit_unpaid'); s = f13['schedule'][-1]
    chk('E', s['exitInterestPaid'] > 0 and close(f13['balloonM'], max(0.0, s['exitPrincipalPaid'] - s['scheduledPrincipal'])), 'AM4 F13: interest settled at exit; balloon = exit principal - installment')
try:
    am_scenarios()
except Exception as e:
    chk('E', False, f'AM scenario checks crashed {type(e).__name__}: {e}')

# ---- D. validation ---------------------------------------------------------------------------
good = fcases['F03_pct_fixedMonth_nextPeriod']
def bad(mut, needle):
    c2 = copy.deepcopy(good); mut(c2); f = c2['facilities'][0]
    try:
        ref.run(c2); chk('D', False, f'expected error containing {needle!r}')
    except ValueError as e:
        chk('D', needle in str(e), f'error {e!s} should contain {needle!r}')
fx = lambda **kw: (lambda c2: c2['facilities'][0].update(kw))
bad(lambda c2: c2.update(ltc=65), 'Generic construction debt must be disabled')
bad(lambda c2: c2.update(mezzLtcPct=5), 'Generic construction debt must be disabled')
bad(fx(issueMonth=0), 'issueMonth must be >= 1')
bad(fx(firstPaymentMonth=3), 'issueMonth must be < firstPaymentMonth')
bad(fx(maturityMonth=126), 'maturityMonth must be <= months')
bad(fx(maturityMonth=104), 'multiple of 6')
bad(fx(buildings=['B1', 'Nope']), 'unknown building')
bad(fx(buildings=[]), 'non-empty')
bad(lambda c2: c2['facilities'].append(copy.deepcopy(c2['facilities'][0])), 'Duplicate facility id')
bad(fx(amortization={'type': 'pctOriginalPerYear', 'annualPct': 120}), 'annualPct')
bad(fx(amortization={'type': 'pctOriginalPerYear'}), 'annualPct')
bad(fx(amortization={'type': 'explicit', 'amountsM': [10, -1]}), 'finite and >= 0')
bad(fx(amortization={'type': 'explicit', 'amountsM': [10, float('nan')]}), 'finite and >= 0')
bad(lambda c2: c2['facilities'][0].pop('amortStart'), 'amortStart is required')
bad(fx(maturityMonth=None, maturityDate='2037-02-15'), 'maturityMonth must be <= months')   # date -> month 134
bad(fx(faceM=0), 'faceM')
bad(fx(amortStart={'type': 'afterFirstRent', 'offsetMonths': -1}), 'offsetMonths')

print('Self-check summary')
for g, n in counts.items():
    print(f'  {g}: {n} checks, {sum(1 for x in fails if x.startswith("[" + g))} failed')
print(f'  facility cases: {len(fcases)}')
for x in fails[:40]: print('  FAIL', x)
print('RESULT:', 'PASS' if not fails else f'FAIL ({len(fails)})')
raise SystemExit(1 if fails else 0)
