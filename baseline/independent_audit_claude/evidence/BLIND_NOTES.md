# Blind code-audit notes (written before reading V25_8_FINANCIAL_AUDIT.md or the test suites)
Source read: PowerPath_v25_8/workspace/underwrite25.js evaluate() and contract_notes258.js

H1 Refinanced loan sized on ANNUITY payment (paymentPerDollar) but repaid on LEVEL-PRINCIPAL
   (debt / remaining months) -> early actual debt service well above the sized amount; DSRA target
   uses annuity too. Expect DSCR below refinanceDscrMin right after refi.
H2 Shared (unassigned) power tranches are re-allocated from scratch every month in building order.
   If a later-listed building is ready first and takes shared MW, an earlier-listed building
   becoming ready later steals it -> "Physical supply allocation fell" exception on valid input.
H3 Tranche MW is always treated as IT MW even when capacityBasis='gross' (buildings converted by PUE,
   tranches not) -> gross/IT unit mixing.
H4 summary.operatingMWh still uses flat 730 h/month although energy cost uses calendar hours.
H5 Terminal balance-sheet leaks: tenant reimbursement receivable outstanding at horizon and the
   working-capital balance are never settled/reported at exit.
H6 After any earlier default, residual cash left after ALL debt is repaid at exit is neither
   distributed nor reported (stranded); creditor priority is respected but equity residual vanishes.
H7 amortMonths (construction loan) and dsraReleaseAtExit are validated/defaulted but never used.
H8 rateShockPct does not apply to the refinanced rate or mezz rate (stress grid only shocks
   construction senior interest).
H9 Campus-wide capitalisation: all interest is capitalised while ANY building is under construction,
   even when earlier buildings are generating CFADS (policy assumption, not a bug per se).
H10 contract_notes258.js: coupon = face x coupon/2 on every row including first (stub) period
   regardless of issue date; no link to evaluate().
