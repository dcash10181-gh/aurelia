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

    # ---- tool selection capability -------------------------------------
    # Providers that can reliably emit constrained JSON may override
    # tool_decision to let the model route requests to tools. Returning
    # None means "no decision" — the agent loop falls back to regex
    # intent routing. The bundled echo/mini providers cannot produce
    # structured output, so the default is None.
    supports_tool_selection: bool = False

    def tool_decision(self, message: str, tools: list[dict],
                      observations: list[dict] | None = None,
                      memories: list[dict] | None = None) -> dict | None:
        return None


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

    @staticmethod
    def build_messages(prompt: str, history: list[dict] | None) -> list[dict]:
        """Chat-format payload: context (system memories + prior turns) then
        the current user message. Pure function — unit-tested directly."""
        msgs = [{"role": m.get("role", "user"), "content": str(m.get("content", ""))}
                for m in (history or [])]
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def generate(self, prompt: str, history: list[dict] | None = None) -> str:
        # /api/chat (not /api/generate): the messages array is how history and
        # the memory system-message actually reach the model.
        body = json.dumps({"model": self.model, "stream": False,
                           "messages": self.build_messages(prompt, history)}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode())
            return (data.get("message") or {}).get("content",
                                                   "(empty response from Ollama)")
        except Exception as e:
            return f"Ollama request failed: {e}. Is `ollama serve` running?"

    supports_tool_selection = True

    _DECISION_PROMPT = (
        "You route a user request to at most one tool.\n"
        "Available tools (name — description — args):\n{tools}\n\n"
        "User message: {message}\n\n"
        "Reply with ONLY a JSON object, no other text:\n"
        '{{"tool": <tool name as string, or null>, "args": {{<arg name>: <value>}}}}\n'
        "Rules:\n"
        "- Choose a tool ONLY if the request explicitly requires it; "
        "if no tool is clearly required, tool MUST be null.\n"
        "- Tools that persist data (notes.write, memory.save) may be used "
        "ONLY when the user explicitly asks to save, remember, record, or "
        "note something. NEVER persist when the user asks for ideas, "
        "suggestions, names, or options — answering with text needs no tool.\n"
        "- Never invent or choose values on the user's behalf and persist "
        "them; persist only what the user stated.\n"
        "- Use exact tool and arg names. For calculator, args is "
        '{{"expression": <plain arithmetic, digits and + - * / ( ) only — '
        'no currency symbols, no words, e.g. "200/4"}}.\n'
        "- Questions about the user's own saved facts, preferences, or "
        "past statements (\"what is my...\", \"do I have...\") -> "
        "memory.search FIRST; never the calculator.\n"
        "Examples:\n"
        'User: "remember my dog is Biscuit" -> {{"tool": "memory.save", '
        '"args": {{"content": "User\'s dog is named Biscuit"}}}}\n'
        'User: "what is my dog\'s name?" -> {{"tool": "memory.search", '
        '"args": {{"query": "dog name"}}}}\n'
        'User: "fetch https://example.com/page and summarize it" -> '
        '{{"tool": "web.fetch", "args": {{"url": "https://example.com/page"}}}}\n'
        'User: "suggest a name for my cat" -> {{"tool": null, "args": {{}}}}'
        "{memories}"
        "{observations}"
    )

    @staticmethod
    def _format_memories(memories: list[dict] | None) -> str:
        if not memories:
            return ""
        lines = "\n".join(f"- {m['content']}" for m in memories)
        return ("\n\nYou ALREADY KNOW these saved facts about the user "
                "(they are provided to you automatically):\n" + lines +
                "\nIf these facts already answer the user's question, tool "
                "MUST be null — do NOT call memory.search for facts listed "
                "above, and NEVER call the calculator unless the user asked "
                "for arithmetic.")

    @staticmethod
    def _format_observations(observations: list[dict] | None) -> str:
        if not observations:
            return ""
        lines = "\n".join(
            f"{i + 1}. {o['tool']}({json.dumps(o['args'])}) -> {o['result']}"
            for i, o in enumerate(observations))
        return ("\n\nResults from tools you already called this turn:\n"
                + lines +
                "\nIf these results are sufficient to answer the user, "
                "tool MUST be null. If a result is an ERROR, you may retry "
                "that tool ONCE with corrected args (follow any hint in the "
                "error message); otherwise only call another tool if more "
                "information is genuinely required.")

    def tool_decision(self, message: str, tools: list[dict],
                      observations: list[dict] | None = None,
                      memories: list[dict] | None = None) -> dict | None:
        """One constrained JSON decision pass at temperature 0.

        Returns {"tool": str|None, "args": dict} or None on any failure —
        the caller treats None as "fall back to regex routing", so a flaky
        model can degrade quality but never availability.
        """
        tool_lines = "\n".join(
            f"- {t['name']} — {t['description']} — args: {t['args']}"
            for t in tools if t.get("enabled")
        )
        prompt = self._DECISION_PROMPT.format(
            tools=tool_lines, message=message,
            memories=self._format_memories(memories),
            observations=self._format_observations(observations))
        body = json.dumps({
            "model": self.model, "prompt": prompt, "stream": False,
            "format": "json", "options": {"temperature": 0},
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode())
            decision = json.loads(data.get("response", ""))
            if not isinstance(decision, dict):
                return None
            tool = decision.get("tool")
            args = decision.get("args") or {}
            if tool is not None and not isinstance(tool, str):
                return None
            if not isinstance(args, dict):
                return None
            return {"tool": tool, "args": args}
        except Exception as e:
            log.info("tool_decision unavailable/failed, falling back: %s", e)
            return None

    def stream(self, prompt: str, history: list[dict] | None = None) -> Iterator[str]:
        """Native streaming: Ollama emits NDJSON, one object per token chunk;
        forward each `response` fragment as it arrives over the wire."""
        body = json.dumps({"model": self.model, "stream": True,
                           "messages": self.build_messages(prompt, history)}).encode()
        req = urllib.request.Request(
            f"{self.base_url}/api/chat", data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for raw in resp:
                    line = raw.decode().strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    piece = (obj.get("message") or {}).get("content", "")
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
