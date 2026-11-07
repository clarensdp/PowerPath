# PowerPath v25.8.4 — Underwriting power-cost responsibility

Open `PowerPath.html` locally for offline scenario analysis. In **Project Intelligence → Underwrite**, select a project-level power payer and reimbursement share; optionally override the payer per building. Enter sources into the lease reference fields. The user is responsible for entering verified project information. Importing these assumptions does not confirm utility rights.

- `workspace/underwrite25.js`: authoritative current financial prototype.
- `workspace/test_power_pass2584.cjs`: power and cash-flow regression tests.
- `independent_power_reference.py`: independent operating arithmetic reference check.
- `benchmarks/case_catalog_v2584.json`: corrected 16-case public disclosure / confidence catalog.
- `benchmarks/run_power_cost_2584.cjs`: 16-case + 720-scenario run and v25.8.3 comparison.
- `benchmarks/v2584_results/`: outputs of the run.
- `V25_8_4_POWER_COST_AUDIT.md`: disclosure and validation findings.
- `CLAUDE_NEXT_AUDIT_PROMPT.md`: independent reviewer brief.

This application is an **assumption-driven prototype**, not a secure production application, a project finance model certification, or an audit opinion.
