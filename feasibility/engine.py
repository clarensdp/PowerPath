"""Pure, workbook-derived v1 scoring functions. No remote data and no finance assertions."""
import math
from collections import defaultdict

def utility(value, breakpoints, direction):
    if value is None: raise ValueError('Missing metric input: provide sourced value')
    s=1 if direction.lower()=='lower' else -1
    b=list(map(float,breakpoints));x=float(value)
    for i,level in enumerate((100.,70.,30.,0.)):
        if s*x <= s*b[i]:
            if i==0:return level
            y0=(100.,70.,30.)[i-1]; y1=level
            return y0+(y1-y0)*(x-b[i-1])/(b[i]-b[i-1])
    return 0.

def gate_multiplier(gates, conditional=0.7):
    if not gates: raise ValueError('Gate evidence required; empty is not unconditional approval')
    if any(v not in ('Y','C') for v in gates.values()):return 0.
    return conditional**sum(v=='C' for v in gates.values())

def totals(pillars, weights):
    if set(weights)!=set(pillars):raise ValueError('Pillar/weight mismatch')
    z=sum(weights.values());assert z>0
    add=sum(weights[k]*pillars[k] for k in weights)/z
    geo=math.exp(sum((weights[k]/z)*math.log(max(1.,pillars[k])) for k in weights))
    return add,geo

def score_from_model_values(values, metrics, params, profile='training', cooling='Evaporative', gate_mult=1, political=1, uncertainty=0, mode='spread'):
    by_pillar=defaultdict(list); metric_scores={}
    for metric in metrics:
        name=metric['name'];value=values.get(name)
        if value is None:raise ValueError('Missing input: '+name)
        val=utility(value,metric['breakpoints'],metric['direction']);metric_scores[name]=val
        weight=metric['weight_in_pillar']
        if metric['pillar']=='Cooling & water':weight=params['cooling_weights'][cooling].get(name,weight)
        by_pillar[metric['pillar']].append((val,weight))
    pillars={k:max(1.,sum(v*w for v,w in arr)/sum(w for _,w in arr)) for k,arr in by_pillar.items()}
    add,geo=totals(pillars,params['profiles'][profile])
    r=params['risk']['max_discount']*params['risk']['share_political']*(political-1)/4
    if mode=='discount':r+=params['risk']['max_discount']*params['risk']['share_confidence']*uncertainty
    return {'metrics':metric_scores,'pillars':pillars,'additive':add,'geometric':geo,'risk_discount':r,'final_additive':gate_mult*add*(1-r),'final_geometric':gate_mult*geo*(1-r)}
