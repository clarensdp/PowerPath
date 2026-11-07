"""v8.2 fixture-backed scoring wired through the existing schedule27 implementation.

SCREENING ONLY. The v8.2 workbook uses independent parallel gate delays. This adapter
constructs one independent schedule milestone per applicable gate for fixture parity.
For live use, callers may pass predecessor dependencies or fully specified project
milestones, which schedule27 evaluates instead; no new COD arithmetic is introduced.
No lender, utility or delivery verification is asserted.
"""
from __future__ import annotations
import copy
import json
from functools import lru_cache
from pathlib import Path
from server import schedule27
from .model_definitions import GATE_SHORT, METRICS, PATH_KEYS, PATH_NAMES
from .reference_model import score_site

BASE=Path(__file__).resolve().parent
VALID_MODES=('default','inference','discount','dollar')

@lru_cache(maxsize=1)
def _config():
    return json.loads((BASE/'params.json').read_text())


def parameters(mode='default'):
    if mode not in VALID_MODES: raise ValueError('Unknown mode: '+str(mode))
    c=_config()
    w=c['profiles']['inference' if mode=='inference' else 'training']
    z=sum(w.values())
    return {'pw':{k:float(v)/z for k,v in w.items()},
            'appl':{int(k):v for k,v in c['appl'].items()},
            'metrics':c['metrics'],'cool':c['cool'],'sev':c['sev'],
            'phase_w':c['phase_w'],'maxR':c['maxR'],'share_conf':c['share_conf'],
            'conf_mode':'Discount' if mode=='discount' else 'Spread',
            'time_mode':'Dollar' if mode=='dollar' else 'Breakpoints',
            'rate':c['rate'],'horizon':c['horizon'],'value_mw_month':c['value_mw_month']}


def _validate(inp):
    req=('raw','gates','severity','remediation_months','remediation_cost_musd','political_risk','confidence')
    for k in req:
        if k not in inp: raise ValueError('Missing input group: '+k)
    if float(inp['raw'].get('target') or 0)<=0: raise ValueError('Target IT MW must be positive')
    for g in GATE_SHORT:
        st=inp['gates'].get(g)
        if st not in ('Y','C','N','U','NA',''):
            raise ValueError('Invalid gate state '+repr(g)+': '+repr(st))
    for pk in PATH_KEYS:
        first=inp['raw'].get(pk+'_first')
        if first is not None:
            if float(first)<0: raise ValueError('Negative first-power month: '+pk)
            if inp['raw'].get(pk+'_cls') not in ('Verified viable','Provisionally viable','Not viable'):
                raise ValueError('Invalid path class: '+pk)
            full=inp['raw'].get(pk+'_full')
            if full is not None and float(full)<float(first): raise ValueError('Full-load month before first power: '+pk)
            mw=inp['raw'].get(pk+'_mw1')
            if mw is None or float(mw)<=0 or float(mw)>float(inp['raw']['target']):
                raise ValueError('First-power MW must be within (0, target] for '+pk)
    for k,v in inp['confidence'].items():
        if v is None: raise ValueError('Missing confidence: '+k)
        if not (1<=float(v)<=5): raise ValueError('Confidence outside 1-5: '+k)


def _schedule_one(pk,raw,inp,P,dependencies=None,actual_milestones=None,actual_permits=None):
    first=raw.get(pk+'_first')
    if first is None: return None
    path={'id':'v82-'+pk,'power_month':float(first),'delay_months':0}
    if actual_milestones is not None:
        milestones=actual_milestones
        permits=actual_permits or []
        # An externally supplied schedule must explicitly represent each applicable
        # remediation gate; otherwise the date would silently drop an open delay.
        present={m.get('id') for m in milestones}|{m.get('gate_key') for m in milestones}
        for i,g in enumerate(GATE_SHORT):
            if P['appl'][i][pk] and inp['gates'][g] in ('C','U','') and float(inp['remediation_months'].get(g) or 0)>0:
                if g not in present:
                    raise ValueError('Missing milestone for applicable remediation gate: '+g)
    else:
        milestones=[]
        for i,key in enumerate(GATE_SHORT):
            if not P['appl'][i][pk] or inp['gates'][key] not in ('C','U',''): continue
            d=float(inp['remediation_months'].get(key) or 0)
            if d<0: raise ValueError('Negative gate delay for '+key)
            if d==0:continue
            pred=(dependencies or {}).get(key)
            if pred and pred not in GATE_SHORT:raise ValueError('Unknown predecessor gate: '+pred)
            milestones.append({'id':key,'title':key,'category':'permitting','status':'not_started',
                               'planned_month':float(first),'delay_months':d,'float_months':0,
                               'predecessor_id':pred,'permit_id':None})
        ids={m['id'] for m in milestones}
        for m in milestones:
            if m['predecessor_id'] and m['predecessor_id'] not in ids:
                raise ValueError('Dependency references an inactive gate milestone: '+m['predecessor_id'])
        permits=[]
    sched=schedule27.compute(path,milestones,permits)
    if sched['evidence_conflicts']:
        raise ValueError('Conflicting schedule evidence: '+str(sched['evidence_conflicts']))
    return sched


