# PowerPath v26.1 — Integration Review (Oct 26, 2026)

## Decision
**ACCEPT as a local, bounded screening integration.** Do **not** deploy as hosted SaaS, real-project transaction valuation, debt placement analysis, or certified lender tool.

The uploaded independently reviewed v25.9.0-risk1 debt engine is integrated into the persistent v26 application as an **additional** scenario mode `notes_v259`. The original v26 underwriting engine and separate `facilities` alpha remain intact, with their hashes compared to frozen baselines. No stored legacy runs are migrated or reinterpreted.

## What was implemented in this integration

- Copied, without modifying the source, the release's `underwrite.cjs`, `facilities.cjs`, `notes.cjs` and `assurance.cjs` under `engine/v259_verified/src/`.
- Added a `notes_v259` calculation mode to the isolated Node bridge, and exposed a synthetic note sample from `/api/defaults`.
- Extended persistent project scenarios and versioned run history to support `notes_v259`. The new engine's SHA-256 is stored as `engine_sha256`; the facility module hash is stored as `finance_sha256`.
- Ran Risk's original G0–G5 source module on every new note run, supplying **no verified documentary or external-review assertions**. Client-provided approvals are ignored. The server always blocks `transactionValuation` and `lenderCertification` in the current local-only release.
- Made Risk's `screening` permission consistent with the new engine's `screeningReadiness` when facility DSCR fails, and ensured `financeabilityStatus` also identifies the facility breach.
- Added the notes scenario to the actual interactive Debt Facilities page. The visible red decision strip precedes the NPV. Old facility and underwriting scenarios still work.
- Preserved the uploaded three-destination `PowerPath_Institutional.html` inside `design/` as a **nonpersistent design reference**, not falsely represented as the deployed frontend. The project-based v26 web interface remains fully functional.
- Added new tests for saving, reopening, forged-approval attempts, nonperforming note DSCR, collateral validation and source hashes. Added Chromium desktop/tablet/mobile workflow check.

## Independently reproduced checks

- **34/34 top-level v26 audit jobs PASS**, including legacy financial suites, browser, API, notes integration and hash checks (`V26_AUDIT.json`).
- **61/61 imported v25.9 Node tests pass**, rerun from the actual uploaded source.
- **80,240 field checks** passed using the uploaded `scripts/reference_parity.cjs` runner, maximum gap approximately `1.42e-12 $M`. The upstream release claims 173,768 comparisons across its wider collaboration; that wider count was not independently reproduced by this runner in our environment, and is not claimed here.
- Chromium accepted the notes workflow and blocking decision at 1440 px; project views passed at 1440/1000/390 px, with no page JavaScript errors or horizontal overflow.
- The v25.9 engine and Risk modules preserve the supplied bytewise SHA-256 source hashes. The original v26 finance modules are also unchanged.

## Material blockers retained

1. **G4 FAIL / G5 NOT STARTED:** no executed lease, utility-rights or indenture-to-model reconciliation, or qualified independent human model review.
2. **Facility cash pools:** no legal ring-fencing, arrears ledgers, default interest, make-whole or contractual ECF offers. Facility labels and hierarchy are screening assumptions.
3. **Transactions:** Applied Digital, Galaxy and Core note terms contain uncertain amortization schedules, obligations, collateral scope and rent-trigger dates. The hypothetical note in v26 is **not** one of these transactions.
4. **Input realism:** frozen public cases retain generic power-payer and capex assumptions. The scenario NPV is *not* a verified security or transaction valuation.
5. **Server security:** v26 binds to loopback, uses local SQLite and file evidence, and has **no authentication, permissioning, multi-tenant isolation, hosted encrypted storage or operational certification**. Do not expose through a tunnel or upload sensitive documents.
6. **Frontend convergence:** the imported institutional single-file interface is a product-design reference. Porting its three-destination navigation into the persistent v26 web app is still a separate engineering task.

## Start, inspect, verify

```bash
cd PowerPath_v26_1_Integrated
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./run_local.sh
# Local browser: http://127.0.0.1:8768
```

From the **Debt Facilities** view, select **New v25.9 notes scenario**. It uses a synthetic $250M note (7.5% coupon) and cannot be used as a public transaction claim. Edit face/coupon, or open advanced JSON to edit multiple sourced/unsourced note facilities. Saving produces immutable inputs, a dated run, ledger rows, engine hash and Risk decisions.

```bash
python tests/run_audit.py
# See V26_AUDIT.json and previews/notes_v259_desktop.png
```

## Next release priorities

1. Risk/CFO: contract- and building-specific cash pools, source-backed note triggers and note/lease reconciliation.
2. CPO/Design: port the `design/` three-destination interface into the **persistent** web app without losing project history and evidence permissions.
3. CTO: proper authentication, permissions, private storage, evidence attestation and hosted deployment preparation; no public deployment before security review.
4. Independent qualified reviewer: G5 frozen-version scope review after G4 is complete.
