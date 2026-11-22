# PowerPath v28 — Parcel & Decision Workspace

## Delivered

The home page now follows Project brief → Explore parcels → Compare options → Diligence → Decision memo. It uses a restrained green/cream visual system, persistent project selection, responsive map/list presentation and progressive source inspection.

- Locally vendored Leaflet 1.9.4 with its BSD license. Optional OpenStreetMap tiles and attribution; per-session consent explains external viewport/IP requests. Parcel geometry/list inspection works without tiles. Tile failures have an explicit fallback message.
- Actual Loudoun County tax parcel polygons, PINs, recorded square footage/acres, source update dates and retrieval provenance in `data_sources/loudoun_parcels.geojson`.
- 120 records, selected through an eastern Loudoun bounding envelope (-77.60,38.94,-77.40,39.13), recorded area ≥20 acres. This is a bounded snapshot, not an exhaustive search or live feed. It contains real property, which may already be developed or unavailable. No title, zoning or available-power conclusion is inferred.
- PIN and acreage filtering, map/list selection, project-specific saved shortlists, comparison and evidence inspector.
- Project-specific factor assessments with source URL, source date, rating and rationale, recorded through the existing audit mechanism.
- Project-level power-pathway creation using existing API objects. These are explicitly hypotheses, separate from parcel-level service verification. Handoff links retain the project and chosen detailed-workspace view.
- Diligence tasks with owner, due date and completion state. Task completion does not change evidence classifications or scores.
- Decision memo with source register, index limitations, missing factors and power hypotheses. JSON export additionally includes geometry and tasks; browser print supports PDF saving. No automatic investment recommendation.

## PP-SITE-1.0 methodology

A provisional analyst-rated site feasibility index, NOT a probability of completion or engineering reliability score.

| Factor | Weight | Evidence to investigate |
|---|---:|---|
| Power access | 30% | Requested load, utility study/service route, rights and competing load |
| Permitting/community | 20% | Applicable allowed use, permit route, restrictions and documented concerns |
| Land/site control | 15% | Title, control, easements and buildable area |
| Environment | 15% | Flood, wetlands, habitat and contamination |
| Delivery/equipment | 10% | Equipment availability and energization dependencies |
| Fiber/water | 10% | Documented connections and project-specific design needs |

Each assessment has gate unknown/pass/flag/fail and an analyst rating 0–5 (least to most favorable). Any assessed gate requires an HTTP(S) source, source date, and rationale. Future dates are rejected. A date does not authenticate a document.

Coverage = sum of weights with non-unknown ratings supported by evidence no older than 180 days. Index = 100 × sum(weight × rating / 5) / covered weight, rounded to an integer. It is withheld until coverage ≥60% AND both power and permitting have current assessments. Any failed gate blocks the index, including a stale adverse gate. Clearing a previously failed gate requires a current sourced reassessment. The 180-day policy and weights are initial product assumptions, not empirically calibrated thresholds. Favorable scores can still contain material flagged risks and uncovered factors.

Public county acreage is a recorded-area fact, not an automatic favorable land assessment. All initial scores are unavailable; none are fabricated to create an attractive map. Electrical reliability remains `not_assessed` in every scoring response. A future engineering layer needs load profiles, electrical topology, contingency analysis and project-specific reliability requirements.

## Preserved controls

The existing `/advanced` workspace, financial calculations, scenario/run histories, PermitIQ, geographic intelligence and transaction review remain available. No financial-engine file changed. New persistent tables are additive. Existing installations should back up `data/` before updating and copy it into the new release to retain work. Removing a shortlist entry retains its assessment/task history for later re-addition.

Required-auth routes inherit existing tenant and role middleware; new parcel mutations require project analyst access and cross-tenant access is denied. The new workspace supports local bearer sign-in and new-project tenant selection; tokens are held in page memory. Detailed legacy tools may require a separate authentication flow in required-auth mode. Default launch is still loopback-only and unauthenticated; do not host publicly. No new production-security claim is made.

## Verification

- New parcel API/scoring suite: 8/8 passed.
- New parcel required-auth suite: 3/3 passed (isolated process).
- Existing geographic/critical-path suite: 6/6 passed.
- Existing institutional security suite: 5/5 passed.
- Existing schedule parity: 11/11 passed.
- Existing v27.1 required-auth: 3/3 passed.
- Existing transaction workspace: 3/3 passed.
- Existing Core Scientific suite: 15/16 passed. One inherited golden-output hash mismatch remains. The original archive's unchanged underwrite25.js produces the identical mismatching hash in this runtime, confirming this mismatch is not introduced by the redesign. Expected hash 47846c474a3e234e72056d86bbc0cfad4b371dc42b3fa21537b00bae9fcdb327; original and current runtime output 5f27b4a4b567f0e53339e96b79864877e43cfa277fcd1d78743f75bb585037fd. Do not replace the golden fixture without investigation.
- All 12 engine files compared with the original v27.2 archive: identical.
- TypeScript compilation and JavaScript syntax checks passed.
- DOM smoke checks passed: initialization, 120 parcel rows, unavailable-map fallback, PIN filtering, parcel selection, five-step navigation, dialogs and memo methodology. These are not browser render tests.
- Browser visual/map-tile QA remains unverified: managed preview could not launch the existing Python application. No alternate public server was opened and no deployment occurred.

Run each Python test module in a separate process. Inherited suites change global auth/data environment variables; combined test discovery causes cross-suite contamination.

## Sources and coverage gaps

County parcel service: https://logis.loudoun.gov/gis/rest/services/COL/pol_connect/MapServer/3
County data context: https://www.loudoun.gov/1776/GeoHub-and-Other-Online-Resources
Basemap/license: https://www.openstreetmap.org/copyright and vendored Leaflet license.
Product references considered: Paces and Basepoint public product pages. No proprietary datasets or competitor scoring formulas were copied, and no competitive parity is claimed.

Next data integrations: licensed/official parcel coverage beyond this pilot, zoning/use and environmental overlays, utility territory and source-backed infrastructure, then project-specific utility studies. The shipped snapshot has no automatic refresh endpoint; refresh/retention semantics need to preserve saved parcel source versions before live updating is added.
