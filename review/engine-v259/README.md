# @powerpath/engine

PowerPath's monthly underwriting engine as a standalone package. It is pure and deterministic, with no DOM, storage, network or clock access, so the same code runs in the browser app, on a server and in audits. Units are $M, MW and months.

**Status:** v25.9.0 adds debt-facility (fixed-rate notes) integration (see below). Roadmap step 1 (engine separation): The source is the red-team-patched v25.8.4 engine (`v25.8.4-ca.1`), split from the UI and formatted, **with behaviour unchanged**. Across 751 scenarios the package's output is byte-identical to the patched single-file build, and it is identical again in the browser.

## Layout

| Path | What it is |
|---|---|
| `src/underwrite.cjs` | The engine: `evaluate()`, `defaults()`, `irr()`, `rentAudit()` |
| `src/facilities.cjs` | v25.9 fixed-rate note facilities (validation, schedule, DSRA, DSCR, lock-up, exit), used by `evaluate()` |
| `src/notes.cjs` | Standalone fixed-rate notes calculator (day-count 30/360 stubs; separate from the v25.9 monthly facility ledger) |
| `data/transactions_v259.json` | Public notes facility templates with evidence labels and fact IDs (inputs, never hard-coded) |
| `scripts/demo_facilities.cjs` | Runs each modelable template on a **synthetic** campus (`npm run demo:facilities`) |
| `src/index.cjs`, `src/index.d.ts` | Public entry point and TypeScript declarations for every input, monthly row and summary field |
| `ui/underwrite-panel.js` | Browser underwriting panel; contains no financial logic and reads `window.PowerPathEngine` |
| `test/legacy/` | The 10 bundled engine suites from v25.8 |
| `test/redteam_*.test.cjs` | 20 red-team regression checks (refinance annuity, tranches, units, funding-default halt, lease tail, reimbursement lag, …) |
| `test/golden.test.cjs` | 16 public cases × 45 stresses = 720 runs; each run's monthly rows are hashed, so any output change fails until reviewed |
| `test/types_drift.test.cjs` | Fails if `index.d.ts` and the runtime output disagree by a single field, with and without facilities |
| `test/amendment1.test.cjs` | Amendment 1 (AM1-AM5) tests: each passes on the current engine and fails on the frozen pre-amendment engine |
| `test/facilities.test.cjs` | 26 v25.9 facility tests, including byte-identity against the frozen v25.8.4-ca.1 engine (`test/fixtures/underwrite_v2584ca1.cjs`) |
| `test/purity.test.cjs` | Fails if the engine gains DOM, storage, network, clock or randomness dependencies |
| `reference/` | A separately written Python ledger plus 31 cases; `npm run test:reference` compares every monthly field |
| `scripts/build_browser.cjs` | Writes `dist/powerpath-engine.js` and `dist/underwrite-panel.js` with SHA-256 sums |
| `.github/workflows/ci.yml` | Runs everything below on every push |

## Commands

```bash
npm ci
npm run ci              # format check, strict typecheck, tests, reference parity, browser build
npm run golden:update   # only when an output change is intended; review the diff
```

Results at v25.9.0 with Amendment 1: 18 test files and 49 tests pass (26 in `test/facilities.test.cjs`, 6 in `test/amendment1.test.cjs`; each AM1-AM4 test also proves the pre-amendment engine in `test/fixtures/underwrite_v259_pre_am1/` fails). The golden snapshot is unchanged, and reference parity is unchanged at 80,240 checks with a max gap of 1.4e-12 $M (those cases have no facilities; the Python reference does not yet model them).

Results at v25.8.4-ca.1: 16 test files pass; reference parity is 80,240 checks with a max gap of 1.4e-12 $M; types match the runtime at 73 row fields and 62 summary fields.

## v25.9: debt facilities (fixed-rate notes)

`evaluate({ ..., ltc: 0, mezzLtcPct: 0, facilities: [...] })` models one or more fixed-rate notes per `FACILITY_SPEC_v259.md`; where the spec is ambiguous, the resolution is listed in `ENGINE_V259_REPORT.md`. Without `facilities`, or with an empty array, every output is byte-identical to v25.8.4-ca.1. The golden snapshot is unchanged, and `test/facilities.test.cjs` diffs the full JSON output against a frozen copy of the original engine over 256 cases.

