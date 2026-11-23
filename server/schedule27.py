"""PowerPath canonical schedule engine (schedule-27.1.0). One function computes the COD effect of every delay; every
interface (Decision Center, Power paths, PermitIQ/Execution, sensitivities, change-proposal previews, agent proposals)
calls it and reports the same schedule_version.

Method (DELAY_CONVENTION.md):
  * Activities are a path's delivery milestones, typed as interconnection, utility_energization, permitting, construction,
    equipment_procurement, tenant_readiness or financing_ntp. An open permit that is NOT linked to a milestone is an
    independent parallel activity.
  * Along a dependency (predecessor) edge, delay ACCUMULATES: shift(m) = own(m) + shift(predecessor). A finished activity
    has shift 0 (its delay has already happened and is in the baseline).
  * Each activity's COD impact is max(0, shift - float), where float is the activity's total float to COD (default 0,
    i.e. assumed critical unless the analyst records float).
  * Independent drivers run in PARALLEL, so COD moves by the LONGEST critical driver, not the sum:
        COD delay = max(path-level unattributed estimate, max activity COD impact, max unlinked open permit delay).
  * The path-level estimate is an overall analyst figure that may overlap the activity detail, so it is never added.
  * A linked permit's own delay is evidence for its milestone, not an extra driver; disagreement is flagged.
This is a screening convention, not an engineering CPM schedule or a utility-confirmed date.
"""

from __future__ import annotations
from server.services.power_capacity import constrain, period_capacity
import hashlib, json

METHOD_VERSION = "schedule-27.1.0"
ACTIVITY_TYPES = (
    "interconnection",
    "utility_energization",
    "permitting",
    "construction",
    "equipment_procurement",
    "tenant_readiness",
    "financing_ntp",
)
CATEGORY_TO_TYPE = {
    "interconnection": "interconnection",
    "utility": "utility_energization",
    "permitting": "permitting",
    "construction": "construction",
    "finance": "financing_ntp",
    "equipment": "equipment_procurement",
    "tenant": "tenant_readiness",
}
MILESTONE_CATEGORIES = tuple(CATEGORY_TO_TYPE)


class ScheduleError(ValueError):
    pass


def _norm_inputs(path, milestones, permits, overrides):
    return {
        "method": METHOD_VERSION,
        "path": {k: path.get(k) for k in ("id", "power_month", "delay_months")},
        "milestones": sorted(
            (
                {
                    k: m.get(k)
                    for k in (
                        "id",
                        "category",
                        "status",
                        "planned_month",
                        "delay_months",
                        "float_months",
                        "predecessor_id",
                        "permit_id",
                        "source_url",
                        "evidence_id",
                    )
                }
                for m in milestones
            ),
            key=lambda x: x["id"],
        ),
        "permits": sorted(
            ({k: p.get(k) for k in ("id", "status", "delay_months", "evidence_id")} for p in permits),
            key=lambda x: x["id"],
        ),
        "overrides": {k: overrides[k] for k in sorted(overrides)},
    }


