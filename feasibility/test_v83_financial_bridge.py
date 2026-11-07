"""v30.3 financial bridge acceptance and anti-overclaiming / contract tests."""
import copy
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest
from feasibility.v82.financial_bridge import map_path_to_config, compare_paths, candidate_for
from feasibility.v82.integration import score_one
from server.app import calculate

F=json.loads((Path(__file__).parent/'v82'/'fixtures_v8_2.json').read_text())

@pytest.fixture(scope='module')
def original_config():
    b=calculate('defaults27',{})['project']
    b['buildings']=[{'name':'Campus','itMW':200,'constructionStart':1,'constructionMonths':12,
                     'powerMonth':1,'leaseMonth':1,'leaseTermMonths':120,'rentEscalatorPct':0}]
    b['months']=120
    b['ltc']=0
    b['initialCash']=2500
    b['minLiquidity']=0
    b['reserveTargetM']=0
    b['refinanceLtvPct']=0
    b['sponsorCommitmentM']=None
    return b


def test_hybrid_bridge_tranches_and_capex_exactly_once(original_config):
    g=candidate_for('Site G', F['inputs']['Site G'], 'default', 'hyb')
    b,a=map_path_to_config(original_config,g)
    assert b['powerTranches']==[{'month':17,'mw':100.0,'basis':'IT'}, {'month':44,'mw':100.0,'basis':'IT'}]
    assert b['delayMonths']==0
    assert b['constructionCostMW'] == pytest.approx(original_config['constructionCostMW']+90.4/200)
    assert a['extra_capex_musd']==pytest.approx(90.4)
    r=calculate('underwrite',b)
    assert next(row['month'] for row in r['rows'] if row['leaseRevenue']>0)==17
    assert next(row['month'] for row in r['rows'] if row['availableMW']>=200)==44
    # Capex increases by the exact bridge and remediation amount and is not lost/charged twice.
    b0=copy.deepcopy(b); b0['constructionCostMW']=original_config['constructionCostMW']
    r0=calculate('underwrite',b0)
    assert sum(x['constructionDue'] for x in r['rows'])-sum(x['constructionDue'] for x in r0['rows'])==pytest.approx(90.4,abs=.0001)
    assert a['schedule_method']=='schedule-27.1.0'


def test_capex_not_overmultiplied_by_existing_overrun(original_config):
    g=candidate_for('Site G', F['inputs']['Site G'], 'default', 'hyb')
    base=copy.deepcopy(original_config)
    base['overrunPct']=20
    bridge,a=map_path_to_config(base,g)
    before=calculate('underwrite',base)
    after=calculate('underwrite',bridge)
    added = sum(x['constructionDue'] for x in after['rows'])-sum(x['constructionDue'] for x in before['rows'])
    assert added == pytest.approx(90.4, abs=1e-5)
    assert a['extra_capex_musd'] == pytest.approx(90.4)


def test_grid_fallback_eliminates_hybrid_capex(original_config):
    x=copy.deepcopy(F['inputs']['Site G']); x['gates']['Air permit']='N'
    g=candidate_for('Site G', x, 'default', 'grid')
    assert candidate_for('Site G', x, 'default','hyb') is None
    b,a=map_path_to_config(original_config,g)
    assert a['extra_capex_musd']==0
    assert b['powerTranches'][0]['month']==42


def test_flexible_loss_not_automatically_borne_by_landlord(original_config):
    h=candidate_for('Site H',F['inputs']['Site H'],'default','flex')
    b,a=map_path_to_config(original_config,h)
    assert a['extra_capex_musd']==pytest.approx(5.3)
    assert a['curtailment_annual_compute_value_musd']==pytest.approx(12.328767,abs=.00001)
    assert a['curtailment_loss_in_owner_financials_musd_at_full_occupancy']==0
    assert b['rentPerKwMonth']==original_config['rentPerKwMonth']
    assert b['buildings']==original_config['buildings']
    with pytest.raises(ValueError,match='acknowledgement'):
        map_path_to_config(original_config,h,curtailment_allocation='owner_contractual_revenue')


