"""Opt-in local watch loop: file snapshots -> changes -> optional live role review.

Never reads external network sources or changes milestones; users place licensed source files into data/inbox.
Single launch terminal process; not a hosted background service.
"""

import argparse, datetime, hashlib, json, os, time
from pathlib import Path
from fastapi.testclient import TestClient
from server.app import app, DATA
from server.intelligence import REGIONS

NAME_RE = "(EIA860|ERCOT_GIS|PJM_QUEUE)__YYYY-MM-DD.csv"


def check_once(pid, folder, live=False):
    from agents.run_live import run, live_available

    inbox = Path(folder)
    inbox.mkdir(parents=True, exist_ok=True)
    manifest_path = inbox / ".processed.json"
    state = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    imports = []
    rejected = []
    with TestClient(app, base_url="http://127.0.0.1") as client:
        for path in sorted(inbox.glob("*.csv")):
            stem = path.stem.split("__")
            if len(stem) != 2 or stem[0] not in REGIONS:
                continue
            try:
                datetime.date.fromisoformat(stem[1])
            except ValueError:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if state.get(path.name) in (digest, "rejected:" + digest):
                continue
            # RT-W02: send the exact file text (no BOM stripping or newline translation) so the stored hash is the file hash.
            # RT-W03: hand-copied inbox files are labelled as such, not as an automated provider feed.
            body = {
                "source_key": stem[0],
                "csv_text": path.read_bytes().decode("utf-8"),
                "source_url": REGIONS[stem[0]]["url"],
                "source_published_date": stem[1],
                "import_label": "operator_inbox_file",
            }
            r = client.post(f"/api/projects/{pid}/intelligence/snapshots", json=body)
            if r.status_code == 201:
                state[path.name] = digest
                imports.append(r.json())
            elif r.status_code == 409 and "Out-of-order" in r.text:
                # RT-B07: an older vintage arriving late is reported, not silently marked as imported.
                state[path.name] = "rejected:" + digest
                rejected.append({"file": path.name, "reason": r.json().get("detail", "")})
            elif r.status_code == 409:
                state[path.name] = digest
            else:
                raise RuntimeError(f"{path.name}: import rejected HTTP {r.status_code}: {r.text[:250]}")
    # No records are marked processed when import fails.
    manifest_path.write_text(json.dumps(state, indent=2))
    reviews = []
    if live and any(i["changes"] > 0 for i in imports):
        if not live_available():
            raise RuntimeError("Source imports succeeded, but no live API authorization; see docs/LIVE_AGENTS.md")
        reviews.append(run(pid))
    return {
        "imported_snapshots": imports,
        "rejected_files": rejected,
        "live_reviews": reviews,
        "watching": str(inbox),
        "model_calls": sum(x.get("api_calls", 0) for x in reviews),
    }


def main():
    p = argparse.ArgumentParser(description="Local source snapshots watcher; nothing is auto-approved")
    p.add_argument("--project", default="demo-campus-001")
    p.add_argument("--inbox", default="data/inbox")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=600)
    p.add_argument("--live", action="store_true")
    a = p.parse_args()
    if a.interval < 60:
        raise SystemExit("Minimum watch interval is 60 seconds")
    while True:
        try:
            print(json.dumps(check_once(a.project, a.inbox, a.live), indent=2), flush=True)
        except Exception as e:
            print(json.dumps({"error": type(e).__name__, "detail": str(e)[:300]}), flush=True)
        if not a.watch:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
