# PowerPath v26.2 — Decision Center and PermitIQ release

**Release date:** October 26, 2026  
**Status:** functional local alpha; no public deployment; no lender-grade transaction use.  
**Design source:** Two Basepoint interface recordings supplied by the user, and the time-coded `PowerPath_v26_2_Video_Derived_UX_Brief.md`. Borrowed **workflow patterns**, not Basepoint's source code, user interface assets, brand or implied data rights.

## What actually shipped

| Workstream | User-facing behavior | Persistence / verification |
|---|---|---|
| CPO + Design: Decision Center | Every project opens to a single decision view with target load, alternatives, unresolved dependencies, evidence link, and permanent red blocked-use banner | Live records from project-scoped local API, not a screenshot |
| Power intelligence | Select grid, onsite, hybrid or colocation alternative in a shortlist/spatial inspector. Paths store MW, target month, optional coordinates, evidence link, delay and cost sensitivities | `power_paths` SQLite table and CRUD. **Spatial visualization is schematic without actual coordinates; even with coordinates it is not a GIS tile map or verified grid study.** |
| CTO + CFO: path-linked finance | Click 'Create versioned sensitivity' to clone an existing *underwriting* scenario, apply explicit extra delivery delay / construction-capex / energy-price shocks, optionally include maximum open linked permit delay, and save a new model run | `scenarios` + immutable `runs`. Source scenario and version are in `powerPathLink`. Uses unchanged underwriting engine. Existing scenario versions and previous results are retained. |
| PermitIQ / Execution | Project-specific permit/utility/financing queue with owner, status, target model month, delay exposure; relative timeline, checklist steps, notes and evidence links | `permit_items`, `permit_steps`, `permit_notes` tables and append-only activity records. Internal status is NOT a regulator filing or executed approval. |
| Chief Risk Officer | Persistent 'Transaction valuation BLOCKED / Lender certification BLOCKED' across primary project pages; no project path can attest to utility-confirmed MW | Existing server-enforced v25.9 G0–G5 logic is unchanged; added workflows never modify risk authorization. |
| Intelligence | Local updates feed from activity saved against the project | No unattended monitoring or utility/regulator connector yet. |

## Exact model linkage / important limits

A path's sensitivity uses the base scenario `delayMonths`, `constructionCostMW` and `powerCostMWh` plus user-entered path changes:

```
newDelayMonths = baseDelay + pathDelay + (includeOpenPermits ? max(openLinkedPermitDelays) : 0)
newConstructionCostMW = baseConstructionCostMW * (1 + capexUpliftPct/100)
newPowerCostMWh = basePowerCostMWh * (1 + energyUpliftPct/100)
```

**Do not treat this as a path feasibility model.** Candidate `power_month` is **displayed only** in v26.2, not imposed as a per-building supply constraint, and `capacity_mw` is a working hypothesis, not a utility allocation. A one-candidate/one-permit scenario can show relative impact, but cannot establish an actual connection date, available site capacity, contract economics or financing approval.

Permit delay is not automatically applied to any existing scenario. The user must expressly opt into generating a *new* sensitivity and can select whether to include the maximum open linked-permit exposure. Summing uncorrelated delays or selecting the maximum can both be wrong for real project networks; a fully sourced CPM/PERT schedule is deferred. Updating a permit does not silently mutate a saved underwriting result.

## What remains outside release

- Actual utility service, substation GIS/queue/interconnection rights, equipment availability, hydraulic/thermal grid constraints, CAD, GIS basemap, and physical deliverable MW validation.
- Permitting jurisdictions' filing APIs, document review automation, live approval status, and authorized submission workflows.
- Multi-tenant production security, internet exposure, third-party live agents, customer sharing and native desktop app.
- Real project financing certification (G4/G5), contract-level facility scope/ring-fencing, legal waterfall priority and independent human model review.
- True power-availability-based model constraints and comprehensive critical-path network calculations. These are natural next milestones.

## QA and release gates

The accepted release requires TypeScript compilation; old and imported financial regressions; v26 API and Risk tests; six extra v26.2 API tests; and v26.2 browser walkthroughs at 1440, 1024 and 390px, including path-linked model runs and permit checklist updates. The former v26.1 browser-navigation test script is retained in the repository as an older-UI diagnostic, but is **not** the v26.2 release gate. Keep version hashes of all four frozen financial/Risk source modules unchanged. Review `V26_AUDIT.json` for machine-run acceptance status.

**CAUTION:** Local databases, attachments and records are unencrypted-by-application, not tenant isolated and not backed by a managed system. Keep the service loopback-only. Do not expose private data or share this server over a network.
