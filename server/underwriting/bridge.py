"""Power-to-returns bridge with explainable attribution.

Given an approved case and a set of physical/commercial changes (drivers), the bridge
reruns the frozen engine and splits the change in NPV, levered IRR and minimum DSCR
among the drivers. Attribution uses exact Shapley values over every subset of
drivers, so the parts always add up to the total change regardless of the order the
changes are listed in. Interactions (e.g. a delay that matters more because capex
also rose) are shared evenly between the drivers involved.
"""
from itertools import combinations
from math import factorial

from server.underwriting import drivers as D

MAX_DRIVERS = 7
ATTRIBUTED = ('npvM', 'leveredIRR', 'minDSCR')


def _value(calculate, base_cfg, chosen, cache):
    key = frozenset(chosen)
    if key not in cache:
        cache[key] = D.summarize(calculate('underwrite', D.apply(base_cfg, {k: chosen[k] for k in chosen})))
    return cache[key]


def run(calculate, base_cfg, changes, order=None):
    if not changes:
        raise ValueError('Provide at least one driver')
    if len(changes) > MAX_DRIVERS:
        raise ValueError(f'At most {MAX_DRIVERS} drivers per bridge (2^n engine runs)')
    for k, v in changes.items():
        D.validate(k, v)
    keys = [k for k in D.ORDER if k in changes]
    n, cache = len(keys), {}
    subsets = {}
    for size in range(n + 1):
        for combo in combinations(keys, size):
            subsets[frozenset(combo)] = _value(calculate, base_cfg, {k: changes[k] for k in combo}, cache)
    base, final = subsets[frozenset()], subsets[frozenset(keys)]
    attribution = {m: {} for m in ATTRIBUTED}
    unavailable = {}
    for m in ATTRIBUTED:
        if any(v[m] is None for v in subsets.values()):
            attribution[m] = None
            unavailable[m] = 'At least one combination has no defined value (e.g. IRR undefined when equity is never repaid)'
            continue
        for i in keys:
            others = [k for k in keys if k != i]
            total = 0.0
            for size in range(n):
                weight = factorial(size) * factorial(n - size - 1) / factorial(n)
                for combo in combinations(others, size):
                    s = frozenset(combo)
                    total += weight * (subsets[s | {i}][m] - subsets[s][m])
            attribution[m][i] = total
    isolated = {i: {m: (None if subsets[frozenset([i])][m] is None or base[m] is None else subsets[frozenset([i])][m] - base[m])
                    for m in ATTRIBUTED} for i in keys}
    seq_order = [k for k in (order or keys) if k in changes]
    waterfall, applied, prev = [], {}, base
    for k in seq_order:
        applied[k] = changes[k]
        cur = subsets[frozenset(applied)]
        waterfall.append({'driver': k, 'label': D.CATALOG[k]['label'],
                          **{m: (None if cur[m] is None or prev[m] is None else cur[m] - prev[m]) for m in ATTRIBUTED}})
        prev = cur
    total = {m: (None if base[m] is None or final[m] is None else final[m] - base[m]) for m in ATTRIBUTED}
    residual = {m: (None if attribution[m] is None or total[m] is None else total[m] - sum(attribution[m].values())) for m in ATTRIBUTED}
    return {'base': base, 'final': final, 'total_change': total,
            'drivers': [{'key': k, 'label': D.CATALOG[k]['label'], 'unit': D.CATALOG[k]['unit'], 'value': changes[k],
                         'from': D.current_value(base_cfg, k)} for k in keys],
            'attribution': attribution, 'attribution_unavailable': unavailable, 'reconciliation_residual': residual,
            'isolated_impact': isolated, 'sequential_waterfall': waterfall,
            'explanation': explain(total, attribution, keys),
            'engine_runs': len(cache), 'method': 'Exact Shapley attribution over all driver subsets; parts sum to the total change. '
            'Isolated impacts and the listed-order waterfall are shown for reference and do not reconcile when drivers interact.'}


def explain(total, attribution, keys):
    lines = []
    for m, unit, scale, word in (('leveredIRR', ' pts', 100, 'Levered IRR'), ('npvM', 'M', 1, 'NPV'), ('minDSCR', 'x', 1, 'Minimum DSCR')):
        if total[m] is None or attribution[m] is None:
            continue
        direction = 'fell' if total[m] < 0 else 'rose'
        parts = sorted(((attribution[m][k], k) for k in keys), key=lambda t: -abs(t[0]))
        fmt = (lambda v: f'{abs(v) * scale:.1f}{unit}') if m == 'leveredIRR' else (lambda v: f'${abs(v):,.1f}{unit}') if m == 'npvM' else (lambda v: f'{abs(v):.2f}{unit}')
        detail = ', '.join(f'{fmt(v)} {"from" if (v < 0) == (total[m] < 0) else "offset by"} {D.CATALOG[k]["label"].lower()}' for v, k in parts if abs(v) > 1e-9)
        lines.append(f'{word} {direction} {fmt(total[m])}: {detail}.' if detail else f'{word} unchanged.')
    return lines


def path_drivers(config, path, schedule):
    """Decompose a power path's adjustments into bridge drivers (matches schedule27.apply_to_config)."""
    out = {}
    if int(schedule.get('effective_delay_months') or 0):
        out['energization_delay_months'] = int(schedule['effective_delay_months'])
    if float(path.get('capex_uplift_pct') or 0):
        out['construction_cost_mw'] = float(config.get('constructionCostMW', 7)) * (1 + float(path['capex_uplift_pct']) / 100)
    if float(path.get('energy_uplift_pct') or 0):
        out['power_cost_mwh'] = float(config.get('powerCostMWh', 85)) * (1 + float(path['energy_uplift_pct']) / 100)
    if path.get('power_phases') or (path.get('power_month') is not None and (path.get('capacity_mw') or 0) > 0):
        phases = path.get('power_phases') or [{'month': path['power_month'], 'mw': path['capacity_mw']}]
        out['grid_capacity'] = {'basis': path.get('capacity_basis', 'IT'), 'phases': phases}
    return out
