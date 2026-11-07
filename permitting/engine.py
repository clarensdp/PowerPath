"""PowerPath permitting engine (permitting-1.0).

Project design + parcel facts + jurisdiction rules  ->  required permit set (with the trigger that fired),
a calendar critical path for P50 and P90 cases, per-tranche earliest power dates, v8.2 gate states, and
schedule27 milestones for each power path.

Conventions
  * Months are measured from project.anchor_date (month 0). Use the same anchor as the v8.2 path months.
  * A node starts when all applicable predecessors finish; durations come from the rule's basis-labelled
    P50/P90. Approved permits are fixed at their actual date. Nothing here is a utility or agency commitment.
  * Export to schedule27 uses its parallel-driver convention: one milestone per permit whose delay is how far
    that permit alone (plus everything downstream of it) pushes power past the path's baseline month.
    The maximum over milestones equals this engine's total delay, so nothing is double counted.
"""
from __future__ import annotations

import copy
import json
import math
from datetime import date, timedelta
from pathlib import Path

ENGINE_VERSION = 'permitting-1.0'
DATA = Path(__file__).resolve().parent / 'data'
SCENARIOS = ('p50', 'p90')
INF = float('inf')
SYNTHETIC = ('ONSITE_EQUIPMENT', 'CONSTRUCTION', 'ENERGIZATION_GRID', 'ENERGIZATION_ONSITE')
GATE_FOR_ALIAS = {'ENERGIZATION': ('ENERGIZATION_GRID', 'ENERGIZATION_ONSITE')}
JURISDICTION_FILES = {('VA', 'Loudoun'): ['us-federal.json', 'us-va.json', 'utility-dominion-va.json', 'us-va-loudoun.json']}


class PermittingError(ValueError):
    pass


# ---------------------------------------------------------------- dates
def month_to_date(anchor: date, m: float) -> date | None:
    if m is None or m == INF:
        return None
    return anchor + timedelta(days=round(m * 30.4375))


def date_to_month(anchor: date, d: date | str) -> float:
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return (d - anchor).days / 30.4375


# ---------------------------------------------------------------- rules
def load_jurisdiction(state: str, county: str) -> dict:
    files = JURISDICTION_FILES.get((state, county))
    if not files:
        raise PermittingError(f'No permitting rules mapped for {county}, {state}; screening must report this as unknown, not as clear')
    merged = {'rules': {}, 'overlays': {}, 'policy_areas': {}, 'statutes': {}, 'facts': {}, 'files': [], 'last_verified': []}
    for f in files:
        d = json.loads((DATA / 'rules' / f).read_text())
        merged['files'].append(f)
        merged['last_verified'].append(d.get('last_verified'))
        for r in d.get('rules', []):
            if r['id'] in merged['rules']:
                raise PermittingError('Duplicate rule ' + r['id'])
            merged['rules'][r['id']] = dict(r, jurisdiction=d['jurisdiction']['id'])
        merged['overlays'].update(d.get('overlays', {}))
        merged['policy_areas'].update(d.get('policy_areas', {}))
        merged['statutes'].update(d.get('statutes', {}))
        if d.get('facts'):
            merged['facts'][d['jurisdiction']['id']] = d['facts']
        if d.get('zoning_facts'):
            merged['facts'][d['jurisdiction']['id']] = d['zoning_facts']
    merged['sources'] = json.loads((DATA / 'sources.json').read_text())['sources']
    merged['taxonomy'] = json.loads((DATA / 'taxonomy.json').read_text())
    for r in merged['rules'].values():
        for s in r.get('sources', []):
            if s not in merged['sources']:
                raise PermittingError(f"Rule {r['id']} cites unknown source {s}")
    return merged


def _get(obj, path):
    cur = obj
    for part in path.split('.'):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def evaluate(cond, ctx) -> bool:
    if 'all' in cond:
        return all(evaluate(c, ctx) for c in cond['all'])
    if 'any' in cond:
        return any(evaluate(c, ctx) for c in cond['any'])
    v = _get(ctx, cond['field'])
    op, ref = cond['op'], cond.get('value')
    if op == 'true':
        return v is True
    if op == 'false':
        return v is False or v is None
    if v is None:
        return False
    ops = {'gt': lambda: v > ref, 'ge': lambda: v >= ref, 'lt': lambda: v < ref, 'le': lambda: v <= ref,
           'eq': lambda: v == ref, 'ne': lambda: v != ref, 'in': lambda: v in (ref or [])}
    if op not in ops:
        raise PermittingError('Unknown trigger operator ' + op)
    return ops[op]()


