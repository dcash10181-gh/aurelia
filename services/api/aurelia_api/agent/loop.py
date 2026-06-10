"""Agent loop: plan→act→respond.

Routing has two tiers:
1. LLM-driven tool selection — when the active provider supports constrained
   JSON output (Ollama), the model itself decides which tool to call via a
   temperature-0 decision pass, then composes the final answer from the tool
   result. The ToolRegistry remains the sole enforcement point: the model can
   only *request* tools; disabled tools (e.g. shell) still raise.
2. Regex intent routing — the deterministic fallback, used for the bundled
   echo/mini providers (which cannot emit structured output) and whenever the
   LLM decision pass fails, returns malformed JSON, or names an unknown or
   disabled tool. Selection can never reduce availability, only improve
   routing quality.
"""
from __future__ import annotations

import json
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


# Context budget: enough history for coherent multi-turn dialogue without
# blowing small local context windows. Each message is also length-capped so
# one giant paste can't evict everything else.
_MAX_HISTORY_MSGS = 12
_MAX_MSG_CHARS = 1200
_MAX_MEMORIES = 5


def build_context(message: str, memory=None,
                  history: list[dict] | None = None) -> list[dict]:
    """Assemble the provider-facing context for one turn.

    Returns chat-format messages: an optional leading system message carrying
    memories relevant to the current request (FTS5 BM25 search over saved
    memories), followed by recent conversation history. Providers that cannot
    use context (echo, mini) simply ignore it — injection never breaks them.
    """
    ctx: list[dict] = []
    if memory is not None:
        try:
            hits = memory.search_memories(message, limit=_MAX_MEMORIES, match_any=True)
        except Exception as e:  # a memory failure must never kill a turn
            log.warning("memory recall failed: %s", e)
            hits = []
        if hits:
            lines = "\n".join(f"- {h['content']}" for h in hits)
            ctx.append({
                "role": "system",
                "content": ("Relevant saved memories about this user (use them "
                            "when they apply; do not recite them unprompted):\n"
                            + lines),
            })
    for m in (history or [])[-_MAX_HISTORY_MSGS:]:
        content = str(m.get("content", ""))[:_MAX_MSG_CHARS]
        ctx.append({"role": m.get("role", "user"), "content": content})
    return ctx


def _llm_select_tool(message: str, provider: Provider, tools: ToolRegistry,
                     observations: list[dict] | None = None) -> dict[str, Any] | None:
    """Ask a capable provider to route the request (one ReAct step). Returns
    a validated {"tool": name, "args": dict}, or None (no capability,
    declined, malformed, unknown tool) → the loop stops.
    """
    if not getattr(provider, "supports_tool_selection", False):
        return None
    from ..config import settings  # late import: tests monkeypatch settings
    if not settings.llm_tool_selection:
        return None
    decision = provider.tool_decision(message, tools.list(), observations)
    if not decision or not decision.get("tool"):
        return None
    name = decision["tool"]
    known = {t["name"] for t in tools.list()}
    if name not in known:
        log.info("LLM selected unknown tool %r; stopping loop", name)
        return None
    return {"tool": name, "args": decision.get("args") or {}}


def _react_steps(message: str, provider: Provider, tools: ToolRegistry):
    """The ReAct core: decide → act → observe, repeated.

    Yields one observation dict per executed tool call. Guards:
    * settings.agent_max_steps hard-caps iterations;
    * an identical (tool, args) repeat breaks the loop — a deterministic
      temperature-0 model that re-requests the same call is stuck;
    * tool errors (including PermissionError from disabled tools) become
      ERROR observations rather than exceptions, so the model can adapt
      course and the registry's refusals stay visible in the transcript.
    """
    from ..config import settings
    observations: list[dict] = []
    seen: set[tuple] = set()
    for _ in range(max(1, settings.agent_max_steps)):
        sel = _llm_select_tool(message, provider, tools, observations)
        if sel is None:
            return
        key = (sel["tool"], json.dumps(sel["args"], sort_keys=True, default=str))
        if key in seen:
            log.info("ReAct loop repeated %s with identical args; breaking", sel["tool"])
            return
        seen.add(key)
        try:
            result = tools.invoke(sel["tool"], sel["args"])
        except Exception as e:
            result = f"ERROR: {e}"
        obs = {"tool": sel["tool"], "args": sel["args"], "result": result}
        observations.append(obs)
        yield obs


def _compose_react_prompt(message: str, observations: list[dict]) -> str:
    lines = "\n".join(
        f"{i + 1}. {o['tool']}({json.dumps(o['args'], default=str)}) -> {o['result']}"
        for i, o in enumerate(observations))
    return (f"The user asked: {message}\n"
            f"You called these tools:\n{lines}\n"
            "Answer the user concisely using these results. If a tool "
            "returned an ERROR, work around it or say plainly what could "
            "not be done. Do not mention internal tooling unless they "
            "asked about it.")


def _provider_tag(provider: Provider, observations: list[dict]) -> str:
    tools_used = list(dict.fromkeys(o["tool"] for o in observations))
    return f"{provider.name}+{'+'.join(tools_used)}"


def run_agent_turn(
    message: str, provider: Provider, tools: ToolRegistry, memory=None,
    history: list[dict] | None = None, use_llm_selection: bool = True,
) -> dict[str, Any]:
    """One agent turn. Returns {reply, provider, tool_calls}.

    use_llm_selection=False skips the LLM decision pass — used by the
    streaming path when it has already run (and been declined) once,
    so a turn never pays for two decision calls.
    """
    tool_calls: list[dict] = []
    ctx = build_context(message, memory, history)

    if use_llm_selection:
        observations = list(_react_steps(message, provider, tools))
        if observations:
            reply = provider.generate(
                _compose_react_prompt(message, observations), ctx)
            return {"reply": reply,
                    "provider": _provider_tag(provider, observations),
                    "tool_calls": observations}

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

    # No tool intent → defer to the model provider, with context.
    reply = provider.generate(message, ctx)
    return {"reply": reply, "provider": provider.name, "tool_calls": tool_calls}


def run_agent_turn_stream(message: str, provider: Provider, tools: ToolRegistry,
                          memory=None, history: list[dict] | None = None):
    """Streaming agent turn: yields {'token': str} frames, then one
    {'meta': {...}} frame.

    Architectural decision: tool-routed turns reuse run_agent_turn and emit
    the reply as a single token frame — tool results are atomic facts
    ("7*6 = 42"), not generated text; faking incremental delivery for them
    adds latency without value. Model-routed turns stream provider tokens
    as they are produced.
    """
    ctx = build_context(message, memory, history)

    observations: list[dict] = []
    for obs in _react_steps(message, provider, tools):
        observations.append(obs)
        # Surface each act/observe step live so the UI can show progress.
        yield {"tool_event": obs}
    if observations:
        for piece in provider.stream(
                _compose_react_prompt(message, observations), ctx):
            yield {"token": piece}
        yield {"meta": {"provider": _provider_tag(provider, observations),
                        "tool_calls": observations}}
        return

    probe = (run_agent_turn(message, provider, tools, memory, history,
                            use_llm_selection=False)
             if _has_tool_intent(message) else None)
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

    for piece in provider.stream(message, ctx):
        yield {"token": piece}
    yield {"meta": {"provider": provider.name, "tool_calls": []}}


def _has_tool_intent(message: str) -> bool:
    m = message.strip()
    return bool(_CALC_RE.search(m) or _TIME_RE.search(m) or _NOTE_RE.match(m))
