#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/PowerPath_v25_8_claude/workspace"
echo '=== JS deterministic test suites ==='
num=0
for f in test_*.cjs; do node "$f" >/dev/null; echo "PASS $f"; num=$((num+1)); done
echo "JS SUITES: $num"
cd "$HERE/PowerPath_v25_8_claude"
echo '=== Independent Python reference ==='
python3 audit/reference257.py > /tmp/powerpath_reference258_base.json
python3 audit/verify_v258_cases.py
cat audit/reference258_results.json | tail -5
echo '=== Public project stress suite ==='
node benchmarks/run_benchmarks_v258.cjs
echo '=== Regression impact examples ==='
node audit/change_impact258.cjs
python3 workspace/build_page.py
echo 'PASS all commands; this proves deterministic arithmetic, NOT lender-grade certification.'