def _validate_project(p):
    for k in ('name', 'anchor_date', 'jurisdiction', 'parcel', 'design'):
        if k not in p:
            raise PermittingError('Project missing ' + k)
    d = p['design']
    if not (isinstance(d.get('it_mw'), (int, float)) and d['it_mw'] > 0):
        raise PermittingError('design.it_mw must be positive')
    date.fromisoformat(p['anchor_date'])


def derive(project, scenario, J):
    ctx = copy.deepcopy(project)
    d, parcel = ctx['design'], ctx['parcel']
    d.setdefault('anticipated_utility_mw', d['it_mw'])
    d.setdefault('backup_generators', True)
    d.setdefault('onsite_generation_mw', 0)
    d.setdefault('new_substations', 0)
    d.setdefault('new_transmission_kv', 0)
    d.setdefault('construction_months', 18)
    grandfathered = bool(parcel.get('grandfathered_by_right')) and (parcel.get('residential_within_ft') or 0) > 500
    rescission_risk = 'LC_GRANDFATHER_2025' in J['overlays'] and scenario == 'p90'
    by_right = grandfathered and not rescission_risk
    ctx['_derived'] = {'by_right_grandfathered': by_right, 'legislative_required': not by_right,
                       'grandfather_converted_in_p90': grandfathered and rescission_risk}
    return ctx


# ---------------------------------------------------------------- schedule
def _duration(rule, ctx, scenario):
    dur = rule.get('duration') or {}
    for alt in rule.get('duration_if', []):
        if evaluate(alt['when'], ctx):
            dur = alt['duration']
    return float(dur.get(scenario, 0)), dur.get('basis', 'prior')


def applicable_rules(J, ctx, exclude=()):
    out, reasons = {}, {}
    for rid, r in J['rules'].items():
        if rid in exclude:
            continue
        if evaluate(r['trigger'], ctx):
            out[rid] = r
            reasons[rid] = r.get('trigger_note') or json.dumps(r['trigger'])
    return out, reasons


def _preds(rules, ctx):
    """Predecessor map over applicable rules plus synthetic nodes. Edge kinds: start, decision, lag."""
    nodes = set(rules) | {'CONSTRUCTION', 'ENERGIZATION_GRID'}
    if ctx['design']['onsite_generation_mw'] > 0:
        nodes |= {'ONSITE_EQUIPMENT', 'ENERGIZATION_ONSITE'}
    preds = {n: [] for n in nodes}
    for rid, r in rules.items():
        for dep in r.get('depends_on', []):
            if dep in rules:
                preds[rid].append((dep, 'start', None))
        for tgt in r.get('gates', []):
            for t in GATE_FOR_ALIAS.get(tgt, (tgt,)):
                if t in preds:
                    preds[t].append((rid, 'start', None))
        for tgt in r.get('gates_decision_of', []):
            if tgt in rules:
                preds[tgt].append((rid, 'decision', None))
        for c in r.get('min_after', []):
            if c['rule'] in rules:
                preds[rid].append((c['rule'], 'lag', c['lag']))
    preds['ENERGIZATION_GRID'].append(('CONSTRUCTION', 'start', None))
    if 'ENERGIZATION_ONSITE' in preds:
        preds['ENERGIZATION_ONSITE'] += [('CONSTRUCTION', 'start', None), ('ONSITE_EQUIPMENT', 'start', None)]
    return preds


def _topo(preds):
    order, seen, stack = [], set(), set()

    def visit(n):
        if n in seen:
            return
        if n in stack:
            raise PermittingError('Permit dependency cycle at ' + n)
        stack.add(n)
        for p, _, _ in preds[n]:
            visit(p)
        stack.discard(n)
        seen.add(n)
        order.append(n)
    for n in sorted(preds):
        visit(n)
    return order


