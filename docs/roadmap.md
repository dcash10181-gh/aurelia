# Roadmap

## Near-term
- SQLite FTS5 for memory search (replace LIKE).
- True token streaming from providers through the existing SSE contract.
- LLM-driven tool selection when a capable provider (Ollama) is configured.
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
