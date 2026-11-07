# PowerPath v25.1 — Financial model integrity release

## Changes
- Replaced simplified loan amortization with explicit construction-loan maturity. `loanMaturityMode` can refinance, fund payoff with sponsor equity, or flag an unfunded loan default. Refinancing pays off old loan and opens a new loan limited by modelled refinance LTV and valuation. Refinance assumptions are user assumptions, **not guaranteed financing**.
- Segregated sponsor funding, unrestricted cash, and restricted reserves. Equity flows are modeled contributions and distributions; initial sponsor cash is an initial equity flow. A cash shortfall is met by separately recorded sponsor contributions, never hidden in a negative cash account.
- Monthly sources-and-uses reconciliation. Includes operating EBITDA, eligible loan draws, refinancing proceeds, capex, fees, interest, principal, equity funding, reserve movements, terminal sale proceeds, exit debt retirement, and distributions.
- Added shared and building-specific power-tranche allocations with construction/lease eligibility. Staged operating MW drives rent and energy expense. Shared tranches may not be duplicated across buildings.
- Added a modelled terminal asset sale and full debt payoff to avoid valuing unreturned equity as if it were liquid. Exit value is a highly sensitive unverified input.
- Added v25.1 UI inputs for loan maturity, refinance LTV/valuation/rate, reserve, liquidity, exit valuation, and optional power tranches. Monthly financial schedule CSV retains all reconciliation fields.

## Limitations / underwriting caution
- This is **not lender-grade**, not a committed credit facility, and not an independent project valuation. Refinance proceeds, asset exit value, energy tariffs, capex, and lease assumptions require documentary evidence.
- Equity-funding shortfalls are assumed financeable: sponsor capacity or availability of equity is NOT tested. A default flag does not simulate restructuring, foreclosure, interest penalties, or lender remedies.
- Monthly power availability is a deterministic schedule; it does not incorporate utility stochastic risk, forced outages, equipment dispatch or customer-specific lease commencement conditions.
- Loan covenants use a simple DSCR proxy; formal lender definitions, debt sizing based on DSCR/LLCR, cash sweeps, refinance underwriting, revolvers, taxes, lender reserves, and financing fees at draw are not fully modelled.
- No integration to the existing hourly dispatch engine: `powerCostMWh` is an averaged input.
- Exit cash flow and terminal leverage are extremely sensitive assumptions. Change values before reliance.

## Tests
`cd workspace && for f in test_*.cjs; do node "$f"; done`
The archived original test suite assumes a loan balance that can never refinance and is retained for reference as `legacy_test_underwrite25_pre_refi.txt`.

## Use
Open standalone `PowerPath.html` and navigate Project Intelligence → Underwrite. Enter one record per optional power tranche as `month,MW,building name`; omit building name for shared power.
