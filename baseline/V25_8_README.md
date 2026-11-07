# PowerPath v25.8 — Runbook

A self-contained PowerPath HTML application with a deterministic JS financial engine. It can open offline, and the financial underwriting module is accessible under **Project Intelligence → Underwrite**. Data connectors and the local vault have separate setup and security requirements.

## Quick commands

```bash
cd PowerPath_v25_8/workspace
for file in test_*.cjs; do node "$file" || exit 1; done
cd ..
python audit/reference257.py
python audit/verify_v258_cases.py
node benchmarks/run_benchmarks_v258.cjs
node audit/change_impact258.cjs
python workspace/build_page.py
```

The benchmark comparison requires **PowerPath_v25_7/** and **PowerPath_v25_8/** as sibling directories. The run scripts support that layout. The baseline's complete folder is included in the Claude handoff package.

- `workspace/underwrite25.js` — updated core engine and UI.
- `workspace/test_transaction258.cjs` — newly discovered defect regression tests.
- `workspace/contract_notes258.js` — independent public notes calculator, **not** integrated into underwriting.
- `workspace/test_contract_notes258.cjs` — notes arithmetic regression fixtures.
- `audit/reference257.py` — independently written Python monthly projection updated for v25.8 functionality.
- `audit/verify_v258_cases.py` — six independent tricky financing and delivery comparisons.
- `benchmarks/run_benchmarks_v258.cjs` — 16 public cases and 720 consistent stresses; uses disclosure strength labels.
- `benchmarks/v258_results/` — frozen inputs, modeled results, and summary.
- `V25_8_FINANCIAL_AUDIT.md` — detailed audit findings and material exception register.

**Do not interpret passing tests as signed utility MW, independently validated lease terms or lender-approved financial results.**
