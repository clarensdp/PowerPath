# PowerPath v26.8 — Five-milestone intelligence and agents release

**Status:** local-first ALPHA; financial screening and limited source intelligence. This does not prove grid access, utility-confirmed MW, executed permits, transaction values, or lender certification. G4/G5 remain blocked, regardless of CSV and agent output.

The five milestones are cumulative and delivered together on top of frozen PowerPath v26.3.

| Version / owner | Implemented capability | Acceptance proof | Limit |
|---|---|---|---|
| **v26.4 — CDO / CTO** | Curated public source adapters for EIA-860 plant references, PJM queue, ERCOT generator status; dated original CSV snapshots with hashes, normalized identities, provider-domain validation | `test_v268_intelligence.test_01_*`, TypeScript build | Public generation queue is not the data-center service queue. Operator supplies actual source bytes; source URLs and vintages aren't authenticated against provider. Not an automated official download. |
| **v26.5 — CDO / COO** | Per-source snapshot change detection with immutable historical source rows, added/removed/updated detection, field-level diffs, project isolation | `test_02_*` | No automatic external monitoring unless operator starts local inbox watcher and keeps it running. |
| **v26.6 — COO / Risk** | Proposed PermitIQ milestone links from source changes; approval/rejection activity; no silent schedule update | `test_03_*` | Linkage and proposed delay remain analyst assumptions, not causal evidence of utility service timing. |
| **v26.7 — CFO / CTO** | Read-only before/after CFADS/NPV/DSCR comparison using the preserved engine, followed by deliberate use of the existing v26.3 critical-path sensitivity | `test_04_*` | Not a transaction valuation. NPV is a synthetic sensitivity, and changes in generator queue status alone don't change load-service capacity. |
| **v26.8 — Chief of Staff / all ten roles / Risk** | Full ten-role *offline rule* council, retained meeting reports, opt-in ten sequential LIVE Responses API requests via CLI, local inbox watcher with daily call budget and no agent write tools | `test_05_*`, `test_v268_live_workflow.py`, browser acceptance | An API key, model, metadata sharing permission and running process are required for live model calls. Not executed here. No continuous independent agents run from this chat. |

## Data and Risk standards

- **Source record observation** means uploaded CSV metadata; `available_mw_verified` remains false. No utility-committed delivery or capacity inferred.
- **Source freshness**: caller records source_published_date and observed time separately; user must review vintage. Imported CSV is operator-provided even when the source URL domain is official.
- **Changes are suggestions** and cannot change a project milestone unless approved in the Intelligence review queue.
- **Underwriting baseline remains untouched**. Preview uses pure engine calls in memory; approved delays are subsequently used to create a separate immutable scenario.
- **Autonomous agents** have *read-only memo production*. There are no API tools supplied to write projects, file permits, contact third parties, or certify debt.
- **Live and offline statuses cannot be confused:** `OFFLINE_RULES` = deterministic plan, `LIVE_API` = independently invoked remote models; each saved meeting lists mode and created time.
- **No human external sign-off** has occurred. This development build is not production-safe or independently lender-certified.

## Quality evidence

Run:

```bash
python -m unittest discover -s tests -p 'test_v268_intelligence.py' -v
python -m unittest discover -s tests -p 'test_v268_live_workflow.py' -v
python tests/browser_v268.py
python tests/run_audit.py
```

Read `docs/V26_8_TEST_RESULTS.json` for the actual results recorded in the build session. The browser bridge uses a real local API and Chromium JavaScript, but intercepts browser HTTP because this execution environment blocks Chromium localhost navigation; end-to-end API calls are still made against the running local FastAPI service.

## Next institutional work

1. Obtain licensed canonical queue interfaces and independent site-to-utility mapping for each target region (queue generation records alone are insufficient).
2. Institute field-level provider schema contracts, HTTP/download authorization, ingestion health alarms, and legal review of public-source terms.
3. Upgrade milestone modeling from synthetic critical-delay conventions to verified task dates and independent schedule analysis.
4. Deploy secure authentication, isolated storage, secret management, queue workers, CI, and production operations before cloud exposure.
5. Source executed leases, indentures and utility agreements; obtain external human model review to attempt G4/G5. Agents and passing tests never replace these gates.
