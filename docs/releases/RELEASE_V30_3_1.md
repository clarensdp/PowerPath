# PowerPath v30.3.1 — Financial Bridge Proof

**29 October 2026. Additive patch to v30.3. Local-only, read-only previews. Engine files unchanged.**

## Why

v30.3 wired each v8.2 power path into the frozen v27.1 underwriter. Its tests run on an unlevered scenario (`ltc=0`), where DSCR and financing shortfall are undefined. This patch proves the bridge on a leveraged scenario and fixes three gaps the leveraged runs exposed.

## Independent verification of v30.3 (all pass)

| Check | Result |
| --- | --- |
| Engine routing | `underwrite` resolves to `underwrite27.js` from `engineVersion: 27.1.0` |
| Engine integrity | All 12 engine files match `ENGINE_HASH_AUDIT_V30_3.json` (now a test) |
| Identity | A month-1, zero-capex, zero-curtailment path reproduces the leveraged baseline exactly |
| Rent commencement | Each month of power delay moves first rent by exactly one month (tested 0–24 months) |
| Construction binding | Power at month 17 with construction done at 18 starts rent at 19, not 17 |
| Phased rent | 100 MW tranche earns rent in proportion to energized MW; full rent at the second tranche |
| Capex once | Capex rises by exactly the path amount at 65% LTC and 15% overrun; the extra in `constructionDue` is the 1% debt fee on the larger draw, which is correct |
| Attribution | Schedule + capex + curtailment NPV steps sum to the total; signs are correct |
| Fallback | A failed flexible-load agreement leaves only the grid path |

## Fixes

1. **Financing shortfall was not reported, and minimum DSCR could not rank paths.** When cash interest starts before rent, minimum DSCR is 0 for every path. The summary now adds `pre_rent_debt_service_musd`, `months_debt_service_before_rent`, `uncovered_debt_service_musd`, `pre_rent_sponsor_carry_musd`, `stabilized_min_dscr` (from full rent) and `full_rent_month`, plus `peak_debt_musd` and `sponsor_remaining_musd`. All are read from the engine's monthly rows; no new financial math is added. The Power Deliverability table shows stabilized DSCR and pre-rent debt service.
2. **Path capex could be part-funded by the tenant without a contract.** v27.1 applies `tenantCapexPct` to all construction cost, so bridge power capex added through `constructionCostMW` was shared with the tenant (30% of $100M in the probe). The bridge now rejects that unless `acknowledge_tenant_capex_share=True`, and records the share in the audit.
3. **Scenario power dates could silently cap the comparison.** A building's own `powerMonth`/`leaseMonth` later than construction readiness already embeds a power assumption, so a faster path shows no benefit. The audit now lists `binding_building_power_dates`, and the path gets a warning. Use a power-neutral source scenario (power and lease month at or before construction completion) for path comparisons.

## Proof on a leveraged 200 MW campus

Source scenario: v27.1 defaults (65% LTC, 8% rate, 1.20x covenant, $170/kW-month), one 200 MW building, 18-month construction (ready month 19), power-neutral, 180-month horizon. Fixture Sites G and H. Illustrative only.

| Site / path | First / full power | First rent | NPV | Equity IRR | Stabilized DSCR | Pre-rent debt service | Sponsor equity |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline (unconstrained power) | — | 19 | $575.5M | 20.67% | 2.02x | $0 | — |
| G Hybrid | 17 / 44 | 19 | $303.5M | 14.77% | 2.01x | $0 (ramp month DSCR 0.92x) | $750.1M |
| G Grid | 42 / 42 | 42 | $229.4M | 13.51% | 2.02x | $148.7M over 23 months | $798.7M |
| H Flexible (curtailment memo) | 22 / 22 | 22 | $521.5M | 19.28% | 2.02x | $19.5M over 3 months | $673.5M |
| H Flexible (owner bears $12.3M/yr) | 22 / 22 | 22 | $452.7M | 18.01% | 1.88x | $19.5M | $674.4M |
| H Grid | 40 / 40 | 40 | $256.6M | 13.97% | 2.02x | $135.8M over 21 months | $785.8M |

Hybrid beats grid at Site G by $74M of NPV after its $90.4M bridge capex, because it avoids $148.7M of uncovered carry. At Site H, flexible load stays ahead of grid even if the landlord bears all curtailment.

## Open items (not fixed here)

- **Hybrid full-load timing (v8.2 rule).** The air-permit delay shifts the whole hybrid path, so the grid tranche reaches full load at 44 instead of 42. This understates hybrid. Fixing it changes the frozen v8.2 fixtures, so it belongs in v8.3: gate delays should apply per tranche.
- **Core Scientific note case is not connected.** `transaction271.py` uses a single rent-commencement date per scenario; the $773.6M pre-rent note service and $428.8M reserve gap do not move with power paths yet. Next step: feed each path's tranche dates into `illustrative_project` as phased rent starts.
- v30.3 blockers 1–5 (real path sourcing, contract draw timing, dispatch, lender validation, pilot evidence) still apply. G4/G5 remain BLOCKED.

## Tests

```bash
python -m pytest -q feasibility/test_v831_bridge_proof.py feasibility/test_v83_financial_bridge.py feasibility/test_v82_integration.py feasibility/test_phase1.py tests/test_api.py tests/test_public30.py
python -m pytest -q tests/v271/test_schedule_parity.py
npm run check
```

Result: 62 passed (51 from v30.3 + 11 new), 11 schedule parity passed, JS check passed.

Changed files: `feasibility/v82/financial_bridge.py`, `web/public/power-deliverability.js`. Added: `feasibility/test_v831_bridge_proof.py`, this note, `SHA256_MANIFEST_V30_3_1.json`.
