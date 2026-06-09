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
