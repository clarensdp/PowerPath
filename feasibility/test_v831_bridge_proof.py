"""v30.3.1 proof tests: the financial bridge under a LEVERAGED scenario (65% LTC, 1.20x covenant).

The v30.3 suite uses ltc=0, where DSCR and financing shortfall are undefined. These tests prove the
direction and size of each power-path effect on rent commencement, equity IRR, DSCR and pre-rent carry.
"""
import copy
import json
from pathlib import Path
import pytest
from feasibility.v82.financial_bridge import map_path_to_config, compare_paths, candidate_for, summary_of
from server.app import calculate

F = json.loads((Path(__file__).parent / 'v82' / 'fixtures_v8_2.json').read_text())
ENGINE = Path(__file__).resolve().parent.parent / 'engine'


def leveraged(construction_months=12, power_month=1):
    b = calculate('defaults27', {})['project']          # ltc 65, dscrCovenant 1.2, rate 8%
    b['buildings'] = [{'name': 'Campus', 'itMW': 200, 'constructionStart': 1, 'constructionMonths': construction_months,
                       'powerMonth': power_month, 'leaseMonth': power_month, 'leaseTermMonths': 180, 'rentEscalatorPct': 2.5}]
    b['months'] = 180
    b['sponsorCommitmentM'] = 3000
    return b


def synth(first, full, mw1, capex=0.0, curt=0.0):
    return {'first_power': first, 'full_load': full, 'mw_first': mw1, 'target_it_mw': 200.0, 'total_extra_capex': capex,
            'curtailment_loss': curt, 'selected': 'Grid', 'selected_class': 'Verified viable', 'schedule_method': 'synthetic',
            'schedule_versions': {}}


def run(cfg):
    return summary_of(calculate('underwrite', cfg), 200.0)


def test_engine_files_unchanged_from_v30_3_audit():
    import hashlib
    audit = json.loads((ENGINE.parent / 'ENGINE_HASH_AUDIT_V30_3.json').read_text())['files']
    for rel, meta in audit.items():
        assert hashlib.sha256((ENGINE / rel).read_bytes()).hexdigest() == meta['sha256'], rel


def test_identity_path_reproduces_leveraged_baseline():
    base = leveraged()
    s0, s1 = run(base), run(map_path_to_config(base, synth(1, 1, 200))[0])
    for k in ('npv_musd', 'levered_irr', 'minimum_dscr', 'stabilized_min_dscr', 'pre_rent_debt_service_musd',
              'sponsor_equity_musd', 'first_rent_month'):
        assert s1[k] == pytest.approx(s0[k], rel=1e-12, abs=1e-12), k


def test_delay_monotonic_across_all_four_outputs():
    base, prev = leveraged(), None
    for k in range(0, 25, 3):
        s = run(map_path_to_config(base, synth(20 + k, 20 + k, 200))[0])
        assert s['first_rent_month'] == 20 + k
        if prev:
            assert s['npv_musd'] < prev['npv_musd']
            assert s['levered_irr'] < prev['levered_irr']
            assert s['pre_rent_debt_service_musd'] > prev['pre_rent_debt_service_musd']
            assert s['uncovered_debt_service_musd'] >= prev['uncovered_debt_service_musd']
            assert s['stabilized_min_dscr'] == pytest.approx(prev['stabilized_min_dscr'], rel=0.05)
        prev = s


def test_pre_rent_carry_equals_engine_debt_service_rows():
    cfg = map_path_to_config(leveraged(), synth(30, 30, 200))[0]
    r = calculate('underwrite', cfg)
    s = summary_of(r, 200.0)
    direct = sum(x['debtService'] for x in r['rows'] if x['month'] < s['first_rent_month'])
    assert s['pre_rent_debt_service_musd'] == pytest.approx(direct)
    assert s['months_debt_service_before_rent'] == sum(1 for x in r['rows'] if x['debtService'] > 1e-9 and x['month'] < 30)
    assert s['minimum_dscr'] == 0 and s['stabilized_min_dscr'] > 1.2   # min DSCR cannot rank; stabilized can