def compute(path: dict, milestones: list[dict], permits: list[dict], overrides: dict | None = None) -> dict:
    """path: power_paths row; milestones: delivery_milestones rows of this path; permits: permit_items rows of this path.
    overrides: {milestone_id: proposed own delay} for read-only previews."""
    overrides = dict(overrides or {})
    byid = {m["id"]: m for m in milestones}
    for mid in overrides:
        if mid not in byid:
            raise ScheduleError(f"Override for unknown milestone {mid}")
    memo, chain = {}, {}

    def own(m):
        if m["status"] == "completed":
            return 0
        return int(overrides.get(m["id"], m["delay_months"]) or 0)

    def shift(mid, stack=()):
        if mid in stack:
            raise ScheduleError("Milestone dependency cycle")
        if mid in memo:
            return memo[mid]
        m = byid[mid]
        if m["status"] == "completed":
            memo[mid] = 0
            chain[mid] = [mid]
            return 0
        pred = m.get("predecessor_id")
        up = shift(pred, stack + (mid,)) if pred and pred in byid else 0
        memo[mid] = up + own(m)
        chain[mid] = (chain[pred] if pred and pred in byid else []) + [mid]
        return memo[mid]

    acts = []
    for m in milestones:
        s = shift(m["id"])
        fl = int(m.get("float_months") or 0)
        pred = m.get("predecessor_id")
        inherited = s - own(m) if m["status"] != "completed" else 0
        acts.append(
            {
                "id": m["id"],
                "title": m.get("title"),
                "activity_type": CATEGORY_TO_TYPE.get(m.get("category"), "unclassified"),
                "status": m["status"],
                "predecessor_id": pred,
                "baseline_month": m.get("planned_month"),
                "own_delay_months": own(m),
                "inherited_delay_months": inherited,
                "shift_months": s,
                "float_months": fl,
                "cod_impact_months": max(0, s - fl),
                "revised_month": (m["planned_month"] + s) if m.get("planned_month") else None,
                "path_delay_to_here": s,
                "overridden": m["id"] in overrides,
                "evidence": "SOURCED" if (m.get("source_url") or m.get("evidence_id")) else "UNSOURCED",
            }
        )
    linked = {m["permit_id"] for m in milestones if m.get("permit_id")}
    open_permits = [p for p in permits if p["status"] != "approved"]
    unlinked = [p for p in open_permits if p["id"] not in linked]
    drivers = [{"kind": "path_estimate", "id": path["id"], "months": int(path.get("delay_months") or 0)}]
    drivers += [
        {"kind": "activity_chain", "id": a["id"], "months": a["cod_impact_months"], "chain": chain[a["id"]]}
        for a in acts
    ]
    drivers += [
        {"kind": "unlinked_open_permit", "id": p["id"], "months": int(p.get("delay_months") or 0)} for p in unlinked
    ]
    effective = max(d["months"] for d in drivers)
    critical = [d for d in drivers if d["months"] == effective and effective > 0]
    on_cp = {mid for d in critical if d["kind"] == "activity_chain" for mid in d["chain"]}
    for a in acts:
        a["on_critical_path"] = a["id"] in on_cp
    # Evidence quality and unresolved dependencies
    conflicts = []
    for m in milestones:
        if m.get("permit_id"):
            p = next((x for x in permits if x["id"] == m["permit_id"]), None)
            if (
                p
                and p["status"] != "approved"
                and m["status"] != "completed"
                and int(p.get("delay_months") or 0) != own(m)
            ):
                conflicts.append(
                    {
                        "milestone_id": m["id"],
                        "permit_id": p["id"],
                        "milestone_delay": own(m),
                        "permit_delay": int(p.get("delay_months") or 0),
                        "classification": "CONFLICTING_EVIDENCE",
                        "governs": "milestone",
                    }
                )
        pred = m.get("predecessor_id")
        if m["status"] == "completed" and pred in byid and byid[pred]["status"] != "completed":
            conflicts.append(
                {
                    "milestone_id": m["id"],
                    "issue": "completed milestone has an unfinished predecessor",
                    "classification": "CONFLICTING_EVIDENCE",
                }
            )
    unresolved = [
        {"id": m["id"], "status": m["status"]}
        for m in milestones
        if m["status"] in ("blocked", "awaiting", "submitted")
    ] + [
        {"id": p["id"], "status": p["status"], "kind": "permit"}
        for p in open_permits
        if p["status"] in ("blocked", "awaiting_third_party")
    ]
    inputs = _norm_inputs(path, milestones, permits, overrides)
    version = hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()[:20]
    critical_ids = sorted({d["id"] for d in critical})
    baseline_cod = path.get("power_month")
    return {
        "schedule_version": version,
        "method": METHOD_VERSION,
        "path_id": path["id"],
        "baseline_cod_month": baseline_cod,
        "revised_cod_month": baseline_cod + effective if baseline_cod else None,
        "effective_delay_months": effective,
        "critical_drivers": critical,
        "critical_path": critical_ids,
        "drivers": drivers,
        "activities": acts,
        "evidence_conflicts": conflicts,
        "unresolved_dependencies": unresolved,
        "evidence_quality": {
            "activities": len(acts),
            "sourced": sum(a["evidence"] == "SOURCED" for a in acts),
            "unsourced": sum(a["evidence"] == "UNSOURCED" for a in acts),
            "path_estimate_sourced": bool(path.get("evidence_id")),
            "utility_confirmed": False,
        },
        # backward-compatible keys used by v26.3 clients
        "source_power_month": baseline_cod,
        "path_delay_months": int(path.get("delay_months") or 0),
        "milestone_critical_delay_months": max([a["cod_impact_months"] for a in acts], default=0),
        "unlinked_permit_delay_months": max([int(p.get("delay_months") or 0) for p in unlinked], default=0),
        "modeled_power_month": baseline_cod + effective if baseline_cod else None,
        "linked_milestones": acts,
        "ready_to_assert_delivery": False,
        "available_mw_verified": False,
        "status": "UNVERIFIED SCENARIO; NOT UTILITY-CONFIRMED OR A DELIVERY FORECAST",
        "convention": "Delays accumulate along dependency edges; independent drivers run in parallel (COD moves by the longest); float reduces COD impact; path-level estimate never added.",
    }


def load(con, pid, pathid):
    path = con.execute("SELECT * FROM power_paths WHERE id=? AND project_id=?", (pathid, pid)).fetchone()
    if not path:
        return None, [], []
    ms = [
        dict(r)
        for r in con.execute("SELECT * FROM delivery_milestones WHERE path_id=? AND project_id=?", (pathid, pid))
    ]
    ps = [dict(r) for r in con.execute("SELECT * FROM permit_items WHERE path_id=? AND project_id=?", (pathid, pid))]
    return dict(path), ms, ps


