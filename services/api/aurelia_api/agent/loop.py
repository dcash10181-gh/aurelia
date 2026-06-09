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
