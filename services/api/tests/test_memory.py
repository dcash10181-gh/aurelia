def test_memory_crud(client):
    r = client.post("/api/memory", json={"content": "AURELIA test memory", "tags": ["qa"]})
    assert r.status_code == 200
    mem = r.json()
    assert mem["content"] == "AURELIA test memory"
    assert mem["tags"] == ["qa"]

    r = client.get("/api/memory")
    assert any(m["id"] == mem["id"] for m in r.json())

    r = client.get("/api/memory", params={"q": "test memory"})
    assert any(m["id"] == mem["id"] for m in r.json())

    r = client.delete(f"/api/memory/{mem['id']}")
    assert r.status_code == 200
    r = client.delete(f"/api/memory/{mem['id']}")
    assert r.status_code == 404


def test_clear_messages_keeps_memories(client):
    client.post("/api/memory", json={"content": "durable fact", "tags": []})
    client.post("/api/chat", json={"message": "hello", "provider": "echo"})
    assert len(client.get("/api/messages").json()) >= 2
    r = client.delete("/api/messages")
    assert r.status_code == 200 and r.json()["cleared"] >= 2
    assert client.get("/api/messages").json() == []
    # Memories survive a new-chat — that's the contract.
    mems = client.get("/api/memory").json()
    assert any(m["content"] == "durable fact" for m in mems)
