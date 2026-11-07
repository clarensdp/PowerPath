"""SQLite backup + restore drill (v30.8.2). Safe: works only in fresh temporary directories, never on data/.

1. Build a realistic workspace in a temp data dir through the real API (project with starter scenario, saved run,
   evidence record with an uploaded file).
2. Back it up with the verified online backup (infrastructure.db_audit.verified_backup) AND copy evidence files,
   which live outside the database and were previously not covered by any backup step.
3. Verify the backup manifest, restore into a second empty data dir, boot the app there, and compare every API-visible
   record, run summary, evidence hash and the append-only triggers.

Usage: python -m scripts.restore_drill [--report path.json]      Exit code 0 only if every check passes.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_SNAPSHOT = r"""
import hashlib, io, json, os, sys
from fastapi.testclient import TestClient
from server.app import app, db
from server.seed_demo import seed
mode = sys.argv[1]
c = TestClient(app, base_url='http://127.0.0.1')
if mode == 'build':
    seed()
    p = c.post('/api/projects?starter_scenario=true', json={'name': 'Drill campus', 'target_mw': 120}).json()
    sid = c.get(f"/api/projects/{p['id']}/scenarios").json()[0]['id']
    assert c.post(f"/api/projects/{p['id']}/scenarios/{sid}/runs").status_code == 201
    e = c.post(f"/api/projects/{p['id']}/evidence", json={'title': 'Utility letter', 'category': 'utility'}).json()
    up = c.post(f"/api/projects/{p['id']}/evidence/{e['id']}/file", files={'attachment': ('letter.pdf', io.BytesIO(b'%PDF-1.4 drill'), 'application/pdf')})
    assert up.status_code == 200, up.text
out = {'projects': [], 'triggers': []}
for p in sorted(c.get('/api/projects').json(), key=lambda x: x['id']):
    pid = p['id']
    runs = c.get(f'/api/projects/{pid}/runs').json()
    ev = c.get(f'/api/projects/{pid}/evidence').json()
    files = {}
    for x in ev:
        if x.get('stored_filename'):
            r = c.get(f"/api/projects/{pid}/evidence/{x['id']}/download")
            files[x['id']] = {'status': r.status_code, 'sha256': hashlib.sha256(r.content).hexdigest(), 'recorded': x['content_hash']}
    out['projects'].append({'id': pid, 'name': p['name'], 'target_mw': p['target_mw'],
        'scenarios': sorted((s['id'], s['version'], json.dumps(s['config'], sort_keys=True)) for s in c.get(f'/api/projects/{pid}/scenarios').json()),
        'runs': sorted((r['id'], r.get('engine_sha256'), json.dumps(c.get(f"/api/projects/{pid}/runs/{r['id']}").json().get('summary'), sort_keys=True)) for r in runs),
        'evidence_files': files})
with db() as con:
    out['triggers'] = sorted(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'pp_append_only%'"))
print(json.dumps(out, sort_keys=True))
"""


def _snapshot(data_dir: Path, mode: str) -> dict:
    env = {**os.environ, "POWERPATH_DATA_DIR": str(data_dir), "PYTHONDONTWRITEBYTECODE": "1"}
    env.pop("POWERPATH_DATABASE_URL", None)
    out = subprocess.run(
        [sys.executable, "-c", _SNAPSHOT, mode], cwd=ROOT, env=env, capture_output=True, text=True, check=True
    )
    return json.loads(out.stdout.strip().splitlines()[-1])


def run() -> dict:
    from infrastructure.db_audit import verified_backup, verify_backup

    with tempfile.TemporaryDirectory(prefix="pp-drill-") as tmp:
        tmp = Path(tmp)
        live, backup_dir, restored = tmp / "live", tmp / "backup", tmp / "restored"
        before = _snapshot(live, "build")
        manifest = verified_backup(live / "powerpath.sqlite3", backup_dir / "powerpath.sqlite3")
        # Evidence binaries are not inside SQLite: back them up alongside, with their own hash list.
        shutil.copytree(live / "evidence", backup_dir / "evidence")
        evidence_manifest = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (backup_dir / "evidence").iterdir()
            if p.is_file()
        }
        check = verify_backup(backup_dir / "powerpath.sqlite3")
        restored.mkdir()
        shutil.copy2(backup_dir / "powerpath.sqlite3", restored / "powerpath.sqlite3")
        shutil.copytree(backup_dir / "evidence", restored / "evidence")
        after = _snapshot(restored, "read")
        files_ok = all(
            f["status"] == 200 and f["sha256"] == f["recorded"]
            for p in after["projects"]
            for f in p["evidence_files"].values()
        )
        checks = {
            "backup_manifest_verified": bool(check["verified"]),
            "records_identical_after_restore": before == after,
            "evidence_files_restored_and_hash_verified": files_ok and bool(evidence_manifest),
            "append_only_triggers_survive_restore": len(after["triggers"]) == 8,
            "has_runs": any(p["runs"] for p in after["projects"]),
        }
        return {
            "drill": "PP-RESTORE-DRILL-30.8.2",
            "passed": all(checks.values()),
            "checks": checks,
            "backup_sha256": manifest["sha256"],
            "evidence_files": len(evidence_manifest),
            "projects": len(after["projects"]),
            "runs": sum(len(p["runs"]) for p in after["projects"]),
        }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--report")
    a = ap.parse_args()
    result = run()
    text = json.dumps(result, indent=2)
    print(text)
    if a.report:
        Path(a.report).write_text(text + "\n")
    sys.exit(0 if result["passed"] else 1)
