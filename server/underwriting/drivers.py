"""Catalog of underwriting assumptions that map onto the frozen engine's inputs.

The same catalog drives evidence exposure (one assumption at its downside) and the
returns bridge (several assumptions changed together). Each driver is a pure
function of (config, value) -> config, applied in a fixed canonical order so a
given set of changes always produces the same engine input.
"""
import copy
import math

from server.services.power_capacity import constrain


def _num(value, lo, hi, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lo <= value <= hi:
        raise ValueError(f'{label} must be a number between {lo} and {hi}')
    return float(value)


def _set(field, lo, hi, label):
    def apply(cfg, value):
        cfg[field] = _num(value, lo, hi, label)
        return cfg
    return apply


def _delay(cfg, value):
    cfg['delayMonths'] = int(cfg.get('delayMonths', 0)) + int(_num(value, 0, 240, 'Energization delay'))
    return cfg


def _lease_delay(cfg, value):
    months = int(_num(value, 0, 240, 'Lease start delay'))
    for b in cfg['buildings']:
        b['leaseMonth'] = int(b['leaseMonth']) + months
    return cfg


def _capacity(cfg, value):
    if not isinstance(value, dict) or not isinstance(value.get('phases'), list) or not value['phases']:
        raise ValueError('Grid capacity needs {"basis": "IT"|"gross", "phases": [{"month", "mw"}, ...]}')
    basis = value.get('basis', 'gross')
    phases = [{'month': int(_num(p.get('month'), 1, 600, 'Phase month')), 'mw': _num(p.get('mw'), 0, 100000, 'Phase MW')}
              for p in value['phases']]
    return constrain(cfg, phases, basis)


def _power_capex(cfg, value):
    capex = _num(value, 0, 100000, 'Power capex (USD M)')
    if capex and (cfg.get('tenantCapexPct', 0) or any(b.get('tenantCapexPct', 0) for b in cfg['buildings'])):
        raise ValueError('Power capex sensitivity assumes owner funding; set tenant capital contributions to zero')
    mw = sum(float(b['itMW']) for b in cfg['buildings'])
    # Spread through the engine's own construction spend schedule (same convention as power_dispatch).
    cfg['constructionCostMW'] = float(cfg.get('constructionCostMW', 7)) + capex / (mw * (1 + float(cfg.get('overrunPct', 0)) / 100))
    return cfg


# Order matters only for determinism: "set" drivers before additive ones.
CATALOG = {
    'power_cost_mwh': {'label': 'Delivered power cost', 'unit': 'USD/MWh', 'apply': _set('powerCostMWh', 0, 10000, 'Power cost'), 'field': 'powerCostMWh'},
    'construction_cost_mw': {'label': 'Construction cost', 'unit': 'USD M per IT MW', 'apply': _set('constructionCostMW', 0, 1000, 'Construction cost'), 'field': 'constructionCostMW'},
    'rent_per_kw_month': {'label': 'Rent', 'unit': 'USD per kW-month', 'apply': _set('rentPerKwMonth', 0, 10000, 'Rent'), 'field': 'rentPerKwMonth'},
    'pue': {'label': 'PUE', 'unit': 'ratio', 'apply': _set('pue', 1, 3, 'PUE'), 'field': 'pue'},
    'interest_rate_pct': {'label': 'Senior debt rate', 'unit': '%', 'apply': _set('rate', 0, 50, 'Interest rate'), 'field': 'rate'},
    'grid_capacity': {'label': 'Grid capacity delivery', 'unit': 'MW phases', 'apply': _capacity, 'field': 'powerTranches'},
    'power_capex_m': {'label': 'Power infrastructure / bridge generation capex', 'unit': 'USD M', 'apply': _power_capex, 'field': 'constructionCostMW'},
    'energization_delay_months': {'label': 'Energization delay', 'unit': 'months', 'apply': _delay, 'field': 'delayMonths'},
    'lease_start_delay_months': {'label': 'Lease commencement delay', 'unit': 'months', 'apply': _lease_delay, 'field': 'buildings[].leaseMonth'},
}
ORDER = list(CATALOG)


def validate(key, value):
    if key not in CATALOG:
        raise ValueError(f'Unknown underwriting assumption "{key}". Supported: {", ".join(ORDER)}')
    CATALOG[key]['apply'](copy.deepcopy(_probe()), value)


def _probe():
    return {'buildings': [{'itMW': 50, 'leaseMonth': 19, 'powerMonth': 19}], 'pue': 1.3, 'months': 120}


def apply(config, assignments):
    """assignments: {key: value}. Returns a new config; input is not mutated."""
    cfg = copy.deepcopy(config)
    for key in ORDER:
        if key in assignments:
            cfg = CATALOG[key]['apply'](cfg, assignments[key])
    return cfg


def current_value(config, key):
    """What the saved scenario already assumes for a key (for 'from → to' displays)."""
    spec = CATALOG[key]
    if key in ('energization_delay_months', 'lease_start_delay_months', 'power_capex_m'):
        return 0
    if key == 'grid_capacity':
        return {'basis': 'IT', 'phases': config.get('powerTranches') or []} if config.get('powerTranches') else None
    return config.get(spec['field'])


METRICS = ('npvM', 'leveredIRR', 'minDSCR', 'breachMonths', 'liquidityBreachMonths')


def summarize(result):
    s = result['summary']
    return {m: s.get(m) for m in METRICS}
