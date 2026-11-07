# PowerPath v20.1 — Live official-data gateway

## Start

1. Extract `PowerPath_v20_1_Live_Source.zip` and open a terminal in the extracted directory.
2. Run `python3 live_server.py` (Python 3.10+). This serves the application at **http://127.0.0.1:8765/PowerPath.html**.
3. Open the browser URL above. Select **Data connectors**. Choose a historical date (allow a lag for published records), select a balancing authority, then click **Fetch EIA live**.
4. For PJM, obtain a PJM Data Miner API key and start the server with `PJM_API_KEY=your_key python3 live_server.py` (Mac/Linux), or set the environment variable on Windows. Enter a numeric PJM pnode ID, then **Fetch PJM live**.
5. Open **Data connectors** to see imported record counts, the date retrieved, warnings and provenance. Export snapshots as JSON when desired.

**Important:** Opening the HTML directly with `file://` maintains the offline app but cannot use the local live gateway. Launch the Python server first. The Python server binds only to localhost; it is not a deployed online data service.

## What is and isn't live

- EIA-930 balancing authority hourly demand is fetched from the official EIA API on request, subject to upstream availability.
- PJM Data Miner day-ahead nodal LMP is fetched on request with an authorized server-side key. It is a wholesale market price, not delivered utility service pricing.
- EPA ECHO and FERC eLibrary evidence still require deliberate document/reference intake. They are **not automatically monitored** in this build.
- Live observations are **quarantined** in browser storage, so they cannot silently replace underwriting assumptions. In particular, a historical PJM LMP must not be treated as a delivered retail tariff or a utility-approved MW commitment.
- Fresh upstream network requests could not be confirmed in the build environment because DNS/network access was unavailable. Contract tests use synthetic responses and are labeled as such.

## Run validation

```
python3 test_live_gateway.py
cd workspace
node test_engine2.cjs
node test_finance.cjs
node test_development.cjs
node test_feasibility.cjs
node test_decision.cjs
node test_connectors.cjs
```

## Sources

EIA API documentation: https://www.eia.gov/opendata/documentation.php
PJM official API guide: https://www.pjm.com/-/media/DotCom/etools/data-miner-2/data-miner-2-api-guide.pdf
EPA ECHO services: https://echo.epa.gov/tools/web-services
FERC eLibrary: https://elibrary.ferc.gov/eLibrary/

## Release boundaries

This is a **manual-refresh local gateway**, not a continuously running service, and it makes no claim of permit automation, live substation headroom, guaranteed time-to-power, or data-licensed redistribution rights. For commercial deployment: authenticate users; persist external data in a managed store; check API quotas, data licenses, DST/time zone correctness, QA approval and node-to-asset mapping; and add monitored jobs with audit logs and permissions.
