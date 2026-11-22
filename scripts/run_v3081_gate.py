"""v30.8.1 bounded process-isolated release gate; does not run or claim PG integration."""

from __future__ import annotations
import hashlib, json, os, re, signal, subprocess, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    "tests/test_v3081_pg_staging.py",
    "tests/test_v308_database_foundation.py",
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
    "tests/agent_ops307_test.py",
    "tests/agent_ops307_concurrency_test.py",
    "tests/agent_ops307_auth_test.py",
    "tests/test_api.py",
    "tests/test_geo29.py",
    "tests/test_v262_workflows.py",
    "tests/test_v263_geo.py",
    "tests/test_v27_security_transaction.py",
]


def bounded_run(args, env, timeout=40):
    proc = subprocess.Popen(
        args, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        return 124, out + "\nTIMEOUT: process group terminated\n"


def main():
    records = []
    fail = []
    extended = "--extended" in sys.argv[1:]
    selected = (
        MODULES
        if extended
        else [
            "tests/test_v3081_pg_staging.py",
            "tests/test_v308_database_foundation.py",
            "permitting/test_footprint.py",
            "permitting/test_permitting.py",
            "tests/agent_ops307_test.py",
            "tests/agent_ops307_concurrency_test.py",
            "tests/agent_ops307_auth_test.py",
        ]
    )
    for i, module in enumerate(selected):
        with tempfile.TemporaryDirectory(prefix="pp3081-ci-") as td:
            env = {**os.environ, "POWERPATH_DATA_DIR": td, "PYTHONDONTWRITEBYTECODE": "1"}
            # Each test is in its own OS process; avoids historical module/global SQLite/auth state pollution.
            code, out = bounded_run([sys.executable, "-m", "pytest", "-q", module], env)
        match = re.findall(r"(\d+) passed", out)
        count = int(match[-1]) if match else 0
        record = {"module": module, "passed": count, "exit_code": code}
        if code:
            record["failure_tail"] = out.splitlines()[-16:]
            fail.append(module)
        records.append(record)
        print(f"{i+1:02d}/{len(selected)} {module}: {count} passed (exit {code})", flush=True)
    audit = json.loads((ROOT / "docs/manifests/ENGINE_HASH_AUDIT_V30_3.json").read_text())["files"]
    hashes = {
        p: hashlib.sha256((ROOT / "engine" / p).read_bytes()).hexdigest() == v["sha256"] for p, v in audit.items()
    }
    try:
        js_code, js_output = bounded_run(["npm", "run", "check"], os.environ.copy(), timeout=20)
    except FileNotFoundError:
        js_code, js_output = 127, "npm not available"
    report = {
        "release": "30.8.1-staging-preparation",
        "selected_tests_passed": sum(r["passed"] for r in records),
        "tests_process_isolated": True,
        "extended_gate_requested": extended,
        "groups": records,
        "all_selected_passed": not fail,
        "protected_engine_files": len(hashes),
        "protected_engine_unchanged": all(hashes.values()),
        "javascript_check_pass": js_code == 0,
        "javascript_check_error": js_output[-1200:] if js_code else "",
        "postgres_live_parity_verified": False,
        "postgres_app_cutover": False,
        "full_single_process_suite_verified": False,
        "tenant_rls_runtime_verified": False,
        "remote_gis_verified": False,
        "browser_acceptance_verified": False,
        "production_ready": False,
    }
    (ROOT / "docs/reports/TEST_REPORT_V30_8_1.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "groups"}, indent=2), flush=True)
    return 0 if not fail and all(hashes.values()) and js_code == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
