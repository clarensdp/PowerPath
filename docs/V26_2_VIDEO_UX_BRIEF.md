# PowerPath v26.2 — Video-derived Product & UX Brief

**Reference:** Two user-supplied Basepoint Features screen recordings (94.24 seconds and 13.47 seconds, respectively), reviewed 26 October 2026. The recordings show a phone playing a video of a desktop interface, so some detailed captions cannot be independently read. Time codes are approximate and refer to the recordings. This is a design review, not a claim that Basepoint's operational integrations or agents work as shown.

## A. What the recordings actually demonstrate

| Recording / time | Observable UX pattern | PowerPath translation |
|---|---|---|
| Long 0:04–0:15 | Project lists and a versioned files table with document type and uploader | Searchable project evidence register with version, fact ID, uploader, evidence grade and linked financing input |
| Long 0:20–0:27 | Agent directory organized by specialties such as Land, Grid, Permits and Engineering, with work statuses and application icons | PowerPath Workbench: feasibility, interconnection, PermitIQ, finance and Risk assistants; all work attached to one project and one audit trail |
| Long 0:28–0:37 | Inbox/updates feed grouped by action item, risk, project update, milestone and waiting-on tags; related people/projects attached | Decision-changing alerts with owner, due date, affected path to power, expected timing / financial sensitivity and source |
| Long 0:39–0:56 | Grid map with selection/search, surrounding infrastructure/substations, a contextual detail inspector, progress log and scored table | Compare geospatial interconnection candidates and power-delivery alternatives in map + evidence + financial impact workspace; sourced vs model-estimated distinguishable |
| Long 0:58–1:12 | Layered site drawing and an equipment/layout configuration dialog | Consume / display site layouts and constraints and let users compare space requirements; do not build a CAD tool before buyer evidence warrants it |
| Long 1:13–1:21 | Multistep permit/document checklist culminating in a generated, structured PDF-like permit package | PermitIQ: jurisdiction-specific checklist, dependency chain, supporting files, human approvals, package export, status and evidence provenance |
| Long 1:24–1:34 | Project-specific finance deliverable table and project-member invite/share affordance | Finance tab with source-backed financial outputs and shareable review scopes; signed off only where Risk gates pass |
| Short 0:00–0:05 | Project list, horizontal schedule/Gantt timeline and structured permit list | Portfolio register → project execution schedule → permit record without switching disconnected systems |
| Short 0:06–0:13 | Detailed permit drawer with review status/progress (5/11), Checklist/Details/Files/Notes/Activity tabs, task linkage and package preview | PowerPath permit drawer with evidence checklist, blocking dependencies, timeline and live model-run impact from delay |

## B. The signature PowerPath product interaction

User starts with a load target (MW, geography, energization deadline, risk budget). PowerPath maintains a **single durable project** and compares 3 or more feasible configurations **only when assumptions and source status are displayed**:

1. **Decision** — shortest credible path to energization, fastest / lowest-cost / lowest-carbon alternatives, utility commitments, key unknowns, financeability block, and source-backed delay sensitivity.
2. **Power** — substations, queues, grid and behind-the-meter options, mapped source confidence, energy prices and power responsibility, potential trapped energy.
3. **Execution** — permitting + interconnection critical path, milestones, owners, evidence checklist, dependencies and change alerts.
4. **Finance** — capex, lease cohorts, power pass-through, debt facility waterfall, DSCR, covenant breaches, cash gaps, scenario run comparison.
5. **Evidence** — contracts, document versions, facts, provenance, input-to-source mapping, contradictions, approval gates, and review history.

Global navigation should stay minimal: **Portfolio / Projects / Intelligence**. Within a project, keep the five contextual tabs above. Persistent project header always shows project, version, evidence tier and Risk's BLOCKED/CONDITIONAL decision; don't hide warnings below the fold.

## C. Features with the strongest leverage

### P0: Evidence-backed permit & interconnection action stream
- Display cards for risk signals, actions, milestones, awaiting third parties, data freshness.
- Each card has `source`, `owner`, `confidence`, `affected milestone`, `delayMonths`, `deltaNPV`, `approvalRequired`.
- Clicking a card opens a contextual drawer, never an unrelated route; any modeling change requires a versioned scenario and approval.
- Start with user-entered or uploaded milestone data. Do not claim automatic regulator/utility monitoring until a real connector exists.

### P0: Unified facility/site inspector
- A map and shortlist can show hypothetical sites or grounded spatial features, with evidence tags and capacity basis explicitly displayed.
- Selecting a utility asset/candidate overlays assumptions, interconnection status, contingencies, and scenario changes.
- Do not display unsourced 'available MW' as utility-confirmed or commercializable power.

### P0: Decision comparison + model linkage
- Present grid-only, onsite, hybrid/colocation in a comparable table; date, probability/uncertainty, initial cost, power cost, sponsor gap, DSCR, carbon and source status.
- Missing source inputs should read **UNKNOWN**, not be assigned reassuring default zeros.
- Expanding a path shows the financial run that generated its metrics and the evidence it used.

### P1: PermitIQ detailed drawer
- Replicate interaction pattern, not visual design: Review status, checklist x/y, related tasks, files, notes, activity, dependencies, package export.
- Separate AI-generated draft from user-approved final; label hypothetical requirements if jurisdiction-specific rules haven't been verified.

### P1: Visible, honest AI workflow
- Agent cards show job, evidence sources, work completed, blockers, time of last action and human approvals.
- 'Generate memo' is permitted with cited source facts; 'submit filing', 'change financing scenario' and 'certify' require higher permissions; certification is never performed by AI alone.

### P2: Document generation and layout intelligence
- Structured diligence binders, review-ready monthly model book, permit packages and data room exports.
- Site design/CAD should be integrated via third-party viewer or imported drawing, not engineered from scratch for MVP.

## D. UI acceptance criteria

- Entire flow from portfolio → project → candidate power path → permit critical path → saved financing sensitivity → evidence gate is navigable without abandoning project context.
- All user-triggered model changes create a new run and preserve previous inputs, engine version, source hashes and Risk assessment.
- Failure condition: a low facility DSCR, unfunded cash, undocumented utility supply, or unresolved rent/capex assumption must not raise the readiness category.
- Screen reader / keyboard accessible; responsive at 390px, 1024px and 1440px; no blocked warnings hidden on mobile.
- Clearly distinguish **project data** from **synthetic demo inputs**, *modeled* from *verified*, *suggested* from *executed* and human review from AI review.
- No external writes, permit submission, financing action or document sharing without explicit user approval and permission checks.

## E. Out of scope for v26.2

- Full CAD/layout authoring, automatic utility-confirmed MW, live regulator filing, unreviewed permit submission, lender certification, and production-grade agent autonomy.
- Native desktop app. Web-first product architecture remains the right path.

## F. Design-agent assignment

**CPO**: define principal target user and top-three decision tasks; **Head of Design**: create low-fidelity UX and component system for Decision, Execution and Evidence; **CTO**: implement against v26.1 project/run/evidence API while preserving versioned engine; **CDO**: distinguish source confidence and confirm rights to data; **CFO**: validate financial impact cards and their units; **Risk**: own immutable gates and approval rules; **Chief of Staff**: release scorecard and QA signoff.

**Immediate build slice:** project decision overview + critical-path/permit drawer + linked versioned finance scenario. This is the fastest route to demonstrate Basepoint-like continuity while emphasizing PowerPath's differentiated speed-to-power and investability analysis.
