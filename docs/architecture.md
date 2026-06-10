# AURELIA Architecture

## Overview
A monorepo of four runnable parts joined by one HTTP API:

```
 Browser UI (React/Vite :3000) ──┐
                                  ├──► FastAPI backend (:8484) ──► SQLite (./data)
 CLI (Typer, `aurelia ...`) ─────┘            │
                                              ├─► Tool registry (plugins)
                                              └─► Provider layer ─► echo | mini LLM | Ollama
```

## Frontend (`apps/web`)
React 18 + Vite + TypeScript + Tailwind. Dev server proxies `/api` to the
backend, so the UI is zero-config. State is plain React hooks — the app is
small enough that a store would be overhead. Panels: conversation (with the
halo state indicator), system status, model selector, tools, memory, ⌘K
command palette, and a first-run onboarding screen. Accessibility floor:
visible focus rings, ARIA roles on dynamic regions, `prefers-reduced-motion`
respected, AA-checked text colors.

## Backend (`services/api`)
FastAPI app (`aurelia_api.main`). Routes: health/status, chat (+ SSE
streaming variant), agent, messages, memory CRUD/search, tools list/invoke,
providers. JSON-lines structured logging. CORS restricted to the local UI
origin; server binds localhost.

## Agent runtime (`aurelia_api/agent/loop.py`)
A deterministic plan→act→respond turn. Tool routing is intent-based (regex
detection of calculation/time/note intents) because the bundled models cannot
emit reliable structured tool calls; the loop is provider-agnostic so
Routing is two-tier. Tier 1: LLM-driven tool selection — when the active
provider supports constrained JSON (Ollama), a temperature-0 decision pass
lets the model pick a tool and args, the registry executes it, and a second
streaming pass composes the answer from the result. Tier 2: regex intent
routing — the deterministic fallback for echo/mini and for any failed,
malformed, unknown, or disabled selection. The ToolRegistry is the sole
enforcement point: models request tools, the registry decides; a disabled
shell tool stays disabled no matter what the model emits. Selection failures
degrade routing quality, never availability. Disable with
AURELIA_LLM_TOOL_SELECTION=false.

## Streaming (`/api/chat/stream`)
True token-level SSE. The provider interface exposes `stream()`: the mini LLM
yields each sampled token (one char with the char tokenizer), Ollama forwards
NDJSON chunks as they arrive, and the rule-based fallback word-chunks its
deterministic reply. The agent loop streams model turns and emits tool results
as a single atomic frame (a computed fact gains nothing from fake typing).
The endpoint bridges the sync generator via `iterate_in_threadpool` so tokens
flush the moment they are sampled, and persists the assistant message after
the stream completes.

## Memory (`aurelia_api/storage/db.py`)
SQLite with WAL mode; `memories` and `messages` tables. Search uses an
FTS5 external-content index (`memories_fts`) with BM25 relevance ranking and
per-token prefix matching; insert/update/delete triggers keep it in sync, and
startup rebuilds the index if it diverges (auto-migration for pre-FTS
databases). User input is never interpreted as FTS5 query syntax — tokens are
quoted and ANDed. Builds without FTS5, or pathological queries, degrade to
LIKE. Plain `sqlite3` + DAO functions — an ORM adds nothing at this scale.

## Tools (`aurelia_api/tools/`)
`Tool` dataclass + `ToolRegistry`. Built-ins: calculator (ast-allowlist, no
eval), time, sandboxed notes (path-traversal-checked, scoped to
`<data_dir>/notes`), shell (disabled by default, list-args subprocess,
timeout). The same registry serves the API, UI and agent loop.

## Model providers (`aurelia_api/services/providers.py`)
`Provider` ABC with `generate()` and `available()`. `echo` is the always-on
fallback; `mini` lazily loads the from-scratch checkpoint and degrades
gracefully; `ollama` adapts a local Ollama server via stdlib urllib (no
added dependency).

## Mini LLM (`packages/mini_llm`)
Character tokenizer → mini-GPT (2 layers, 2 heads, 64-dim, weight-tied head,
pre-norm blocks, explicit causal mask) → AdamW training loop → top-k sampled
generation → single-file checkpoint (config + weights + vocab). Synthetic
4-line-template corpus shipped in `data/tiny_corpus.txt`. ~0.2M parameters;
trains on CPU in <1 minute. Educational only — documented as such everywhere.

## Install flow (`install.sh`)
Preflight (python3 ≥3.10, git, node, npm) → clone or `--local` → venv →
editable installs (api, cli, mini_llm with graceful torch failure) →
`npm install` for the UI → copy `.env.example` → initialize SQLite → print
next commands. `--dry-run` prints actions without changing anything.
