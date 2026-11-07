"""PowerPath feasibility model v8.2 - static definitions.

Single source for the workbook build (build/build_workbook.py) and the validation harness
(reference_model.py, acceptance.py). Pure data: no file I/O, no workbook code.
"""

# power paths: key, label, order used to break ties (lower wins)
PATHS = [("grid", "Grid", "Grid"), ("btm", "BTM", "Behind-the-meter"),
         ("hyb", "Hybrid", "Hybrid (grid + on-site bridge)"), ("flex", "Flexible", "Flexible load (curtailable grid service)")]
PATH_KEYS = [p[0] for p in PATHS]
PATH_NAMES = [p[1] for p in PATHS]
PATH_FIELDS = [("first", "months to first power", "months", "0"),
               ("full", "months to full target load (blank = same as first)", "months", "0"),
               ("mw1", "MW deliverable at first power", "MW", "#,##0"),
               ("cls", "path class (Verified viable / Provisionally viable / Not viable)", "status", "@"),
               ("capex", "path capex uplift", "$M", "0.0"),
               ("curt", "curtailment hours per year", "hrs/yr", "#,##0")]
PATH_RAW = [(f"{pk}_{fk}", f"{plab}: {flab}", unit, fmt)
            for pk, _, plab in PATHS for fk, flab, unit, fmt in PATH_FIELDS]
PATH_CLASSES = ["Verified viable", "Provisionally viable", "Not viable"]
GATE_STATES = ["Y", "C", "N", "U", "NA"]   # NA = gate not relevant (path not pursued)
SEVERITY = {"Minor": 0.95, "Moderate": 0.85, "Major": 0.65}   # defaults; editable on the Weights tab
TIERS = ["1 Decision-ready", "2 Verified path - gate diligence open", "3 Provisional power opportunity", "4 Excluded"]

PILLARS = ["Power: availability & speed", "Power: cost & quality", "Cooling & water",
           "Connectivity & latency", "Land & buildout", "Regulatory & incentives",
           "Community & political", "Market demand"]
NP = len(PILLARS)
TRAIN = [0.30, 0.17, 0.10, 0.05, 0.12, 0.10, 0.08, 0.08]
INFER = [0.25, 0.12, 0.08, 0.16, 0.11, 0.08, 0.08, 0.12]

# raw inputs: key, label, unit, number format
RAW = [
    ("target", "Target IT load", "MW", "#,##0"),
] + PATH_RAW + [
    ("head", "Available grid headroom", "MW", "#,##0"),
    ("exp", "10-yr expansion path", "MW", "#,##0"),
    ("gas", "Distance to gas pipeline (on-site generation option)", "miles", "0"),
    ("cost", "All-in delivered power cost", "$/MWh", "0"),
    ("vol", "Price volatility (std dev of hourly price)", "$/MWh", "0"),
    ("ppa", "Clean PPA access", "1-5", "0"),
    ("cool", "Cooling design (Evaporative / Closed-loop / Dry)", "type", "@"),
    ("fc", "Free-cooling hours (PUE sanity check only, not scored)", "hrs/yr", "#,##0"),
    ("pue", "Expected PUE", "ratio", "0.00"),
    ("water", "Water stress (WRI Aqueduct)", "0-5", "0.0"),
    ("lat", "Latency to nearest major IXP", "ms", "0"),
    ("fiber", "Diverse fiber routes", "count", "0"),
    ("acres", "Contiguous developable land", "acres", "#,##0"),
    ("cci", "Construction cost index (US avg = 100)", "index", "0"),
    ("lead", "Long-lead equipment (transformers, switchgear)", "months", "0"),
    ("tax", "Tax incentive strength", "1-5", "0"),
    ("permit", "Permitting timeline", "months", "0"),
    ("opp", "Local opposition risk", "1-5", "0"),
    ("rate", "Large-load tariff / rate-case exposure", "1-5", "0"),
    ("vac", "Market vacancy rate", "%", "0.0%"),
    ("pre", "Preleasing of market pipeline", "%", "0%"),
    ("abs", "Annual net absorption in market", "MW/yr", "#,##0"),
    ("cloud", "Distance to nearest hyperscale cloud region", "miles", "#,##0"),
    ("carbon", "Grid carbon intensity (tiebreaker only, not scored)", "gCO2/kWh", "0"),
]
RAWKEYS = [r[0] for r in RAW]

