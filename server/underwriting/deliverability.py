"""Power availability & deliverability engine.

Answers "can this site deliver X MW by month T, and what has to be true?" as a range.
Capacity is classified by how far it has progressed toward real delivery:

    nameplate  → never counted (equipment or line rating, not available to the site)
    headroom   → counted only in the upside case (estimated spare capacity)
    studied    → counted in upside and base (utility study supports it; not contracted)
    contracted → counted in every case (executed agreement; delivery still dated)
    energized  → counted in every case from its energization month

Upside / base / downside use the earliest / likely / latest dates of each source and
of every dependency (network upgrades, permits, long-lead equipment) it waits on.
These are transparent scenario rules, not probabilities; the forecast ledger records
each issued range so outcomes can calibrate it over time.
"""
from server.underwriting import evidence as ev

LABELS = ('nameplate', 'headroom', 'studied', 'contracted', 'energized')
COUNTED = {'upside': {'headroom', 'studied', 'contracted', 'energized'},
           'base': {'studied', 'contracted', 'energized'},
           'downside': {'contracted', 'energized'}}
DATE_FIELD = {'upside': 'earliest', 'base': 'likely', 'downside': 'latest'}
CASES = ('upside', 'base', 'downside')
NON_FIRM = {'onsite_solar', 'wind'}


def _dep_finish(deps, case):
    field = DATE_FIELD[case] + '_months'
    done, visiting = {}, set()

    def finish(dep_id):
        if dep_id in done:
            return done[dep_id]
        if dep_id not in deps:
            raise ValueError(f'Unknown dependency "{dep_id}"')
        if dep_id in visiting:
            raise ValueError(f'Dependency cycle through "{dep_id}"')
        visiting.add(dep_id)
        d = deps[dep_id]
        start = max([d.get('start_month') or 1] + [finish(x)[0] for x in d.get('depends_on', [])])
        if d.get('status') == 'complete':
            result = (d.get('complete_month') or 0, [])
        else:
            chain = max([finish(x) for x in d.get('depends_on', [])] or [(0, [])], key=lambda t: t[0])[1]
            result = (start + int(d[field]), chain + [dep_id])
        visiting.discard(dep_id)
        done[dep_id] = result
        return result
    return finish


def _validate(data):
    deps = {d['id']: d for d in data.get('dependencies', [])}
    if len(deps) != len(data.get('dependencies', [])):
        raise ValueError('Dependency ids must be unique')
    ids = [s['id'] for s in data['sources']]
    if len(set(ids)) != len(ids):
        raise ValueError('Source ids must be unique')
    for d in deps.values():
        if not d.get('status') == 'complete' and not (0 <= d['earliest_months'] <= d['likely_months'] <= d['latest_months']):
            raise ValueError(f'Dependency "{d["id"]}" durations must satisfy earliest ≤ likely ≤ latest')
    for s in data['sources']:
        if s['label'] not in LABELS:
            raise ValueError(f'Source "{s["id"]}" label must be one of {", ".join(LABELS)}')
        if not (1 <= s['earliest_month'] <= s['likely_month'] <= s['latest_month'] <= 600):
            raise ValueError(f'Source "{s["id"]}" months must satisfy 1 ≤ earliest ≤ likely ≤ latest ≤ 600')
        for x in s.get('depends_on', []):
            if x not in deps:
                raise ValueError(f'Source "{s["id"]}" depends on unknown "{x}"')
    return deps


