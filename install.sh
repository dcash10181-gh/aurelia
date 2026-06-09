#!/usr/bin/env bash
# AURELIA installer — macOS/Linux.
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/dcash10181-gh/aurelia/main/install.sh | bash
# Flags:
#   --local    install from the current checkout (skip clone)
#   --dry-run  print what would happen, change nothing
set -euo pipefail

REPO_URL="https://github.com/dcash10181-gh/aurelia.git"
TARGET_DIR="${AURELIA_DIR:-$HOME/aurelia}"
LOCAL=0; DRY=0
for a in "$@"; do
  case "$a" in
    --local) LOCAL=1 ;;
    --dry-run) DRY=1 ;;
    *) echo "Unknown flag: $a"; exit 2 ;;
  esac
done

say()  { printf "\033[33m[aurelia]\033[0m %s\n" "$*"; }
fail() { printf "\033[31m[aurelia] ERROR:\033[0m %s\n" "$*" >&2; exit 1; }
run()  { if [ "$DRY" = 1 ]; then echo "  would run: $*"; else "$@"; fi; }

# --- preflight ---------------------------------------------------------------
command -v python3 >/dev/null || fail "python3 not found. Install Python 3.10+ first."
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' \
  || fail "Python 3.10+ required (found $(python3 -V))."
command -v git  >/dev/null || fail "git not found. Install git first."
command -v node >/dev/null || fail "node not found. Install Node 18+ (https://nodejs.org)."
command -v npm  >/dev/null || fail "npm not found. It ships with Node."
say "preflight ok: $(python3 -V), node $(node -v), npm $(npm -v)"

# --- source ------------------------------------------------------------------
if [ "$LOCAL" = 1 ]; then
  TARGET_DIR="$(pwd)"
  say "installing from current checkout: $TARGET_DIR"
else
  if [ -d "$TARGET_DIR/.git" ]; then
    say "repo exists at $TARGET_DIR — pulling latest"
    run git -C "$TARGET_DIR" pull --ff-only
  else
    say "cloning into $TARGET_DIR"
    run git clone "$REPO_URL" "$TARGET_DIR"
  fi
fi
[ "$DRY" = 1 ] && { say "dry-run complete."; exit 0; }
cd "$TARGET_DIR"

# --- python env ----------------------------------------------------------------
say "creating virtualenv (.venv)"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q --upgrade pip

say "installing backend + CLI"
pip install -q -e services/api -e packages/cli

say "installing mini LLM (PyTorch — may take a few minutes; optional)"
if pip install -q -e packages/mini_llm; then
  say "mini LLM installed"
else
  say "WARN: mini LLM install failed (torch). The agent still works with the"
  say "      fallback provider. Retry later: pip install -e packages/mini_llm"
fi

# --- frontend ------------------------------------------------------------------
say "installing frontend dependencies"
(cd apps/web && npm install --no-audit --no-fund)

# --- config + storage ------------------------------------------------------------
[ -f .env ] || { cp .env.example .env; say "created .env from .env.example"; }
mkdir -p data
say "initializing SQLite storage"
python - << 'PY'
from aurelia_api.config import settings
from aurelia_api.storage.db import Database
Database(settings.db_path)
print(f"[aurelia] storage ready: {settings.db_path}")
PY

cat << 'NEXT'

  ✦ AURELIA installed.

  Next steps:
    cd $HOME/aurelia            # (or your checkout)
    source .venv/bin/activate
    aurelia start               # backend on http://127.0.0.1:8484
    make web                    # UI on http://localhost:3000  (new terminal)

  Or run both:  make dev
  Open:         http://localhost:3000

  Optional: train the from-scratch mini LLM (educational, ~1 min on CPU):
    aurelia train-mini-llm
NEXT
