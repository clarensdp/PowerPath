# PowerPath v25.6 — Credit waterfall controls and independent ledger review

## Implemented
- Added a debt-service reserve account (DSRA) target expressed as configurable months of projected **refinance term-loan** scheduled debt service. The modeled restricted reserve target is the higher of the previous fixed reserve target and the DSRA target. No DSRA months defaults to zero, leaving previous model economics intact.
- Monthly restricted cash contributions/releases are explicit. Underfunded reserve targets produce a deficiency flag and prevent equity distributions.
- Added independent monthly accounting controls for senior principal, mezzanine principal, and restricted reserve movements; reported maximum residuals are in the summary and export.
- Exposed DSRA months and audit outcomes in the Underwrite screen. No autonomous agents were introduced.

## Testing and limits
- All existing workspace `test_*.cjs` scripts passed; new `test_waterfall256.cjs` covers six illustrative configurations and reserve accounting.
- Independent Python script `audit/independent_ledger.py` recalculates cash/reserve identities and refinance proceeds **using reported PowerPath cash-flow lines**. It is independent arithmetic verification, **not** an independently built forecast of rent, construction, taxes, or loan economics.
- Reference verification: 5 scenarios; 2,404 Python assertions; maximum absolute cash/reserve residual about 2.3e-13 million dollars. Details: `audit/results.json`.

## Material remaining blockers
1. No independently sourced lender agreement with a fully observable project-level waterfall. The DSRA sizing rule is an illustrative product control, not a reproduction of any executed loan covenant.
2. Modeling still assumes unlimited sponsor equity funding when the modeled minimum-cash threshold would be violated; actual sponsor capacity, equity cure terms, and restructuring/recovery are not validated.
3. Refinance proceeds use a synthetic reference value and spot-month annualization of EBITDA, not a documented forward twelve-month CFADS financing case.
4. DSCR currently uses EBITDA rather than contract-defined CFADS and does not fully implement project taxes, working capital, reserves for maintenance or contractually defined lender adjustments.
5. Interest capitalizes into debt before refinance where construction is active; contractual allocation and priority across multiple tranches need validation.
6. The model is **not** lender-certified. No independent human audit or signed-off transaction model comparison is available.

## How to reproduce
```
cd workspace
for f in test_*.cjs; do node "$f"; done
cd ..
python audit/independent_ledger.py
python workspace/build_page.py
```

This release is appropriate for hypothesis-driven comparative underwriting only. Financial verification status remains NOT INDEPENDENTLY VALIDATED.
