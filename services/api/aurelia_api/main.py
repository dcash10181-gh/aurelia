"""AURELIA backend entrypoint.

Run: uvicorn aurelia_api.main:app --port 8484
Endpoints are documented at /docs (FastAPI's built-in OpenAPI UI).

Streaming: /api/chat/stream returns Server-Sent Events with true token-level
delivery — each frame is emitted as the provider produces it (per sampled
token for the mini LLM, per NDJSON chunk for Ollama, word-chunked for the
rule-based fallback). Frames are JSON `data:` lines ending with `[DONE]`.
"""
from __future__ import annotations

import json
import logging
import platform
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from starlette.concurrency import iterate_in_threadpool

from . import __version__
from .agent.loop import run_agent_turn, run_agent_turn_stream
from .config import settings
from .logging_setup import configure_logging
from .models.schemas import ChatRequest, ChatResponse, MemoryCreate, MemoryOut, ToolInvoke
from .services.providers import build_providers
from .storage.db import Database

configure_logging(settings.log_level)
log = logging.getLogger("aurelia.api")

def _git_commit() -> str:
    """Short hash of the running code, for at-a-glance staleness checks.

    Walks up from this file to the repo root (editable installs live inside
    the checkout). 'unknown' for non-git deployments — never an error.
    """
    import pathlib
    import subprocess
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            try:
                return subprocess.run(
                    ["git", "-C", str(parent), "rev-parse", "--short", "HEAD"],
                    capture_output=True, text=True, timeout=5,
                ).stdout.strip() or "unknown"
            except Exception:
                return "unknown"
    return "unknown"


_BUILD = _git_commit()

app = FastAPI(title="AURELIA API", version=__version__)
# Local-only UI origins. The server binds 127.0.0.1 by default.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

db = Database(settings.db_path)
providers = build_providers(settings)
from .tools.builtin import build_default_registry  # noqa: E402

registry = build_default_registry(settings.data_dir, enable_shell=settings.enable_shell_tool, db=db, enable_web=settings.enable_web_tool)
from .tools.builtin import WorkspaceTool  # noqa: E402
_workspace = WorkspaceTool(settings.data_dir)
_started = time.time()


def _provider(name: str | None):
    key = (name or settings.default_provider).lower()
    if key not in providers:
        raise HTTPException(400, f"Unknown provider '{key}'. Options: {sorted(providers)}")
    return providers[key]


# ------------------------------------------------------------------ system
@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": __version__,
            "build": _BUILD}


@app.get("/api/status")
def status():
    return {
        "app": settings.app_name,
        "version": __version__,
        "build": _BUILD,
        "uptime_s": round(time.time() - _started, 1),
        "python": platform.python_version(),
        "providers": {k: p.available() for k, p in providers.items()},
        "default_provider": settings.default_provider,
        "shell_tool_enabled": settings.enable_shell_tool,
        "data_dir": settings.data_dir,
    }


# -------------------------------------------------------------------- chat
@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    provider = _provider(req.provider)
    # History is captured before the new user message is persisted, so the
    # context contains prior turns only — not an echo of the current one.
    history = [{"role": m["role"], "content": m["content"]}
               for m in db.recent_messages(limit=12, conversation_id=req.conversation_id or "default")]
    conv = req.conversation_id or "default"
    db.maybe_autotitle(conv, req.message)
    db.add_message("user", req.message, conv)
    result = run_agent_turn(req.message, provider, registry, db, history)
    db.add_message("assistant", result["reply"], conv)
    return result


@app.post("/api/agent")
def agent(req: ChatRequest):
    """Alias of /api/chat that always runs the full agent loop and returns
    the tool trace. Kept separate so chat can later become model-only."""
    return chat(req)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    provider = _provider(req.provider)
    history = [{"role": m["role"], "content": m["content"]}
               for m in db.recent_messages(limit=12, conversation_id=req.conversation_id or "default")]
    conv = req.conversation_id or "default"
    db.maybe_autotitle(conv, req.message)
    db.add_message("user", req.message, conv)

    async def gen():
        # Bridge the synchronous agent/provider generator into the async SSE
        # response without blocking the event loop: iterate_in_threadpool
        # pulls each item on a worker thread, so tokens flush to the client
        # the moment the model samples them.
        parts: list[str] = []
        agent_iter = run_agent_turn_stream(req.message, provider, registry, db, history)
        async for frame in iterate_in_threadpool(agent_iter):
            if "token" in frame:
                parts.append(frame["token"])
            yield f"data: {json.dumps(frame)}\n\n"
        yield "data: [DONE]\n\n"
        # Persist once, after the full reply exists. Runs inside the generator
        # so a client disconnect mid-stream still persists what was sent.
        db.add_message("assistant", "".join(parts), conv)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.delete("/api/messages")
async def clear_messages():
    """New-chat: clears conversation history (the agent's 12-message context
    window reads from this table). Durable memories are not affected."""
    n = db.clear_messages()
    return {"cleared": n}


@app.post("/api/conversations")
async def create_conversation():
    return db.create_conversation()


@app.get("/api/conversations")
async def list_conversations():
    return db.list_conversations()


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    if conv_id == "default":
        raise HTTPException(400, "The default conversation cannot be deleted")
    if not db.delete_conversation(conv_id):
        raise HTTPException(404, "No such conversation")
    return {"deleted": conv_id}


@app.get("/api/workspace")
async def workspace_list():
    """Read-only browser over the agent's file workspace."""
    return {"files": _workspace.list({}).splitlines()
            if "(workspace is empty)" not in _workspace.list({}) else []}


@app.get("/api/workspace/file")
async def workspace_file(path: str):
    try:
        return {"path": path, "content": _workspace.read({"path": path})}
    except ValueError as e:
        raise HTTPException(404, str(e))


@app.get("/api/messages")
def messages(limit: int = 50, conversation_id: str | None = None):
    return db.recent_messages(limit=min(limit, 500),
                              conversation_id=conversation_id)


# ------------------------------------------------------------------ memory
@app.post("/api/memory", response_model=MemoryOut)
def memory_create(req: MemoryCreate):
    return db.create_memory(req.content, req.tags)


@app.get("/api/memory", response_model=list[MemoryOut])
def memory_list(q: str | None = None, limit: int = 100):
    limit = min(limit, 500)
    return db.search_memories(q, limit) if q else db.list_memories(limit)


@app.delete("/api/memory/{memory_id}")
def memory_delete(memory_id: str):
    if not db.delete_memory(memory_id):
        raise HTTPException(404, "Memory not found")
    return {"deleted": memory_id}


# ------------------------------------------------------------------- tools
@app.get("/api/tools")
def tools_list():
    return registry.list()


@app.post("/api/tools/invoke")
def tools_invoke(req: ToolInvoke):
    try:
        result = registry.invoke(req.name, req.args)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    except PermissionError as e:
        raise HTTPException(403, str(e)) from e
    except Exception as e:
        raise HTTPException(400, f"Tool error: {e}") from e
    return {"tool": req.name, "result": result}


# ----------------------------------------------------------------- providers
@app.get("/api/providers")
def providers_list():
    return [{"name": k, "available": p.available(),
             "default": k == settings.default_provider} for k, p in providers.items()]
