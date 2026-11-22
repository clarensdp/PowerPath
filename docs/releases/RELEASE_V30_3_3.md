# PowerPath v30.3.3 — Note Phasing Proof

**29 October 2026. Additive patch to v30.3.2. Read-only, local-only. No engine, note-model input or historical scenario changed.**

## Independent verification of v30.3.2

| Check | Result |
| --- | --- |
| Release gate | 61 + 12 + 11 + 16 + 3 tests pass in their documented groups; JS check passes |
| Engine integrity | All 12 engine files match `ENGINE_HASH_AUDIT_V30_3.json` |
| Identity | Restating every campus at the single-date schedule reproduces the no-override result exactly |
| Neutral split | Splitting Denton into two tranches on the same date changes nothing |
| Monotonicity | Delaying a tranche never lowers pre-rent note service or peak funding need |
| Reconciliation | Semiannual CFADS equals the engine's monthly CFADS ($2,313.61M in the phased example) |
| Note calendar | Power at month 3 for every campus leaves the first installment at 2029-11-15 and every scheduled payment unchanged |
| Legacy parity | No-override simple gap equals the legacy figure in all four scenarios (early $45.22M, base $428.84M, delayed $684.59M, no trigger $812.47M) |
| Rendering | New UI writes values with `textContent`; no HTML injection path |
| Rent-start reporting | **Failed at one edge:** `construction_ready_month = 1` was reported as rent month 1, but the engine starts rent in month 2. Fixed below |

## What the sweep shows: the simple gap is not a usable shortfall measure

Denton tranche 1 (100 MW) moved from month 10 to 38, with the other 160 MW at month 40. Base note trigger, static $344.8M DSRA, balloon excluded.

| Tranche 1 power month | Note service before any rent | Simple gap | Peak funding need | Peak gap after DSRA |
| ---: | ---: | ---: | ---: | ---: |
| 10 | $134.27M | $0 | $358.45M | $13.65M |
| 14 | $262.14M | $0 | $419.72M | $74.92M |
| 18 | $262.14M | $0 | $479.45M | $134.65M |
| 22 | $390.02M | $45.22M | $539.19M | $194.39M |
| 26 | $517.89M | $173.09M | $598.92M | $254.12M |
| 30 | $517.89M | $173.09M | $657.16M | $312.36M |
| 34 | $645.77M | $300.97M | $715.40M | $370.60M |
| 38 (= single date) | $773.64M | $428.84M | $773.64M | $428.84M |

- The simple gap reads $0 at month 18 while the peak gap is $134.65M. 100 MW of rent (about $87M a half-year of CFADS) does not cover roughly $128M of coupons a half-year, so the deficit keeps building after rent starts.
- The simple gap moves in steps at semiannual payment dates; the peak gap moves smoothly at about $15M for each month the tranche slips.
- So the peak gap is the shortfall measure. The simple gap is only a lower bound.

## Changes

1. **Rent-start reporting matches the engine.** `modeled_rent_start_month` now uses `max(2, construction_ready_month)`, because the frozen engine's earliest readiness is month 2. Reported first and full rent months and period rent status now equal the engine's.
2. **Peak gap is the headline.** The response adds `headline_funding_metric` and a `simple_gap_note`. The Transaction Review panel lists the peak gap first, then the peak need before DSRA, then the simple gap labelled as a lower bound, then the legacy figure.
3. **Proof tests.** `tests/v271/test_note_phasing333.py` (8 tests) covers identity, neutral split, monotonicity, lower bound, CFADS reconciliation, rent-start consistency, the fixed note calendar and legacy parity.
4. Version strings bumped to 30.3.3.

## Still open

- **No link from PowerPath power paths to Core Scientific tranches.** v8.2 path months are relative to project start, while the note model counts from May 2026. An adapter needs a calendar anchor per campus (for example, a dated notice to proceed) before a path's first and full power can become note-model tranches.
- Static DSRA, optimistic mid-month cash timing, unverified campus MW and hypothetical rent all stand as documented in v30.3.2. G4/G5 remain BLOCKED.
- Hybrid per-tranche gate delays still need workbook v8.3.

## Tests

```bash
npm run check
python -m pytest -q tests/v271/test_note_phasing333.py
python -m pytest -q tests/v271/test_note_phasing332.py feasibility/test_v831_bridge_proof.py feasibility/test_v83_financial_bridge.py feasibility/test_v82_integration.py feasibility/test_phase1.py
python -m pytest -q tests/test_api.py tests/test_public30.py
python -m pytest -q tests/v271/test_schedule_parity.py
python -m pytest -q tests/v271/test_core_scientific.py
python -m pytest -q tests/v271/test_v272_workspace.py
```

Changed: `server/note_phasing.py`, `web/public/transaction-workspace.js`, `server/app.py` (version), `package.json` (version). Added: `tests/v271/test_note_phasing333.py`, this note, `SHA256_MANIFEST_V30_3_3.json`.
