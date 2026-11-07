# PowerPath v22 — Evidence-first infrastructure diligence (local prototype)

## New features

* **Data room:** project-specific register for utility studies, service agreements, interconnection evidence, permits, zoning, equipment quotes, financial records and other documents. Optional local file attachments stored in IndexedDB. When available, SHA-256 fingerprint per attachment. Self-declared review status, reviewer, source URL, date, annotation, manifest JSON export, CSV export, and local activity log. No automatic regulatory determination.
* **Infrastructure screen:** site coordinate entry and user-sourced candidate infrastructure (substations, generation, transmission, gas, fiber, water) with great-circle distance and provenance, separated by project. No assertion of deliverable MW or utility rights. These are manually entered candidates, **not a live GIS feed**.
* **Tariff worksheet:** volumetric charges, demand charges, fixed charges, loss adjustment, load factor, and an additional per-MWh allowance to calculate an illustrative all-in delivered rate and monthly cash cost. Independent of the underlying dispatch engine pending evidence review; avoids silent changes to pre-existing model economics.
* **Review queue:** v21 rule-based worklist remains, with no autonomous agents. Project Evidence and Power sections link to the diligence room.
* **Exports:** local JSON manifest (not file contents), diligence CSV, tariff CSV; existing v21 project/decision exports remain.

## Starting the application

Unzip the source package, then from its root run:

```sh
python3 -m http.server 8765
```

Navigate to `http://localhost:8765/PowerPath.html`. Choose **Site & Data room** in the left navigation. Select a project, then choose Data room / Infrastructure / Tariff / Audit.

Standalone `PowerPath_v22.html` works for modeling and some local UI, but origin-based browser storage and document uploads can be unreliable or blocked from `file://` or embedded preview contexts. The local HTTP workflow is recommended for the room.

## Privacy and operational boundaries

* This is **not an enterprise VDR**. Browser storage may be cleared, cannot be shared across users, has no access controls, SSO, audit immutability, encrypted document service, backup, server search, malware scanning, retention policy or role-based authorization. Avoid importing genuinely confidential utility studies, NDAs or contracts until those controls are implemented.
* The JSON manifest includes **metadata only**, not file bytes. Export underlying attachments separately. The local audit log is editable by the browser user and **not tamperproof**.
* Reviewing a file is not a permit approval or contractual service entitlement. Do not automatically promote documents into the feasibility engine.
* Geodesic proximity is **not** available transmission capacity, substation headroom, easements or routed construction distance. Inputs are manually sourced.
* The tariff is illustrative: actual tariffs can include ratchets, time-of-use, standby charges, taxes, minimum bills, and negotiated large-load provisions. Not yet linked into the dispatch engine automatically.
* Existing live EIA/PJM connectors require their gateway, credentials where applicable, and verification. This release does not add new licensed live GIS datasets, an autonomous permitting agent, cloud collaboration, a bankable interconnection study, or native Excel ingestion.

## Validation

* Previous engine, finance, development, feasibility, connectors, market-price, and v21 tests remain passing.
* Nine new unit tests cover proximity and tariff mathematics / invalid input handling.
* Desktop and mobile Chromium smoke tests exercised the new tabs and metadata workflows; document-file upload was not end-to-end tested in a persistent origin in this runtime. Browser navigation to localhost was restricted, so tests used simulated local storage for UI flows.

## Next production work

1. Enterprise data room backend with identity, access control, encryption, malware scanning, backups, versioning, retention and immutable logs, plus S3-compatible object storage.
2. Source-licensed parcel/substation/transmission layers, spatial database, utility territory and site-to-node mapping; distinguish screening from utility service confirmations.
3. State- and utility-specific large-load tariff adapters with source citations, calendar-hour schedules, and reconciled model inputs.
4. Docket-specific permitting change monitoring with human-reviewed facts and source versioning.
5. Import/export bridge with user Excel models, including explicit versioned input mapping and model reconciliation.

No AI agents are included or required in this phase.
