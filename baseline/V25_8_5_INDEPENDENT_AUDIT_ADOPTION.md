# v25.8.5 independent audit adoption (conditional screening only)

Changes from v25.8.4:
- Power reimbursements use their **own collection lag** (`powerReimbursementLagMonths`, default 0) independent of lease `workingCapitalDays`. A monthly billed reimbursement contributes to accrual EBITDA; outstanding bills are current receivables deducted via changes in working capital from CFADS.
- Optional building-specific reimbursement lag overrides project lag (0–24 months). Never silently infer actual collection from filing descriptions.
- Corrected contractual last-rent-month display from `start+term` to `start+term-1`.
- Applied Digital PF1/PF2/DF1 capex screening uses documented $11–13M/IT MW **anticipated guidance**, $12M midpoint. PF3/DF2 values remain unverified assumptions.
- Withheld asserted power pass-through at PF3/DF2; changed to landlord-paid screening assumption with warnings. Core Scientific client-pay mode is classified as route-unknown (default tenant direct, test reimbursed sensitivity).
- PF1 building-level $3B/$4B/$4B headline split now source-linked but still subject to amended contracts.
- This is *not* a contract-verified financing model. No model output is lender-certified.

Source: https://ir.applieddigital.com/sec-filings/all-sec-filings/content/0001144879-26-000036/apld_invxinvestorpresent.htm

Independent reviewer reported original reimbursement lag and lease off-by-one issues. This package implements them independently from reviewer code and includes regression tests.
