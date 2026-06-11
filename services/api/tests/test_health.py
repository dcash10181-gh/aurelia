def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"] == "AURELIA"


def test_status_reports_shell_disabled_by_default(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    assert r.json()["shell_tool_enabled"] is False


def test_health_reports_build(client):
    """The running git commit must be visible — 'is the server running the
    code I think it is' caused repeated lost debugging rounds."""
    data = client.get("/api/health").json()
    assert "build" in data and data["build"]  # short hash here; 'unknown' off-git
