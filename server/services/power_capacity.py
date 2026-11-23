"""Translate cumulative delivery assumptions to the unchanged engine's incremental IT tranches."""
import copy
import math


def tranches(phases, pue=1.3, basis='IT'):
    if basis not in ('IT', 'gross') or not math.isfinite(pue) or pue < 1:
        raise ValueError('Capacity basis must be IT/gross and PUE must be at least 1')
    out, previous, last = [], 0.0, 0
    for phase in phases:
        month, mw = phase['month'], float(phase['mw'])
        if isinstance(month, bool) or int(month) != month or month <= last or month > 600:
            raise ValueError('Phases require increasing integer project months in 1–600')
        if not math.isfinite(mw) or mw < previous or mw > 100000:
            raise ValueError('Phase MW must be finite, nonnegative and cumulative (never decreasing)')
        increment = (mw-previous)/(pue if basis == 'gross' else 1)
        if increment > 0:
            if increment < .001:
                raise ValueError('Capacity increments must be at least 0.001 IT MW')
            out.append({'month': int(month), 'mw': increment, 'basis': 'IT'})
        previous, last = mw, month
    return out


def constrain(config, phases, basis='IT'):
    out = copy.deepcopy(config)
    out['powerTranches'] = tranches(phases, float(out.get('pue', 1.3)), basis)
    if not out['powerTranches']:
        # Empty means unlimited supply in the frozen engine. Explicit zero supply
        # uses a positive tranche strictly outside its modeled/forward horizon.
        out['powerTranches'] = [{'month': int(out.get('months',120))+100, 'mw': .001, 'basis':'IT'}]
    out['powerCapacityAssumptions'] = {'phases': phases, 'basis': basis,
        'semantics':'Cumulative capacity; shared IT tranches after PUE conversion. Building construction and lease gates still apply.'}
    return out


def target_it(config):
    return sum(float(b['itMW'])/(float(config.get('pue',1.3)) if b.get('capacityBasis', config.get('capacityBasis','IT'))=='gross' else 1) for b in config['buildings'])


def period_capacity(config, rows):
    target = target_it(config)
    result=[]
    for row in rows:
        m=row['month']
        available=sum(t['mw']/(config.get('pue',1.3) if t.get('basis')=='gross' else 1) for t in config.get('powerTranches',[]) if t['month']+config.get('delayMonths',0)<=m)
        result.append({'month':m,'available_it_mw':available,'operating_it_mw':row['onlineMW'],
                       'unmet_target_it_mw':max(0,target-available), 'not_operating_it_mw':max(0,target-row['onlineMW'])})
    return result
