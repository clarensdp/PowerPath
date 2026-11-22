# PowerPath v27.1.0 — financial engine remediation and first transaction reconstruction

**Development alpha, local only. G4 and G5 remain BLOCKED.** Read `docs/v27_1/` for the full validation packet.

## What changed (financial scope only; no new product modules)
1. **RT-A02 fixed in a new versioned engine** `engine/underwrite27.js` (27.1.0). Cash-constrained debt service, separate
   unpaid interest / past-due principal / unpaid payables, configurable payment priority and reserve use, lender claims
   preserved at exit, monthly identities. `engine/underwrite25.js` is byte-identical and still runs every scenario stored
   before v27.1 (no `engineVersion`). New underwriting scenarios default to `engineVersion: "27.1.0"`.
2. **RT-E04b fixed**: one canonical schedule engine `server/schedule27.py` (`schedule-27.1.0`) used by every interface,
   with a `schedule_version` on every result, plus the read-only `/paths/{id}/schedule-impact` report.
3. **Core Scientific Finance I 7.750% notes due 2031**: evidence register with six classifications and a promotion guard,
   instrument schedule (`engine/fixed_note27.cjs`) under contingent-amortisation scenarios, filing reconciliation, and a
   separately labelled illustrative project scenario. Endpoints under `/api/projects/{pid}/transactions/core-scientific-2026/`.
4. Restored `review/engine-v259/data/transactions_v259.json`, missing from the v27.0 package (inherited audit was 36/37).

## Validate
```bash
python -m pip install -r requirements.txt
python tests/run_v268_audit.py            # full: 18 checks incl. inherited 37/37 and all v27.1 suites
python tools/build_underwrite27.py . --check
```
Browser checks need Playwright's Chromium (set POWERPATH_CHROMIUM if not on the default path) and TypeScript 5.x for `tsc`.

## Use limits
Local prototype; financial screening on user assumptions; public-debt instrument reconstruction as an inspectable
reproduction of filed terms. NO project valuation, hosted institutional use, live agents, or lender-certified use.
