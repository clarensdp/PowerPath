"""Rebuild monthly financial inputs from the retained v11 hourly dispatch exports."""
import sys,json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'starter'))
import check_submission as cs
NAMES={'outputs':'Balanced','priority_change_speed_full_demand_by_24':'Earlier opening','priority_change_zero_tier2':'No interruptions','priority_change_clean_under_100kg':'Carbon cap ≤100 kg/MWh','priority_change_n1_reliability':'Extra onsite resilience','extension_execution_aware_today_m0':'Lead-time aware'}
profiles=[]
for folder,name in NAMES.items():
    p=ROOT/'outputs' if folder=='outputs' else ROOT/'outputs'/folder
    port=json.loads((p/'portfolio.json').read_text()); d=pd.read_csv(p/'dispatch.csv')
    score=cs.score(port,d)
    if not score['physical_checks_passed']: raise ValueError((name,score))
    ctx=cs.prepare_inputs(port); n=ctx['n']; op=np.zeros(n); recovery=np.zeros(n);variable=np.zeros(n); capex=np.zeros(120)
    for _,r in cs.options.iterrows():
        mw=ctx['caps'].get(r.option_id,0); mask=cs.available_mask(r,ctx)
        crf=cs.case['discount_rate_real']/(1-(1+cs.case['discount_rate_real'])**(-r.life_years))
        recovery+=mask*mw*1000*r.capex_usd_per_kw*crf/8760
        op+=mask*mw*1000*r.fom_usd_per_kw_year/8760
        gen=np.zeros(n) if r.kind=='storage' else d[r.option_id+'_mw'].to_numpy(float)
        billed=mw*cs.profile(r,ctx) if r.payment_basis=='available_generation' else gen
        variable+=billed*r.payment_usd_per_mwh+gen*ctx['gas_price']*r.heat_rate_mmbtu_per_mwh_hhv
        capex[int(max(ctx['start'],r.available_month))]+=mw*1000*r.capex_usd_per_kw
    variable+=d.grid_mw.to_numpy()*ctx['grid_price']
    moved=d.tier1_relocated_mw.to_numpy(); cut=d.tier2_curtailed_mw.to_numpy()
    relocation=moved*ctx['relocation_price']; consequence=cut*ctx['interruption_price']
    assert np.isclose((op+variable+recovery+relocation+consequence).sum(),score['total_decision_cost_usd'])
    local=ctx['load']-moved-cut
    def monthly(a):return np.asarray(a).reshape(120,730).sum(axis=1).round(6).tolist()
    profiles.append(dict(id=folder,name=name,open=port['initial_service_month'],full=port['initial_service_month']+10,caps=port['capacities_mw'],kg=score['combined_electricity_co2_kg_per_mwh'],clean=score['clean_energy_share'],benchmark_cost=score['total_decision_cost_usd'],source=str(p.relative_to(ROOT)),monthly=dict(requested=monthly(ctx['load']),billable=monthly(local+moved),variable=monthly(variable),fixed=monthly(op),relocation=monthly(relocation),consequence=monthly(consequence),recovery=monthly(recovery),capex=capex.tolist(),interrupted=monthly(cut))))
(ROOT/'workspace/profiles.json').write_text(json.dumps(profiles))
print('Reconciled',len(profiles),'profiles to original checker cost totals.')
