# PowerPath v30.2 — Feasibility v8.2 Integration Alpha

**Status: local-only screening integration, not utility-verified, not lender-verified.**

## Delivered

- Preserved all v30.1 application components, existing parcel APIs, legacy v7 feasibility files and every frozen financial engine byte-for-byte.
- Added `feasibility/v82/` with a v8.2 reference rule module, **calibrated** metric/risk/config JSON exported from the provided v8.2 workbook with artifact_tool, an immutable copy of the eight-site/four-mode reference fixture, the gate-sensitive schedule27 adapter and pure score/batch helpers.
- Four competing paths: grid, BTM, hybrid and flexible-load. Selection prefers the fastest verified first-power path; a provisional option cannot outrank a verified option. Four screening tiers prevent a high provisional score from overtaking decision-ready sites.
- **No parallel scheduling implementation:** the adapter delegates effective gate delay to `server/schedule27.compute`, including dependency accumulation along milestone predecessor chains. With independent gate milestones it matches the workbook's parallel-delay screening convention; with an explicit predecessor edge it can differ intentionally and exposes the schedule version.
- Extra capex and annual curtailment loss are computed and shown as v8.2 screening values. **They do not yet flow to the frozen financial engine**, and no IRR/NPV/DSCR changes are asserted here.
- Added local API `POST /api/projects/{pid}/feasibility`, `GET /api/projects/{pid}/feasibility`, and `GET /api/projects/{pid}/feasibility/{run_id}` with append-only SQLite snapshots and input/config SHA-256 hashes. API rejects target-MW mismatches and invalid inputs, and it is deliberately disabled when the authenticated multi-tenant mode is required pending RBAC review.
- Added a guard against marking a gate NA when it applies to the selected path, to prevent a silent false-Go status. This extends the input validation, not the scoring equations.

## Tests and verification

- `python -m pytest -q feasibility/test_v82_integration.py feasibility/test_phase1.py tests/test_api.py tests/test_public30.py`: **42 passed** in the isolated local-mode test environment used during build.
- The v8.2 integration parity test checks every numeric metric, pillar, site/geo score, four path statuses, first/full power, capex, curtailment, gate multiplier, tier and position against all **32 site-mode fixture cases** (eight sites x four modes) to 0.01.
- Tests cover a failed hybrid air-permit fallback, failed flexible-load agreement fallback, dependent-vs-parallel gate schedules, invalid/missing confidence, tiers, selected-path-only capex and POST/GET immutable API behavior in a separate process.
- Original financial-engine folder: **12 of 12 hashes byte-for-byte unchanged** against the v30.1 ZIP; no files added or removed there.
- `npm run check`: passed.
- Full mixed-suite `pytest tests` is **not** a verified release gate: legacy v27 auth suites set import-time global security mode and database state, and collecting incompatible modes in one interpreter produces unrelated tenant fixture conflicts. Run security suites in their prescribed isolated processes.

## Run locally

```bash
unzip PowerPath_v30_2_Feasibility_Integration_Alpha.zip
cd PowerPath_v30_2_Feasibility_Integration_Alpha
pip install -r requirements.txt -r requirements-feasibility.txt
python -m pytest -q feasibility/test_v82_integration.py feasibility/test_phase1.py tests/test_api.py tests/test_public30.py
./run_local.sh
```

Use POST requests to `/api/projects/{pid}/feasibility` with a project whose `target_mw` matches `inputs.raw.target`. Example request shape is in `feasibility/v82/fixtures_v8_2.json` (the `inputs.Site D` object), plus `site_name` and `mode` fields. Responses include non-certified and self-reported-data labels. The app remains bound to localhost.

## Explicit remaining blockers

1. **Database-backed canonical milestone sourcing**: request handlers currently score supplied v8.2-style path inputs. Next: map each v30 `power_paths` and its existing `delivery_milestones`/`permit_items` to a single `schedule27.schedule_for` computation, with human-reviewed gate-to-milestone evidence links and first-power/full-load per phase.
2. **Finance contract**: verify dollar conversion of path capex and remediation capex exactly once and treatment of curtailment (tenant/operator/owner allocation) before mapping to the frozen underwriter. Run scenario-by-scenario financial reconciliations and G4/G5 regression tests.
3. **Live parcel evidence**: evidence map from NC OneMap/VA VGIN and `parcels28.py`, provenance/freshness, one project record and UI Feasibility card are not yet wired.
4. **Model governance**: source inputs in API remain user-provided, not checked for executed contracts or utility confirmation. No predictions, external calibration or lender certification. v2 probability layer stays internal and unported.
5. **Authenticated multi-tenant RBAC**: alpha v8.2 feasibility endpoints intentionally refuse requests in required-auth mode.

### Specification errata requiring reconciliation

- The v8.2 spec's master prompt says *any* `N` gate implies No-go; the actual tested rule is **no surviving viable path**. A failed path-scoped gate excludes only affected paths.
- The engineering backlog still refers to `fixtures_v8_1.json`; replace with `fixtures_v8_2.json`.
- `gate_inputs.applies_to` schema example lists only `all/grid/btm`, but v8.2 now requires the full gate-by-four-path applicability matrix.
- Tier 1 called `Decision-ready` includes conditional sites such as Site B with major rezoning; avoid presenting this as a permitting or financing approval.
- The first verified **MW** is not necessarily the full required target; economically preferred option must be decided by full-load schedule, incremental capital and tenant economics, not shortest first-power month alone.

## Outcome schedule governance

Frozen live-test predictions and historical model versions remain untouched. Next outcome checks: **2027-04-28** and **2027-10-28**.