def test_owner_curtailment_reduces_rent_in_frozen_engine(original_config):
    h=candidate_for('Site H',F['inputs']['Site H'],'default','flex')
    b0,_=map_path_to_config(original_config,h)
    b1,a=map_path_to_config(original_config,h,curtailment_allocation='owner_contractual_revenue',acknowledge_contract_assumption=True)
    assert a['curtailment_loss_in_owner_financials_musd_at_full_occupancy']==pytest.approx(12.328767,abs=1e-6)
    r0=calculate('underwrite',b0)
    r1=calculate('underwrite',b1)
    # First rent month stays physical; no curtailment is monetized before tenant lease starts.
    assert next(x['month'] for x in r0['rows'] if x['leaseRevenue']>0)==22
    assert next(x['month'] for x in r1['rows'] if x['leaseRevenue']>0)==22
    # With 0 escalation, 12 months of fully occupied load loses the annualized amount.
    n0=sum(x['leaseRevenue'] for x in r0['rows'] if 22<=x['month']<=33)
    n1=sum(x['leaseRevenue'] for x in r1['rows'] if 22<=x['month']<=33)
    assert n0-n1==pytest.approx(12.328767, abs=1e-4)
    assert r1['summary']['npvM'] < r0['summary']['npvM']
    assert r1['summary']['leveredIRR'] < r0['summary']['leveredIRR']
    contracted=copy.deepcopy(original_config)
    contracted['buildings'][0]['contractedRentM']=100
    with pytest.raises(ValueError,match='Contract rent'):
        map_path_to_config(contracted,h,curtailment_allocation='owner_contractual_revenue',acknowledge_contract_assumption=True)


def test_compare_all_paths_read_only_and_no_certification(original_config):
    original=copy.deepcopy(original_config)
    r=compare_paths('Site H',F['inputs']['Site H'],'default',original_config,calculate)
    assert original_config==original
    assert {x['path_key'] for x in r['paths']}=={'flex','grid'}
    assert [p['path_key'] for p in r['paths']]==['flex','grid']
    for p in r['paths']:
        assert p['summary']['engine_version']=='27.1.0'
        assert p['summary']['maximum_available_mw']==pytest.approx(200)
        assert p['underwriting_config_sha256'] and p['power_schedule_sha256']
        assert 'npv_musd' in p['deltas_vs_original_scenario']
    assert r['certification']=={'g4':'BLOCKED','g5':'BLOCKED','valuation_allowed':False,'lender_certified':False}
    assert r['economic_recommendation'] is None and r['persisted_changes'] is False
    assert 'CURTAILMENT' in r['paths'][0]['warnings'][0]


def test_provisional_not_promoted_and_not_lender_ready(original_config):
    r=compare_paths('Site F',F['inputs']['Site F'],'default',original_config,calculate)
    assert len(r['paths'])==1 and r['paths'][0]['viability']=='Provisionally viable'
    assert r['paths'][0]['decision']=='Diligence required'
    assert 'PROVISIONAL' in r['paths'][0]['warnings'][0]
    r2=compare_paths('Site E',F['inputs']['Site E'],'default',original_config,calculate)
    assert r2['paths']==[]


def test_input_guards_block_double_application_and_bad_contract(original_config):
    g=candidate_for('Site G',F['inputs']['Site G'],'default','hyb')
    for key, val, expected in [('powerPathLink',{'id':'old'},'original'),('delayMonths',9,'zero'),
                               ('powerTranches',[{'mw':200,'month':1}],'powerTranches'),
                               ('engineVersion','25.8.5','27.1.0'),
                               ('capacityBasis','gross','IT capacity')]:
        c=copy.deepcopy(original_config);c[key]=val
        with pytest.raises(ValueError,match=expected):map_path_to_config(c,g)
    c=copy.deepcopy(original_config);c['buildings'][0]['itMW']=100
    with pytest.raises(ValueError,match='building IT MW'):
        map_path_to_config(c,candidate_for('Site H',F['inputs']['Site H'],'default','flex'))


def test_api_financial_preview_is_read_only(tmp_path):
    env=os.environ.copy()
    env.pop('POWERPATH_V27_AUTH_MODE',None)
    env['POWERPATH_DATA_DIR']=str(tmp_path/'local')
    p=subprocess.run([sys.executable,'-m','feasibility.v82.api_financial_smoke'],
                     cwd=Path(__file__).resolve().parent.parent,env=env,capture_output=True,text=True,timeout=75)
    assert p.returncode==0,p.stdout+'\n'+p.stderr