def test_construction_binds_before_power():
    s = run(map_path_to_config(leveraged(construction_months=18), synth(17, 17, 200))[0])
    assert s['first_rent_month'] == 19


def test_phased_full_rent_month_from_second_tranche():
    s = run(map_path_to_config(leveraged(), synth(17, 44, 100))[0])
    assert s['first_rent_month'] == 17 and s['full_rent_month'] == 44


def test_tenant_capex_share_guard():
    b = leveraged(); b['tenantCapexPct'] = 30
    with pytest.raises(ValueError, match='tenantCapexPct'):
        map_path_to_config(b, synth(20, 20, 200, capex=90.4))
    cfg, a = map_path_to_config(b, synth(20, 20, 200, capex=90.4), acknowledge_tenant_capex_share=True)
    assert a['tenant_capex_share_of_path_capex_pct'] == 30
    map_path_to_config(b, synth(20, 20, 200, capex=0))   # no path capex: nothing to guard


def test_binding_scenario_power_dates_are_flagged():
    b = leveraged(construction_months=12, power_month=30)
    _, a = map_path_to_config(b, synth(17, 17, 200))
    assert a['binding_building_power_dates'] == [{'building': 'Campus', 'construction_ready_month': 13, 'scenario_power_or_lease_month': 30}]
    r = compare_paths('Site G', F['inputs']['Site G'], 'default', b, calculate)
    hyb = next(p for p in r['paths'] if p['path_key'] == 'hyb')
    assert any('BIND' in w for w in hyb['warnings'])
    assert hyb['summary']['first_rent_month'] == 30          # faster path cannot beat the embedded date
    _, clean = map_path_to_config(leveraged(), synth(17, 17, 200))
    assert clean['binding_building_power_dates'] == []


@pytest.mark.parametrize('site,pk,alloc', [('Site G', 'hyb', 'tenant_or_compute_operator'), ('Site H', 'flex', 'owner_contractual_revenue')])
def test_attribution_waterfall_sums_and_signs(site, pk, alloc):
    sc = candidate_for(site, F['inputs'][site], 'default', pk)
    b = leveraged(construction_months=18)
    kw = {'curtailment_allocation': alloc, 'acknowledge_contract_assumption': alloc != 'tenant_or_compute_operator'}
    s_base = run(b)
    s_sched = run(map_path_to_config(b, {**sc, 'total_extra_capex': 0, 'curtailment_loss': 0})[0])
    s_cap = run(map_path_to_config(b, {**sc, 'curtailment_loss': 0})[0])
    s_all = run(map_path_to_config(b, sc, **kw)[0])
    steps = [s_sched['npv_musd'] - s_base['npv_musd'], s_cap['npv_musd'] - s_sched['npv_musd'], s_all['npv_musd'] - s_cap['npv_musd']]
    assert sum(steps) == pytest.approx(s_all['npv_musd'] - s_base['npv_musd'])
    assert steps[0] <= 0 and steps[1] < 0 and steps[2] <= 0
    if alloc == 'owner_contractual_revenue':
        assert steps[2] < 0
    else:
        assert steps[2] == 0


def test_compare_paths_reports_carry_and_ranks_faster_path_lower_carry():
    r = compare_paths('Site G', F['inputs']['Site G'], 'default', leveraged(construction_months=18), calculate)
    by = {p['path_key']: p['summary'] for p in r['paths']}
    assert by['hyb']['first_rent_month'] == 19 and by['grid']['first_rent_month'] == 42
    assert by['hyb']['pre_rent_debt_service_musd'] < by['grid']['pre_rent_debt_service_musd']
    assert by['hyb']['levered_irr'] > by['grid']['levered_irr']
    assert r['certification']['g4'] == 'BLOCKED' and r['economic_recommendation'] is None
