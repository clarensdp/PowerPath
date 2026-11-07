# PowerPath v25 — Staged Development & Debt Stress Test

**Date:** October 25, 2026. **Status:** Local prototype; not validated financing advice.

## What was built
The new **Underwrite** tab inside Project Intelligence models three individually scheduled data-center buildings, per-building construction capex, first-service power gating, lease starts, operating income, power costs, loan-to-cost construction draws, loan origination fees, capitalized interest while construction is ongoing, interest cash payments thereafter, scheduled principal payments after the loan term, levered equity flows, NPV, IRR, equity multiple, minimum DSCR, liquidity and covenant flags. A 120-month monthly schedule can be exported as CSV from the UI. The Underwrite model currently uses its own assumptions; it does **not** automatically import hourly dispatch, utility tariff results, true contracted lease rates, real lender terms, or equipment delivery delays from the v24 screening engine.

## Default illustrative case
- Three 50 MW IT buildings, 150 MW IT total, each with staggered construction and energization.
- Rent $170/kW-month, $7M per IT MW capital cost, 65% LTC, 8% stated debt interest, 10% equity discount rate, $85/MWh wholesale-style power input, $50M opening cash.
- Default levered NPV **$-129.0M**, IRR **-1.97%**, equity multiple **0.91x**, peak debt **$773.1M**, minimum DSCR **1.19x**. The default scenario has **3 covenant warning months** and **82 liquidity-shortfall months**. A negative result is important feedback about the assumptions, not a judgment on a real property.

## Additional stress testing
- **45 deterministic combinations**: additional power delays 0, 3, 6, 12, 18 months; capex overruns 0%, 10%, 20%; borrowing-cost shocks 0, 200, 400 basis points.
- Worst case by levered NPV: **$-553.0M**, at **18 additional months**, **20% overrun**, and **400 bps** rate increase. It produces **84 monthly DSCR warnings** and **114 liquidity-shortfall warnings**.
- **300 seeded randomized assumption sets** were tested for finite output and the debt-balance reconciliation identity.
- **16 focused test groups** cover staged power availability, full capex spending, construction draw mechanics, conservation of debt, equity cash-flow identities, no-debt scenarios, direction of sensitivity to delays/overruns/rates/power prices/rent, invalid inputs, and the 45-case grid.
- **Desktop 1365 px and mobile 390 px smoke tests** succeeded, including calculation and table rendering; neither displayed horizontal page overflow or uncaught JavaScript errors.

## What the exercise found
1. Funding risk can dominate an attractive stabilized rent case: initial cash and equity-call requirements must be modeled explicitly, rather than interpreting the equity IRR as fully funded.
2. Debt maturity risk is not yet properly treated: the current prototype begins amortizing after the construction-loan term instead of implementing a true repayment/refinancing balloon. This likely understates a term-loan maturity constraint. **Do not use the debt assumptions for lender commitments.**
3. DSCR covenant breaches are flagged, but no default, cash sweep, lender remedy, extension fee, refinancing rejection, or forced sale is modeled.
4. The scenario grid is deterministic and **does not** provide event probabilities, P50 dates, or calibrated NPV-at-risk.
5. Real utility service, equipment slots, regional delivered tariffs, staged lease contracts, tax, depreciation, escalation, and terminal values remain future integrations.

## Recommended next model hardening
- Replace simple debt maturity logic with separate construction and term loan facilities, fixed versus floating rate terms, interest-rate hedge, capitalized carry, draw reserve, lender fees and a real maturity/refinancing balloon.
- Track sponsor equity contributions and restricted cash separately from distributions and unrestricted liquidity, avoiding cross-use of equity-return flows as liquidity.
- Derive building-level energization from specific power tranches and minimum firm MW, and connect verified utility schedules to lease commencement and liquidated damages.
- Reconcile an annual lender model against the 120-month schedule; publish full sources/uses and financial statement identities.

**Caution:** All values above are derived from synthetic illustrative assumptions supplied as defaults in v25. They are not live price forecasts, signed utility commitments, or actual project underwriting.
