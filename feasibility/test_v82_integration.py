"""v8.2 integration: full workbook parity, canonical scheduling, tier invariants, local API persistence."""
import copy, json, os, subprocess, sys
from pathlib import Path
import pytest
from feasibility.v82.integration import score_batch,score_one
from server import schedule27

ROOT=Path(__file__).resolve().parent
F=json.loads((ROOT/'v82'/'fixtures_v8_2.json').read_text())
SCALARS=('selected','selected_class','first_power','full_load','mw_first','gate_multiplier','decision',
         'remediation_capex','path_capex','total_extra_capex','curtailment_loss','additive','geometric',
         'risk_discount','final_additive','final_geometric','tier','rank_in_tier','screening_position')

@pytest.mark.parametrize('mode',list(F['expected']))
def test_v82_parity_all_sites_and_modes(mode):
    scored=score_batch(F['inputs'],mode)
    for name,expected in F['expected'][mode].items():
        got=scored[name]
        for key in SCALARS:
            if isinstance(expected[key],(int,float)):
                assert got[key]==pytest.approx(expected[key],abs=.01), (name,key)
            else: assert got[key]==expected[key], (name,key)
        for key in ('metric_scores','pillars','path_classes','path_first'):
            for label,v in expected[key].items():
                if isinstance(v,(float,int)):
                    assert got[key][label]==pytest.approx(v,abs=.01),(name,key,label)
                else: assert got[key][label]==v,(name,key,label)
        assert got['schedule_method']==schedule27.METHOD_VERSION
        assert got['model_version']=='workbook_v8_2'

def test_provisional_never_ranks_with_verified():
    x=score_batch(F['inputs'])
    assert x['Site F']['tier_num']==3
    assert x['Site F']['screening_position']==7
    assert all(x[s]['screening_position']<7 for s in ['Site A','Site B','Site C','Site D','Site G','Site H'])

def test_failing_hybrid_gate_falls_back_to_grid():
    x=copy.deepcopy(F['inputs']['Site G']);x['gates']['Air permit']='N'
    z=score_one('Site G',x)
    assert z['selected']=='Grid' and z['first_power']==42 and z['decision']=='Go'
    assert z['path_capex']==0 and z['curtailment_loss']==0

def test_failing_flex_agreement_falls_back_to_grid():
    x=copy.deepcopy(F['inputs']['Site H']);x['gates']['Flex agreement']='N'
    z=score_one('Site H',x)
    assert z['selected']=='Grid' and z['first_power']==40 and z['decision']=='Go'

def test_schedule_dependencies_accumulate_on_one_path_not_others():
    x=copy.deepcopy(F['inputs']['Site G'])
    x['gates']['Zoning']='C'
    x['remediation_months']['Zoning']=3
    # Workbook assumes parallel: hybrid 15 + max(3,2) = 18 months.
    independent=score_one('Site G',x)
    assert independent['first_power']==18
    # Real schedule27 dependency edge adds zoning -> air permit = 3 + 2 = 5 months.
    dependent=score_one('Site G',x,dependencies={'hyb':{'Air permit':'Zoning'}})
    assert dependent['selected']=='Hybrid' and dependent['first_power']==20
    assert dependent['full_load']==47
    assert dependent['schedule_versions']['hyb']!=independent['schedule_versions']['hyb']
    assert dependent['schedule_versions']['grid']==independent['schedule_versions']['grid']

def test_capex_is_selected_path_only():
    for site in F['inputs']:
        z=score_one(site,F['inputs'][site])
        assert z['total_extra_capex']==pytest.approx(z['path_capex']+z['remediation_capex'])
    assert score_one('Site G',F['inputs']['Site G'])['total_extra_capex']==pytest.approx(90.4)
    assert score_one('Site H',F['inputs']['Site H'])['curtailment_loss']==pytest.approx(12.328767,abs=.001)

def test_na_gate_cannot_override_path_requirement():
    x=copy.deepcopy(F['inputs']['Site H'])
    x['gates']['Flex agreement']='NA'
    with pytest.raises(ValueError,match='cannot be NA'):
        score_one('Site H',x)

def test_missing_or_invalid_facts_cannot_pass_as_verified():
    x=copy.deepcopy(F['inputs']['Site A'])
    x['raw']['target']=0
    with pytest.raises(ValueError):score_one('bad',x)
    x=copy.deepcopy(F['inputs']['Site A'])
    x['confidence']['Expected PUE']=None
    with pytest.raises(ValueError):score_one('bad',x)

def test_api_persists_immutable_runs_isolated(tmp_path):
    # The original v27 auth tests set process-global environment variables at import.
    # A subprocess avoids contaminating those test suites with one local-mode app.
    env=os.environ.copy()
    env.pop('POWERPATH_V27_AUTH_MODE',None)
    env['POWERPATH_DATA_DIR']=str(tmp_path/'data')
    result=subprocess.run([sys.executable,'-m','feasibility.v82.api_smoke'],cwd=ROOT.parent,
                          env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+'\n'+result.stderr
