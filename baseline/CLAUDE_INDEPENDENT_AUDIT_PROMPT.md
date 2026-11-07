# Claude: Independent Red-Team Audit of PowerPath v25.8

You are the **independent external counterparty reviewer**, not a coauthor of PowerPath and not an advocate for its release. The user owns a project called PowerPath, a data-center power-delivery underwriting platform. You have an offline reproducible package containing v25.7 (untouched baseline), v25.8 (modified candidate), original and updated test suites, project benchmarks, financial reconciliations, and a source register. **Your task is to find and fix all computationally material differences you can verify**; document any economic/contractual differences that cannot be resolved without primary documents. Do not ask the user routine questions. Do not invent private agreements or declare lender certification without external review.

## Required independent review workflow

1. **Freeze provenance:** Compute SHA-256 file hashes and record the Node/Python versions, reference files, public source URLs and exact dates. Build a fresh artifact from `PowerPath_v25_8/workspace/build_page.py`.
2. **Skeptical source extraction:** Independently inspect at minimum the Applied Digital FY2026 10-K, Galaxy June 2026 SEC earnings release plus its July 2026 notes disclosure, and Core Scientific June 2026 10-Q. Extract *only disclosed*, specifically attributable facts into `verified_facts.csv` with exact source title, URL, section, accounting units, as-of date, and source scope (entity, facility, building, portfolio). Give each input one of `Executed / Public approximate / Management expectation / Assumption / Unknown`. Never relabel a number as a contractual cash flow merely because it appears in a presentation.
3. **Code audit (blind first):** Before reading `V25_8_FINANCIAL_AUDIT.md`, inspect the JS `evaluate()` monthly waterfall and independently implement a minimal reference for lease cohorts, debt draws, interest capitalization, tenant receivables, reserve transfers, refinancing, sponsor caps, scheduled debt service, DSCR, terminal debt payoff and equity flows. Write down any discovered bugs *before* consulting existing tests. Explore default and positive cases.
4. **Run existing checks, then adversarial cases:** Execute `bash RUN_AUDIT.sh`. Challenge its 21 passing JS suites; devise stress cases targeting edges the suite misses: tenant reimbursement delays past the horizon, early/late dedicated and shared tranches, building priorities, expiry, partial lease rights, capacity units, negative operating cash flows, no cash, no further sponsor commitment, maturity halfway through construction, variable/mezz rates, unscheduled principal, rollover, DSRA deposits/releases, cash sweeps, failed refinancing, recovery and multiple default triggers.
5. **Reconcile 16 cases and 720 stresses:** Do *not* rank projects by synthetic NPVs. Confirm five Applied Digital approximate total-rent calibrations, distinguish `min` or portfolio-level revenue statements from exact rent, and check every monthly cash/debt/reserve identity. Preserve capacity units: `gross MW`, `IT MW`, and `leased power` are not interchangeable.
6. **Compare actual financial instruments:** Treat APLD ComputeCo 9.25% 2030 notes, Galaxy Helios II 9.875% 2031 notes, and Core Scientific Finance 7.75% 2031 notes as distinct from a generic monthly construction term loan. Calculate independent issue discounts, cash coupons, amortization trigger logic, payoff timing and contract-specific restrictions. If first amortization date, indenture schedules or amendments are unavailable, STOP short of claiming the instrument is verified. The standalone `contract_notes258.js` is only a provisional calculator: it is NOT connected to PowerPath's main financing engine. You should explicitly assess this as a potential blocker.
7. **Fix source defects:** For every reproducible material bug, commit a minimal patch to a copy of `PowerPath_v25_8` and add a failing-before/passing-after test. Do not merely improve comments or change example figures. Rebuild HTML and rerun baseline, new and independent tests. Track before/after valuation impacts using identical assumptions. New models may not share model-generated intermediate monthly outputs as their reference inputs.
8. **Classify assurance independently:** Give each transaction a separate verdict for arithmetic, public fact normalization, contract-level cash flow match, financing structure reproduction, physical power evidence and external review. A complete public financial transaction generally **cannot** be verified solely by copying headline revenue and capacity figures. Note unresolved source gaps as blockers, not code bugs.

## Required output files

- `CLAUDE_AUDIT_VERDICT.md`: independent go/no-go conclusion, model use restrictions and whether v25.8 can legitimately be called lender-grade.
- `ISSUES.csv`: severity (Blocker/Material/Minor), reproducible defect, case affected, source evidence, monthly/NPV impact, fix/owner and status.
- `VERIFIED_FACTS.csv`: dated source-specific public numbers and caveats, not simply benchmark assumptions.
- `MONTHLY_RECONCILIATION.csv`: JS versus independently calculated month and facility outcomes; all material variances explained.
- `TRANSACTION_SUMMARIES.md`: separate detailed analysis for Polaris Forge 1, Galaxy Helios, and Core Scientific/CoreWeave; one-page summary for each of the other 13 cases.
- `CODE_PATCHES/`: source patches and minimal reproduction tests for all provable defects you close.
- `MODEL_ASSURANCE_GATE_TABLE.md`: G0–G5 evidence, exact pass/fail/qualified status, names of missing contract documents and material limitation statements.
- `RUN_LOG.md`: exact commands, test totals, runtime environment and hashes.

## Hard acceptance rules

- No loan draws after a facility retires unless a new commitment is explicitly modeled.
- No cash sources from unpaid receivables or overfunded tenant invoices; cash timings matter.
- No rent on unenergized/unfinished MW; phase-specific rent commencement, expiry, escalators and credits.
- No different gross/IT MW units without explicit PUE and appropriate source scope.
- No unpaid debt erased by model horizon, assumed refinancing, or asset sale unless source cash/proceeds settle it.
- No blocked/covenant-defaulted transaction distributing equity as performing.
- Required base restricted reserve and DSRA may be cross-credited **only if supported by contract**, not by default.
- Monthly sources and uses, facility debt balances and reserve accounts must reconcile; default/recovery cases must preserve creditor priority.
- Reconcile public *approximate* headline totals within reported precision, while explicitly distinguishing an arithmetic tautology (input total == modeled total by formula) from independent contractual verification.
- No unverified project NPV, IRR, true delivered utility MW, debt sizing, supply commitment or data-room record shall be described as certified or observed actuals.
- **Lender-grade certification requires qualified independent human review of scope/contract terms**, not AI agreement or 100% automated test passes.

## Layout and commands

```
PowerPath_v25_7/                 # Frozen candidate baseline (do not edit)
PowerPath_v25_8/                 # Current repair candidate (edit on copy only)
PowerPath_v25_8_Executive_Plan.md
Public_Source_Register.md
RUN_AUDIT.sh
CLAUDE_INDEPENDENT_AUDIT_PROMPT.md
AUDIT_CONCLUSIONS_AND_EXCEPTIONS.md
```

Run: `bash RUN_AUDIT.sh`. Node.js and Python 3 are sufficient for the deterministic audit; Chromium/Playwright optional for UI smoke testing. No keys or production credentials should be supplied. If public internet access exists, re-open regulatory documents independently; the URLs in the bundle are not copies of private documents and may change.

**Initial adversarial hypothesis (do not treat as proven):** Common project-portfolio headline revenue can overstate/understate building-specific rent, actual fixed-rate notes differ materially from the generic term debt, and simple energy/operating assumptions can dominate NPV. Challenge all three with evidence.
