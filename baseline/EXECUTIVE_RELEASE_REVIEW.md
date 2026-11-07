# PowerPath v25.9-alpha — Ten-Role Executive Release Review
**Date:** 26 October 2026  
**Decision:** GO for local exploratory software preview; **NO-GO for lender-grade or public transaction valuations**.  
**Execution mode:** coordinated role-based work in one assistant session, backed by actual code, tests and browser checks. No independent agent model calls or background operation. The Executive Desk v0.3 contains ten role prompts and an end-to-end ten-role workflow for separately consented local API use.

## CEO brief
A redesigned project-first navigation and an **opt-in**, facility-level cash-flow experiment have been delivered. The original v25.8.5 underwriting engine is byte-for-byte unchanged. The additional finance pathway reuses v25.8.5 project cash flow (rent, power, CFADS, construction and tenant receipts), then allocates cash to defined construction debt and fixed-rate note instruments month by month. It does not reproduce the specific Applied Digital, Galaxy or Core Scientific indentures; it uses user-entered terms and retains an explicit screening-only label.

## Agent-by-agent work record
| Role | Workstream outcome | Evidence/artifact | Release judgment |
|---|---|---|---|
| **Chief of Staff** | Sequenced model + UX + risk, documented go/no-go, approval boundaries | This report, `/AUDIT_RUN.json`, Executive Desk workflow | Local alpha only |
| **CFO** | Defined note face/OID, coupon, installments, DSRA, exit, sponsor-cap and debt-scope requirements | `workspace/facility_waterfall259.js` | Assumptions only, not contractual |
| **CTO** | Built separate facility engine; preserved old engine; full regression | `workspace/test_facilities259.cjs`, 27-suite QA, matching legacy SHA-256 | Conditional engineering pass |
| **CPO** | Rebuilt information architecture around user decisions | `workspace/shell.html`, active-project context | Prototype needs actual user interviews |
| **Head of Product Design** | Lighter workspace, guided note inputs, progressive advanced JSON, desktop/mobile styles | `institutional259.css`, browser screenshots | Visual smoke pass, no accessibility certification |
| **CDO** | Kept public-source classifications and exact term exceptions; no unsupported MW confirmations | `benchmarks/case_catalog_v2584.json`, release source caveats | Source qualification remains conditional |
| **COO** | Created reproducible release runner and packaging path | `run_v259_audit.py`, `AUDIT_RUN.json` | Release reproducible locally |
| **CMO** | Bounded position: energy delivery and investment scenario intelligence rather than lender-grade credit certification | Copy in new contextual headers and finance page | No public marketing claims authorized |
| **CRO** | ICP hypothesis: infrastructure finance users and data center development teams; guided scenario walk-through | Project-first UX, workflow spec | No customer validation or outreach performed |
| **Chief Risk Officer** | Blocked any model output from being labeled verified; stopped unresolved-default forecasts; required explicit source and scope | Source warnings, `test_facilities259.cjs`, this no-go register | Lender-grade BLOCKED |

## Improvements released
### Finance — v25.9 Alpha (new opt-in pathway)
- Separate construction and fixed-note facilities with explicit borrower-project building scope.
- Monthly construction draw calculation against eligible construction cost by scoped building, less tenant-funded capex.
- Fixed notes: face liability, issue-price discount, coupon dates, optional explicit first-stub 30/360 fraction, amortization start/first-rent-offset trigger, balloon, principal and interest cash uses.
- Per-facility restricted cash reserve target and priority order as a **screening convention**. Cannot model actual restricted entity-level permitted-use rights or complete intercreditor subordination.
- Capped sponsor funding, funding default, no equity distributions on shortfalls, and no fabricated post-default cash flows or recovery valuation.
- Monthly reconciliation ledger with sources/uses and debt residuals; scenario CSV export has explicit `UNVERIFIED` metadata.
- Guided note inputs plus project financial-input import from **locally saved**, selected Underwrite case. Imports assumptions only; does not import signed documents or validate note terms.