def _case(sources, deps, case, target_mw, target_month):
    finish = _dep_finish(deps, case)
    counted, excluded, warnings = [], [], []
    for s in sources:
        if s['label'] not in COUNTED[case]:
            excluded.append({'id': s['id'], 'reason': f'{s["label"]} capacity is not counted in the {case} case'})
            continue
        own = s[DATE_FIELD[case] + '_month']
        dep_month, chain = max([finish(x) for x in s.get('depends_on', [])] or [(0, [])], key=lambda t: t[0])
        month = max(own, dep_month + 1 if dep_month else 0)
        mw = float(s['mw'])
        study_cap = (s.get('study') or {}).get('max_mw')
        if study_cap is not None and study_cap < mw and case != 'upside':
            warnings.append(f'{s["name"]}: capped at the {study_cap} MW supported by the attached study')
            mw = float(study_cap)
        firm = 0.0 if s.get('kind') in NON_FIRM or s.get('firm') is False else mw
        until = s.get('until_month')
        counted.append({'id': s['id'], 'name': s['name'], 'kind': s.get('kind', 'grid'), 'label': s['label'],
                        'firm_mw': firm, 'month': month, 'until_month': until,
                        'binding': 'dependency' if dep_month + 1 > own and chain else 'source date', 'dependency_chain': chain,
                        'capex_m': s.get('capex_m') or 0})
    months = sorted({c['month'] for c in counted} | {c['until_month'] + 1 for c in counted if c['until_month']})

    def available(m):
        return sum(c['firm_mw'] for c in counted if c['month'] <= m and (not c['until_month'] or m <= c['until_month']))
    phases, reached = [], None
    for m in months:
        phases.append({'month': m, 'mw': available(m)})
        if reached is None and available(m) >= target_mw - 1e-9:
            reached = m
    at_target = available(target_month)
    # Sources whose dates set the time to target (the critical items).
    critical = []
    if reached is not None:
        running = 0.0
        for c in sorted(counted, key=lambda c: c['month']):
            if c['month'] <= reached and (not c['until_month'] or reached <= c['until_month']):
                running += c['firm_mw']
                critical.append(c)
                if running >= target_mw - 1e-9:
                    break
    return {'case': case, 'mw_at_target_month': round(at_target, 6), 'gap_mw_at_target_month': round(max(0.0, target_mw - at_target), 6),
            'target_reached_month': reached, 'months_late': (reached - target_month) if reached and reached > target_month else (0 if reached else None),
            'firm_phases': _cumulative(phases), 'counted_sources': counted, 'excluded_sources': excluded,
            'critical_items': [{'source': c['name'], 'month': c['month'], 'binding': c['binding'], 'dependency_chain': c['dependency_chain']} for c in critical],
            'power_capex_m': round(sum(c['capex_m'] for c in counted), 6), 'warnings': warnings}


def _cumulative(phases):
    """Engine tranches must never decrease; report temporary-source roll-offs separately."""
    out, peak = [], 0.0
    for p in phases:
        if p['mw'] > peak:
            peak = p['mw']
            out.append({'month': p['month'], 'mw': round(peak, 6)})
    return out


def _must_be_true(base, deps, target_mw, target_month):
    items = []
    for c in base['counted_sources']:
        if c['label'] != 'energized':
            items.append(f'{c["name"]}: {c["firm_mw"]:g} MW currently "{c["label"]}" must be energized by month {c["month"]}.')
        for d in c['dependency_chain']:
            items.append(f'{deps[d]["name"]} must complete on the likely schedule (feeds {c["name"]}).')
    if base['gap_mw_at_target_month'] > 0:
        items.append(f'{base["gap_mw_at_target_month"]:g} MW more firm capacity is needed by month {target_month} '
                     f'beyond studied and contracted sources (headroom, bridge or dedicated generation).')
    return list(dict.fromkeys(items))


