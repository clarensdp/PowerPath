## v30.8.3 — Single flow, in-flow economics, append-only records, PostgreSQL acceptance (2026-11-07)

- Six-step flow (Brief → Parcels → Power paths → **Economics** → Diligence → Memo); the detailed workspace and standalone pages become Expert tools.
- New Economics step: every pathway through the frozen 27.1.0 underwriter side by side (read-only); results land in the memo and the evidence export; pathway timing mismatches disclosed.
- Opt-in illustrative starter scenario sized to the project's MW target (create-project checkbox, plus a button for existing projects).
- Append-only `runs`, `feasibility_v82_runs`, `activity`; evidence attach-once (SQLite triggers + PostgreSQL grants/policies/guard triggers). Closes the Nov 4 P0.
- PostgreSQL acceptance script + CI job: stage import with geometry quarantine (137+1 reproduced), runtime RLS, a 24-check adversarial test, pg_dump/pg_restore drill.
- SQLite backups now include evidence files with a hash manifest; restore drill in CI.
- "Verified viable" disclosed as analyst-asserted; leaked synthetic test parcels relabelled; in-page dialogs; back/forward in the detailed workspace; diligence → factor scoring.
- black + prettier formatting pass (AST-verified no logic change). Engines unchanged 12/12; gate 257/257. See `RELEASE_V30_8_3.md`.

## v30.8.2-audit — Full technical + UX/UI workflow audit (2026-11-07)

- **Data integrity:** saving a new underwriting scenario no longer silently downgrades it to the legacy v25.8.5 engine (client keeps server config; server PUT preserves the stored engine when an update leaves it out).
- **Unblocked workflows:** new projects can reach financial comparison (guided scenario creation and an IT-MW mismatch pre-check); transaction review gets a one-click input registration; dead-end empty states now explain the next step.
- **UI:** CSP-safe geometry (Decision Center pins and timelines render again), WCAG AA contrast (114 → 0 axe violations), mobile project picker and tab cues, consistent six-section navigation, agent operations re-skinned to the shared palette, the `hidden` attribute respected everywhere, URL keeps the open view.
- **Engineering:** executable launcher, `npm run check` covers all 9 entrypoints, TS→JS drift guard plus pinned TypeScript build, `requirements.lock`, `?allow_empty=true` on latest feasibility, 9 new regression tests.
- Protected financial engines unchanged (12/12). Extended gate 257/257. See `docs/AUDIT_2026-11-07.md`.

## v30.8.0 — Infrastructure stabilization baseline

- Central SQLite connection factory and extracted original core schema without changes to model logic.
- Non-destructive database inspection, required-column contract, and consistent, SHA-256-verified backups.
- Alembic baseline for existing SQLite, with compatibility checks and no PostgreSQL cutover claim.
- Architecture tests, process-isolated regression gate, and a prioritized debt register.

## v30.7.1 — Read-only parcel footprint alpha (2026-10-29)
- Accurate WGS84 whole-polygon acreage intersections using Shapely + pyproj local equal-area projection.
- Optional bounded FEMA NFHL SFHA and USFWS NWI polygon queries; explicit operator/user opt-in, fail closed. Live network integration pending.
- Cached parcel ID and uploaded GeoJSON support, uploaded zoning/constraint polygons with declared coverage extents.
- Interactive PermitIQ map overlays, area fractions and explicit unknowns; no buildability certification or underwriting change.
- New `permitting/test_footprint.py`, release/contract documentation, unchanged protected financial engines.

## v30.7.0 — Agent Operating Foundation (2026-10-29)

- Added versioned agent-domain SQLite migration, durable daily task queue, foreground worker, bounded model reviews, approval inbox, local event hashes, and role-scoped dashboard.
- Tightened shared model-call budget accounting across legacy and new agent runners.
- No automatic external actions; frozen financial engine unchanged.
- See `RELEASE_V30_7_AGENT_OPERATING_FOUNDATION.md` for test evidence and limits.

## v26.3 — October 26, 2026
- Introduced geographic source registry, EIA-style CSV ingestion, evidence/vintage tagging, actual Web Mercator coordinate plotting and cited source inspectors. No available MW claims.
- Introduced linked PermitIQ/utility/interconnection milestone graph; cycle-scoped API; critical delay by dependency path and parallel max.
- Introduced `/sensitivity-v263` creating a versioned, screening-only financial scenario without changing baseline models.
- Restored missing original `transactions_v259.json` fixture to execute inherited note-engine regression tests.
- Added six API tests plus responsive browser walkthrough; all 37 release audit jobs passed; financial source hashes unchanged.

# Changelog

## v26.0.0-alpha · 2026-10-26

- Replaced standalone browsing context with a server-backed, persistent web application.
- New project-centered UI: Portfolio / Overview / Power & Delivery / Economics / Debt Facilities / Evidence / Run History.
- Local SQLite project, scenario, run, evidence and activity tables with foreign keys.
- Saved scenario versions, frozen input and monthly run outputs, source-engine hashes and CSV exports.
- Local evidence attachments with immutable stored bytes and SHA-256 checksums.
- Cross-project query isolation for scenarios, model runs and evidence.
- Readiness warnings for all investment outputs; not lender certified.
- Strictly preserved the original underwriting and alpha debt engines without rewriting formulas.
- TypeScript / local FastAPI integration tests and Chromium responsive acceptance tests.

See `V26_AUDIT.json` for passed suite details and `docs/RELEASE_GATES.md` for remaining production limitations.

## v26.1 (October 26, 2026) — Risk-gated note integration

- Imported source-preserved v25.9.0-risk1 note finance and Risk packages, with source hashes and separate model mode.
- Added backend persistence and UI for v25.9 note scenarios, calculated cash flows, and blocking risk gates.
- Added adversarial API cases for unsupported lender approvals and collateral conflicts.
- Included independently uploaded institutional design as a reference; persistent frontend remains the existing modular TypeScript v26 site.
- G4, G5, and public deployment remain blocked. Details in `docs/V26_1_INTEGRATION_REVIEW.md`.

## v26.2 (October 26, 2026) — Decision Center and PermitIQ

- Implemented new **Decision Center**, **Power paths**, **PermitIQ**, and locally sourced **Intelligence** project views, following workflow patterns visible in user-supplied Basepoint screen recordings.
- Added durable candidate pathways, optional coordinate inspector, permit/utility action records, checklists and dated notes.
- Added opt-in path-to-finance sensitivity creation with explicit assumption deltas and preserved source-scenario lineage; previous model versions remain unchanged.
- Preserved all frozen underwriting, notes and Risk engines; G4/G5 transaction-use blocks remain enforced.
- Added workflow API/browser regression tests and a time-coded UX design handoff.
- **No live GIS basemap, verified delivered MW, regulator monitoring, permit submission, hosted login or lender-grade claims.**

See `docs/V26_2_DECISION_CENTER_RELEASE.md`, `docs/V26_2_EXECUTIVE_DECISION.md`, and `V26_AUDIT.json`.

## v27.1.0 — October 27, 2026
- New versioned engine `engine/underwrite27.js` (27.1.0) with a cash-constrained debt-service waterfall (RT-A02); legacy engine unchanged and selected by `engineVersion`.
- Canonical schedule engine `server/schedule27.py`; both sensitivity routes, previews and Decision Center use it (RT-E04b). `/schedule-impact` added.
- Core Scientific notes: evidence register, `engine/fixed_note27.cjs`, scenarios, reconciliation, illustrative Layer 3. G4/G5 BLOCKED.
- Restored missing note-engine test fixture; 18-check release runner; independent oracles and mutation suite under `tests/v271/`.
