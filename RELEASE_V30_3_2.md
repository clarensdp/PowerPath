# PowerPath v30.3.2 — Core Scientific Phased Power / Note Cash-Flow Alpha

**29 October 2026. Additive, local-only, read-only screening sensitivity.** This release builds on v30.3.1 and preserves frozen v27.1 engines, earlier feasibility versions and historical Core Scientific scenarios.

## What actually changed

1. **Phased rent in the Core Scientific illustrative Layer 3 case.** New `POST /api/projects/{pid}/transactions/core-scientific-2026/illustrative-power-paths` accepts site-specific power tranches: each tranche's MW, power month, construction-readiness month and lease-eligibility month. The five unverified illustrative site capacities are Denton 260 MW, Dalton 175 MW, Muskogee 70 MW, Marble 65 MW, Austin 20 MW (590 MW combined). Every override must reconcile exactly to its own site's total MW. Unspecified sites retain the selected single-date hypothetical scenario. Synthetic Site G/H (200 MW each) cannot silently be used as Core campus data.
2. **Frozen engine calculations, not a new finance engine.** Each tranche is passed as a distinct building through `underwrite` (v27.1.0); monthly CFADS and lease revenue are aggregated into semiannual payment periods from `fixed_note27`. Existing revenue assumption and 144-month illustrative leases are unchanged. All outputs are labeled *hypothetical*, not actual Core Scientific earnings or a project valuation.
3. **Note payment trigger stays independent of the power date.** The issuer's 2029-11-15 modeled first installment remains fixed for the `base` case. Another hypothetical first installment can be modeled ONLY by supplying *both* an explicit hypothetical rent-commencement date and a hypothetical revenue-credit abatement date. Power energization alone does not establish the contractual trigger.
4. **Two explicit reserve stress definitions.** (a) `simple_pre_rent_reserve_gapM`: note coupon/regular installments in payment periods with no energized/rent-eligible MW, minus the $344.8M reference DSRA; comparable to the previous simplistic $428.84M metric. (b) `peak_funding_gap_after_static_dsra_ex_balloonM`: maximum cumulative negative monthly CFADS less scheduled coupons/principal, offset against the **same static reference** DSRA, excluding the terminal balloon. The figures are different because phased rent can start during a payment period and monthly CFADS can still be insufficient to cover coupons. This is an illustrative funding indicator, NOT a conclusion about real liquidity: actual DSRA release/replenishment, other cash/debt sources, rent credits, contracted payment timing and issuer financing are unverified. Monthly cash is optimistically assumed available for mid-month coupon payments.
5. **Transaction Review UI.** A two-tranche input panel lets a local analyst select a hypothetical campus, choose the MW and first/full power dates, compare the gap against the unchanged single-date reference, and see the note-date CFADS and debt service. All values render as text, not HTML. G4/G5 remain BLOCKED.

## Numerical proof (synthetic only)

At the identical default note trigger and rent assumption, moving 100 of Denton's illustrative 260 MW to month 20, with the other 160 MW in month 40, gives:

| Measure | Original single-date scenario | Phased example |
|---|---:|---:|
| First modeled rent month (May 2026 = 1) | 39 | 20 |
| Full modeled rent month | 39 | 40 |
| Model first installment | 2029-11-15 | 2029-11-15 |
| Note service before **any** rent | $773.64M | $390.02M |
| Static DSRA reference | $344.80M | $344.80M |
| Simple pre-rent gap | **$428.84M** | **$45.22M** |
| Peak cumulative cash gap vs static DSRA, excluding balloon | $428.84M | **$164.52M** |

These figures are model sensitivities based on **unverified site MW, hypothetical rent, hypothetical tranches** and a static reserve. They do not imply the actual Core Scientific gap is $164.52M or $45.22M. Note that the $2.54B base-case maturity balloon is excluded from the peak funding indicator and remains a separate refinancing obligation.

## Validation / release gate

- 61 targeted note-phasing and feasibility/bridge tests passed in one isolated test group (11 new tests).
- 12 legacy API tests passed separately; 11 canonical scheduler tests passed separately.
- 16 Core Scientific existing note verification tests and 3 institutional-workspace tests passed in their own processes.
- JS syntax checks passed, including the new transaction-workspace.js.
- SHA-256 of all **12 frozen engine files** matches `ENGINE_HASH_AUDIT_V30_3.json`. No file in `engine/` changed.
- Baseline scenario reproduces the existing $428.84375M simple reserve gap exactly; new API is read-only and preserves input versions.

**Why the test groups run separately:** the existing test modules set different process-wide `POWERPATH_DATA_DIR` and authentication modes during import. Combining them in one pytest collection can make an otherwise passing API test read another test group's blank SQLite database. Run the documented groups separately; the CI harness needs later isolation cleanup.

## Try locally

```bash
pip install -r requirements.txt -r requirements-feasibility.txt
npm run check
python -m pytest -q tests/v271/test_note_phasing332.py feasibility/test_v831_bridge_proof.py feasibility/test_v83_financial_bridge.py feasibility/test_v82_integration.py feasibility/test_phase1.py
python -m pytest -q tests/test_api.py tests/test_public30.py
python -m pytest -q tests/v271/test_schedule_parity.py
python -m pytest -q tests/v271/test_core_scientific.py
python -m pytest -q tests/v271/test_v272_workspace.py
./run_local.sh
```

Open `http://127.0.0.1:8768/transaction-workspace` and load a project where the existing Core Scientific illustrative model has been registered. See `examples/note_phasing_request.json` for an API request and `examples/note_phasing_proof.json` for an example output. The route performs no write to DB or linked files.

## Still BLOCKED / not claimed

- **No verified real mapping from data-center site contracts or PowerPath schedule27 records to Core Scientific campuses**: the analyst provides phased dates. Auto-sourcing, authoritative executed lease dates and revenue-credit triggers remain future integration work.
- Hybrid's v8.2 per-path rather than per-tranche air permit delay remains unchanged and requires a separately versioned workbook v8.3 and fixtures.
- No verified executed note/lease or DSRA terms; no actual Core Scientific liquidity, lender certification, valuation, debt sizing, or security opinion.
- Contract draw schedule, tax/tariff assumptions, curtailment allocation, G4/G5 human signoff remain unverified or blocked.
