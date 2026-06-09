"""AURELIA backend entrypoint.

Run: uvicorn aurelia_api.main:app --port 8484
Endpoints are documented at /docs (FastAPI's built-in OpenAPI UI).

Streaming-readiness: /api/chat/stream returns Server-Sent Events. Today it
chunks the final reply word-by-word; the contract (SSE `data:` frames ending
with `[DONE]`) is what real token streaming will use, so the frontend never
needs to change when a streaming provider lands.
"""
from __future__ import annotations

import asyncio
import json
import logging
import platform
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from . import __version__
from .agent.loop import run_agent_turn
from .config import settings
from .logging_setup import configure_logging
from .models.schemas import ChatRequest, ChatResponse, MemoryCreate, MemoryOut, ToolInvoke
from .services.providers import build_providers
from .storage.db import Database

configure_logging(settings.log_level)
log = logging.getLogger("aurelia.api")

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

registry = build_default_registry(settings.data_dir, enable_shell=settings.enable_shell_tool)
_started = time.time()


def _provider(name: str | None):
    key = (name or settings.default_provider).lower()
    if key not in providers:
        raise HTTPException(400, f"Unknown provider '{key}'. Options: {sorted(providers)}")
    return providers[key]


# ------------------------------------------------------------------ system
@app.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name, "version": __version__}


@app.get("/api/status")
def status():
    return {
        "app": settings.app_name,
        "version": __version__,
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
    db.add_message("user", req.message)
    result = run_agent_turn(req.message, provider, registry, db)
    db.add_message("assistant", result["reply"])
    return result


@app.post("/api/agent")
def agent(req: ChatRequest):
    """Alias of /api/chat that always runs the full agent loop and returns
    the tool trace. Kept separate so chat can later become model-only."""
    return chat(req)


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    provider = _provider(req.provider)
    db.add_message("user", req.message)
    result = run_agent_turn(req.message, provider, registry, db)
    db.add_message("assistant", result["reply"])

    async def gen():
        for word in result["reply"].split(" "):
            yield f"data: {json.dumps({'token': word + ' '})}\n\n"
            await asyncio.sleep(0.012)
        yield f"data: {json.dumps({'meta': {'provider': result['provider'], 'tool_calls': result['tool_calls']}})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/messages")
def messages(limit: int = 50):
    return db.recent_messages(limit=min(limit, 500))


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
