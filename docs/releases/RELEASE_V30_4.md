# PowerPath v30.4.0 — Permitting Alpha (Loudoun County, Virginia)

**29 October 2026. Additive. Read-only rule engine and API. No financial engine, v8.2 fixture or database schema changed.**

## What it does

`permitting/` turns a project description (parcel facts, design, power paths, known permit status) into:

1. **The required permit set**, each with the trigger that fired, issuing authority, discretion level (0 by right to 3 legislative), hearings and citations.
2. **A calendar critical path** for typical (P50) and slow (P90) cases, honouring dependencies, approved and denied permits, known hearing dates and an as-of date (nothing undecided finishes in the past; anything without a recorded status is assumed not started).
3. **Per-tranche power dates**: grid and on-site tranches separately, so a hybrid path reports first power from on-site generation and full load from the grid.
4. **v8.2 gate states** (Zoning, Moratorium, Air permit) with severity and remediation months, plus **schedule27 milestones** per path. `apply_to_v82_inputs()` merges both into a v8.2 input for `score_one`.

API: `POST /api/permitting/assess` with the project JSON. Disabled in required-auth mode, like the other alpha routes.

## Rule set (last verified 2026-10-29)

| Layer | Rules |
| --- | --- |
| Federal | FAA Form 7460-1 notice (14 CFR 77.9 screening radius), Section 404/401 wetlands |
| Virginia | HB 153 / SB 94 high-energy-use facility assessment (§ 15.2-2209.5, from 2026-07-01, 100 MW and up), DEQ minor NSR for backup generators, DEQ permit for on-site prime generation, VESMP land disturbance (more than 1 acre), SCC certificate for lines 138 kV and up, line construction |
| Dominion | Large-load service: 4-stage queue, 100 MW threshold, 300 MW per-request cap, zoning confirmation in stage 2 |
| Loudoun | Legislative approval (rezoning and special exception; by-right ended 2025-03-18), grandfathered by-right route, substation special exception, § 15.2-2232 conformity review, site plan, building permits |
| Loudoun overlays | Board decision pause (status: proposed; resolution deferred to 2026-11-17; switch `overlay_assumptions.LC_PAUSE_2026`), grandfather rescission risk (P90 converts to legislative), Phase 2 standards (on-site generation, noise, substations, height; Board vote planned July 2027), policy areas (Rural prohibited; Transition Major) |

Statutory clocks are recorded separately from durations: Board action within 12 months (§ 15.2-2286(A)(7)), site plans 40/30 days (§ 15.2-2259), conformity review 60 days (§ 15.2-2232), DEQ 90/180 days (9VAC5-80-1160).

Every duration carries a basis: `statute`, `observed` (n stated), `industry`, or `prior`. Prior means an assumption awaiting calibration. Tests enforce that any non-prior basis cites a source. Outputs report how many critical-path months rest on priors.

## Backtest (consistency check, not validation)

Blind predictions at filing, using today's rules, against documented outcomes. Filing months are estimated from application-number years, and the two Loudoun legislative-duration priors were set with these cases in view.

| Case | Predicted | Actual | Result |
| --- | --- | --- | --- |
| Cross Mill (LEGI-2023-0064), JLMA, near Leesburg Executive Airport | PC hearing month 18–28, decision 26–40; FAA notice flagged; no substation | PC hearing month 18.8 (2024-09-24), approved 5-4 at month 28.5 (2025-07-15); airport proximity raised at hearings; no substation in the application | Inside the P50–P90 band on both; permit-set flags consistent |
| Spring Valley (LEGI-2024-0074), Transition Policy Area, on-site generation, 3 substations | Zoning gate C/Major; PC hearing month 18–28; substation, air, HB 153 and wetlands permits flagged | PC hearing month 24.7 (2026-07-23), staff and PC (6-0) recommended denial citing the policy area; Board hearing deferred indefinitely | Risk direction and PC timing consistent; decision past blind P50 |

**Live prediction (as of 2026-10-29):** if the pause is adopted, Spring Valley gets no Board decision before **2027-07-23** (12 months from its PC hearing). That date coincides with the statutory 12-month limit unless the applicant consents to longer.

## Example: a new 200 MW filing in a Suburban place type today

Legislative decision P50 Dec 2028 / P90 Mar 2030. Grid energization P50 Nov 2031 / P90 Nov 2033. Dominion's queue is the critical path, and the land-use chain runs about 7 months behind it. A path assuming power at month 42 is 18 months late at P50.

## Known limitations

- **v8.2 shifts both tranches by one delay.** For hybrid paths `score_one` moves full load by the on-site tranche's delay. The engine's own per-tranche dates are correct; v8.3 should accept per-tranche milestones.
- **Priors dominate outside zoning and the utility queue.** Site plan, building permit, air permits, wetlands, FAA, HB 153 assessment and construction slippage are assumptions. The next calibration source is Loudoun's LandMARC permit records.
- **n = 2 observed Loudoun cases.** The legislative distribution needs the full set of 2023–2026 data center LEGI cases.
- **Screening triggers.** The FAA rule flags any site inside the notice radius, not a slope-surface penetration test. Wetland impact size switches nationwide versus individual permits at an assumed 0.5 acre.
- **Only Loudoun is mapped.** Other counties return an error, never an all-clear.

## Tests

```bash
python -m pytest -q permitting/test_permitting.py          # 30 tests
python -m permitting.backtest                               # prints backtest JSON
```

Full release gate: 30 permitting + 8 + 61 + 12 + 11 + 16 + 3 existing tests pass in their groups; JS check passes; the 12 engine files match `ENGINE_HASH_AUDIT_V30_3.json`.

Added: `permitting/` (engine, data, cases, backtest, tests), `server/permitting_api.py`, this note, `SHA256_MANIFEST_V30_4.json`. Changed: `server/app.py` (route registration, version), `package.json` (version).
