"""Model provider abstraction.

A Provider turns conversation context into a reply. Three implementations:

* RuleBasedProvider ("echo"): deterministic fallback that always works —
  zero dependencies, so the app is useful straight after install.
* MiniLLMProvider ("mini"): the from-scratch tiny transformer in
  packages/mini_llm. It is an educational model: it produces text but is
  NOT intelligent. Loaded lazily; gracefully degrades if torch or the
  checkpoint is missing.
* OllamaProvider ("ollama"): optional adapter for a real local runtime.
  Stub uses stdlib urllib so we add no HTTP dependency; documented in
  docs/local_models.md.
"""
from __future__ import annotations

import json
import logging
import urllib.request
from abc import ABC, abstractmethod
from typing import Iterator

log = logging.getLogger("aurelia.providers")


class Provider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str, history: list[dict] | None = None) -> str: ...

    def stream(self, prompt: str, history: list[dict] | None = None) -> Iterator[str]:
        """Yield reply text incrementally.

        Default: generate the full reply, then chunk by words — correct for
        providers without native streaming (rule-based). Streaming-capable
        providers override this with true token-level emission.
        """
        reply = self.generate(prompt, history)
        words = reply.split(" ")
        for i, w in enumerate(words):
            yield w if i == len(words) - 1 else w + " "

    def available(self) -> bool:
        return True


class RuleBasedProvider(Provider):
    name = "echo"

    def generate(self, prompt: str, history: list[dict] | None = None) -> str:
        p = prompt.strip()
        lowered = p.lower()
        if any(g in lowered for g in ("hello", "hi ", "hey")) or lowered in ("hi", "hey"):
            return ("Hello — AURELIA online. I'm running fully on your machine. "
                    "Try the tools panel, or ask me to save a note.")
        if "who are you" in lowered or "what are you" in lowered:
            return ("I'm AURELIA, a local-first agent. Right now you're talking to my "
                    "rule-based fallback provider; connect a local model (mini LLM or "
                    "Ollama) for generative replies. See docs/local_models.md.")
        if lowered.endswith("?"):
            return (f"I heard: \u201c{p}\u201d. The fallback provider can't reason about "
                    "this — switch to the mini LLM or an Ollama model in the model panel.")
        return f"Acknowledged: \u201c{p}\u201d. (Fallback provider — connect a model for generative replies.)"


class MiniLLMProvider(Provider):
    name = "mini"

    DISCLAIMER = ("\n\n— mini LLM (experimental from-scratch model; "
                  "output is not factual or intelligent)")

    def __init__(self, checkpoint: str | None = None):
        self.checkpoint = checkpoint
        self._gen = None
        self._stream_gen = None
        self._err: str | None = None

    def _load(self):
        if self._gen is not None or self._err is not None:
            return
        try:
            # Lazy import: torch is heavy and optional at runtime.
            from aurelia_mini_llm.generate import load_generator, load_stream_generator
            self._gen = load_generator(self.checkpoint)
            self._stream_gen = load_stream_generator(self.checkpoint)
        except Exception as e:  # torch missing, no checkpoint, etc.
            self._err = str(e)
            log.warning("MiniLLM unavailable: %s", e)

    def available(self) -> bool:
        self._load()
        return self._gen is not None

    def generate(self, prompt: str, history: list[dict] | None = None) -> str:
        self._load()
        if self._gen is None:
            return (f"Mini LLM unavailable ({self._err}). Train it first: "
                    "`aurelia train-mini-llm`, then retry. Falling back is recommended.")
        text = self._gen(prompt)
        return f"{text}{self.DISCLAIMER}"

    def stream(self, prompt: str, history: list[dict] | None = None) -> Iterator[str]:
        """True token-level streaming: each piece is one sampled model token
        (one character with the char tokenizer), emitted as it is sampled."""
        self._load()
        if self._stream_gen is None:
            yield from super().stream(prompt, history)
            return
        yield from self._stream_gen(prompt)
        yield self.DISCLAIMER


class OllamaProvider(Provider):
    """Optional adapter for a locally running Ollama server."""
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def available(self) -> bool:
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=1.5):
                return True
        except Exception:
            return False

    def generate(self, prompt: str, history: list[dict] | None = None) -> str:
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
            return data.get("response", "(empty response from Ollama)")
        except Exception as e:
            return f"Ollama request failed: {e}. Is `ollama serve` running?"

    def stream(self, prompt: str, history: list[dict] | None = None) -> Iterator[str]:
        """Native streaming: Ollama emits NDJSON, one object per token chunk;
        forward each `response` fragment as it arrives over the wire."""
        body = json.dumps({"model": self.model, "prompt": prompt, "stream": True}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw in resp:
                    line = raw.decode().strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    piece = obj.get("response", "")
                    if piece:
                        yield piece
                    if obj.get("done"):
                        return
        except Exception as e:
            yield f"Ollama request failed: {e}. Is `ollama serve` running?"


def build_providers(settings) -> dict[str, Provider]:
    return {
        "echo": RuleBasedProvider(),
        "mini": MiniLLMProvider(),
        "ollama": OllamaProvider(settings.ollama_base_url, settings.ollama_model),
    }
