"""Evidence-first, parcel-level development feasibility screening.

This module intentionally provides NO automatic approvals, legal conclusions, utility-capacity
certifications, or invented site scores. User-supplied evidence is labeled accordingly.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
import json
from typing import Iterable

@dataclass(frozen=True)
class Criterion:
    id: str
    domain: str
    title: str
    critical: bool
    evidence_hint: str
    source_owner: str

CRITERIA = [
    Criterion('p01','Power','Serving utility and service territory confirmed',True,'Utility service map or written correspondence','Utility'),
    Criterion('p02','Power','Deliverable initial import capacity confirmed',True,'Written utility capacity and terms; proximity is insufficient','Utility'),
    Criterion('p03','Power','Grid energization and upgrade milestones established',True,'Executed utility schedule or dated utility estimate','Utility'),
    Criterion('p04','Power','Large-load tariff and curtailment obligations reviewed',True,'Applicable tariff/service agreement and effective date','Utility / counsel'),
    Criterion('p05','Power','Onsite generation and fuel availability evaluated',False,'Resource plan, gas utility capacity, generation layout','Engineering'),
    Criterion('p06','Power','N-1 reliability and backup requirements assessed',False,'Critical-load and electrical redundancy study','Electrical engineer'),
    Criterion('s01','Land & Site','Legal site control and title reviewed',True,'Executed option/deed, title and encumbrance report','Real estate counsel'),
    Criterion('s02','Land & Site','Zoning and land use support intended project',True,'Parcel zoning determination from local authority','Planning authority'),
    Criterion('s03','Land & Site','Buildable area, setbacks and equipment footprint fit',True,'Survey, layout, setbacks and easement plan','Civil engineer'),
    Criterion('s04','Land & Site','Flood, wetlands and drainage constraints assessed',True,'FEMA/wetland screen and project-specific engineering','Environmental consultant'),
    Criterion('s05','Land & Site','Geotechnical conditions and grading reviewed',False,'Geotechnical report and earthworks estimate','Civil engineer'),
    Criterion('s06','Land & Site','Site ingress, road access and heavy-haul routes reviewed',False,'Road/access study and equipment transport plan','Logistics'),
    Criterion('w01','Water & Cooling','Cooling design and peak water demand established',True,'Cooling concept, process loads and design weather','Mechanical engineer'),
    Criterion('w02','Water & Cooling','Water supply or dry-cooling feasibility evidenced',True,'Supplier letter, water rights, or dry-cooling study','Water utility / engineer'),
    Criterion('w03','Water & Cooling','Wastewater, discharge and stormwater pathway reviewed',False,'Sewer/wastewater and stormwater requirements','Environmental consultant'),
    Criterion('w04','Water & Cooling','Heat rejection, acoustic and thermal limits reviewed',False,'Thermal/noise study and planning criteria','Mechanical engineer'),
    Criterion('c01','Connectivity','Diverse fiber routes and carriers confirmed',True,'Carrier letters, diversity map and delivery estimate','Telecom carrier'),
    Criterion('c02','Connectivity','Network latency, resiliency and bandwidth assessed',False,'Customer network specifications and carrier SLA','Network engineer'),
    Criterion('c03','Connectivity','Telecom easements and construction rights identified',False,'ROW plan, recorded easements and permits','Telecom / counsel'),
    Criterion('r01','Permitting & Compliance','Authority having jurisdiction established for parcel',True,'Parcel boundaries and agency confirmation','Land-use counsel'),
    Criterion('r02','Permitting & Compliance','Enacted restrictions or moratoria screened',True,'Official ordinance, effective date, parcel applicability','Land-use counsel'),
    Criterion('r03','Permitting & Compliance','Proposed changes separately tracked',False,'Official meeting agenda and legislative docket','Land-use counsel'),
    Criterion('r04','Permitting & Compliance','State air authorization applicability established',True,'Equipment emissions and applicable agency pathway','Environmental counsel'),
    Criterion('r05','Permitting & Compliance','Building, fire and energy storage requirements mapped',True,'AHJ code edition and agency submittal checklist','AHJ / fire marshal'),
    Criterion('r06','Permitting & Compliance','Environmental and community review obligations mapped',False,'Project-specific agency consult and outreach plan','Environmental counsel'),
    Criterion('f01','Financial & Delivery','Utility upgrade and connection cost estimates supported',True,'Utility cost estimate and commercial terms','Utility / finance'),
    Criterion('f02','Financial & Delivery','Equipment procurement dates and prices evidenced',True,'Current vendor quote, terms and delivery conditions','Procurement'),
    Criterion('f03','Financial & Delivery','Development budget and financing sources assessed',False,'Budget, contingencies and financing plan','Finance'),
    Criterion('f04','Financial & Delivery','Construction and commissioning critical path established',True,'Dependency-linked construction schedule','EPC / PM'),
    Criterion('f05','Financial & Delivery','Tax and incentive terms verified',False,'Official program eligibility and binding letters','Tax / economic development'),
]
DOMAINS = list(dict.fromkeys(c.domain for c in CRITERIA))
STATES = ['Unknown / not assessed','Evidence requested','Evidence received — unverified','Verified — requirement met','Verified — blocked','Not applicable — verified']


def blank_records() -> list[dict]:
    return [{**asdict(c), 'status':STATES[0], 'evidence_reference':'', 'verified_by':'',
             'as_of':'', 'owner':'', 'notes':'', 'target_month':None} for c in CRITERIA]


def evaluate(records: Iterable[dict]) -> dict:
    rows = list(records)
    valid = {c.id for c in CRITERIA}
    if len(rows) != len(CRITERIA) or {r.get('id') for r in rows} != valid:
        raise ValueError('Feasibility records must contain one entry for each catalog criterion')
    critical_blocked = [r for r in rows if r['critical'] and r['status']=='Verified — blocked']
    critical_open = [r for r in rows if r['critical'] and r['status'] not in ('Verified — requirement met','Not applicable — verified','Verified — blocked')]
    verified = [r for r in rows if r['status'] in ('Verified — requirement met','Not applicable — verified')]
    blocked = [r for r in rows if r['status']=='Verified — blocked']
    # A claimed verified result without evidence is still not a valid determination.
    unsupported = [r for r in rows if r['status'].startswith('Verified') or r['status'].startswith('Not applicable')
                   if not r.get('evidence_reference','').strip() or not r.get('verified_by','').strip()]
    supported_blocked = [r for r in critical_blocked if r not in unsupported]
    if supported_blocked:
        result='Documented blocker — redesign or resolve'
    elif critical_blocked or critical_open or unsupported:
        result='Unverified / conditional — additional diligence required'
    else:
        result='All critical screening gates evidenced — further engineering and approval still required'
    by_domain={}
    for domain in DOMAINS:
        subset=[r for r in rows if r['domain']==domain]
        by_domain[domain]={'total':len(subset),'verified_evidenced':sum(r in verified and r not in unsupported for r in subset),
                           'blocked':sum(r in blocked for r in subset), 'critical_open':sum(r in critical_open or r in unsupported for r in subset if r['critical'])}
    return {'determination':result,'criteria_count':len(rows),'verified_with_support':len([r for r in verified if r not in unsupported]),
            'critical_unresolved':len(critical_open),'supported_critical_blockers':len(supported_blocked),
            'evidence_deficiencies':len(unsupported), 'domains':by_domain,
            'blockers':supported_blocked,'next_actions':(critical_blocked+critical_open+unsupported)[:15]}


def export_report(project: dict, rows: list[dict]) -> str:
    return json.dumps({'product':'PowerPath Feasibility','generated_on':date.today().isoformat(),
                       'disclaimer':'Desktop screening only. No approval or utility capacity certification.',
                       'project':project,'assessment':evaluate(rows),'criteria':rows},indent=2,default=str)


def drafting_checklist(project: dict, rows: list[dict]) -> str:
    result=evaluate(rows)
    lines=[f"# Site feasibility diligence — {project.get('name','Project')}", '',
           'PRELIMINARY SCREENING. Not a regulatory opinion, engineering certification or permit application.',
           f"Parcel: {project.get('parcel','Not provided')}", f"Location: {project.get('location','Not provided')}",
           f"Demand: {project.get('peak_mw','Not provided')} MW", '',
           f"## Status: {result['determination']}", '',
           'A status is verified only when primary evidence and a responsible reviewer are recorded.', '']
    for domain in DOMAINS:
        lines.append(f'## {domain}')
        for r in rows:
            if r['domain'] != domain: continue
            lines.extend([f"- [{'CRITICAL' if r['critical'] else 'ADVISORY'}] {r['title']}",
                          f"  - Status: {r['status']}",f"  - Evidence needed: {r['evidence_hint']}",
                          f"  - Evidence ref: {r['evidence_reference'] or 'MISSING'}",
                          f"  - Reviewer: {r['verified_by'] or 'UNASSIGNED'}"])
        lines.append('')
    return '\n'.join(lines)
