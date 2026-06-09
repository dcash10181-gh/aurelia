"""Agent loop: a deterministic plan→act→respond cycle.

Architectural decision: tool routing is intent-based (pattern detection) rather
than LLM-function-calling, because the bundled models (rule-based fallback and
the educational mini LLM) cannot reliably emit structured tool calls. The loop
is provider-agnostic, so when a capable model (e.g. via Ollama) is configured,
LLM-driven tool selection can be layered in without changing the API surface.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ..services.providers import Provider
from ..tools.base import ToolRegistry

log = logging.getLogger("aurelia.agent")

_CALC_RE = re.compile(r"(?:calculate|compute|what is)\s+([0-9\s\.\+\-\*\/\(\)%]+)\??$", re.I)
_TIME_RE = re.compile(r"\b(what time|current time|today's date|what day)\b", re.I)
_NOTE_RE = re.compile(r"^(?:save|write)\s+(?:a\s+)?note\s+(?P<name>[\w\- ]+):\s*(?P<content>.+)$",
                      re.I | re.S)


def run_agent_turn(
    message: str, provider: Provider, tools: ToolRegistry, memory=None
) -> dict[str, Any]:
    """One agent turn. Returns {reply, provider, tool_calls}."""
    tool_calls: list[dict] = []

    m = _CALC_RE.search(message.strip())
    if m:
        expr = m.group(1).strip().rstrip("?")
        try:
            result = tools.invoke("calculator", {"expression": expr})
            tool_calls.append({"tool": "calculator", "args": {"expression": expr}, "result": result})
            return {"reply": f"{expr} = {result}", "provider": "agent+calculator",
                    "tool_calls": tool_calls}
        except Exception as e:
            log.info("calculator route failed, falling through: %s", e)

    if _TIME_RE.search(message):
        result = tools.invoke("time", {})
        tool_calls.append({"tool": "time", "args": {}, "result": result})
        return {"reply": f"Local time: {result}", "provider": "agent+time", "tool_calls": tool_calls}

    m = _NOTE_RE.match(message.strip())
    if m:
        args = {"name": m.group("name").strip().replace(" ", "-"),
                "content": m.group("content").strip()}
        try:
            result = tools.invoke("notes.write", args)
            tool_calls.append({"tool": "notes.write", "args": args, "result": result})
            return {"reply": result, "provider": "agent+notes", "tool_calls": tool_calls}
        except Exception as e:
            return {"reply": f"Couldn't save that note: {e}", "provider": "agent+notes",
                    "tool_calls": tool_calls}

    # No tool intent → defer to the model provider.
    reply = provider.generate(message)
    return {"reply": reply, "provider": provider.name, "tool_calls": tool_calls}


def run_agent_turn_stream(message: str, provider: Provider, tools: ToolRegistry):
    """Streaming agent turn: yields {'token': str} frames, then one
    {'meta': {...}} frame.

    Architectural decision: tool-routed turns reuse run_agent_turn and emit
    the reply as a single token frame — tool results are atomic facts
    ("7*6 = 42"), not generated text; faking incremental delivery for them
    adds latency without value. Model-routed turns stream provider tokens
    as they are produced.
    """
    probe = run_agent_turn(message, provider, tools) if _has_tool_intent(message) else None
    if probe is not None:
        if probe["tool_calls"]:
            # Atomic tool result: one frame.
            yield {"token": probe["reply"]}
        else:
            # Tool intent fell through; run_agent_turn already produced a
            # provider reply — chunk it rather than generating a second time.
            words = probe["reply"].split(" ")
            for i, w in enumerate(words):
                yield {"token": w if i == len(words) - 1 else w + " "}
        yield {"meta": {"provider": probe["provider"], "tool_calls": probe["tool_calls"]}}
        return

    for piece in provider.stream(message):
        yield {"token": piece}
    yield {"meta": {"provider": provider.name, "tool_calls": []}}


def _has_tool_intent(message: str) -> bool:
    m = message.strip()
    return bool(_CALC_RE.search(m) or _TIME_RE.search(m) or _NOTE_RE.match(m))
