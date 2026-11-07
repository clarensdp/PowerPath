"""Independent Python implementation of the PowerPath v8.2 feasibility rules.

It reads only INPUT values and parameters from a recalculated workbook (Inputs, Weights, Metrics breakpoints,
Value Translator) and recomputes every result itself. acceptance.py compares these results with the
workbook's own formulas. Rules are written out here from the specification, not translated from the
workbook formulas, so a formula error in either place shows up as a mismatch.
"""
import math
from .model_definitions import (RAW, METRICS, GATES, GATE_SHORT, PILLARS, PATHS, PATH_KEYS, PATH_NAMES,
                               PATH_FIELDS, TIERS)

PATH_LABEL = {pk: plab for pk, _, plab in PATHS}
NAME = dict(zip(PATH_KEYS, PATH_NAMES))
KEY = dict(zip(PATH_NAMES, PATH_KEYS))


def rows_by_label(ws, col=1):
    d = {}
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, col).value
        if isinstance(v, str) and v not in d:
            d[v] = r
    return d


def utility(x, bp, direction):
    """Piecewise-linear: breakpoints score 100 / 70 / 30 / 0, clamped at both ends."""
    b1, b2, b3, b4 = bp
    better = (lambda a, b: a <= b) if direction == "Lower" else (lambda a, b: a >= b)
    if better(x, b1): return 100.0
    if better(x, b2): return 100 - 30 * (x - b1) / (b2 - b1)
    if better(x, b3): return 70 - 40 * (x - b2) / (b3 - b2)
    if better(x, b4): return 30 - 30 * (x - b3) / (b4 - b3)
    return 0.0


def params(wb):
    ww, wm, wv = wb["Weights"], wb["Metrics"], wb["Value Translator"]
    WR = rows_by_label(ww)
    p = lambda label: ww[f"C{WR[label]}"].value
    profile = ww["C3"].value
    col = "B" if profile == "Training" else "C"
    pw = {ww[f"A{r}"].value: ww[f"{col}{r}"].value for r in range(6, 6 + len(PILLARS))}
    z = sum(pw.values())
    # gate x path matrix
    g0 = next(r for r in range(1, ww.max_row + 1) if ww[f"A{r}"].value == "Gate" and ww[f"B{r}"].value == PATH_NAMES[0])
    appl = {k: {pk: ww.cell(g0 + 1 + k, 2 + j).value == "Y" for j, pk in enumerate(PATH_KEYS)} for k in range(len(GATES))}
    MR = {wm[f"B{r}"].value: r for r in range(5, 5 + len(METRICS))}
    metrics = {m[1]: dict(bp=[wm[f"{c}{MR[m[1]]}"].value for c in "FGHI"], direction=wm[f"D{MR[m[1]]}"].value,
                          w=wm[f"J{MR[m[1]]}"].value) for m in METRICS}
    cool = {}
    for name in ("Evaporative", "Closed-loop", "Dry"):
        r = WR[name]
        cool[name] = {"Expected PUE": ww[f"B{r}"].value, "Water stress (WRI Aqueduct)": ww[f"C{r}"].value}
    return dict(
        pw={k: v / z for k, v in pw.items()}, appl=appl, metrics=metrics, cool=cool,
        sev={"Minor": p("Gate severity multiplier: Minor"), "Major": p("Gate severity multiplier: Major"),
             "Moderate": p("Gate severity multiplier: Moderate (default for C)")},
        phase_w=[p("Phased delivery weight: month 24"), p("Phased delivery weight: month 36"), p("Phased delivery weight: month 48")],
        maxR=p("Max risk discount (R cap)"), share_conf=p("Share of R from data confidence (Discount mode only)"),
        conf_mode=p("Data confidence handling"), time_mode=p("Time-to-power curve"),
        rate=wv["B14"].value, horizon=wv["B15"].value, value_mw_month=wv["B9"].value)


