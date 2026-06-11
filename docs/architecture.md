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
## Context injection (`agent/loop.py: build_context`)
Every model turn carries context: a system message holding memories relevant
to the current request (FTS5 BM25 recall in match-any mode, so filler words
can't veto a match — distinct from the match-all precision mode used for
explicit search) plus the last 12 conversation messages, each capped at 1200
chars so one giant paste can't evict the rest. History is captured before the
in-flight message is persisted, so context never echoes the current turn.
Ollama consumes context natively via /api/chat messages; echo and mini ignore
it harmlessly. A memory-recall failure degrades to no-context, never a failed
turn.

Routing is two-tier. Tier 1: a ReAct loop — when the active provider
supports constrained JSON (Ollama), the agent runs decide→act→observe:
a temperature-0 decision pass picks a tool, the registry executes it, the
result is fed back into the next decision pass, and the loop continues until
the model declines (results sufficient) or a guard fires. Guards: a hard step
cap (AURELIA_AGENT_MAX_STEPS, default 5) and identical-call detection (a
deterministic model re-requesting the same tool+args is stuck). Tool errors —
including the registry refusing a disabled tool — become ERROR observations
the model can adapt to, visible in the transcript rather than hidden. Each
act/observe step streams to the UI as a tool_event frame; the final answer is
composed from all observations and token-streamed. Tier 2: regex intent
routing — the deterministic fallback for echo/mini and for any failed,
malformed, unknown, or disabled selection. The ToolRegistry is the sole
enforcement point: models request tools, the registry decides; a disabled
shell tool stays disabled no matter what the model emits. Selection failures
degrade routing quality, never availability. Disable with
AURELIA_LLM_TOOL_SELECTION=false.

## Conversations
Chats are first-class: a `conversations` table, `conversation_id` on every
message, and history scoped per conversation — the agent's 12-message context
window can no longer bleed topics across chats. First user message auto-titles
the conversation. Pre-conversation databases migrate in place (column added,
rows land in a 'default' conversation, which also keeps the CLI working with
zero changes). The UI offers a switcher, New chat, and resume-most-recent on
load. DELETE /api/conversations/{id} removes a chat and its messages; durable
memories are never touched by any conversation operation.

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
