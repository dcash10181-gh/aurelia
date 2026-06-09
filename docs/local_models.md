# Local Models

## 1. The from-scratch mini LLM (`mini` provider)
What it is: a ~0.2M-parameter character-level GPT implemented from scratch in
PyTorch in `packages/mini_llm`. Train it locally:

```bash
aurelia train-mini-llm            # ~300 steps, <1 min CPU, saves ~/.aurelia/mini_llm.pt
aurelia generate --prompt "aurelia "
```

What to expect, honestly: loss drops from ~4.3 to ~2.0 and the model emits
word-shaped character sequences echoing the tiny synthetic corpus. It is
**not intelligent, not factual, and not production-grade** — it is a complete,
readable LM pipeline you can modify: edit `config.py` hyperparameters, swap
the corpus in `data/tiny_corpus.txt` (use only data you have rights to), and
retrain.

Selecting it: model panel in the UI, ⌘K palette, or
`aurelia chat "hi" --provider mini`. If no checkpoint exists the provider
reports itself unavailable and tells you how to train.

## 2. Ollama adapter (`ollama` provider)
For real generative quality, install [Ollama](https://ollama.com), then:

```bash
ollama pull llama3.2
ollama serve            # usually already running as a service
```

Configure via `.env` (`AURELIA_OLLAMA_BASE_URL`, `AURELIA_OLLAMA_MODEL`).
The adapter calls `POST /api/generate` on localhost with stdlib urllib; if
the server isn't reachable the provider shows as unavailable in the UI.

## 3. Other runtimes (llama.cpp, etc.)
Implement a `Provider` subclass in `services/providers.py` with `generate()`
and `available()`, add it to `build_providers()`, done — the UI, CLI and
agent pick it up automatically.

## Fallback (`echo`)
A deterministic rule-based provider that always works, so the app is useful
immediately after install with zero model downloads.
