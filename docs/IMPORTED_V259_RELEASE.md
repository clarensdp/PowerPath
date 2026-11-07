# PowerPath v25.9.0-risk1 — Release Note

**Date:** 26 Oct 2026. **Workstreams:** CFO+CTO (engine), Independent Reconciliation (reference), CPO+Design (interface), Risk (gates and review). **Status:** screening tool. **Transaction valuation and lender certification are BLOCKED for all 16 public cases**, by policy and in code.

## What shipped
| Workstream | Deliverable | Verification |
|---|---|---|
| CFO + CTO | `engine-v259`: fixed-rate note facilities (OID, stub coupons, semiannual payments, amortization types, event-based start triggers, balloon, four DSRA types, draw before sponsor, facility DSCR, lock-ups, construction lock-up, priority of payments, exit waterfall); transaction templates with evidence labels (`data/transactions_v259.json`) | `npm run ci` green: **61/61 tests**; 720-run golden snapshot unchanged; facilities-absent output byte-identical over 256 cases |
| Reconciliation | `reference-v259`: separate Python implementation built from the spec only (independence enforced; no engine code read) | 71,519 self-checks pass; **engine vs reference: 56 cases, 173,768 required-field checks, 0 disagreements** |
| CPO + Design | `ui-v259/PowerPath_Institutional.html`: 3-destination app (Portfolio, Evidence library, Method and limits), with a project record (Summary, Power, Finance, Debt facilities, Evidence, Decisions); engine embedded byte-for-byte | **47/47 browser checks** (1440 and 390 px, light and dark, zero page errors) |
| Risk | `assurance.cjs` + `RISK_POLICY.md`: G0–G5 gates and permitted uses | Policy tests in CI; all 16 cases BLOCKED for valuation and certification |

## Defects found by the process and fixed before release
1. **Look-ahead amortization trigger (spec Amendment 1, AM1/AM2).** The engine resolved "after first rent" in month 1 from the planned schedule. The construction DSRA (Galaxy $285M, Core $343M) never applied, and a halted campus kept amortizing.
2. **Balloon in the final model month (AM4).** It was paid before exit, so unpaid-at-exit was impossible; it is now settled in the exit waterfall.
3. **No construction lock-up (AM3).** Unspent note proceeds (about $1.4–1.7B in test cases) were distributed in the issue month while the sponsor then funded capex. Both teams had implemented this literal spec flaw.
4. **Facility DSCR failures did not block readiness (risk1).** A Polaris Forge 1 notes scenario with all 10 DSCR tests at 0.00–0.53× showed "CONDITIONAL". It now shows "BLOCKED", with a credit warning and a certification block.
5. **Conflicting gate definitions in the UI.** The interface had invented its own G0–G5. It now uses the Risk module, and its own checks are renamed E1–E3.

## Still blocked or open
- **Installment schedules, distribution tests and waterfalls** (indenture §14.01 / 4.05 / 4.23) are not public. APLD 2030 amortization is "unknown → bullet assumed" with a warning; ComputeCo 2 and 3 are not modelable (dates unknown).
- Single project cash pool: no ring-fencing, excess-cash-flow offers, make-whole, default interest or arrears balance (warnings emitted).
- The Polaris Forge 1 notes scenario maps buildings by MW order (synthetic). The Helios and Core notes are shown as terms only.
- The inherited input issues stay open: landlord-pays power default in the frozen cases, $7M/MW capex vs $11–13M guidance, unsourced pass-through for PF3/DF2.
- G4 (executed-document reconciliation) and G5 (qualified human review) have not started. No arithmetic result here is lender validation.

## Specs
`FACILITY_SPEC_v259.md` + `FACILITY_SPEC_v259_AMENDMENT_1.md`. Each team's ambiguity resolutions are recorded in `engine-v259/ENGINE_V259_REPORT.md` and `reference-v259/REFERENCE_V259_NOTES.md`.