def _pause(overlay, anchor, referral_m, decision_m, scenario):
    eff = date_to_month(anchor, overlay['effective_from'])
    if decision_m == INF or decision_m < eff:
        return decision_m, None
    release_target = date_to_month(anchor, overlay['release_target'][scenario])
    release = min(release_target, referral_m + overlay['hold_months_from_referral'])
    if release <= decision_m:
        return decision_m, None
    return release, {'overlay': 'LC_PAUSE_2026', 'held_from_month': decision_m, 'released_month': release,
                     'binding': 'referral + 12 months' if release < release_target else 'Phase 2 adoption target'}


def schedule(project, J, scenario):
    """Two passes: a rule with effective_from (e.g. Va. Code § 15.2-2209.5, from 2026-07-01) applies only if the
    decision it gates falls on or after that date."""
    first = _schedule(project, J, scenario, ())
    anchor = first['anchor']
    drop = []
    for rid, r in first['rules'].items():
        eff = r.get('effective_from')
        if not eff:
            continue
        gated = [first['nodes'][g]['finish'] for g in r.get('gates_decision_of', []) if g in first['nodes']]
        if gated and max(gated) != INF and max(gated) < date_to_month(anchor, eff):
            drop.append(rid)
    if not drop:
        return first
    out = _schedule(project, J, scenario, tuple(drop))
    out['excluded_by_effective_date'] = drop
    return out


def _schedule(project, J, scenario, exclude):
    anchor = date.fromisoformat(project['anchor_date'])
    ctx = derive(project, scenario, J)
    rules, reasons = applicable_rules(J, ctx, exclude)
    # Nothing undecided can finish before the as-of date (default: anchor, i.e. a prediction made at filing).
    as_of = max(0.0, date_to_month(anchor, project.get('as_of_date') or project['anchor_date']))
    status = project.get('status', {})
    preds = _preds(rules, ctx)
    order = _topo(preds)
    nodes, notes = {}, []
    policy = J['policy_areas'].get(ctx['parcel'].get('policy_area'))
    for n in order:
        pr = preds[n]
        start_preds = [p for p in pr if p[1] == 'start']
        start = max([nodes[p]['finish'] for p, _, _ in start_preds] + [0.0])
        rec = {'id': n, 'start': start, 'basis': 'prior', 'steps': [], 'holds': []}
        r = rules.get(n)
        st = status.get(n, {})
        if r and r.get('start_after_months'):
            start = max(start, float(r['start_after_months'][scenario]))
        if r and st.get('filed_date'):
            start = date_to_month(anchor, st['filed_date'])
        elif r and not st:
            start = max(start, as_of)   # no recorded status: assume not started as of the as-of date
        rec['start'] = start
        if n == 'CONSTRUCTION':
            d = float(ctx['design']['construction_months']) + (6 if scenario == 'p90' else 0)
            rec.update(finish=max(start + d, as_of), basis='prior' if scenario == 'p90' else 'project_input')
        elif n == 'ONSITE_EQUIPMENT':
            lead = ctx['design'].get('onsite_equipment_lead_months', 18)
            st0 = 0.0 if ctx['design'].get('onsite_equipment_ordered') else as_of
            rec.update(start=st0, finish=st0 + float(lead) + (6 if scenario == 'p90' else 0), basis='prior')
        elif n.startswith('ENERGIZATION'):
            rec.update(finish=start, basis='derived')
        elif r.get('bundle_with') and r['bundle_with'] in rules:
            tgt = nodes[r['bundle_with']]
            rec.update(start=tgt['start'], finish=tgt['finish'], basis=tgt['basis'], bundled_with=r['bundle_with'])
        elif st.get('state') == 'approved':
            m = date_to_month(anchor, st['decision_date']) if st.get('decision_date') else 0.0
            rec.update(start=m, finish=m, basis='actual')
        elif st.get('state') == 'denied':
            rec.update(finish=INF, basis='actual', blocked='denied')
        elif r.get('steps'):
            t = start
            bases = []
            for s in r['steps']:
                st_start = t
                if s.get('decision'):
                    dec_preds = [nodes[p]['finish'] for p, k, _ in pr if k == 'decision']
                    t = max([t + float(s['duration'][scenario])] + dec_preds)
                else:
                    t = t + float(s['duration'][scenario])
                fixed = st.get(s['id'] + '_date')
                if fixed:
                    t = date_to_month(anchor, fixed)
                else:
                    t = max(t, as_of)
                referral = t if not s.get('decision') else rec['steps'][-1]['finish'] if rec['steps'] else start
                if s.get('decision'):
                    for ov in r.get('overlays', []):
                        o = J['overlays'].get(ov)
                        assumed = (project.get('overlay_assumptions') or {}).get(ov, (o or {}).get('default_assumption', 'adopted'))
                        if o and o['type'] == 'decision_hold' and assumed == 'adopted' and \
                                not (n == 'LU_SUBSTATION' and ctx['design'].get('grid_reliability_substation')):
                            t2, hold = _pause(o, anchor, referral, t, scenario)
                            if hold:
                                rec['holds'].append(hold)
                                t = t2
                bases.append(s['duration'].get('basis', 'prior'))
                rec['steps'].append({'id': s['id'], 'name': s['name'], 'start': st_start, 'finish': t, 'basis': s['duration'].get('basis')})
            rec['finish'] = t
            rec['basis'] = 'observed' if all(b == 'observed' for b in bases) else 'mixed'
        else:
            d, basis = _duration(r, ctx, scenario)
            rec.update(finish=max(start + d, as_of), basis=basis)
        for p, k, lag in pr:
            if k == 'lag':
                rec['finish'] = max(rec['finish'], nodes[p]['finish'] + float(lag[scenario]))
        if n == 'LU_LEGISLATIVE' and policy and policy.get('legislative_outcome') == 'prohibited':
            rec.update(finish=INF, blocked='policy area prohibits data centers')
        rec['duration'] = (rec['finish'] - rec['start']) if rec['finish'] != INF else INF
        nodes[n] = rec
    # mark inherited infinity
    for n in order:
        if any(nodes[p]['finish'] == INF for p, _, _ in preds[n]) and nodes[n]['finish'] != INF:
            nodes[n]['finish'] = INF
            nodes[n]['blocked'] = nodes[n].get('blocked') or 'upstream blocked'
    return {'ctx': ctx, 'rules': rules, 'reasons': reasons, 'preds': preds, 'order': order, 'nodes': nodes, 'anchor': anchor}