- **Inputs:** `Facility` in `src/index.d.ts`. Fields are face, coupon, issue price, fee; issue, first-payment and maturity months or ISO dates; collateral `buildings`; `priority`; amortization (`none`, `unknown`, `pctOriginalPerYear`, `explicit`) and its start (`fixedMonth`, `afterFirstRent`, `afterFinalCommencement`); DSRA (`none`, `fixed`, `nextPeriod`, `constructionThenNextPeriod`); `lockupDscr`; and per-term `evidence`.
- **Generic debt is disabled.** With facilities, `ltc` and `mezzLtcPct` must be 0 (the default `ltc` of 65 throws). The generic refinance path is inert.
- **Amortization start and construction lock-up are event-based** (Amendment 1): nothing is resolved before the triggering event has happened on the schedule current at that month.
- **Monthly order:** sources and uses (proceeds, fees, interest, principal), then facility DSRA draws before sponsor support, then sponsor support (cap respected), then facility DSRA funding (cash above minimum liquidity first, then sponsor), then the base reserve, then lock-up, then distributions, then the exit.
- **Outputs:** facility-only row fields (`notesProceeds`, `facilityDebtService`, `facilityDsra`, …, `facilityLockup`), plus `summary.facilities[]` (per-facility schedule, DSCR tests, lock-up and DSRA-deficiency months, balloon, evidence, warnings) and `summary.facilityPaymentShortfallMonths`. These fields are emitted only when facilities are modeled.
- **Templates:** `data/transactions_v259.json` holds five public notes facilities. Two are marked `"modelable": false` because their payment and maturity dates are Unknown, and the engine refuses any facility marked that way. Terms without a stated label are recorded as `Public approximate` with no fact ID. Every term that is not Executed produces a warning.
- `ENGINE_V259_REPORT.md` lists every spec ambiguity and how it was resolved.

### v25.9 limitations (spec §9 and §11)
- A **single project cash pool**. Ring-fenced per-facility waterfalls, cash sweeps and excess-cash-flow offers are not modeled; a warning is always emitted.
- **Payment shortfalls are not arrears.** A facility payment is always recorded as made, and any shortfall shows as `unfundedGapM` (a funding default). There is no arrears balance and no default interest.
- **Fixed rates only.** No floating rates, PIK, make-whole or redemption premia, covenant cure, tax on OID, or intercreditor terms beyond `priority`. OID is reported, not amortized. `rateShockPct` does not apply to fixed coupons.
- **Interest uses a month-count proxy** (coupon/1200 per model month, 30/360-like). Calendar days are ignored; `src/notes.cjs` remains the day-count audit calculator.
- **Amortization start is derived from the modeled schedule.** `afterFirstRent` and `afterFinalCommencement` are resolved from the modeled physical schedule, not from contractual notices, and are flagged as such. `unknown` amortization is modeled as a bullet, which understates debt service.
- **Facility DSCR allocates project CFADS** by collateral lease-revenue share. It is a screening test, not the indenture's definition.
- **Amendment 1 (`FACILITY_SPEC_v259_AMENDMENT_1.md`):**
  - AM1: amortization start is event-based, with no look-ahead. A halted campus whose collateral never rents never amortizes.
  - AM2: `constructionThenNextPeriod` holds the construction amount until the event month E.
  - AM3: distributions are locked until every collateral building pays rent, so unspent proceeds fund capex.
  - AM4: a maturity in the final model month settles in the exit waterfall, so `unpaidAtExitM` can be positive.
  - AM5: adds `constructionEndMonth`, `constructionLockupEndMonth` and `rows[].facilityConstructionLockup`.
- **Arithmetic agreement is not lender validation.** The templates are inputs to be confirmed against executed documents.

## Rules for changing the engine
1. Every behaviour change ships with a test that fails before and passes after.
2. If outputs change, update the golden snapshot in the same commit and explain why.
3. Extend `reference/powerpath_reference.py` independently. Never copy engine output into it.
4. Bump `version`; the browser build stamps it and the SHA-256 sums into `dist/`.

## Not done yet (next steps)
- **1b:** convert `src/underwrite.cjs` to TypeScript modules (lease cohorts, power, debt, reserves, waterfall). The golden snapshot and reference parity make that refactor safe to verify.
- **1c:** package the hourly power engine (`engine2.js`). The app currently shows two engines with different headline numbers, and they need one authoritative output.
- **v25.9 follow-ups:** day-count accuracy for stub periods, ring-fenced waterfalls, arrears and default interest, and confirmed payment/maturity dates for the two non-modelable templates.
- The v25.8.4 author tests (`test_power_pass2584.cjs`) and `case_catalog_v2584.json` were not provided, so they are not included.
- Arithmetic agreement is not lender validation.
