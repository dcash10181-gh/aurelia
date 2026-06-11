"""Pydantic request/response schemas for the public API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: str | None = None  # None -> 'default' (CLI compat)
    message: str = Field(min_length=1, max_length=20000)
    provider: str | None = None


class ChatResponse(BaseModel):
    reply: str
    provider: str
    tool_calls: list[dict] = []


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    tags: list[str] = []


class MemoryOut(BaseModel):
    id: str
    content: str
    tags: list[str]
    created_at: float


class ToolInvoke(BaseModel):
    name: str
    args: dict = {}
