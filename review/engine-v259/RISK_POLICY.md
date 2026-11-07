# PowerPath Risk Policy — Valuation and Certification Gates (v25.9)

**Owner:** Risk. **Effective:** 26 Oct 2026. **Enforced in code:** `assurance.assess()`, with policy tests in `test/assurance.test.cjs`.

## 1. Permitted uses
| Use | Status today | Unlocks only when |
|---|---|---|
| Scenario screening | **Allowed, qualified** | Monthly accounting identities hold (G2 not FAIL) |
| Real-transaction valuation | **BLOCKED for all cases** | G4 PASS (executed leases, indenture schedules, utility agreements, model-to-contract match, every material term labeled *Executed*) **and** G5 PASS, with no modeled default |
| Lender-grade certification | **BLOCKED for all cases** | As for valuation, **and** zero covenant breach months |

Material terms that must be *Executed*: rent, lease term, commencement, power responsibility, capex, debt terms, amortization, utility service.

## 2. What can never unlock a gate
- Test counts, CI passes, golden snapshots or reference parity. These prove arithmetic only (G2/G3).
- AI or automated review of any kind, including this one. A reviewer or firm name matching AI or automated tools is rejected.
- A review of a different engine version or different inputs: the review must carry the exact `engineVersion` and the `inputHash` of the assumptions it covered.
- Public headline totals: "total" rent calibration is an identity by construction (G1 is never more than QUALIFIED).
- Management expectations or secondary reports, which stay labeled as such.

## 3. Display rules (binding on every UI)
1. A valuation figure (NPV, IRR, equity multiple) never appears without the label **"Screening scenario — not a valuation"** while `uses.transactionValuation === 'BLOCKED'`.
2. Credit warnings are visible by default, never collapsed and never color-only.
3. The project status chip (screening readiness, financeability, "Not contract-verified") is always on screen in a project view.
4. Portfolio views never rank or sort cases by valuation by default.
5. Every editable assumption shows its evidence label; anything unsourced shows "Assumption".
6. Exports (memo, PDF, CSV) carry the same labels, the gate table and the engine version and input hash.

## 4. Change control
- Any change to `assurance.cjs` thresholds or the material-term list needs a policy-test change in the same commit and Risk sign-off.
- Any new engine output used for valuation must be added to the display rules before it ships.
- Releasing a version requires the checklist below.

## 5. Release checklist (Risk sign-off)
- [ ] `npm run ci` passes; golden snapshot unchanged, or the change is explained
- [ ] Independent reference parity is ≥ 1 per new feature, with disagreements resolved or listed
- [ ] Every 16-case assessment reports valuation BLOCKED and certification BLOCKED
- [ ] UI review against §3 completed, with screenshots at 1440 px and 390 px
- [ ] Issues and exceptions registers updated; no "lender-grade", "certified" or "validated" wording anywhere in product copy