# metrics: pillar, name, unit, dir, P100, P70, P30, P0, weight, value expression type, number format
METRICS = [
    (0, "Time to energization (fastest path)", "months", "Lower", 18, 30, 48, 60, 0.30, ("path",), "0"),
    (0, "Phased delivery (time-weighted share of target)", "share", "Higher", 1.0, 0.8, 0.5, 0.25, 0.30, ("phase",), "0%"),
    (0, "Grid headroom / target load", "x", "Higher", 1.5, 1.0, 0.75, 0.5, 0.10, ("ratio", "head", "target"), "0.00x"),
    (0, "10-yr expansion / target load", "x", "Higher", 5, 3, 1.5, 1, 0.15, ("ratio", "exp", "target"), "0.0x"),
    (0, "Distance to gas pipeline", "miles", "Lower", 1, 5, 15, 30, 0.15, ("raw", "gas"), "0"),
    (1, "All-in delivered power cost", "$/MWh", "Lower", 40, 55, 75, 100, 0.60, ("raw", "cost"), "0"),
    (1, "Price volatility", "$/MWh", "Lower", 15, 30, 60, 100, 0.15, ("raw", "vol"), "0"),
    (1, "Clean PPA access", "1-5", "Higher", 5, 4, 2.5, 1, 0.25, ("raw", "ppa"), "0"),
    (2, "Expected PUE", "ratio", "Lower", 1.15, 1.25, 1.40, 1.60, 0.60, ("raw", "pue"), "0.00"),
    (2, "Water stress (WRI Aqueduct)", "0-5", "Lower", 1, 2, 3.5, 4.5, 0.40, ("raw", "water"), "0.0"),
    (3, "Latency to nearest major IXP", "ms", "Lower", 5, 15, 35, 60, 0.60, ("raw", "lat"), "0"),
    (3, "Diverse fiber routes", "count", "Higher", 4, 3, 2, 1, 0.40, ("raw", "fiber"), "0"),
    (4, "Contiguous developable land", "acres", "Higher", 500, 250, 100, 50, 0.35, ("raw", "acres"), "#,##0"),
    (4, "Construction cost index", "index", "Lower", 90, 100, 115, 130, 0.35, ("raw", "cci"), "0"),
    (4, "Long-lead equipment", "months", "Lower", 12, 24, 36, 48, 0.30, ("raw", "lead"), "0"),
    (5, "Tax incentive strength", "1-5", "Higher", 5, 4, 2.5, 1, 0.60, ("raw", "tax"), "0"),
    (5, "Permitting timeline", "months", "Lower", 6, 12, 24, 36, 0.40, ("raw", "permit"), "0"),
    (6, "Local opposition risk", "1-5", "Lower", 1, 2, 3.5, 5, 0.60, ("raw", "opp"), "0"),
    (6, "Large-load tariff / rate-case exposure", "1-5", "Lower", 1, 2, 3.5, 5, 0.40, ("raw", "rate"), "0"),
    (7, "Market vacancy rate", "%", "Lower", 0.02, 0.05, 0.10, 0.15, 0.25, ("raw", "vac"), "0.0%"),
    (7, "Preleasing of market pipeline", "%", "Higher", 0.90, 0.70, 0.40, 0.20, 0.30, ("raw", "pre"), "0%"),
    (7, "Annual net absorption", "MW/yr", "Higher", 500, 250, 100, 25, 0.25, ("raw", "abs"), "#,##0"),
    (7, "Distance to nearest cloud region", "miles", "Lower", 50, 150, 400, 800, 0.20, ("raw", "cloud"), "#,##0"),
]
NM = len(METRICS)
GATES = [
    "Credible power path to target load in timeline (any path)",
    "Outside 100-yr floodplain / high seismic (or mitigated)",
    "Zoning allows use (or rezoning realistic)",
    "Water allocation secured OR dry/closed-loop cooling",
    "No active data center moratorium",
    "Air permit for on-site generation (behind-the-meter and hybrid paths)",
    "Utility flexible-load / curtailment agreement (flexible-load path only)",
]
NG = len(GATES)

def site(name, desc, gates, vals, pol, conf):
    return dict(name=name, desc=desc, gates=gates, vals=vals, pol=pol, conf=conf)

def confs(base, over=None):
    c = [base] * NM
    for k, v in (over or {}).items():
        c[k] = v
    return c


GATE_SHORT = ["Power path", "Flood/seismic", "Zoning", "Water", "Moratorium", "Air permit", "Flex agreement"]
# which power paths each gate applies to (editable matrix on the Weights tab)
GATE_PATHS = {0: {"grid", "btm", "hyb", "flex"}, 1: {"grid", "btm", "hyb", "flex"}, 2: {"grid", "btm", "hyb", "flex"},
              3: {"grid", "btm", "hyb", "flex"}, 4: {"grid", "btm", "hyb", "flex"}, 5: {"btm", "hyb"}, 6: {"flex"}}
# per-site gate detail: gate index -> (severity if conditional, remediation delay months, remediation cost $M)
GATE_DETAIL = {"Site B": {2: ("Major", 9, 2.0)}, "Site C": {1: (None, 3, 0.1)}, "Site F": {5: (None, 6, 0.5)},
               "Site G": {5: ("Minor", 2, 0.4)}, "Site H": {6: (None, 4, 0.3)}}


def _p(**kw):
    """Per-path inputs: kw like grid=(first, full, mw1, cls, capex, curt)."""
    out = {}
    for pk in PATH_KEYS:
        v = kw.get(pk)
        if v is None:
            continue
        for (fk, *_), val in zip(PATH_FIELDS, v):
            out[f"{pk}_{fk}"] = val
    return out