def schedule_for(con, pid, pathid, overrides=None):
    path, ms, ps = load(con, pid, pathid)
    if path is None:
        return None
    return compute(path, ms, ps, overrides)


def apply_to_config(config: dict, path: dict, schedule: dict) -> dict:
    """The ONLY mapping from a schedule result to underwriting inputs (used by every sensitivity and preview).
    COD delay shifts energisation and lease commencement (engine delayMonths); construction spend timing is unchanged,
    so carry cost rises. Path capex and energy uplifts are path characteristics, applied identically with or without delay.
    """
    x = dict(config)
    x["delayMonths"] = int(config.get("delayMonths", 0)) + int(schedule["effective_delay_months"])
    x["constructionCostMW"] = float(config.get("constructionCostMW", 7)) * (1 + float(path["capex_uplift_pct"]) / 100)
    x["powerCostMWh"] = float(config.get("powerCostMWh", 85)) * (1 + float(path["energy_uplift_pct"]) / 100)
    if path.get("power_month") is not None or path.get("power_phases") is not None:
        phases = path.get("power_phases") or [{'month': path['power_month'], 'mw': path['capacity_mw']}]
        x = constrain(x, phases, path.get('capacity_basis', 'IT'))
    return x


def financial_impact(calculate, config: dict, path: dict, schedule: dict) -> dict:
    """Read-only baseline (path uplifts, no schedule delay) vs revised (path uplifts + schedule delay)."""
    base_cfg = apply_to_config(config, path, {**schedule, "effective_delay_months": 0})
    rev_cfg = apply_to_config(config, path, schedule)

    def summarise(cfg):
        r = calculate("underwrite", cfg)
        s, rows = r["summary"], r["rows"]
        first_rev = next((x["month"] for x in rows if (x.get("leaseRevenue") or 0) > 1e-9), None)
        # Carry cost of delay: interest incurred (paid in cash or capitalised into debt) while the campus earns no rent.
        pre_rev = [x for x in rows if first_rev is None or x["month"] < first_rev]
        carry_interest = sum((x.get("cashInterest") or 0) for x in pre_rev)
        carry_capitalised = sum((x.get("capitalizedInterest") or 0) for x in pre_rev)
        return {
            "power_periods": period_capacity(cfg, rows) if cfg.get('powerCapacityAssumptions') else None,
            "npvM": s.get("npvM"),
            "leveredIRR": s.get("leveredIRR"),
            "minDSCR": s.get("minDSCR"),
            "breach_months": len(s.get("breachMonths") or []),
            "liquidity_breach_months": len(s.get("liquidityBreachMonths") or []),
            "min_cashM": min(x["cash"] for x in rows),
            "interest_incurredM": s.get("interestM"),
            "cash_interest_paidM": sum(x.get("cashInterest") or 0 for x in rows),
            "capitalized_interestM": sum(x.get("capitalizedInterest") or 0 for x in rows),
            "sponsor_equityM": s.get("equityInvestedM"),
            "interest_paid_before_first_revenueM": carry_interest,
            "interest_capitalised_before_first_revenueM": carry_capitalised,
            "first_revenue_month": first_rev,
            "defaulted": s.get("defaulted"),
            "payment_default": s.get("paymentDefault"),
            "unpaid_lender_claims_at_exitM": s.get("unpaidLenderClaimsAtExitM", s.get("unpaidDebtAtExitM")),
            "screening": s.get("screeningReadiness"),
            "engine_version": s.get("engineVersion", "25.8.5"),
            "assumptions_hash": hashlib.sha256(
                json.dumps(cfg, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
            ).hexdigest(),
        }

    b, a = summarise(base_cfg), summarise(rev_cfg)
    d = lambda k: (a[k] - b[k]) if isinstance(a.get(k), (int, float)) and isinstance(b.get(k), (int, float)) else None
    return {
        "schedule_version": schedule["schedule_version"],
        "baseline": b,
        "revised": a,
        "deltas": {
            "npvM": d("npvM"),
            "leveredIRR": d("leveredIRR"),
            "minDSCR": d("minDSCR"),
            "carry_cost_interest_incurredM": d("interest_incurredM"),
            "carry_cost_interest_before_revenueM": (
                a["interest_paid_before_first_revenueM"] + a["interest_capitalised_before_first_revenueM"]
            )
            - (b["interest_paid_before_first_revenueM"] + b["interest_capitalised_before_first_revenueM"]),
            "cash_interest_paidM": d("cash_interest_paidM"),
            "revenue_commencement_months": d("first_revenue_month"),
            "min_cashM": d("min_cashM"),
            "breach_months": d("breach_months"),
            "sponsor_equityM": d("sponsor_equityM"),
        },
        "valuation_allowed": False,
        "label": "SCREENING SENSITIVITY - not a valuation; schedule is analyst-entered and not utility-confirmed",
    }
