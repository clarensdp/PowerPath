"""v30.3.2: assumption-only phased-rent bridge into the frozen Core Scientific note model.

This module never modifies transaction271's public-source inputs, its historical
single-date scenario, the note engine, or the underwriting engine. All site MW
are unverified illustrative values, and the first-installment trigger is NOT
inferred from the first/last energized phase.
"""

from __future__ import annotations
from datetime import date
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from server import transaction271 as note_model


class RentTranche(BaseModel):
    mw: float = Field(gt=0, le=10_000)
    power_month: int = Field(ge=1, le=240)
    construction_ready_month: int = Field(default=2, ge=1, le=240)
    lease_eligible_month: int = Field(default=1, ge=1, le=240)


class SiteSchedule(BaseModel):
    site: str = Field(min_length=1, max_length=100)
    tranches: list[RentTranche] = Field(min_length=1, max_length=30)


class NotePhasingIn(note_model.IllustrativeIn):
    site_schedules: list[SiteSchedule] = Field(default_factory=list, max_length=40)
    note_trigger: Literal["scenario_fixed", "explicit_hypothetical"] = "scenario_fixed"
    trigger_rent_commencement: date | None = None
    trigger_revenue_credit_abatement: date | None = None

    @model_validator(mode="after")
    def validate_trigger(self):
        dates = (self.trigger_rent_commencement, self.trigger_revenue_credit_abatement)
        if self.note_trigger == "explicit_hypothetical" and not all(dates):
            raise ValueError("Both hypothetical trigger dates must be supplied together")
        if self.note_trigger == "scenario_fixed" and any(dates):
            raise ValueError("Dates require note_trigger=explicit_hypothetical; no silent note schedule adjustment")
        if self.site_schedules and self.rent_shift_months:
            raise ValueError("rent_shift_months cannot accompany explicit site schedules; provide full phase dates")
        return self


def month_index(value: date):
    """May 2026 is month 1; every note payment through May 2031 maps to a month 1..61."""
    return (value.year - 2026) * 12 + value.month - 5 + 1


def build_phased_config(inputs: dict, data: NotePhasingIn):
    mw = inputs["site_leased_mw"]["value"]
    if not isinstance(mw, dict) or not mw:
        raise ValueError("No illustrative site MW catalog")
    sc = note_model.SCENARIOS[data.scenario]
    base_start = month_index(date.fromisoformat(sc["rent_commencement"])) + 1 + data.rent_shift_months
    overrides = {}
    for profile in data.site_schedules:
        if profile.site not in mw:
            raise ValueError(
                f"Unknown site {profile.site}; synthetic site names cannot be represented as issuer campuses"
            )
        if profile.site in overrides:
            raise ValueError("Duplicate site schedule: " + profile.site)
        actual = sum(t.mw for t in profile.tranches)
        if abs(actual - float(mw[profile.site])) > 1e-6:
            raise ValueError(
                f"Site {profile.site} tranches total {actual} MW, not the unverified reference {mw[profile.site]} MW"
            )
        overrides[profile.site] = profile.tranches
    cfg = {
        "engineVersion": "27.1.0",
        "months": 61,
        "calendarStartYear": 2026,
        "calendarStartMonth": 5,
        "ltc": 0,
        "mezzLtcPct": 0,
        "initialCash": 0,
        "minLiquidity": 0,
        "reserveTargetM": 0,
        "sponsorCommitmentM": None,
        "constructionCostMW": 0,
        "exitValueM": 0,
        "refinanceValueM": 0,
        "loanMaturityMode": "equity",
        "powerResponsibility": "tenant_direct",
        "rentPerKwMonth": data.rent_per_kw_month,
        "otherOpexPct": data.other_opex_pct,
        "fixedOpexM": data.fixed_opex_m_per_month,
        "discount": data.discount_rate_pct,
        "buildings": [],
    }
    phase_summary = []
    for site, site_mw in mw.items():
        tranches = overrides.get(site) or [
            RentTranche(
                mw=float(site_mw),
                power_month=max(1, base_start),
                construction_ready_month=2,
                lease_eligible_month=max(1, base_start),
            )
        ]
        for idx, t in enumerate(tranches, 1):
            # v30.3.3: the frozen engine's earliest readiness is month 2 (constructionMonths >= 1), so a
            # construction_ready_month of 1 is modeled as 2. Report the month the engine actually uses.
            start = max(t.power_month, max(2, t.construction_ready_month), t.lease_eligible_month)
            # Frozen engine uses constructionStart+constructionMonths as readiness. A 1-month build beginning at
            # month 1 yields month 2. Later readiness is represented exactly without rewriting financial formulas.
            if start > 61:
                # The underwriter still models a phase with no rent within the note's maturity horizon.
                start = min(start, 240)
            cfg["buildings"].append(
                {
                    "name": f"{site} / tranche {idx}",
                    "itMW": float(t.mw),
                    "constructionStart": 1,
                    "constructionMonths": max(1, t.construction_ready_month - 1),
                    "powerMonth": t.power_month,
                    "leaseMonth": t.lease_eligible_month,
                    "leaseTermMonths": 144,
                    "rentEscalatorPct": 2.5,
                }
            )
            phase_summary.append(
                {
                    "site": site,
                    "tranche": idx,
                    "mw": float(t.mw),
                    "power_month": t.power_month,
                    "construction_ready_month": t.construction_ready_month,
                    "lease_eligible_month": t.lease_eligible_month,
                    "modeled_rent_start_month": start,
                    "source": (
                        "USER_ASSUMPTION (not utility-confirmed or executed lease)"
                        if site in overrides
                        else "INHERITED single-date hypothetical scenario"
                    ),
                }
            )
    return cfg, phase_summary


