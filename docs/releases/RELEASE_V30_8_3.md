# PowerPath v30.8.3 — single flow, in-flow economics, append-only records, PostgreSQL acceptance

**Date:** 2026-11-07 · **Builds on:** v30.8.2-audit (`docs/AUDIT_2026-11-07.md`) · **Status:** local engineering alpha, pilot-ready for supervised internal use. Not production, not lender-verified.

Protected financial engines are byte-identical (12/12). Extended regression gate 257/257. No underwriting math changed.

## What changed for users

### One flow, six steps
The streamlined workspace is now the single front door: **Brief → Explore parcels → Power paths → Economics → Diligence → Decision memo**. The detailed workspace and the four standalone pages remain available, labelled **Expert tools**, but no step requires leaving the flow.

### Economics, inside the flow (new)
Step 4 runs **every power pathway through the same frozen 27.1.0 underwriter** on one base scenario and shows the results side by side: first revenue month, modelled NPV (with the effect of schedule delay), levered IRR, minimum DSCR, interest carried before revenue, covenant breach months and sponsor equity.
- Read-only. It uses the existing `GET /paths/{id}/schedule-impact` endpoint and persists nothing.
- Factual tags ("Highest modelled NPV", "Earliest revenue") with an explicit statement that they aren't recommendations.
- **Timing transparency:** the underwriter applies a pathway's *delay months* to the scenario's building schedule; it doesn't use the pathway's entered first-power month. Wherever the two differ, the row says so ("Entered first power M36; modelled energisation M25") and a note explains how to model the timing exactly. *This is a model-semantics finding for the model owner; see Open items.*
- Results flow into the **Decision memo** and the **evidence JSON export** (`modelled_economics`), with base scenario, version, engine and timestamp.
- Measured: **10 seconds** from landing to a two-pathway economic comparison on a new project. Before v30.8.2 this wasn't reachable at all.

### Instant first number, with consent
"New project" has a checkbox, ticked by default: *start with an illustrative working scenario sized to this MW target*. It creates one underwriting scenario from the **unchanged engine defaults**, changing only the building list so IT MW sums exactly to the target (⌈MW ÷ 50⌉ buildings, max 10, standard 9-month stagger). Existing projects get the same option as an explicit button in Economics (`POST /projects/{id}/starter-scenario`). Never applied silently.

### Credibility fixes
- "Verified viable" now reads **"Verified viable (analyst-asserted, not independently checked)"**. It's an analyst-entered input class; nothing in the system verifies it.
- **Synthetic test parcels were masquerading as real NC OneMap records** in the default map view (leaked test residue in the curated fixture, tagged `public_live_viewport`). They're now relabelled `SYN-TEST-A/B`, "Synthetic fixture (not NC OneMap data)". Row counts are unchanged.
- Diligence cards have **Assess evidence**, which jumps to factor scoring.
- Transaction review re-skinned to the shared palette. Agent operations uses an **in-page dialog** instead of native `prompt()`/`confirm()`.
- The detailed workspace supports the **browser back/forward** buttons.

## What changed underneath

### Append-only financial records: closes the Nov 4 review P0
| Table | Rule |
|---|---|
| `runs`, `feasibility_v82_runs`, `activity` | Insert-only. No UPDATE, no DELETE. |
| `evidence` | No DELETE. The file may be attached exactly once; descriptive fields never change. |

- **SQLite:** triggers (`server/append_only.py`), installed at startup, idempotent.
- **PostgreSQL:** `runtime_policies.py` grants these tables INSERT only (plus a one-time attach policy for evidence) **and** adds OLD/NEW guard triggers. Triggers bind every role including the schema owner, and catch a title swap smuggled into the attaching UPDATE, which RLS alone cannot see.
- `scenario PUT` keeps the stored engine version (from v30.8.2).

