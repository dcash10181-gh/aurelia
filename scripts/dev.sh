#!/usr/bin/env bash
# Run API and web UI together for development.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
trap 'kill 0' EXIT
python -m uvicorn aurelia_api.main:app --port 8484 &
(cd apps/web && npm run dev) &
wait