V, P_, X = "Verified viable", "Provisionally viable", "Not viable"
SITES_DEF = [
    site("Site A", "West Texas (ERCOT) greenfield", ["Y", "Y", "Y", "Y", "Y", "U", "NA"],
         dict(target=300, **_p(grid=(20, 30, 250, V, 0, 0), btm=(14, 20, 300, P_, 150, 0)),
              cool="Closed-loop", head=600, exp=2000, gas=2, cost=42, vol=70, ppa=5, fc=3500, pue=1.30, water=4.0, lat=30, fiber=2,
              acres=800, cci=92, lead=24, tax=4, permit=9, opp=2, rate=3, vac=0.06, pre=0.55, abs=150, cloud=300, carbon=380),
         2, confs(3, {0: 4, 19: 2, 20: 2, 21: 2})),
    site("Site B", "Northern Virginia brownfield", ["Y", "Y", "C", "Y", "Y", "NA", "NA"],
         dict(target=150, **_p(grid=(54, 60, 75, V, 0, 0)),
              cool="Evaporative", head=150, exp=300, gas=8, cost=78, vol=30, ppa=3, fc=4200, pue=1.25, water=2.5, lat=2, fiber=6,
              acres=60, cci=115, lead=30, tax=3, permit=18, opp=4, rate=4, vac=0.01, pre=0.95, abs=1200, cloud=10, carbon=300),
         4, confs(4, {0: 3})),
    site("Site C", "Pacific NW hydro-adjacent", ["Y", "U", "Y", "Y", "Y", "NA", "NA"],
         dict(target=200, **_p(grid=(30, 40, 150, V, 0, 0)),
              cool="Evaporative", head=300, exp=700, gas=20, cost=45, vol=20, ppa=4, fc=6500, pue=1.15, water=1.5, lat=18, fiber=3,
              acres=200, cci=108, lead=24, tax=3, permit=15, opp=3, rate=3, vac=0.03, pre=0.80, abs=300, cloud=40, carbon=90),
         3, confs(3, {0: 2, 1: 2})),
    site("Site D", "Ohio retired coal plant site", ["Y", "Y", "Y", "Y", "Y", "Y", "NA"],
         dict(target=300, **_p(grid=(24, 24, 300, V, 0, 0), btm=(18, 30, 150, V, 120, 0)),
              cool="Closed-loop", head=400, exp=900, gas=1, cost=58, vol=35, ppa=2, fc=4800, pue=1.22, water=1.5, lat=12, fiber=3,
              acres=350, cci=98, lead=24, tax=4, permit=12, opp=2, rate=4, vac=0.02, pre=0.85, abs=600, cloud=30, carbon=480),
         2, confs(4)),
    site("Site E", "Arizona desert greenfield", ["Y", "Y", "Y", "N", "Y", "NA", "NA"],
         dict(target=200, **_p(grid=(36, 48, 100, V, 0, 0)),
              cool="Dry", head=250, exp=800, gas=10, cost=60, vol=45, ppa=4, fc=1500, pue=1.35, water=4.5, lat=15, fiber=2,
              acres=600, cci=100, lead=30, tax=4, permit=12, opp=3, rate=3, vac=0.04, pre=0.75, abs=400, cloud=20, carbon=350),
         3, confs(3)),
    site("Site F", "Negative test: grid not viable, on-site path only provisional", ["Y", "Y", "Y", "Y", "Y", "U", "NA"],
         dict(target=200, **_p(grid=(48, 48, 200, X, 0, 0), btm=(16, 30, 100, P_, 140, 0)),
              cool="Closed-loop", head=100, exp=600, gas=1, cost=50, vol=40, ppa=3, fc=4500, pue=1.25, water=2.0, lat=20, fiber=3,
              acres=400, cci=98, lead=24, tax=4, permit=12, opp=2, rate=3, vac=0.03, pre=0.80, abs=300, cloud=60, carbon=420),
         2, confs(2)),
    site("Site G", "Hybrid test: 42-month grid upgrade, on-site bridge from month 15", ["Y", "Y", "Y", "Y", "Y", "C", "NA"],
         dict(target=200, **_p(grid=(42, 42, 200, V, 0, 0), hyb=(15, 42, 100, V, 90, 0)),
              cool="Closed-loop", head=150, exp=600, gas=1, cost=55, vol=35, ppa=3, fc=4000, pue=1.25, water=2.0, lat=15, fiber=3,
              acres=300, cci=95, lead=24, tax=4, permit=12, opp=2, rate=3, vac=0.03, pre=0.80, abs=300, cloud=80, carbon=400),
         2, confs(3)),
    site("Site H", "Flexible-load test: firm service at 40 months, curtailable service earlier", ["Y", "Y", "Y", "Y", "Y", "NA", "C"],
         dict(target=200, **_p(grid=(40, 40, 200, V, 0, 0), flex=(18, 18, 200, V, 5, 300)),
              cool="Closed-loop", head=120, exp=500, gas=10, cost=75, vol=30, ppa=3, fc=4200, pue=1.25, water=2.5, lat=4, fiber=5,
              acres=120, cci=112, lead=30, tax=3, permit=15, opp=3, rate=4, vac=0.01, pre=0.95, abs=1000, cloud=15, carbon=300),
         3, confs(3)),
]
SITES = SITES_DEF