### PostgreSQL acceptance, actually executed (local, disposable)
`scripts/pg_acceptance.sh` runs end to end on PostgreSQL 16 + PostGIS 3.4 and is wired into CI as the `pg-acceptance` job (throwaway `postgis/postgis:16-3.4` service container):
1. **Stage import.** The archived importer *aborted* on the one invalid parcel (rid 12, Loudoun ring self-intersection), as the Nov 4 review found; the live DB had been loaded by an uncommitted variant. The importer now **quarantines** invalid geometries with their PostGIS reason (`pp_parcel_geometry_quarantine_v1`) and reconciles valid + quarantined = source. Result: **137 + 1**, the live figures, now reproducible from source. 45 tables and 182 rows reconciled, financial fingerprint matched.
2. **Runtime schema:** RLS forced on 40/40 tables, 124 policies, 4 guard triggers.
3. **Adversarial test** (`tests/pg/rls_append_only_attack.sql`), 24 checks as the non-owner `powerpath_app` role: an analyst can't update or delete runs, the activity log or evidence, can't swap metadata while attaching, can't write across tenants, self-grant admin or move a project; viewers can't write; no-actor, forged-actor and inactive-admin sessions see nothing; the schema owner can't mutate a run. Legitimate actions (append a run, attach a file once, edit a scenario) still succeed. **24/24 pass.**
4. **Backup → restore drill:** `pg_dump` → `pg_restore` into a fresh database. Policies, triggers, geometries and project/scenario fingerprints are identical, and **24/24 attacks are still blocked on the restored copy.**

### SQLite backup now includes evidence files
`db_manage backup` previously copied only the database. **Uploaded evidence files live outside SQLite and were silently excluded.** Backups now include `<backup>.evidence/` with `EVIDENCE_MANIFEST.json`, and `verify-backup` fails if any evidence file is missing or altered. `scripts/restore_drill.py` (also in CI) builds a real workspace through the API, backs it up, restores it into an empty directory, and proves identical records, hash-verified evidence downloads and surviving triggers.

### Maintainability
- `black` + `prettier` formatting pass in its own commit. **Logic-identical, verified by syntax-tree comparison across all 49 files**; the only differences are one docstring's trailing whitespace and one removed no-op semicolon. Protected engine and feasibility model code is excluded (`pyproject.toml`, `.prettierrc.json`).
- Lines over 400 characters: 201 → 129. The remainder are HTML template literals.

## Verification (this build)
| Check | Result |
|---|---|
| Extended regression gate | 257 / 257, engines unchanged 12/12 |
| Quick suite | 58 / 58 (incl. 14 audit tests: append-only, starter, engine downgrade, restore drill) |
| PostgreSQL acceptance + restore drill | PASS, 24/24 attacks blocked on source and on restore |
| SQLite restore drill (DB + evidence) | PASS |
| Tamper smoke (`feasibility/v82/api_financial_smoke`) | PASS |
| Browser sweep, 6 surfaces × 3 viewports | 0 accessibility violations, 0 failed requests, 0 console errors, no sideways scrolling |
| End-to-end flows | New six-step flow, economics, memo and export, mobile, starter button, back/forward, in-page dialog |

## Open items (honest list)
1. **Model semantics (needs the model owner):** a pathway's entered first-power month isn't an underwriting input. Only its delay months are (`server/schedule27.apply_to_config`). The UI now discloses this, but a decision is needed: either map first-power month onto building power months, or rename the field "target first-power month (informational)". Changing it alters existing sensitivity outputs and the schedule-parity fixtures.
2. **Application on PostgreSQL** (login → CRUD → runs through the HTTP app) still needs Supabase identity and a TLS-verified host. The database layer, policies, triggers and restore are now proven locally; the app adapter path isn't.
3. **Two workspaces still exist in code.** The detailed workspace is demoted to an expert tool, not removed. Converging them is a larger refactor.
4. The map header still reads "Real parcels · screening only" even when only synthetic rows are visible. Per-parcel provenance is correct in the list and inspector.
5. Verified on Python 3.12.3 (CI pins 3.12.10); confirm on the first CI run and on the Mac runtime. A manual screen-reader pass hasn't been done.