### Product Design — Basepoint-inspired but original UI
- Simplified sidebar: portfolio + project workflow + governance; persistent active-project identity and screening/verification status.
- Project journey: Discover → Power → Execution → Economics → Evidence. Finance alpha accessible beside Economics.
- Light institutional default, calmer typography, green action hierarchy, progressive disclosure for note assumptions and responsive design.
- Financing default shows **NPV unavailable**, not an attractive number unsupported by a workout schedule.
- Project Overview NPV is labeled as an illustrative scenario rather than unqualified green return.
- Patterns derived from Basepoint's publicly described project records, permits/agent workflows, evidence gates and finance tools; no Basepoint artwork, branding, software code or proprietary elements copied.

## QA conducted
- **27/27** JavaScript suites passed, including previous red-team, lease, power-pass-through, covenant and financing controls plus **12 new** facility test suites.
- **6,720** from-scratch independent Python fixed-note due-payment comparisons, 40 synthetic note terms; maximum discrepancy ~1.42e-14 USD millions. This checks only note arithmetic, **not** sponsor/lender full waterfalls.
- Existing-engine public calibration/stress rerun: **16 cases, 720 stresses, zero computational exceptions, zero contract-verified cases.** This is not a performance claim for the *new facility module*.
- Browser UI: Chromium **1440/1024/390 pixels**; new workflow interactions, no page JS exceptions/overflow in tested views.
- Legacy `underwrite25.js` SHA-256 matched prior v25.8.5 baseline exactly: `c4e2a090698411e492f5399a52fddbf233539dc3c1871d0877e53fcfb2d9ce29`.
- Agent council orchestrator: **14/14** unit tests, workflow plan lists ten roles; browsers 1440/390 render workflow. Live model-to-model agents **not executed** (API key unavailable).

## Risk vetoes and active blockers
**R-01 — Real transaction financing:** No signed note indenture installments, springing amortization, collateral restrictions, creditor waterfall, covenants or guarantees reconciled. Generic notes use an interval-based coupon calendar, not a full executed date-specific ledger. **NO-GO for lender valuation.**

**R-02 — Insolvency/recovery:** Default stops the new alpha projection. No legal workout, collateral realization, waterfall, deficiency claims or lender recoveries can be inferred. **N/A for defaulted equity NPV.**

**R-03 — Capacity rights:** No utility/engineering verification of MW delivery; geographic screening is not rights-to-power.

**R-04 — Source completeness:** Public-sourced projects still have missing executed lease terms, power ESAs, financing amendments and actual capex schedules. Historical public-project simulation valuations are **not transaction valuations**.

**R-05 — Product maturity:** Prototype user-testing, WCAG 2.2 AA conformance test, production authentication, permission model, encrypted storage and external multi-agent deployment have not been completed.

**R-06 — Agent autonomy:** The v0.3 Executive Desk orchestrates text memo drafts **only** with a separately configured provider API and authorization. It cannot autonomously code, deploy, access private source systems, file permits or monitor continuously. This session's role outputs are coordinated assistant work, not independent agent-generated conclusions.

## Next engineering gates, no input from CEO required for synthetic verification
1. Build from primary publicly accessible indentures and executed exhibits a **document-to-field assumption table** for each note, including exact coupon dates, payment periods, source entity, collateral and amortization triggers.
2. Implement a **facility-level legal priority / permitted-use and swept-reserve waterfall** with unique borrower scope and lender-specific DSCR period, default-rate accrual and cures, plus executable independent regression fixtures.
3. Extend dynamic cash-tax, demand charges, take-or-pay and construction financing interest capitalization only when documents support terms.
4. Re-test Applied Digital PF1, Galaxy Helios II and Core Scientific note tranches without treating distinct campus/phases or gross/IT MW as interchangeable.
5. Run fresh adversarial independent human model review for frozen transaction-specific release. No automatic lender approval claims.

## CEO release decision
**Publishable as:** internal controlled prototype for comparing user-entered scenarios and designing financing structures.  
**Not publishable as:** institutionally validated investment recommendations, contractual financing schedules, executable debt placement proposals or lender-certified model.

## Public UI inspiration, not a model-data source
Basepoint — `https://www.getbasepoint.com/`, `https://www.getbasepoint.com/platform/projects`, `https://www.getbasepoint.com/platform/ai-agents`.
