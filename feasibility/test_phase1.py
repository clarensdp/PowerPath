import json,yaml
from pathlib import Path
import pytest
from feasibility.engine import utility,score_from_model_values,gate_multiplier
from feasibility.montecarlo import simulation
D=Path(__file__).parent
M=yaml.safe_load((D/'config/metrics.yaml').read_text())
P=yaml.safe_load((D/'config/weights.yaml').read_text())
F=json.loads((D/'fixtures.json').read_text())
@pytest.mark.parametrize('fixture',F,ids=[f['site'] for f in F])
def test_every_metric_matches_workbook(fixture):
    for m in M:
        assert utility(fixture['model_values'][m['name']],m['breakpoints'],m['direction'])==pytest.approx(fixture['metric_scores'][m['name']],abs=.01)
@pytest.mark.parametrize('fixture',F,ids=[f['site'] for f in F])
def test_totals_using_reference_pillars(fixture):
    from feasibility.engine import totals
    a,g=totals(fixture['pillars'],P['profiles']['training'])
    assert a==pytest.approx(fixture['additive'],abs=.01)
    assert g==pytest.approx(fixture['geometric'],abs=.01)
def test_gates():
    assert gate_multiplier({'zoning':'N','power':'Y'})==0
    assert gate_multiplier({'zoning':'C','power':'Y'})==pytest.approx(.7)
def test_montecarlo_reproducible():
    s=F[0]['pillars'];w=P['profiles']['training']
    assert simulation(s,w)==simulation(s,w)
def test_missing_does_not_silently_pass():
    with pytest.raises(ValueError): utility(None,[1,2,3,4],'lower')

@pytest.mark.parametrize('fixture',F,ids=[f['site'] for f in F])
def test_complete_default_mode_final_parity(fixture):
    inputs=fixture['inputs']
    result=score_from_model_values(fixture['model_values'],M,P,
      cooling=inputs['Cooling design (Evaporative / Closed-loop / Dry)'],
      gate_mult=fixture['gate_multiplier'],
      political=inputs['Political / regulatory risk (1 = low, 5 = high)'],
      uncertainty=fixture['uncertainty'])
    for name in ('additive','geometric','risk_discount','final_additive','final_geometric'):
        assert result[name]==pytest.approx(fixture[name],abs=.01)
    for name,score in fixture['pillars'].items():
        assert result['pillars'][name]==pytest.approx(score,abs=.01)
