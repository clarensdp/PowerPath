"""Reproducible, process-isolated v30.8.0 test and protected-engine release gate.

Each test batch receives a fresh temporary POWERPATH_DATA_DIR. Some legacy test
modules set their own temp directory at import; process isolation still prevents
one module from contaminating another's globals/auth settings.
"""

from __future__ import annotations
import hashlib, json, os, re, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = [
    (
        "core_gis_permitting_finance",
        [
            "permitting/test_permitting.py",
            "permitting/test_national.py",
            "permitting/test_official_gis.py",
            "permitting/test_footprint.py",
            "tests/test_regrid_pilot.py",
            "tests/test_public30.py",
            "tests/test_notes_integration.py",
            "tests/v271/test_note_phasing332.py",
            "tests/v271/test_note_phasing333.py",
            "tests/v271/test_core_scientific.py",
            "tests/v271/test_schedule_parity.py",
            "tests/test_v308_database_foundation.py",
        ],
    ),
    ("agent_operations", ["tests/agent_ops307_test.py"]),
    ("agent_auth", ["tests/agent_ops307_auth_test.py"]),
    ("agent_concurrency", ["tests/agent_ops307_concurrency_test.py"]),
    ("api", ["tests/test_api.py"]),
    ("georegistry", ["tests/test_geo29.py"]),
    ("legacy_workflows", ["tests/test_v262_workflows.py"]),
    ("legacy_geo", ["tests/test_v263_geo.py"]),
    ("institutional_security", ["tests/test_v27_security_transaction.py"]),
]


def main():
    results = []
    all_ok = True
    for name, modules in GROUPS:
        with tempfile.TemporaryDirectory(prefix="pp308-gate-") as td:
            env = {**os.environ, "POWERPATH_DATA_DIR": td, "PYTHONDONTWRITEBYTECODE": "1"}
            try:
                x = subprocess.run(
                    [sys.executable, "-m", "pytest", "-q", *modules],
                    cwd=ROOT,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=55,
                )
            except subprocess.TimeoutExpired:
                results.append({"group": name, "passed": 0, "exit_code": 124, "error": "Group timed out after 55s"})
                print(name + ": TIMEOUT (unverified)", flush=True)
                all_ok = False
                continue
        lines = (x.stdout + "\n" + x.stderr).splitlines()
        count = sum(int(n) for line in lines for n in re.findall(r"(\d+) passed", line))
        results.append(
            {
                "group": name,
                "passed": count,
                "exit_code": x.returncode,
                "last_lines": lines[-6:] if x.returncode else [],
            }
        )
        print(name + f": {count} passed, exit={x.returncode}", flush=True)
        if x.returncode:
            all_ok = False
    baseline = json.loads((ROOT / "docs/manifests/ENGINE_HASH_AUDIT_V30_3.json").read_text())["files"]
    hashes = {
        k: (hashlib.sha256((ROOT / "engine" / k).read_bytes()).hexdigest() == v["sha256"]) for k, v in baseline.items()
    }
    js = subprocess.run(["npm", "run", "check"], cwd=ROOT, capture_output=True, text=True, timeout=50)
    result = {
        "release": "30.8.0",
        "groups": results,
        "tests_passed": sum(x["passed"] for x in results),
        "all_group_tests_pass": all_ok,
        "protected_engine_files": len(hashes),
        "protected_engine_hashes_match": all(hashes.values()),
        "engine_file_results": hashes,
        "javascript_check_pass": js.returncode == 0,
        "javascript_check_error": js.stderr[-2000:] if js.returncode else "",
        "combined_single_process_suite_verified": False,
        "postgresql_cutover_tested": False,
        "browser_visual_verified": False,
        "production_ready": False,
    }
    print(json.dumps(result, indent=2))
    return 0 if all_ok and all(hashes.values()) and js.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
