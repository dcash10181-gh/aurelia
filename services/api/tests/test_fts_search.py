"""FTS5 memory search tests — exercises the Database layer directly."""
import sqlite3

from aurelia_api.storage.db import Database


def make_db(tmp_path):
    return Database(tmp_path / "test.db")


def test_fts_enabled_on_this_build(tmp_path):
    db = make_db(tmp_path)
    assert db.fts_enabled, "CI/runtime SQLite is expected to ship FTS5"


def test_multi_term_and_prefix_matching(tmp_path):
    db = make_db(tmp_path)
    db.create_memory("project planning for the Q3 launch", ["work"])
    db.create_memory("grocery list: apples and bread", ["home"])
    # prefix: "proj plan" should hit "project planning"
    hits = db.search_memories("proj plan")
    assert len(hits) == 1 and "project planning" in hits[0]["content"]
    # all terms must match (AND semantics)
    assert db.search_memories("project bread") == []


def test_tag_search_and_relevance_order(tmp_path):
    db = make_db(tmp_path)
    db.create_memory("note about something else entirely", ["alpha"])
    dense = db.create_memory("alpha alpha alpha release notes", ["alpha"])
    hits = db.search_memories("alpha")
    assert len(hits) == 2
    # BM25: the content+tag dense row must rank first
    assert hits[0]["id"] == dense["id"]


def test_index_stays_in_sync_after_delete(tmp_path):
    db = make_db(tmp_path)
    mem = db.create_memory("ephemeral fact", [])
    assert len(db.search_memories("ephemeral")) == 1
    db.delete_memory(mem["id"])
    assert db.search_memories("ephemeral") == []


def test_operator_injection_is_neutralized(tmp_path):
    db = make_db(tmp_path)
    db.create_memory("plain content", [])
    # FTS5 operators / syntax in user input must not crash or alter semantics
    for q in ['"unterminated', "a NEAR b", "-negate", "col: value", "(("]:
        db.search_memories(q)  # must not raise


def test_migration_rebuilds_index_for_pre_fts_db(tmp_path):
    """A DB created without the FTS table gets indexed on next startup."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT NOT NULL, "
        "tags TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL);"
        "CREATE TABLE messages (id TEXT PRIMARY KEY, role TEXT NOT NULL, "
        "content TEXT NOT NULL, created_at REAL NOT NULL);"
    )
    conn.execute(
        "INSERT INTO memories VALUES ('m1', 'legacy searchable row', 'old', 1.0)"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    hits = db.search_memories("legacy")
    assert len(hits) == 1 and hits[0]["id"] == "m1"


def test_empty_query_returns_nothing(tmp_path):
    db = make_db(tmp_path)
    db.create_memory("anything", [])
    assert db.search_memories("   ") == []
