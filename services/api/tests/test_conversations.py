"""Conversations: scoped history, isolation, migration, workspace browser."""
import sqlite3

from aurelia_api.storage.db import Database


def test_conversation_crud_and_scoped_history(tmp_path):
    db = Database(tmp_path / "c.db")
    a = db.create_conversation()
    b = db.create_conversation()
    db.add_message("user", "alpha", a["id"])
    db.add_message("user", "bravo", b["id"])
    assert [m["content"] for m in db.recent_messages(conversation_id=a["id"])] == ["alpha"]
    assert [m["content"] for m in db.recent_messages(conversation_id=b["id"])] == ["bravo"]
    assert db.delete_conversation(b["id"])
    assert db.recent_messages(conversation_id=b["id"]) == []


def test_autotitle_from_first_message(tmp_path):
    db = Database(tmp_path / "c.db")
    c = db.create_conversation()
    db.maybe_autotitle(c["id"], "plan the Q3 launch budget")
    titles = {x["id"]: x["title"] for x in db.list_conversations()}
    assert titles[c["id"]] == "plan the Q3 launch budget"
    db.maybe_autotitle(c["id"], "something else")  # must not overwrite
    titles = {x["id"]: x["title"] for x in db.list_conversations()}
    assert titles[c["id"]] == "plan the Q3 launch budget"


def test_pre_conversation_db_migrates(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE memories (id TEXT PRIMARY KEY, content TEXT NOT NULL, "
        "tags TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL);"
        "CREATE TABLE messages (id TEXT PRIMARY KEY, role TEXT NOT NULL, "
        "content TEXT NOT NULL, created_at REAL NOT NULL);")
    conn.execute("INSERT INTO messages VALUES ('m1','user','old msg',1.0)")
    conn.commit()
    conn.close()
    db = Database(path)  # must not raise; column added, default conv exists
    msgs = db.recent_messages(conversation_id="default")
    assert [m["content"] for m in msgs] == ["old msg"]


def test_conversation_isolation_through_endpoint(client):
    a = client.post("/api/conversations").json()
    b = client.post("/api/conversations").json()
    client.post("/api/chat", json={"message": "secret alpha topic",
                                   "provider": "echo", "conversation_id": a["id"]})
    client.post("/api/chat", json={"message": "different bravo topic",
                                   "provider": "echo", "conversation_id": b["id"]})
    a_msgs = client.get(f"/api/messages?conversation_id={a['id']}").json()
    b_msgs = client.get(f"/api/messages?conversation_id={b['id']}").json()
    assert any("alpha" in m["content"] for m in a_msgs)
    assert not any("alpha" in m["content"] for m in b_msgs)
    assert client.delete("/api/conversations/default").status_code == 400


def test_workspace_browser_endpoints(client, tmp_path):
    r = client.get("/api/workspace")
    assert r.status_code == 200 and "files" in r.json()
    assert client.get("/api/workspace/file?path=../etc/passwd").status_code == 404
