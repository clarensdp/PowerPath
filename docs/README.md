# Documentation

Start with the [project README](../README.md) for installation and commands.

## Current guides

- [Power market data](MARKET_DATA.md): NYISO LMP, Henry Hub, spark spread, grid demand, fuel mix, retail prices, licensed imports.
- [Excel add-in (prototype)](EXCEL_ADDIN.md): PP.GET / PP.TABLE / PP.BRIDGE formulas, formula builder, sign-in window, sourced sheets.
- [v31.5 underwriting layer](UNDERWRITING_V31_5.md): evidence register and ledger, deliverability, returns bridge, change review, forecasts, MCP server.
- [Site energy integration](SITE_ENERGY_INTEGRATION.md): EIA, solar, infrastructure and scenario inputs.
- [Architecture](ARCHITECTURE.md): application structure.
- [Engineering handoff](COFOUNDER_HANDOFF.md): project context and operational boundaries.
- [GitHub guide](GITHUB_PUSH_GUIDE.md).
- [PostgreSQL runtime status](POSTGRES_RUNTIME_CANDIDATE_STATUS.md) and [cutover runbook](POSTGRES_CUTOVER_RUNBOOK_V3081.md).
- [Change history](CHANGELOG.md).

## Historical records and verification

- [Release notes and older quickstarts](releases/), including [v30.8.3](releases/RELEASE_V30_8_3.md).
- [Manifests](manifests/): archived package inventories and protected-engine hash baselines.
- [Reports](reports/): retained audit/test results. The v30.8.1 gate writes its current result to `docs/reports/TEST_REPORT_V30_8_1.json`; cutover preflight reads the same location.
- [Archive](archive/): historical migration SQL preview, not an executable deployment instruction.

Historical manifests retain their original bytes, file paths and hashes. They describe
the original release packages, not today's reorganized directory. The protected-engine
checks still read the preserved `docs/manifests/ENGINE_HASH_AUDIT_V30_3.json` baseline
and verify files in `engine/`.

These documentation and verification files do not supply dashboard statistics. Runtime
records remain in `data/`, source datasets in `data_sources/`, and synthetic test fixtures
in `tests/fixtures/`. Historical release notes describe behavior at their release date;
use the current project README for startup instructions. Commands are run from the
repository root unless stated otherwise.
