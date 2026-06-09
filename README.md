# AURELIA

**Your local-first intelligent command layer.**

A private, ambient AI agent that runs entirely on your machine: a calm,
golden command center in the browser, a FastAPI agent backend, a CLI, a
plugin tool system, local SQLite memory — and a tiny transformer language
model built from scratch that you can train on your own CPU in under a minute.

> UI: a dark, bronze-and-gold interface with a breathing halo that reflects
> agent state, a left rail of system/model/tools/memory panels, and a ⌘K
> command palette. *(Screenshot placeholder — run it locally to see it live.)*

## Features
- **Chat + agent loop** — messages route through an intent-aware agent that
  can call tools (calculator, time, sandboxed notes) before answering.
- **Local memory** — create / search / list / delete, stored in SQLite on disk.
- **Tool / plugin architecture** — one registry powers the API, UI and CLI.
  Add a tool in ~10 lines (see `docs/plugin_api.md`).
- **Model provider abstraction** — `echo` (deterministic fallback, always
  works), `mini` (the from-scratch tiny LLM), `ollama` (optional adapter for
  a real local model runtime).
- **Mini LLM from scratch** — a ~0.2M-parameter character-level GPT in plain
  PyTorch: tokenizer, causal self-attention, training loop, sampling,
  checkpoints, tests. Educational, honestly documented as such.
- **Voice-ready architecture** — the chat API exposes an SSE streaming
  endpoint; speech-to-text/text-to-speech adapters can be plugged in front
  of it without backend changes (see `docs/roadmap.md`).
- **Private by design** — binds to localhost, no telemetry, shell tool off by
  default, filesystem tools sandboxed to `./data`.

## One-line install (macOS / Linux)
```bash
curl -fsSL https://raw.githubusercontent.com/dcash10181-gh/aurelia/main/install.sh | bash
```
Windows (PowerShell):
```powershell
irm https://raw.githubusercontent.com/dcash10181-gh/aurelia/main/install.ps1 | iex
```

## Run it
```bash
cd ~/aurelia && source .venv/bin/activate
aurelia start          # backend → http://127.0.0.1:8484
make web               # UI      → http://localhost:3000   (new terminal)
# or both at once:
make dev
```
Open **http://localhost:3000**.

## Local development
```bash
git clone https://github.com/dcash10181-gh/aurelia.git && cd aurelia
./install.sh --local          # installs into ./.venv using this checkout
./scripts/test_all.sh         # backend + CLI + mini LLM + frontend tests
```
Docker alternative: `docker compose up` (API on :8484, UI on :3000).

## Architecture (short version)
```
apps/web        React + Vite + TS + Tailwind UI (proxied to the API in dev)
services/api    FastAPI: chat/agent, memory, tools, providers, SQLite storage
packages/cli    Typer CLI: start/status/chat/tools/memory/train/generate
packages/mini_llm  From-scratch PyTorch mini-GPT (train + generate + tests)
```
Full detail in [`docs/architecture.md`](docs/architecture.md).

## The mini LLM, honestly
`aurelia train-mini-llm` trains a 2-layer, 64-dim character-level transformer
on a ~19 KB synthetic corpus bundled with the repo (written for this project —
no copyrighted data). It converges in seconds and generates text that is
**recognizably structured but not meaningful**. It exists to make the full LLM
pipeline inspectable and hackable, not to be smart. For real generative
quality, run [Ollama](https://ollama.com) locally and select the `ollama`
provider. Details: [`docs/local_models.md`](docs/local_models.md).

```bash
aurelia train-mini-llm            # ~1 min on CPU
aurelia generate --prompt "Hello"
```

## Model providers
| Provider | What it is | Availability |
|---|---|---|
| `echo` | Deterministic rule-based fallback | Always |
| `mini` | The from-scratch tiny LLM | After `aurelia train-mini-llm` |
| `ollama` | Adapter for a local Ollama server | If `ollama serve` is running |

Switch in the UI model panel, the ⌘K palette, or `aurelia chat "..." --provider mini`.

## Safety notes
- API binds `127.0.0.1`; no auth exists — do not expose it to a network.
- Shell tool **disabled by default**; enable with
  `AURELIA_ENABLE_SHELL_TOOL=true` only if you accept it runs commands as you.
- Notes tool cannot write outside `./data/notes` (path-traversal checked).
- No telemetry; the only outbound call is the optional localhost Ollama adapter.
- See [SECURITY.md](SECURITY.md).

## Troubleshooting
- **UI says "Backend offline"** → start the API: `aurelia start`.
- **`aurelia: command not found`** → `source .venv/bin/activate` first.
- **Mini LLM unavailable** → install torch (`pip install -e packages/mini_llm`)
  then `aurelia train-mini-llm`.
- **Port in use** → `AURELIA_PORT=8585 aurelia start` and update the Vite
  proxy in `apps/web/vite.config.ts`.
- **torch install too heavy** → skip it; the agent works with `echo`/`ollama`.

## Roadmap
FTS5 memory search, true token streaming, voice I/O adapters, plugin
hot-loading, LLM-driven tool selection via Ollama. See [`docs/roadmap.md`](docs/roadmap.md).

## License
MIT — see [LICENSE](LICENSE). AURELIA is an original project; it does not use
or imitate any Marvel/Stark/JARVIS branding, assets, or dialogue.
