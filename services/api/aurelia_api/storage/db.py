"""SQLite storage layer.

Architectural decision: plain sqlite3 + small DAO functions instead of an ORM.
The data model is tiny (memories, messages), an ORM would add a dependency and
indirection without benefit. WAL mode keeps reads non-blocking for the UI.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._init()

    def _init(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ----- memories -----------------------------------------------------
    def create_memory(self, content: str, tags: list[str] | None = None) -> dict[str, Any]:
        row = {
            "id": uuid.uuid4().hex,
            "content": content,
            "tags": ",".join(tags or []),
            "created_at": time.time(),
        }
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO memories (id, content, tags, created_at) VALUES (?,?,?,?)",
                (row["id"], row["content"], row["tags"], row["created_at"]),
            )
        return self._memory_out(row)

    def list_memories(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._memory_out(dict(r)) for r in rows]

    def search_memories(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        # Simple LIKE search: adequate for local scale; FTS5 is a documented
        # upgrade path in docs/roadmap.md.
        like = f"%{query}%"
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? OR tags LIKE ? "
                "ORDER BY created_at DESC LIMIT ?",
                (like, like, limit),
            ).fetchall()
        return [self._memory_out(dict(r)) for r in rows]

    def delete_memory(self, memory_id: str) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            return cur.rowcount > 0

    # ----- messages ------------------------------------------------------
    def add_message(self, role: str, content: str) -> dict[str, Any]:
        row = {"id": uuid.uuid4().hex, "role": role, "content": content, "created_at": time.time()}
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO messages (id, role, content, created_at) VALUES (?,?,?,?)",
                (row["id"], row["role"], row["content"], row["created_at"]),
            )
        return row

    def recent_messages(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]

    @staticmethod
    def _memory_out(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        out["tags"] = [t for t in str(out.get("tags", "")).split(",") if t]
        return out
