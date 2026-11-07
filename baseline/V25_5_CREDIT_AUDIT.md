# PowerPath v25.5 — credit controls and lender-source audit

## Source document examined
Applied Digital Corporation / APLD Intermediate Holdco LLC, Credit Agreement, May 29, 2026, SEC Exhibit 10.1: https://www.sec.gov/Archives/edgar/data/1144879/000149315226030333/ex10-1.htm
Applied Digital Q1 FY2027 Form 10-Q: https://ir.applieddigital.com/sec-filings/all-sec-filings/content/0001144879-26-000059/apld-20260831.htm

This is a **parent/holdco revolving-credit agreement**, not a full project-specific Polaris Forge construction loan waterfall. Material covenant inputs are redacted. The publicly filed agreement establishes relevant concepts (restricted payments, indebtedness, defaults, DSCR-based provisions) but DOES NOT substantiate any specific cash-sweep percentage, reserve amount, or project-level DSCR hurdle in this model. The optional credit-control parameters below are clearly illustrative, not reported contractual terms.

## Confirmed code corrections
1. **No post-refinance construction draw:** Once a construction debt facility is refinanced, later construction spending cannot automatically draw more funds from the retired facility. Those later costs are met by operating cash or new sponsor funding unless a new facility is separately modeled. This prevents credit facility reuse without an agreed commitment.
2. **Optional sweep:** `cashSweepPct` [0,100], default 0; a share of free unrestricted cash above `minLiquidity` prepays senior principal. Sweep is part of cash uses, loan principal tracking and cash reconciliation. It cannot use restricted reserves or pay more than the loan balance.
3. **Distribution lock:** Existing debt with unavailable DSCR prevents interim distributions, as does DSCR below `distributionDscrMin` (default 1.20) or existing default. The model does not assume a borrowing agreement's actual covenant terms.
4. **Tested controls:** Post-refinance capital spending with no unauthorized draws; sweep arithmetic and debt balances; restricted distributions; rejection of sweep > 100%; monthly identity checks.

## Test evidence
All `workspace/test_*.cjs` scripts passed in this release, including the new `test_credit255.cjs` with five assertions. This remains a mathematical/regression audit rather than legal-contract validation.

## Remaining restrictions
- Refinance, senior/mezz lien priorities, cash dominion, fee waterfalls, intercreditor arrangements, covenant cures, and restricted-payments exceptions differ across lenders and cannot be generalized from one agreement.
- Detailed reserve release and debt service reserve mechanics are not replicated.
- No executed project-level loan model and actual monthly billing/draw records have been independently reconciled.
- Do not label the valuation lender-certified. Cash sweep and distributions remain scenario-level controls, not lender legal opinions.