def critical_path(sched, target, scenario):
    """Walk back from target through the binding predecessor (start or lag edge whose time sets this node)."""
    nodes, preds = sched['nodes'], sched['preds']
    if target not in nodes:
        return []
    chain, n = [target], target
    while preds[n]:
        cands = []
        for p, k, lag in preds[n]:
            if k == 'start':
                cands.append((nodes[p]['finish'], p))
            elif k == 'lag':
                cands.append((nodes[p]['finish'] + float(lag[scenario]), p))
        if not cands:
            break
        f, p = max(cands)
        binds_start = abs(f - nodes[n]['start']) < 1e-6
        binds_finish = abs(f - nodes[n]['finish']) < 1e-6
        if not (binds_start or binds_finish) or f <= 0:
            break
        chain.append(p)
        n = p
    return list(reversed(chain))


def downstream(sched, src, target, scenario):
    """Longest months from src finishing to target node, along gating edges."""
    nodes, preds = sched['nodes'], sched['preds']
    succ = {}
    for n, pr in preds.items():
        for p, k, lag in pr:
            succ.setdefault(p, []).append((n, k, lag))
    memo = {}

    def down(n):
        if n == target:
            return 0.0
        if n in memo:
            return memo[n]
        best = -INF
        for s, k, lag in succ.get(n, []):
            rest = down(s)
            if rest == -INF:
                continue
            node = nodes[s]
            if k == 'lag':
                w = float(lag[scenario])
            elif k == 'decision':
                w = 0.0   # the decision waits on this item directly; its own step time is already in the node
            else:
                w = node['duration'] if node['duration'] != INF else 0.0
            best = max(best, w + rest)
        memo[n] = best
        return best
    return down(src)


# ---------------------------------------------------------------- outputs
PATH_TRANCHES = {'grid': ('ENERGIZATION_GRID', 'ENERGIZATION_GRID'), 'btm': ('ENERGIZATION_ONSITE', 'ENERGIZATION_ONSITE'),
                 'hyb': ('ENERGIZATION_ONSITE', 'ENERGIZATION_GRID'), 'flex': ('ENERGIZATION_GRID', 'ENERGIZATION_GRID')}


def _rule_applies_to_path(rule, pk):
    p = rule.get('paths', 'all')
    return p == 'all' or pk in p