def site_inputs(wb, col):
    wi = wb["Inputs"]
    IR = rows_by_label(wi)
    get = lambda label: wi[f"{col}{IR[label]}"].value
    return dict(
        name=wi[f"{col}5"].value,
        raw={k: get(lab) for k, lab, unit, fmt in RAW},
        gates=[get(g) or "" for g in GATES],
        sev=[get("Severity: " + g) for g in GATE_SHORT],
        delay=[get("Delay: " + g) or 0 for g in GATE_SHORT],
        cost=[get("Cost: " + g) or 0 for g in GATE_SHORT],
        political=get("Political / regulatory risk (1 = low, 5 = high)"),
        confidence=[get("Confidence: " + m[1]) for m in METRICS])


def score_site(si, P):
    raw, gates, appl = si["raw"], si["gates"], P["appl"]
    NGT = len(GATES)
    is_open = lambda st: st in ("C", "U", "")

    # ---- power paths: each path has its own schedule built from the gates that apply to it
    paths = {}
    for pk in PATH_KEYS:
        first = raw[f"{pk}_first"]
        if first is None:
            paths[pk] = dict(cls="None"); continue
        failed = any(appl[k][pk] and gates[k] == "N" for k in range(NGT))
        stated = raw[f"{pk}_cls"]
        cls = "Not viable" if (stated == "Not viable" or failed) else ("Verified viable" if stated == "Verified viable" else "Provisionally viable")
        if cls == "Not viable":
            paths[pk] = dict(cls=cls); continue
        delay = max([si["delay"][k] for k in range(NGT) if appl[k][pk] and is_open(gates[k])], default=0)
        full = max(first, raw[f"{pk}_full"] or 0)
        paths[pk] = dict(cls=cls, delay=delay, first=first + delay, full=full + delay,
                         mw1=raw[f"{pk}_mw1"] or 0, capex=raw[f"{pk}_capex"] or 0, curt=raw[f"{pk}_curt"] or 0)
    order = {pk: j for j, pk in enumerate(PATH_KEYS)}
    def fastest(cls):
        c = [(v["first"], order[pk], pk) for pk, v in paths.items() if v["cls"] == cls]
        return min(c)[2] if c else None
    sel = fastest("Verified viable") or fastest("Provisionally viable")
    sp = paths.get(sel, {})
    scls = sp.get("cls", "None")
    on_sel = lambda k: sel is not None and appl[k][sel]

    # ---- gates and decision
    if sel is None:
        G = 0.0
    else:
        G = math.prod(P["sev"].get(si["sev"][k] or "Moderate", P["sev"]["Moderate"]) if (on_sel(k) and gates[k] == "C") else 1.0
                      for k in range(NGT))
    any_entered = any(raw[f"{pk}_first"] is not None for pk in PATH_KEYS)
    all_path_N = any(all(appl[k].values()) and gates[k] == "N" for k in range(NGT))
    if sel is None:
        decision = "No-go" if (any_entered or all_path_N) else "Diligence required"
    elif scls != "Verified viable" or any(on_sel(k) and gates[k] in ("U", "") for k in range(NGT)):
        decision = "Diligence required"
    elif any(on_sel(k) and gates[k] == "C" for k in range(NGT)):
        decision = "Conditional"
    else:
        decision = "Go"
    remediation = sum(si["cost"][k] for k in range(NGT) if on_sel(k) and gates[k] in ("C", "U"))
    path_capex = sp.get("capex", 0) if sel else 0
    curtail_musd = (sp.get("curt", 0) / 8760 * (raw["target"] or 0) * P["value_mw_month"] * 12 / 1e6) if sel else 0
    prov = [(v["first"], order[pk], pk) for pk, v in paths.items() if v["cls"] == "Provisionally viable"]
    prov_opp = None
    if scls == "Verified viable" and prov and min(prov)[0] < sp["first"]:
        prov_opp = (min(prov)[2], min(prov)[0])

    # ---- metric model values
    mv = {}
    t = raw["target"]
    for m in METRICS:
        e = m[9]
        if e[0] == "raw":
            v = raw[e[1]]
        elif e[0] == "ratio":
            v = raw[e[1]] / raw[e[2]]
        elif e[0] == "path":
            v = sp.get("first")
        elif e[0] == "phase":
            if sel is None:
                v = None
            else:
                def mw_at(month):
                    if month < sp["first"]: return 0
                    if month < sp["full"]: return min(sp["mw1"], t)
                    return t
                w = P["phase_w"]
                v = sum(wi * min(1, mw_at(mo) / t) for wi, mo in zip(w, (24, 36, 48))) / sum(w)
        mv[m[1]] = v

    # ---- metric scores
    ms = {}
    for m in METRICS:
        x = mv[m[1]]; spec = P["metrics"][m[1]]
        if x is None:
            ms[m[1]] = None
        elif m[9][0] == "path" and P["time_mode"] == "Dollar":
            mo = (1 + P["rate"]) ** (1 / 12) - 1; N = P["horizon"] * 12
            pv = lambda tt: (1 + mo) ** (-tt) - (1 + mo) ** (-N)
            b1, b4 = spec["bp"][0], spec["bp"][3]
            ms[m[1]] = max(0.0, min(100.0, 100 * (pv(x) - pv(b4)) / (pv(b1) - pv(b4))))
        else:
            ms[m[1]] = utility(x, spec["bp"], spec["direction"])

    # ---- pillars, totals, risk
    pil = {}
    for pi, pname in enumerate(PILLARS):
        names = [m[1] for m in METRICS if m[0] == pi]
        if pname == "Cooling & water" and raw["cool"] in P["cool"]:
            cw = P["cool"][raw["cool"]]
            val = sum(cw[n] * (ms[n] or 0) for n in cw) / sum(cw.values())
        else:
            val = sum(P["metrics"][n]["w"] * (ms[n] or 0) for n in names) / sum(P["metrics"][n]["w"] for n in names)
        pil[pname] = max(1.0, val)
    pw = P["pw"]
    add = sum(pw[k] * pil[k] for k in PILLARS)
    geo = math.exp(sum(pw[k] * math.log(pil[k]) for k in PILLARS))
    gw = {}
    for m in METRICS:
        names = [n[1] for n in METRICS if n[0] == m[0]]
        gw[m[1]] = P["metrics"][m[1]]["w"] / sum(P["metrics"][n]["w"] for n in names) * pw[PILLARS[m[0]]]
    unc = min(1.0, sum(gw[m[1]] * (5 - si["confidence"][i]) / 4 for i, m in enumerate(METRICS)) / sum(gw.values()))
    R = P["maxR"] * ((P["share_conf"] * unc if P["conf_mode"] == "Discount" else 0) + (1 - P["share_conf"]) * (si["political"] - 1) / 4)
    final = G * add * (1 - R)
    tier = 4 if decision == "No-go" else 3 if scls != "Verified viable" else 2 if decision == "Diligence required" else 1
    return dict(
        name=si["name"], selected=NAME.get(sel, "None"), selected_class=scls, first_power=sp.get("first"),
        full_load=sp.get("full"), mw_first=min(sp["mw1"], t) if sel else None,
        path_classes={NAME[pk]: v["cls"] for pk, v in paths.items()},
        path_first={NAME[pk]: v.get("first") for pk, v in paths.items()},
        provisional_opportunity=(f"{PATH_LABEL[prov_opp[0]]}: {int(prov_opp[1])} months" if prov_opp else None),
        gate_multiplier=G, decision=decision, remediation_capex=remediation, path_capex=path_capex,
        total_extra_capex=remediation + path_capex, curtailment_loss=curtail_musd,
        model_values=mv, metric_scores=ms, pillars=pil, additive=add, geometric=geo, uncertainty=unc, risk_discount=R,
        final_additive=final, final_geometric=G * geo * (1 - R), tier=TIERS[tier - 1], tier_num=tier,
        rank_key=final - (raw.get("carbon") or 0) / 1e7)


def score_all(wb):
    P = params(wb)
    cols = [c for c in "CDEFGHIJ" if wb["Inputs"][f"{c}5"].value]
    out = {}
    for c in cols:
        r = score_site(site_inputs(wb, c), P)
        r["inputs_column"] = c
        out[r["name"]] = r
    for r in out.values():
        r["rank_in_tier"] = 1 + sum(1 for o in out.values() if o["tier_num"] == r["tier_num"] and o["rank_key"] > r["rank_key"])
    order = sorted(out.values(), key=lambda r: (r["tier_num"], -r["rank_key"], r["inputs_column"]))
    for i, r in enumerate(order, 1):
        r["screening_position"] = i
    return out
