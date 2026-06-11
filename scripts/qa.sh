#!/usr/bin/env bash

# Refuse to run from anywhere but the repo root: a wrong-directory run that
# "fails to find" suites or silently skips them is how bad code gets pushed.
if [ ! -f "scripts/qa.sh" ] || [ ! -f "Makefile" ]; then
  echo "qa.sh must be run from the repository root" >&2
  exit 2
fi
# QA gate: completeness, tests, lint, install dry-run, safety checks.
set -uo pipefail
cd "$(dirname "$0")/.."
FAIL=0
check() { if eval "$2" >/dev/null 2>&1; then echo "PASS  $1"; else echo "FAIL  $1"; FAIL=1; fi; }

echo "== Repo completeness =="
for f in README.md LICENSE SECURITY.md CONTRIBUTING.md CODE_OF_CONDUCT.md \
         .gitignore .env.example install.sh install.ps1 docker-compose.yml Makefile \
         docs/architecture.md docs/plugin_api.md docs/local_models.md docs/roadmap.md; do
  check "exists: $f" "test -f $f"
done

echo "== Install script (dry run) =="
check "install.sh --local --dry-run" "bash install.sh --local --dry-run"
check "bash -n install.sh (syntax)" "bash -n install.sh"

echo "== Tests =="
check "backend+CLI pytest" "python3 -m pytest services/api/tests packages/cli/tests -q"
check "mini LLM pytest" "python3 -m pytest packages/mini_llm/tests -q"
check "frontend vitest" "(cd apps/web && npx vitest run)"
check "frontend build (tsc strict + vite)" "(cd apps/web && npm run build)"

echo "== Lint =="
check "ruff" "python3 -m ruff check services packages"

echo "== Docs / claims =="
check "one-line curl documented" "grep -q 'curl -fsSL https://raw.githubusercontent.com/dcash10181-gh/aurelia/main/install.sh' README.md"
check "mini LLM limitations documented" "grep -qi 'not intelligent' README.md docs/local_models.md"

echo "== Safety =="
check "no Marvel/JARVIS branding in sources" "! grep -rniE 'jarvis|stark industries|marvel|edith' --include='*.py' --include='*.ts' --include='*.tsx' --include='*.md' --include='*.html' . --exclude-dir=node_modules --exclude-dir=dist --exclude=qa_report.md | grep -viE 'imitate|disclaimer' | grep -q ."
check "shell tool defaults off" "grep -q 'enable_shell_tool: bool = False' services/api/aurelia_api/config.py"
check "no eval()/exec() call sites in backend" "! grep -rnE '(^|[^_.a-zA-Z\"])(eval|exec)\\(' services/api/aurelia_api --include='*.py' | grep -vE '#|no eval' | grep -q ."
check "no telemetry SDKs/endpoints" "! grep -rniE 'posthog|sentry|mixpanel|segment\\.io|google-analytics|gtag\\(' services packages apps/web/src apps/web/package.json | grep -q ."

echo
if [ "$FAIL" = 0 ]; then echo "QA: ALL CHECKS PASSED"; else echo "QA: FAILURES PRESENT"; fi
exit $FAIL
