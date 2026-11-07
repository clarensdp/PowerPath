# PowerPath v30.3 — Financial Bridge Alpha

**29 October 2026. Local-only, read-only finance previews.**

## Scope delivered

The v8.2 feasibility screen is now connected to the existing *frozen* PowerPath v27.1 underwriting model through a separate, audited mapping layer, `feasibility/v82/financial_bridge.py`. For each candidate path still viable under its applicable gate matrix, a preview uses the source feasibility snapshot and original versioned financial scenario. It does **not** save or rewrite scenarios, underwriting runs, lease contracts or engineering schedules.

### Financial bridge mapping

- Grid, behind-the-meter, hybrid and flexible load are separately underwritten when a candidate path survives screening. No-go paths are excluded. Provisional paths remain explicitly provisional and never become a Go solely because their cash flows appear attractive.
- `schedule27` still determines gate-sensitive first-power and full-load dates. Each chosen path supplies its own capacity tranches to v27.1's native `powerTranches` input. The underlying building construction readiness, lease commencement assumptions and lease credit terms remain intact, so earlier electric service cannot invent a rent commencement date.
- Selected-path **capital uplift plus remediation** is mapped once into existing per-IT-MW construction cost. Underwriting `overrunPct` is accounted for so the fixed incremental $M is not multiplied a second time. Until payment schedules are documented, this is an explicit *construction-spread proxy*, not a contractual equipment payment waterfall.
- Flexible-load curtailment is a **compute-value exposure**, not assumed landlord expense. Default comparison leaves the value informational. An explicitly acknowledged `owner_contractual_revenue` scenario maps an annualized constant curtailment burden into the existing rent-schedule inputs. It rejects contract-total/scheduled-rent inputs rather than overwriting a rent contract, and cannot be called a proved allocation or actual dispatch simulation.
- The baseline uses the original unlinked v27.1 financial scenario. Preview results include NPV, levered IRR, minimum DSCR, first rent, equity, net cash, monthly-derived construction cost, available MW, funding/default/breach flags, risk warnings, input and configuration hashes, and original scenario version.
- G4 and G5 always return `BLOCKED`; no lender certification, contract valuation or optimal economic-path endorsement is asserted. The earlier historical and live-test predictions are unchanged.
- A new project-first Power Deliverability page is accessible at `/power-deliverability` and linked from Compare Options. It displays financial comparisons and synthetic Site G/H demonstration data (only for **200 IT MW** projects). It never presents the synthetic inputs as real land or utility service.

### API

Create v8.2 screen via the existing route `POST /api/projects/{pid}/feasibility` and retain `run_id`.

```http
POST /api/projects/{pid}/feasibility/{run_id}/financial-preview
Content-Type: application/json

{"source_scenario_id":"<original scenario id>","curtailment_allocation":"tenant_or_compute_operator"}
```

The endpoint recomputes all surviving path alternatives from the immutable source run. A changed feasibility scoring config invalidates old finance previews until a new immutable feasibility run is created. Original source scenario must have `engineVersion: "27.1.0"`, `delayMonths: 0`, no prior `powerTranches`/`powerPathLink`, and buildings whose summed IT MW exactly matches the feasibility project's target. A different lease/owner allocation can be explored using `"curtailment_allocation":"owner_contractual_revenue","acknowledge_contract_assumption":true`, but this is a *new assumption*, not an executed contract.

This endpoint is deliberately disabled in `POWERPATH_V27_AUTH_MODE=required` until reviewed for multi-tenant role-based permissions, and shares the existing loopback-only host restrictions.

## Tests

From the package root:

```bash
pip install -r requirements.txt -r requirements-feasibility.txt
python -m pytest -q feasibility/test_v83_financial_bridge.py feasibility/test_v82_integration.py feasibility/test_phase1.py tests/test_api.py tests/test_public30.py
python -m pytest -q tests/v271/test_schedule_parity.py
npm run check
node --check web/public/power-deliverability.js
```

Release-gate result: **51 tests passed** in combined v30.3 + v30.2 + core APIs; **11 canonical v27.1 schedule tests passed** separately; JS syntax check passed. The original 32 v8.2 site/mode parity cases continue passing. Frozen financial engine directory was checked file-by-file against v30.2; 12/12 files have identical SHA-256 digests (see `ENGINE_HASH_AUDIT_V30_3.json`).

### Explicit non-goals / blockers

1. **No real project DB path sourcing yet.** v8.2 feasibility still accepts externally supplied path assumptions; stored v30 paths have only one `power_month` and no independently sourced full-load capacity curve or signed service evidence. Map dated utility and equipment milestones to v8.2 path keys before using real project assessments.
2. **No actual contract payment timing yet.** Spread-capex proxy needs replacement with contractual draw dates, owner-vs-tenant allocations, equipment and interconnection payments, and actual minimum-demand tariff obligations. Extra $M appears exactly once in modeled construction due, not an independently audited cash-draw calendar.
3. **No dispatch engine for flexible load.** Curtailment is an annualized economic sensitivity, not 300 specific dispatched hours and not an established effect on landlord rent without contractual proof.
4. **No lender validation** or external expert signoff; G4/G5 remain BLOCKED and values are scenario screening outputs.
5. **Real NC/VA parcel evidence/PP-SITE lineage, staged MW procurement, authenticated RBAC and unaltered historical outcomes** still require separate end-to-end pilot work. Full mixed historical test suite is not claimed green due to import-time security mode conflicts; run test groups in isolated modes.

### Governance

This is an additive release. No files in `engine/` were changed. No persistent financial scenarios or runs are created by the financial preview endpoint. The original workbook v7/v8/v8.1/v8.2, v8.2 fixtures, and frozen predictions remain untouched. Two planned future live-test checks remain **2027-04-28** and **2027-10-28**.