def score_one(name,inp,mode='default',dependencies=None,milestone_schedules=None):
    """Score one project. Raw input is the v8.2 fixture schema; no workbook engine runtime.

    milestone_schedules: optional {path_key: {'milestones': [...], 'permits': [...]}}
    Dependencies and gate schedules are mutually exclusive sources, avoiding delay double count.
    """
    _validate(inp)
    P=parameters(mode)
    raw=copy.deepcopy(inp['raw'])
    schedules={}
    for pk in PATH_KEYS:
        ms=(milestone_schedules or {}).get(pk)
        s=_schedule_one(pk,raw,inp,P,(dependencies or {}).get(pk),
                        (ms or {}).get('milestones') if ms is not None else None,
                        (ms or {}).get('permits') if ms is not None else None)
        if s is None:continue
        schedules[pk]=s
        shift=s['effective_delay_months']
        raw[pk+'_first']=float(raw[pk+'_first'])+shift
        full=raw.get(pk+'_full')
        if full is not None:raw[pk+'_full']=float(full)+shift
    # schedule27 has already incorporated gate delay, so never add it again in reference scoring.
    si={'name':name,'raw':raw,'gates':[inp['gates'][g] for g in GATE_SHORT],
        'sev':[inp['severity'].get(g) for g in GATE_SHORT],
        'delay':[0]*len(GATE_SHORT),
        'cost':[inp['remediation_cost_musd'].get(g) or 0 for g in GATE_SHORT],
        'political':inp['political_risk'],
        'confidence':[inp['confidence'][m[1]] for m in METRICS]}
    r=score_site(si,P)
    # 'NA' is allowed only when the gate is irrelevant to the selected power path.
    # Otherwise an omitted regulatory gate could silently produce a false Go decision.
    chosen={label:key for key,label in zip(PATH_KEYS,PATH_NAMES)}.get(r['selected'])
    if chosen:
        for i,g in enumerate(GATE_SHORT):
            if P['appl'][i][chosen] and inp['gates'][g]=='NA':
                raise ValueError(f'Gate {g} cannot be NA for selected {r["selected"]} path')
    r['schedule_versions']={pk:s['schedule_version'] for pk,s in schedules.items()}
    r['schedule_method']=schedule27.METHOD_VERSION
    r['model_version']='workbook_v8_2'
    r['mode']=mode
    r['evidence_label']='SCREENING / UNVERIFIED - source claims are not independently established'
    # Always distinguish an available-but-provisional case from a firm power commitment.
    r['path_class_asserted_verified']=r['selected_class']=='Verified viable'
    r['utility_verified']=False
    if r['selected_class']=='Provisionally viable':r['flags']=['PROVISIONAL POWER / DO NOT ASSERT DELIVERABILITY']
    else:r['flags']=[]
    return r


def score_batch(inputs,mode='default'):
    """Sort tier first. A score cannot move a provisional option above a verified site."""
    results={name:score_one(name,inp,mode) for name,inp in inputs.items()}
    for r in results.values():
        r['rank_in_tier']=1+sum(o['tier_num']==r['tier_num'] and o['rank_key']>r['rank_key'] for o in results.values())
    ordered=sorted(results.values(),key=lambda r:(r['tier_num'],-r['rank_key'],r['name']))
    for pos,r in enumerate(ordered,1):r['screening_position']=pos
    return results
