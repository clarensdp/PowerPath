import numpy as np
def simulation(pillars,weights,gate_multiplier=1,risk_discount=0,seed=42,trials=2000,perturbation=.30,noise=0,uncertainty=None):
    rng=np.random.default_rng(seed); names=list(weights);w=np.array([weights[k] for k in names],float)
    s=np.array([pillars[k] for k in names],float)
    u=np.array([uncertainty.get(k,0) for k in names]) if uncertainty else np.zeros(len(names))
    out=[]
    for _ in range(trials):
        wt=w*rng.uniform(1-perturbation,1+perturbation,len(w)); wt/=wt.sum()
        st=np.clip(s+noise*u*rng.uniform(-1,1,len(w)),1,100)
        rt=max(0,risk_discount*rng.uniform(1-perturbation,1+perturbation))
        out.append(float(np.dot(wt,st)*gate_multiplier*(1-rt)))
    return dict(zip(('p10','p50','p90'),map(float,np.percentile(out,[10,50,90]))))