def phased_note_preview(inputs: dict, data: NotePhasingIn, calculate):
    if data.scenario not in note_model.SCENARIOS:
        raise ValueError("Invalid note scenario")
    cfg, phases = build_phased_config(inputs, data)
    if data.note_trigger == "explicit_hypothetical":
        rc, ab = str(data.trigger_rent_commencement), str(data.trigger_revenue_credit_abatement)
    else:
        sc = note_model.SCENARIOS[data.scenario]
        rc, ab = sc["rent_commencement"], sc["revenue_credit_abatement"]
    fi = note_model.first_installment_date(rc, ab, inputs["maturity_date"]["value"])
    loan = calculate("fixed_note27", note_model.note_input(inputs, fi))
    result = calculate("underwrite", cfg)
    # Compare against legacy only with the exact same assumptions (not an issuer valuation).
    legacy_data = note_model.IllustrativeIn(
        **data.model_dump(
            exclude={"site_schedules", "note_trigger", "trigger_rent_commencement", "trigger_revenue_credit_abatement"}
        )
    )
    legacy = note_model.illustrative_project(inputs, legacy_data, calculate)
    monthly = {r["month"]: r for r in result["rows"]}
    # Liquidity path is evaluated EACH month (not just at semiannual note dates).
    # The note payment date falls on the 15th, but the illustrative underwriter supplies
    # monthly, not daily, receipts: cash during a coupon month is assumed available for it.
    # This is an explicit modeling limitation, NOT a contract-level funding calendar.
    note_due_by_month = {}
    for payment in loan["periods"]:
        m = month_index(date.fromisoformat(payment["date"]))
        note_due_by_month[m] = note_due_by_month.get(m, 0.0) + payment["interestM"] + payment["scheduledPrincipalM"]
    balance, peak_need, monthly_cumulative = 0.0, 0.0, {}
    for m in range(1, cfg["months"] + 1):
        balance += monthly[m]["cfads"] - note_due_by_month.get(m, 0.0)
        monthly_cumulative[m] = balance
        peak_need = max(peak_need, -balance)
    periods = []
    prev = 0
    total_mw = sum(p["mw"] for p in phases)
    first_rent = min((p["modeled_rent_start_month"] for p in phases), default=None)
    full_rent = max((p["modeled_rent_start_month"] for p in phases), default=None)
    for payment in loan["periods"]:
        m = min(month_index(date.fromisoformat(payment["date"])), cfg["months"])
        window = [monthly[k] for k in range(prev + 1, m + 1) if k in monthly]
        cfads = sum(r["cfads"] for r in window)
        lease_revenue = sum((r.get("leaseRevenue") or 0) for r in window)
        ds = payment["interestM"] + payment["scheduledPrincipalM"]
        cumulative = monthly_cumulative[m]
        statuses = [sum(p["mw"] for p in phases if p["modeled_rent_start_month"] <= k) for k in range(prev + 1, m + 1)]
        any_rent = any(x > 1e-6 for x in statuses)
        all_rent = bool(statuses) and all(x >= total_mw - 1e-6 for x in statuses)
        label = "full" if all_rent else ("partial" if any_rent else "none")
        periods.append(
            {
                "date": payment["date"],
                "from_month": prev + 1,
                "through_month": m,
                "rent_status": label,
                "lease_revenueM": lease_revenue,
                "cfadsM": cfads,
                "scheduled_debt_serviceM": ds,
                "balloonM": payment["balloonM"],
                "dscr_ex_balloon": cfads / ds if ds > 0 else None,
                "net_after_scheduled_debt_serviceM": cfads - ds,
                "cumulative_cash_before_reservesM": cumulative,
            }
        )
        prev = m
    dsra = float(inputs["dsra_balance_2026_06_30"]["value"])
    zero_rent_note = sum(p["scheduled_debt_serviceM"] for p in periods if p["rent_status"] == "none")
    return {
        "layer": "LAYER_3_ILLUSTRATIVE_PHASED_POWER_AND_NOTE_SENSITIVITY",
        "NOT_A_CORE_SCIENTIFIC_VALUATION": True,
        "scenario": data.scenario,
        "model_version": "30.3.2-note-phasing-alpha",
        "note_trigger_mode": data.note_trigger,
        "note_trigger_dates": {"rent_commencement": rc, "credit_abatement": ab},
        "first_installment_date": fi,
        "note_trigger_warning": "The trigger dates are hypothetical and are NOT inferred from power delivery. Executed indenture and all revenue-credit provisions must be reviewed.",
        "site_mw_classification": inputs["site_leased_mw"]["classification"],
        "total_unverified_it_mw": total_mw,
        "phase_schedule": phases,
        "first_rent_month": first_rent,
        "full_rent_month": full_rent,
        "periods": periods,
        "dsra_balanceM": dsra,
        "scheduled_service_before_any_rentM": zero_rent_note,
        "simple_pre_rent_reserve_gapM": max(0, zero_rent_note - dsra),
        "peak_cumulative_cash_funding_need_ex_balloonM": peak_need,
        "peak_funding_gap_after_static_dsra_ex_balloonM": max(0, peak_need - dsra),
        "headline_funding_metric": "peak_funding_gap_after_static_dsra_ex_balloonM",
        "simple_gap_note": "Lower bound only: counts note service in payment periods with zero rent and ignores shortfalls once any MW pays rent. Can read $0 while peak funding need remains large.",
        "cash_funding_method": "Monthly cumulative illustrative CFADS less scheduled note coupons and installments in their payment month, excluding maturity balloon. Assumes all monthly cash is available by the mid-month coupon date (optimistic timing approximation). Positive surplus carries forward; DSRA draws, other financing, taxes, contractual credits and opening operating cash are not modeled.",
        "balloon_at_maturityM": loan["summary"]["balloonM"],
        "legacy_single_date_reference": {
            "scheduled_service_before_any_rentM": legacy["pre_rent_debt_serviceM"],
            "simple_pre_rent_reserve_gapM": legacy["pre_rent_funding_gap_vs_dsraM"],
        },
        "delta_vs_legacy_simple_gapM": max(0, zero_rent_note - dsra) - legacy["pre_rent_funding_gap_vs_dsraM"],
        "source_scenario_not_mutated": True,
        "warnings": [
            "All per-site MW are unverified catalog figures; not confirmed leased capacity.",
            "All tranche dates are illustrative user assumptions, not executed utility or tenant milestones.",
            "No automatic debt trigger change; revenue credits and indenture definitions are not verified.",
            "This is not an actual Core Scientific liquidity assessment, financing shortfall or valuation.",
            "Reserve balance is held constant; permitted withdrawals and replenishment are unknown.",
            "Maturity balloon is excluded from the funding-need indicator and shown separately.",
        ],
        **note_model.G_BLOCKS,
    }


def install(app, db, calculate, require, base):
    @app.post(base + "/illustrative-power-paths")
    def illustrative_power_paths(pid: str, data: NotePhasingIn):
        with db() as con:
            inputs = require(con, pid)
        try:
            return phased_note_preview(inputs, data, calculate)
        except (ValueError, TypeError, KeyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