def assess(project: dict) -> dict:
    _validate_project(project)
    jur = project['jurisdiction']
    J = load_jurisdiction(jur['state'], jur['county'])
    anchor = date.fromisoformat(project['anchor_date'])
    runs = {s: schedule(project, J, s) for s in SCENARIOS}
    for s in SCENARIOS:
        runs[s]['_scenario'] = s
    base = runs['p50']
    tax = J['taxonomy']['permit_types']

    permits = []
    for rid in sorted(set(runs['p50']['rules']) | set(runs['p90']['rules'])):
        r = J['rules'][rid]
        row = {'id': rid, 'name': tax[r['permit_type']]['name'], 'authority': r['authority'], 'layer': tax[r['permit_type']]['layer'],
               'discretion': r.get('discretion'), 'hearings': r.get('hearings'), 'paths': r.get('paths', 'all'),
               'trigger': (base['reasons'].get(rid) or runs['p90']['reasons'].get(rid)),
               'only_in_p90': rid not in base['rules'],
               'requires': r.get('requires'), 'v82_gate': tax[r['permit_type']]['v82_gate'],
               'sources': [{'id': s, **{k: J['sources'][s][k] for k in ('title', 'url', 'date', 'class')}} for s in r.get('sources', [])],
               'status': project.get('status', {}).get(rid, {}).get('state', 'not_started')}
        for s in SCENARIOS:
            nd = runs[s]['nodes'].get(rid)
            if nd:
                row[s] = {'start_month': nd['start'], 'finish_month': nd['finish'], 'finish_date': str(month_to_date(anchor, nd['finish']) or 'blocked'),
                          'basis': nd['basis'], 'steps': [{**x, 'finish_date': str(month_to_date(anchor, x['finish']))} for x in nd['steps']],
                          'holds': nd['holds'], 'blocked': nd.get('blocked')}
        for w in r.get('warnings_if', []):
            if evaluate(w['when'], base['ctx']):
                row.setdefault('warnings', []).append(w['text'])
        permits.append(row)

    tranches = {}
    for s in SCENARIOS:
        for t in ('ENERGIZATION_GRID', 'ENERGIZATION_ONSITE'):
            nd = runs[s]['nodes'].get(t)
            if nd:
                cp = critical_path(runs[s], t, s)
                months = [runs[s]['nodes'][c]['duration'] for c in cp if runs[s]['nodes'][c]['duration'] not in (INF,)]
                prior_months = sum(runs[s]['nodes'][c]['duration'] for c in cp
                                   if runs[s]['nodes'][c]['basis'] in ('prior',) and runs[s]['nodes'][c]['duration'] != INF)
                tranches.setdefault(t, {})[s] = {'month': nd['finish'], 'date': str(month_to_date(anchor, nd['finish']) or 'blocked'),
                                                 'critical_path': cp, 'assumption_months_on_critical_path': prior_months,
                                                 'critical_path_months': sum(months)}

    paths_in = project.get('paths') or {}
    available = ['grid'] + (['btm'] if base['ctx']['design']['onsite_generation_mw'] >= base['ctx']['design']['it_mw'] else
                            ['hyb'] if base['ctx']['design']['onsite_generation_mw'] > 0 else [])
    path_out = {}
    for pk in sorted(set(paths_in) | set(available)):
        first_t, full_t = PATH_TRANCHES[pk]
        if first_t not in tranches or full_t not in tranches:
            path_out[pk] = {'available': False, 'reason': 'design has no on-site generation for this path'}
            continue
        row = {'available': True, 'first_power_tranche': first_t, 'full_load_tranche': full_t}
        for s in SCENARIOS:
            f, u = tranches[first_t][s]['month'], tranches[full_t][s]['month']
            u = max(f, u)
            row[s] = {'first_power_month': f, 'full_load_month': u,
                      'first_power_date': str(month_to_date(anchor, f) or 'blocked'), 'full_load_date': str(month_to_date(anchor, u) or 'blocked')}
            b = paths_in.get(pk, {})
            if b.get('first_power_month') is not None:
                row[s]['first_power_delay_months'] = max(0.0, f - float(b['first_power_month'])) if f != INF else INF
            if b.get('full_load_month') is not None:
                row[s]['full_load_delay_months'] = max(0.0, u - float(b['full_load_month'])) if u != INF else INF
        path_out[pk] = row

    gates = build_gates(project, J, runs, path_out)
    flags = build_flags(project, J, runs)
    excluded = {s: runs[s].get('excluded_by_effective_date', []) for s in SCENARIOS}
    return {'engine_version': ENGINE_VERSION, 'project': project['name'], 'anchor_date': project['anchor_date'],
            'jurisdiction_files': J['files'], 'rules_last_verified': min(x for x in J['last_verified'] if x),
            'permits': permits, 'tranches': tranches, 'paths': path_out, 'v82_gates': gates, 'flags': flags,
            'grandfather_converted_in_p90': runs['p90']['ctx']['_derived']['grandfather_converted_in_p90'],
            'excluded_by_effective_date': excluded,
            'label': 'SCREENING: rule-based permit map with basis-labelled durations; not legal advice, an agency commitment or a utility date',
            '_runs': runs, '_J': J, '_status': project.get('status', {}),
            '_baselines': {k: v.get('first_power_month') for k, v in paths_in.items()}}


