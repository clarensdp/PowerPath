"""v30.3 read-only screening financial bridge for v8.2 power-path comparisons.

Builds assumption-labelled configurations for the *existing* frozen v27.1
underwriter. No separate NPV/IRR/DSCR math. Screening-only: power and leases
are unverified; not a credit recommendation or contract valuation.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from .integration import score_one
from .model_definitions import PATH_KEYS

PATH_NAMES = {'grid': 'Grid', 'btm': 'BTM', 'hyb': 'Hybrid', 'flex': 'Flexible'}


def canonical_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def positive_finite(x, label):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0:
        raise ValueError(label + ' must be positive and finite')
    return float(x)


def candidate_for(name, inputs, mode, path_key, gate_dependencies=None, milestone_schedules=None):
    if path_key not in PATH_KEYS:
        raise ValueError('Unknown path key')
    raw = inputs['raw']
    if raw.get(path_key + '_first') is None or raw.get(path_key + '_cls') == 'Not viable':
        return None
    # Do not mutate the underlying source or manufacture a verified path. This is
    # an explicit counterfactual screening choice for one existing candidate.
    candidate = copy.deepcopy(inputs)
    for pk in PATH_KEYS:
        if pk != path_key and candidate['raw'].get(pk + '_first') is not None:
            candidate['raw'][pk + '_cls'] = 'Not viable'
    result = score_one(name, candidate, mode, gate_dependencies, milestone_schedules)
    if result['selected'] != PATH_NAMES[path_key] or result['decision'] == 'No-go':
        return None
    result['target_it_mw'] = float(inputs['raw']['target'])
    return result


def binding_building_power_dates(base, first_power_month):
    """v30.3.1: buildings whose own scenario powerMonth/leaseMonth is later than both construction
    readiness and the path's first power. Those dates already embed a power assumption, so they
    cap any benefit from a faster path; the comparison becomes max(scenario date, path date)."""
    out = []
    for b in base.get('buildings') or []:
        ready = int(b['constructionStart']) + int(b['constructionMonths'])
        own = max(int(b.get('powerMonth', 1)), int(b.get('leaseMonth', 1)))
        if own > max(ready, int(first_power_month)):
            out.append({'building': b.get('name'), 'construction_ready_month': ready,
                        'scenario_power_or_lease_month': own})
    return out


def map_path_to_config(base, score, *, curtailment_allocation='tenant_or_compute_operator', acknowledge_contract_assumption=False,
                       acknowledge_tenant_capex_share=False):
    """Map first/full MW tranches and selected-path costs into v27.1 inputs.

    Extra capex is distributed using the existing constructionCostMW parameter;
    this is a *screening allocation* until a contract-level spending schedule is
    implemented. Curtailment is NOT automatically the landlord's rent loss.
    """
    if base.get('engineVersion') != '27.1.0':
        raise ValueError('Financial bridge requires the versioned 27.1.0 underwriter')
    if base.get('powerPathLink') or base.get('feasibilityFinancialBridge'):
        raise ValueError('Use an original, unlinked underwriting scenario to prevent double application')
    if float(base.get('delayMonths', 0)) != 0:
        raise ValueError('Original scenario delayMonths must be zero; supply schedule dates once through v8.2 tranches')
    if base.get('powerTranches'):
        raise ValueError('Original scenario already contains powerTranches; reconcile its ramp before adding v8.2 tranches')
    if base.get('capacityBasis', 'IT') != 'IT':
        raise ValueError('Financial bridge currently requires IT capacity basis')
    bs = copy.deepcopy(base.get('buildings') or [])
    if not bs:
        raise ValueError('Underwriting scenario must include physical buildings')
    if any(b.get('capacityBasis', 'IT') != 'IT' for b in bs):
        raise ValueError('Mixed gross/IT building capacity basis not supported by this bridge')
    target = sum(positive_finite(b.get('itMW'), 'building IT MW') for b in bs)
    expected_target = positive_finite(score.get('target_it_mw'), 'feasibility target IT MW')
    if abs(target - expected_target)>1e-6:
        raise ValueError('Underwriting building IT MW must exactly equal feasibility target IT MW')
    first = positive_finite(score.get('first_power'), 'first-power month')
    full = positive_finite(score.get('full_load'), 'full-load month')
    mw_first = positive_finite(score.get('mw_first'), 'first-power MW')
    if first != int(first) or full != int(full):
        raise ValueError('v27.1 underwriter requires integer energization months')
    if mw_first > target + 1e-8:
        raise ValueError('first-power MW exceeds the scenario building capacity')
    if full < first:
        raise ValueError('Invalid first/full load sequence')
    if int(full) == int(first) and abs(mw_first-target)>1e-8:
        raise ValueError('Full-load month equals first-power month, but first MW is less than target')
    scenario = copy.deepcopy(base)
    # The building construction-readiness and lease eligibility milestones remain
    # untouched. Real rent begins when building AND power are ready, not at an
    # automatically inferred contract date.
    scenario['powerTranches'] = [{'month': int(first), 'mw': mw_first, 'basis': 'IT'}]
    if target-mw_first > 1e-8:
        scenario['powerTranches'].append({'month': int(full), 'mw': target-mw_first, 'basis': 'IT'})
    extra = float(score.get('total_extra_capex') or 0)
    if extra < 0 or not math.isfinite(extra):
        raise ValueError('Invalid selected-path capex')
    # v30.3.1: v27.1 applies tenantCapexPct to all construction cost, so path capex added through
    # constructionCostMW would be part-funded by the tenant without any contract saying so.
    tenant_pcts = [float(scenario.get('tenantCapexPct', 0) or 0)] + [float(b.get('tenantCapexPct', 0) or 0) for b in bs if b.get('tenantCapexPct') is not None]
    if extra > 0 and any(p > 0 for p in tenant_pcts) and acknowledge_tenant_capex_share is not True:
        raise ValueError('Scenario has tenantCapexPct > 0: path capex would be part-funded by the tenant. '
                         'Set tenantCapexPct to 0 or explicitly acknowledge the tenant share of power-path capex')
    if float(scenario.get('constructionCostMW', 0)) <= 0:
        raise ValueError('Existing constructionCostMW missing or nonpositive')
    overrun_factor = 1 + float(scenario.get('overrunPct', 0)) / 100
    if not math.isfinite(overrun_factor) or overrun_factor <= 0:
        raise ValueError('Invalid construction overrun factor')
    # Because v27.1 applies overrunPct to the entire per-MW cost, divide the
    # *fixed* v8.2 incremental capex by that factor to add it exactly once.
    scenario['constructionCostMW'] = float(scenario['constructionCostMW']) + extra/(target*overrun_factor)
    loss_yr = float(score.get('curtailment_loss') or 0)
    if loss_yr < 0 or not math.isfinite(loss_yr):
        raise ValueError('Invalid curtailment impact')
    if curtailment_allocation not in ('tenant_or_compute_operator', 'owner_contractual_revenue'):
        raise ValueError('Unknown curtailment allocation')
    modeled_loss = 0.0
    if loss_yr > 0 and curtailment_allocation == 'owner_contractual_revenue':
        if acknowledge_contract_assumption is not True:
            raise ValueError('Explicit acknowledgement required to model curtailment as lost landlord rent')
        if any((b.get('rentInputMode', 'starting') != 'starting') or b.get('contractedRentM') is not None or b.get('annualRentM') is not None for b in bs):
            raise ValueError('Contract rent/annual schedule present: explicit lease allocation is required before modeling owner loss')
        global_rent = positive_finite(base.get('rentPerKwMonth'), 'starting rent rate')
        for b in bs:
            r = positive_finite(b.get('rentPerKwMonth', global_rent), 'building rent rate')
            bmw = float(b['itMW'])
            annual_deduction = loss_yr * bmw / target
            term = int(b.get('leaseTermMonths', 180))
            esc = float(b.get('rentEscalatorPct', 2.5)) / 100
            annual = [bmw * 1000 * r * 12 / 1e6 * (1 + esc) ** y - annual_deduction
                      for y in range(math.ceil(term / 12))]
            if any(v < 0 for v in annual):
                raise ValueError('Curtailment loss exceeds modeled annual contract rent')
            b['rentInputMode'] = 'schedule'
            b['annualRentM'] = annual
        modeled_loss = loss_yr
    scenario['buildings'] = bs
    # Metadata is kept OUTSIDE engine inputs to preserve the frozen model's input
    # contract and avoid confusing audit evidence with transaction terms.
    audit = {
        'power_path': score['selected'], 'selected_class': score['selected_class'],
        'first_power_month': int(first), 'full_load_month': int(full), 'first_power_mw': mw_first,
        'total_it_mw': target, 'extra_capex_musd': extra,
        'capex_treatment': 'PROXY: fixed incremental $M applied once after overrun; allocated through existing $M/IT-MW building construction windows',
        'curtailment_annual_compute_value_musd': loss_yr,
        'curtailment_allocation': curtailment_allocation,
        'curtailment_loss_in_owner_financials_musd_at_full_occupancy': modeled_loss,
        'curtailment_treatment': ('Illustrative rent-schedule haircut, dependent on actual powered/leased MW and contract assumptions'
                                  if modeled_loss else 'Memo only: not asserted to be a landlord cost or rent loss'),
        'building_readiness_unchanged': True,
        'lease_rent_commencement': 'max(construction readiness, building power/lease date, allocated power tranche)',
        'schedule_method': score.get('schedule_method'),
        'schedule_versions': score.get('schedule_versions'),
        'source_evidence': 'USER-SUPPLIED SCREENING ASSUMPTIONS; NOT UTILITY OR CONTRACT VERIFIED',
        'tenant_capex_share_of_path_capex_pct': max(tenant_pcts) if extra > 0 else 0.0,
        'binding_building_power_dates': binding_building_power_dates(base, first),
    }
    return scenario, audit


def summary_of(result, target_it_mw=None):
    s = result['summary']
    rows = result['rows']
    first = next((r['month'] for r in rows if (r.get('leaseRevenue') or 0)>1e-9), None)
    # v30.3.1 carry metrics, read from the frozen engine's monthly rows (no new financial math).
    # Minimum DSCR collapses to 0 whenever cash debt service precedes rent, so it cannot rank
    # paths; the pre-rent carry and the stabilized DSCR are the comparable measures.
    target = target_it_mw if target_it_mw is not None else max((r.get('availableMW') or 0 for r in rows), default=0)
    full_rent = next((r['month'] for r in rows if (r.get('onlineMW') or 0) >= target - 1e-6 and target > 0), None)
    ds = lambda r: r.get('debtService') or 0
    pre_rent_ds = sum(ds(r) for r in rows if first is None or r['month'] < first)
    uncovered = sum(max(0.0, ds(r) - (r.get('cfads') or 0)) for r in rows)
    stab = [r['dscr'] for r in rows if full_rent is not None and r['month'] >= full_rent and ds(r) > 1e-9 and r.get('dscr') is not None]
    pre_rent_sponsor = sum((r.get('sponsorContribution') or 0) for r in rows
                           if (first is None or r['month'] < first) and (r.get('capex') or 0) <= 1e-9)
    return {
        'full_rent_month': full_rent,
        'pre_rent_debt_service_musd': pre_rent_ds,
        'months_debt_service_before_rent': sum(1 for r in rows if ds(r) > 1e-9 and (first is None or r['month'] < first)),
        'uncovered_debt_service_musd': uncovered,
        'pre_rent_sponsor_carry_musd': pre_rent_sponsor,
        'stabilized_min_dscr': min(stab) if stab else None,
        'peak_debt_musd': s.get('peakDebtM'),
        'sponsor_remaining_musd': s.get('sponsorRemainingM'),
        'npv_musd': s.get('npvM'), 'levered_irr': s.get('leveredIRR'),
        'minimum_dscr': s.get('minDSCR'), 'equity_multiple': s.get('equityMultiple'),
        'sponsor_equity_musd': s.get('equityInvestedM'),
        'min_cash_musd': min((r.get('cash') or 0 for r in rows), default=None),
        'first_rent_month': first,
        'maximum_online_mw': max((r.get('onlineMW') or 0 for r in rows), default=0),
        'maximum_available_mw': max((r.get('availableMW') or 0 for r in rows), default=0),
        'cumulative_lease_revenue_musd': sum(r.get('leaseRevenue') or 0 for r in rows),
        'cumulative_construction_due_musd': sum(r.get('constructionDue') or 0 for r in rows),
        'dscr_breach_months': list(s.get('breachMonths') or []),
        'liquidity_breach_months': list(s.get('liquidityBreachMonths') or []),
        'funding_default': bool(s.get('fundingDefault')),
        'defaulted': bool(s.get('defaulted') or s.get('paymentDefault')),
        'financeability_status': s.get('financeabilityStatus'),
        'engine_version': s.get('engineVersion'),
        'sources_uses_residual': s.get('sourcesUsesMaxResidual'),
    }


def compare_paths(name, inputs, mode, base_config, calculate, *, gate_dependencies=None, milestone_schedules=None,
                  curtailment_allocation='tenant_or_compute_operator', acknowledge_contract_assumption=False,
                  acknowledge_tenant_capex_share=False):
    baseline = summary_of(calculate('underwrite', base_config), float(inputs['raw']['target']))
    path_results = []
    for pk in PATH_KEYS:
        scored = candidate_for(name, inputs, mode, pk, gate_dependencies, milestone_schedules)
        if scored is None:
            continue
        mapped, audit = map_path_to_config(base_config, scored,
            curtailment_allocation=curtailment_allocation,
            acknowledge_contract_assumption=acknowledge_contract_assumption,
            acknowledge_tenant_capex_share=acknowledge_tenant_capex_share)
        summary = summary_of(calculate('underwrite', mapped), float(inputs['raw']['target']))
        deltas = {k: ((summary[k]-baseline[k]) if isinstance(summary.get(k),(int,float)) and not isinstance(summary.get(k),bool)
                        and isinstance(baseline.get(k),(int,float)) and not isinstance(baseline.get(k),bool) else None)
                  for k in ('npv_musd','levered_irr','minimum_dscr','sponsor_equity_musd','first_rent_month',
                            'cumulative_lease_revenue_musd','cumulative_construction_due_musd',
                            'full_rent_month','pre_rent_debt_service_musd','uncovered_debt_service_musd',
                            'pre_rent_sponsor_carry_musd','stabilized_min_dscr')}
        warnings = (['PROVISIONAL POWER: NO UTILITY CONFIRMATION'] if scored['selected_class']!='Verified viable' else []) \
                   + (['CURTAILMENT IS NOT AUTOMATICALLY A LANDLORD COST'] if scored.get('curtailment_loss') else []) \
                   + (['FUNDING OR CREDIT BREACH: NOT A PERFORMING CASE'] if summary['defaulted'] or summary['dscr_breach_months'] or summary['funding_default'] else [])
        if summary['maximum_available_mw'] < float(inputs['raw']['target']) - 1e-6:
            warnings.append('FULL CAMPUS CAPACITY NOT DELIVERED DURING FINANCIAL MODEL HORIZON')
        if summary['first_rent_month'] is None:
            warnings.append('NO LEASE REVENUE WITHIN FINANCIAL MODEL HORIZON')
        if audit['binding_building_power_dates']:
            warnings.append('SOURCE SCENARIO POWER/LEASE DATES BIND: PATH BENEFIT IS CAPPED BY BASELINE ASSUMPTIONS')
        if summary['pre_rent_debt_service_musd'] > 1e-6:
            warnings.append('CASH DEBT SERVICE BEFORE RENT: CARRY MUST BE FUNDED BY RESERVE OR SPONSOR')
        path_results.append({
            'path_key':pk,'name':PATH_NAMES[pk],'viability':scored['selected_class'],
            'decision':scored['decision'],'screening_tier':scored['tier'],
            'first_power_month':scored['first_power'],'full_load_month':scored['full_load'],
            'first_power_mw':scored['mw_first'],
            'score':scored['final_additive'], 'summary':summary,'deltas_vs_original_scenario':deltas,
            'assumptions':audit,'underwriting_config_sha256':canonical_hash(mapped),
            'power_schedule_sha256':canonical_hash(scored['schedule_versions']),
            'warnings':warnings,
        })
    path_results.sort(key=lambda x: (x['viability']!='Verified viable', x['first_power_month'], x['name']))
    return {
        'label': 'READ-ONLY, ASSUMPTION-BASED SCREENING SENSITIVITY — NOT UTILITY-VERIFIED OR LENDER-VERIFIED',
        'model_version': 'workbook_v8_2', 'underwrite_engine_version':'27.1.0',
        'baseline':baseline, 'paths':path_results,
        'economic_recommendation':None,
        'reason_no_economic_recommendation':'First-power speed is not an economic optimization; executed lease/utility terms and review are missing',
        'certification':{'g4':'BLOCKED','g5':'BLOCKED','valuation_allowed':False,'lender_certified':False},
        'persisted_changes':False,
    }