def assess(data, pid=None, con=None):
    deps = _validate(data)
    target_mw, target_month = float(data['target_mw']), int(data['target_month'])
    configurations = data.get('configurations') or []
    sources = {s['id']: s for s in data['sources']}
    if not configurations:
        grid = [s['id'] for s in data['sources'] if s.get('kind', 'grid') == 'grid']
        configurations = [{'name': 'All sources', 'source_ids': list(sources)}]
        if grid and len(grid) < len(sources):
            configurations.append({'name': 'Utility service only', 'source_ids': grid})
    results = []
    for conf in configurations:
        unknown = [x for x in conf['source_ids'] if x not in sources]
        if unknown:
            raise ValueError(f'Configuration "{conf["name"]}" names unknown sources {unknown}')
        chosen = [sources[x] for x in conf['source_ids']]
        cases = {c: _case(chosen, deps, c, target_mw, target_month) for c in CASES}
        base = cases['base']
        evidence_scores = []
        for s in chosen:
            row = ev.evidence_row(con, pid, s.get('evidence_id')) if con is not None else None
            conf_s = ev.confidence({'verification': s['label'], 'evidence_id': s.get('evidence_id'), 'source_date': s.get('source_date')}, row)
            evidence_scores.append((s, conf_s))
        firm_total = sum(float(s['mw']) for s, _ in evidence_scores if s.get('kind') not in NON_FIRM) or 1
        quality = round(sum(float(s['mw']) * c['score'] for s, c in evidence_scores if s.get('kind') not in NON_FIRM) / firm_total, 3)
        reach = {c: cases[c]['target_reached_month'] for c in CASES}
        mw = {c: cases[c]['mw_at_target_month'] for c in CASES}
        answer = (f'{conf["name"]}: by month {target_month}, {mw["downside"]:g}–{mw["upside"]:g} MW firm (base {mw["base"]:g}) '
                  f'of the {target_mw:g} MW target. Target reached '
                  + ', '.join(f'{c} month {reach[c]}' if reach[c] else f'{c} not within modeled sources' for c in CASES) + '.')
        results.append({'name': conf['name'], 'source_ids': conf['source_ids'], 'answer': answer,
                        'deliverable_mw_at_target': {'low': mw['downside'], 'base': mw['base'], 'high': mw['upside']},
                        'time_to_target_month': {'low': reach['upside'], 'base': reach['base'], 'high': reach['downside']},
                        'meets_target_in': [c for c in CASES if reach[c] is not None and reach[c] <= target_month],
                        'evidence_quality': {'score': quality, 'label': 'high' if quality >= 0.75 else 'medium' if quality >= 0.45 else 'low',
                                             'by_source': [{'id': s['id'], 'name': s['name'], 'label': s['label'], **{k: c[k] for k in ('score', 'basis')}} for s, c in evidence_scores]},
                        'what_must_be_true': _must_be_true(base, deps, target_mw, target_month),
                        'cases': cases})
    return {'target_mw': target_mw, 'target_month': target_month, 'basis': data.get('basis', 'gross'),
            'configurations': results, 'method_version': 'deliverability-1',
            'rules': {'counted_labels': {k: sorted(v) for k, v in COUNTED.items()}, 'dates': DATE_FIELD,
                      'notes': ['Nameplate ratings are never counted as deliverable capacity.',
                                'Non-firm sources (solar, wind) add zero firm MW.',
                                'A study-supported maximum caps a source in base and downside cases.',
                                'Ranges are scenario bounds, not probability intervals; the ledger calibrates them over time.',
                                'External power-flow or utility study results are inputs; PowerPath does not run network studies.']}}


def bridge_drivers(assessment, configuration, case):
    """Turn one configuration × case into returns-bridge drivers."""
    conf = next((c for c in assessment['configurations'] if c['name'] == configuration), None)
    if not conf:
        raise ValueError(f'Configuration "{configuration}" not in assessment')
    if case not in CASES:
        raise ValueError('Case must be upside, base or downside')
    data = conf['cases'][case]
    drivers = {}
    if data['firm_phases']:
        drivers['grid_capacity'] = {'basis': assessment.get('basis', 'gross'), 'phases': data['firm_phases']}
    else:
        drivers['grid_capacity'] = {'basis': 'gross', 'phases': [{'month': 1, 'mw': 0}]}
    if data['power_capex_m']:
        drivers['power_capex_m'] = data['power_capex_m']
    return drivers