def build_gates(project, J, runs, path_out):
    base = runs['p50']
    ctx, nodes = base['ctx'], base['nodes']
    policy_name = ctx['parcel'].get('policy_area')
    policy = J['policy_areas'].get(policy_name)
    gates, sev, months, notes = {}, {}, {}, {}
    st = project.get('status', {})
    # Zoning
    lu = 'LU_LEGISLATIVE' if 'LU_LEGISLATIVE' in base['rules'] else 'LU_BY_RIGHT'
    lst = st.get(lu, {}).get('state')
    if policy and policy.get('legislative_outcome') == 'prohibited':
        gates['Zoning'], notes['Zoning'] = 'N', policy['note']
    elif lst == 'denied':
        gates['Zoning'], notes['Zoning'] = 'N', 'Application denied'
    elif lst == 'approved':
        gates['Zoning'] = 'Y'
    elif lu == 'LU_BY_RIGHT':
        gates['Zoning'], sev['Zoning'] = 'C', 'Minor'
        notes['Zoning'] = 'Grandfathered by-right route; rescission proposal unresolved (P90 assumes legislative review)'
    elif policy is None:
        gates['Zoning'], notes['Zoning'] = 'U', f'Policy area {policy_name!r} not mapped'
    else:
        gates['Zoning'], sev['Zoning'] = 'C', policy.get('severity', 'Moderate')
        notes['Zoning'] = policy['note']
    # Moratorium / pause
    held = [h for n in ('LU_LEGISLATIVE', 'LU_SUBSTATION') for h in nodes.get(n, {}).get('holds', [])]
    if held:
        gates['Moratorium'], sev['Moratorium'] = 'C', 'Moderate'
        o = J['overlays']['LC_PAUSE_2026']
        notes['Moratorium'] = o['summary'] + ' Status: ' + o['status']
    else:
        gates['Moratorium'] = 'Y'
    # Air permit (on-site generation)
    if 'AIR_ONSITE' in base['rules']:
        a = st.get('AIR_ONSITE', {}).get('state')
        gates['Air permit'] = 'Y' if a == 'approved' else ('N' if a == 'denied' else 'C')
        if gates['Air permit'] == 'C':
            sev['Air permit'] = 'Moderate'
    else:
        gates['Air permit'] = 'NA'
    # remediation months: largest P50 first-power delay attributable to the gate's permits
    exp = export_schedule27(None, {'_runs': runs, 'paths': path_out, '_J': J, '_status': st,
                                   '_baselines': {k: v.get('first_power_month') for k, v in (project.get('paths') or {}).items()}})
    for g in gates:
        ms = [m['delay_months'] for v in exp.values() for m in v['milestones'] if m.get('gate_key') == g]
        months[g] = max(ms) if ms else 0
    return {'gates': gates, 'severity': sev, 'remediation_months': months, 'notes': notes}


BLOCKED_DELAY = 999   # schedule27 needs an integer; a blocked permit is reported as an unbounded delay


