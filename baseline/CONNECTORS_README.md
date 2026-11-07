# PowerPath connector foundation (October 25, 2026)

Open PowerPath_v20_connectors.html, select **Data connectors** in navigation, and import individual normalized JSON snapshots. No network connection is required to open the app, and data never silently overrides engine inputs. Browser localStorage holds snapshots per browser/device.

## Live importer (Python standard library)
Run commands from this folder or with absolute paths:

```bash
python connectors_cli.py eia930 --region PJM --start 2026-09-01 --end 2026-09-02 --out pjm_demand.json
PJM_API_KEY='your_personal_key' python connectors_cli.py pjm_lmp --node 51217 --start 2026-09-01 --end 2026-09-02 --out pjm_lmp.json
python connectors_cli.py epa_echo --csv permits.csv --out epa_refs.json
python connectors_cli.py ferc_docket --csv filings.csv --out ferc_refs.json
```

Evidence CSV required columns: `reference,status,as_of`; optional `project_id,facility_id,docket,url,notes`. Import is user-curated and is **not** independent verification or permit status automation. Official PJM API needs a Data Miner key; confirm terms before use in a commercial product. No live calls were made in this restricted environment, so network payloads must be validated on first credentialed run.

EIA 930 importer uses BA **demand** type D. Its EIA-reported period is deliberately retained rather than asserting a UTC time; DST conversion must be verified before enabling hourly engine ingestion. PJM DA prices are wholesale nodal USD/MWh and do not represent utility delivered retail power costs. Full price-activation logic is *not* connected yet. Screens import and inspect records but cannot use them for underwriting until data QA and mapping are completed.

## Run tests
```bash
cd workspace
node test_engine2.cjs
node test_finance.cjs
node test_development.cjs
node test_feasibility.cjs
node test_decision.cjs
node test_connectors.cjs
```

## Source and legal notes
- EIA API: https://www.eia.gov/opendata/
- PJM hourly day-ahead pricing: https://dataminer2.pjm.com/feed/da_hrl_lmps/definition
- EPA ECHO: https://echo.epa.gov/
- FERC eLibrary: https://elibrary.ferc.gov/eLibrary/
- PJM has restrictions on redistribution without membership: https://www.pjm.com/markets-and-operations/etools/data-miner-2

All files in connector_examples are labeled SYNTHETIC test fixtures. No live customer-specific utility capacity, permits, or pricing are asserted.
