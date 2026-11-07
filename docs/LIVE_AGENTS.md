# How to reach LIVE PowerPath agent status

## What is operational now

- The ten roles are configured: Chief of Staff, CFO, CTO, CPO, Head of Product Design, CDO, COO, CRO, CMO, Chief Risk Officer.
- The Intelligence page can run an **offline rules-only** review without an API key. This is not independent AI.
- `agents/run_live.py` can make **ten real sequential model API calls**, if and only if the operator supplies all required authorization/environment variables.
- `agents/watch.py --watch --live` can watch an **operator-managed local CSV inbox** at an interval, import new snapshots, and trigger live role review when changes are detected. The process operates only while a machine keeps it running; no background process is started by ChatGPT.
- Models return local persisted memos only. They cannot auto-apply milestones or edits, file permits, send messages, or certify a project.

## Prerequisites

1. A local or hosted runtime with Python 3.11+, Node 20+, this application, and network access to the Responses API.
2. Your **own** OpenAI API account/key and a supported model listed in your API account. Do not paste API keys into chat. API access and billing are separate from ChatGPT plan access.
3. An explicit policy for what may be shared with API models. This implementation sends only up to 12 public queue record change items (and prior role notes), not attached documents, lease files or the complete project database.
4. Set local variables in your own shell, substituting an actual accessible model:

```bash
export OPENAI_API_KEY='YOUR_PRIVATE_KEY_HERE'
export POWERPATH_AGENT_MODEL='YOUR_SUPPORTED_API_MODEL'
export POWERPATH_LIVE_AGENTS=1
export POWERPATH_SHARE_PROJECT_METADATA=1
export POWERPATH_MAX_CALLS_PER_DAY=20
```

Start the local web app in terminal A:

```bash
./run_local.sh
```

In terminal B, run **one real executive meeting**:

```bash
python -m agents.run_live --project demo-campus-001
```

Use the Intelligence page to read its saved `LIVE_API` report. The meeting makes a separate Responses API request per role with `store: false`; reports are saved only in the local SQLite database. The operator's API billing and data policies still apply. Failures are marked `failed`, not silently replayed as successful meetings.

For recurring **local inbox monitoring**, first copy only licensed datasets whose reuse you are authorized to perform into the inbox. Filenames MUST use `EIA860__YYYY-MM-DD.csv`, `PJM_QUEUE__YYYY-MM-DD.csv` or `ERCOT_GIS__YYYY-MM-DD.csv`:

```bash
mkdir -p data/inbox
cp examples/PJM_QUEUE__2026-10-01.csv data/inbox/
cp examples/PJM_QUEUE__2026-10-15.csv data/inbox/
python -m agents.watch --project demo-campus-001 --inbox data/inbox --watch --interval 600 --live
```

The example source rows are **synthetic test examples**, not real projects. Only new changes trigger model calls. The importer keeps hashes and a processed-file manifest. If the machine stops or sleeps, the watcher stops. The CLI uses no API keys from chat history.

## What remains to make agents truly always-on

- A trusted cloud worker/VM or local always-running computer, supervised process manager, durable job queue, retry policy and alerting.
- Authorized data connections, licensed fetch jobs, freshness monitors, schema/version alerts and independent source authentication.
- A secured API-key vault, encrypted at-rest storage, per-user auth, scoped tenant access, cost/volume quotas, logs, tracing and audits.
- Explicit per-action approvals, restricted tool permissions and a human escalation path for legal, financial or external decisions.
- A separate security and human model review before serving customers or relying on outputs institutionally.

**Important:** The supplied local web server binds to `127.0.0.1`. Do not port-forward it or expose it publicly; it does not implement production authentication. Also, current live roles are sequential independent model calls reading a shared public-source brief, not long-running agents with unrestricted tool execution.
