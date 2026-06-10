# Roadmap

## Near-term
- ~~SQLite FTS5 for memory search (replace LIKE)~~ — shipped: BM25-ranked FTS5 with prefix matching, sync triggers, auto-migration, LIKE fallback.
- ~~True token streaming from providers through the existing SSE contract~~ — shipped: per-token SSE from mini LLM, NDJSON pass-through for Ollama, chunked fallback for rule-based; frontend renders incrementally.
- ~~LLM-driven tool selection when a capable provider (Ollama) is configured~~ — shipped: temperature-0 JSON decision pass, registry-enforced execution, streamed answer composition, regex fallback.
- Memory auto-recall: inject relevant memories into provider prompts.

## Voice
The architecture is voice-ready: STT (e.g. whisper.cpp) feeds text into
`POST /api/chat/stream`; TTS consumes the SSE token stream. Both land as
optional local adapters with no backend changes.

## Later
- Plugin hot-loading from a `plugins/` directory with a manifest.
- Multi-conversation threads in storage and UI.
- Mini LLM: BPE tokenizer option, larger presets, fine-tune-on-your-notes demo.
- Signed releases and a versioned install script.
