# PowerPath v24 — Site-to-Power Delivery Economics

## New workflow
Open the standalone HTML, create/select a Connection Plan project, then go to **Site & Data Room → Delivery economics**. Enter required facility MW, target full-power month, and an explicit economic cost per month of delay. Compare grid-upgrade, onsite, hybrid and custom paths on candidate MW, first/full-service month, upfront connection capex, annual incremental power premium, years, self-reported evidence status, and documentary references. Existing infrastructure from the project register is displayed by straight-line distance.

### Decision rules
- A path is **eligible** only when the user states its evidence is “Utility confirmed,” its capacity meets full project MW, and full delivery is no later than target. This is **self-reported**, not authenticated document verification.
- All others are flagged as screening-only, not credible confirmed recommendations.
- Screening total ($M) = connection capex + incremental annual cost × contract years + months after deadline × specified delay value ($M/month). It is NOT discounted project NPV. The existing dispatch, cashflow, tariff and v21 six-month sensitivity engines remain independent; no implicit changes to core financial assumptions.
- The comparison can be exported as JSON. Entries persist in browser localStorage per project.

### Limitations
Nearby power plants, substations, and pipelines in site screening are not proof of available electrical capacity or delivery rights. The model does not solve network flows, line upgrade estimates, gas permits, reliability, cost of capital, tax, battery operation, or contractability. Entered statuses and assumptions have not been independently verified. Historical generation datasets and imported point GIS may be out of date.

### Testing
Run all tests: `for f in workspace/test_*.cjs; do node "$f"; done`.
New module: `node workspace/test_delivery24.cjs` (11 checks).
Browser smoke tests: desktop 1365 px and mobile 390 px, workflow open and compare, no page errors, no horizontal overflow.

### No autonomous AI
No agents have been added.
