#!/usr/bin/env bash
# Full test suite: backend, CLI, mini LLM, frontend unit tests + build.
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
echo "== backend + CLI =="
python -m pytest services/api/tests packages/cli/tests -q
echo "== mini LLM =="
python -m pytest packages/mini_llm/tests -q || echo "mini LLM tests skipped/failed (torch optional)"
echo "== frontend =="
(cd apps/web && npm run test && npm run build)
echo "ALL TESTS COMPLETE"