def export_schedule27(project, assessment, scenario='p50'):
    """schedule27 milestone sets per path (parallel drivers). Requires baseline first_power_month per path.
    Each milestone's delay = how far that permit plus its downstream chain pushes first power past baseline.
    The maximum over milestones equals the engine's first-power delay for the path."""
    run = assessment['_runs'][scenario]
    J = assessment['_J']
    tax = J['taxonomy']['permit_types']
    status = assessment.get('_status', {})
    out = {}
    for pk, row in assessment['paths'].items():
        if not row.get('available') or 'first_power_delay_months' not in row.get(scenario, {}):
            continue
        d0 = row[scenario]['first_power_delay_months']
        baseline = assessment.get('_baselines', {}).get(pk)
        if baseline is None:
            continue
        target = row['first_power_tranche']
        ms = []

        def add(mid, title, category, finish, down, gate_key, source_url, st='not_started'):
            implied = finish + down
            if implied == INF or baseline is None:
                delay = BLOCKED_DELAY
            else:
                delay = max(0, math.ceil(implied - baseline - 1e-9))
            ms.append({'id': mid, 'title': title, 'category': category, 'status': st, 'planned_month': baseline,
                       'delay_months': delay, 'float_months': 0, 'predecessor_id': None, 'permit_id': None,
                       'gate_key': gate_key, 'source_url': source_url})
        for rid, r in run['rules'].items():
            if not _rule_applies_to_path(r, pk):
                continue
            down = downstream(run, rid, target, scenario)
            if down == -INF:
                continue
            nd = run['nodes'][rid]
            src = (r.get('sources') or [None])[0]
            st = {'approved': 'completed', 'pending': 'submitted'}.get(status.get(rid, {}).get('state'), 'not_started')
            add(rid, tax[r['permit_type']]['name'], 'utility' if tax[r['permit_type']]['category'] == 'power' else 'permitting',
                nd['finish'], down, tax[r['permit_type']]['v82_gate'], J['sources'][src]['url'] if src else None, st)
            for h in nd.get('holds', []):
                o = J['overlays'][h['overlay']]
                add(h['overlay'], 'Board decision hold: ' + o['summary'][:80], 'permitting', nd['finish'], down,
                    o['v82_gate'], J['sources'][o['sources'][0]]['url'])
        if 'ONSITE_EQUIPMENT' in run['nodes'] and target == 'ENERGIZATION_ONSITE':
            nd = run['nodes']['ONSITE_EQUIPMENT']
            add('ONSITE_EQUIPMENT', tax['ONSITE_EQUIPMENT']['name'], 'equipment', nd['finish'],
                downstream(run, 'ONSITE_EQUIPMENT', target, scenario), None, None)
        out[pk] = {'milestones': ms, 'permits': []}
    return out


def build_flags(project, J, runs):
    flags = []
    ctx = runs['p50']['ctx']
    for oid, o in J['overlays'].items():
        if o['type'] == 'pending_standards':
            hits = [f for f in o['flags_designs_with'] if (_get(ctx, f) or 0)]
            if hits:
                flags.append({'overlay': oid, 'severity': 'U', 'text': o['summary'], 'design_fields': hits, 'adoption_target': o['adoption_target']})
        if o['type'] == 'route_risk' and runs['p90']['ctx']['_derived']['grandfather_converted_in_p90']:
            flags.append({'overlay': oid, 'severity': 'C', 'text': o['summary']})
        if o['type'] == 'decision_hold':
            held = [n for n in ('LU_LEGISLATIVE', 'LU_SUBSTATION') if runs['p50']['nodes'].get(n, {}).get('holds')]
            if held:
                flags.append({'overlay': oid, 'severity': 'C', 'text': o['summary'], 'status': o['status'], 'applies_to': held})
    pa = J['policy_areas'].get(ctx['parcel'].get('policy_area'))
    if pa:
        flags.append({'policy_area': ctx['parcel']['policy_area'], 'text': pa['note']})
    return flags


def apply_to_v82_inputs(inp: dict, assessment: dict) -> tuple[dict, dict]:
    """Return (v8.2 inputs with permitting gates merged, milestone_schedules for score_one)."""
    out = copy.deepcopy(inp)
    g = assessment['v82_gates']
    for k, v in g['gates'].items():
        out['gates'][k] = v
        out['severity'][k] = g['severity'].get(k)
        out['remediation_months'][k] = g['remediation_months'].get(k, 0)
    ms = export_schedule27(None, assessment)
    return out, ms


def public(assessment):
    """JSON-safe view without internal run state."""
    a = {k: v for k, v in assessment.items() if not k.startswith('_')}
    return json.loads(json.dumps(a, default=lambda x: None if x == INF else str(x)).replace('Infinity', 'null'))
