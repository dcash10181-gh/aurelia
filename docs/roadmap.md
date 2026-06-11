# Roadmap

## Near-term
- ~~Daily-driver round 2: background tasks + conversation rename/delete~~ — shipped: interval/daily scheduler in app lifespan, per-task result conversations, TASKS panel, ✎/🗑 conversation controls.
- ~~Daily-driver: first-class conversations + workspace browser~~ — shipped: per-chat scoped history with migration, auto-titles, UI switcher/resume, read-only workspace file browser in the side panel, qa.sh root-guard.
- ~~Actuator pack: web.fetch + workspace files~~ — shipped: SSRF-guarded read-only web fetch, sandboxed general file workspace, config-gated.
- ~~ReAct multi-step agent loop~~ — shipped: decide→act→observe chaining with step cap, stuck-loop detection, error-observations, live tool_event streaming to the UI.
- ~~SQLite FTS5 for memory search (replace LIKE)~~ — shipped: BM25-ranked FTS5 with prefix matching, sync triggers, auto-migration, LIKE fallback.
- ~~True token streaming from providers through the existing SSE contract~~ — shipped: per-token SSE from mini LLM, NDJSON pass-through for Ollama, chunked fallback for rule-based; frontend renders incrementally.
- ~~LLM-driven tool selection when a capable provider (Ollama) is configured~~ — shipped: temperature-0 JSON decision pass, registry-enforced execution, streamed answer composition, regex fallback.
- ~~Memory auto-recall: inject relevant memories into provider prompts~~ — shipped, together with conversation history injection (12-message window, per-message cap) and Ollama /api/chat migration.

## Voice
The architecture is voice-ready: STT (e.g. whisper.cpp) feeds text into
`POST /api/chat/stream`; TTS consumes the SSE token stream. Both land as
optional local adapters with no backend changes.

## Later
- Plugin hot-loading from a `plugins/` directory with a manifest.
- Multi-conversation threads in storage and UI.
- Mini LLM: BPE tokenizer option, larger presets, fine-tune-on-your-notes demo.
- Signed releases and a versioned install script.
