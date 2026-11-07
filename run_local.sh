#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
python -m scripts.prepare_local
python -m server.seed_demo
exec python -m uvicorn server.app:app --host 127.0.0.1 --port "${PORT:-8768}"
