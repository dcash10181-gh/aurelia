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

# FTS5 schema is kept separate so we can degrade gracefully on SQLite builds
# compiled without the FTS5 extension (rare, but exists on some distros).
# Architectural decision: external-content FTS table ('content=memories')
# instead of a standalone FTS table — the text is stored once in `memories`,
# the FTS index holds only the inverted index, and triggers keep it in sync.
_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content, tags,
    content='memories', content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS memories_fts_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content, tags)
    VALUES (new.rowid, new.content, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS memories_fts_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags)
    VALUES ('delete', old.rowid, old.content, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS memories_fts_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content, tags)
    VALUES ('delete', old.rowid, old.content, old.tags);
    INSERT INTO memories_fts(rowid, content, tags)
    VALUES (new.rowid, new.content, new.tags);
END;
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.fts_enabled = False
        self._init()

    def _init(self) -> None:
        with self.connect() as conn:
            conn.executescript(_SCHEMA)
            try:
                conn.executescript(_FTS_SCHEMA)
                # Migration for databases created before FTS existed. NB: with
                # an external-content table, `count(*) FROM memories_fts` reads
                # through to `memories` and always matches — the true index
                # state is the docsize shadow table (one row per indexed doc).
                mem_count = conn.execute("SELECT count(*) FROM memories").fetchone()[0]
                fts_count = conn.execute(
                    "SELECT count(*) FROM memories_fts_docsize"
                ).fetchone()[0]
                if mem_count != fts_count:
                    conn.execute("INSERT INTO memories_fts(memories_fts) VALUES ('rebuild')")
                self.fts_enabled = True
            except sqlite3.OperationalError:
                # SQLite built without FTS5 — fall back to LIKE search.
                self.fts_enabled = False

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

    def search_memories(self, query: str, limit: int = 50,
                        match_any: bool = False) -> list[dict[str, Any]]:
        """Full-text search over memory content and tags.

        Uses FTS5 with BM25 relevance ranking when available. User input is
        never passed to FTS5 as raw query syntax: each whitespace token is
        double-quoted (neutralizing operators like NEAR/AND/-) and given a
        prefix wildcard, so "proj plan" matches "project planning". Falls
        back to LIKE on builds without FTS5 or for queries FTS5 rejects.

        match_any=False (default): all terms must match — precision mode for
        explicit user searches. match_any=True: any term may match, BM25
        ranks — recall mode for injecting memories relevant to a natural-
        language message, where filler words must not veto the match.
        """
        query = query.strip()
        if not query:
            return []
        if self.fts_enabled:
            match = self._fts_query(query, match_any=match_any)
            try:
                with self.connect() as conn:
                    rows = conn.execute(
                        "SELECT m.* FROM memories_fts f "
                        "JOIN memories m ON m.rowid = f.rowid "
                        "WHERE memories_fts MATCH ? "
                        "ORDER BY bm25(memories_fts), m.created_at DESC LIMIT ?",
                        (match, limit),
                    ).fetchall()
                return [self._memory_out(dict(r)) for r in rows]
            except sqlite3.OperationalError:
                pass  # pathological query string — degrade to LIKE
        return self._like_search(query, limit)

    @staticmethod
    def _fts_query(query: str, match_any: bool = False) -> str:
        # Quote each token (escaping embedded quotes per FTS5 rules) and add
        # a prefix wildcard. AND = all terms must match (search precision);
        # OR = any term may match, BM25 ranks (recall for natural language).
        tokens = [t.replace('"', '""') for t in query.split()]
        op = " OR " if match_any else " AND "
        return op.join(f'"{t}"*' for t in tokens if t)

    def _like_search(self, query: str, limit: int) -> list[dict[str, Any]]:
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
    def clear_messages(self) -> int:
        """Start a fresh conversation: wipe chat history. Memories are a
        separate, durable store and are deliberately NOT touched."""
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM messages")
            return cur.rowcount

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
