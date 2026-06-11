"""Actuator pack: web.fetch (SSRF-guarded) + workspace files (sandboxed).

Network access is mocked — these tests must pass offline. The security
properties are the point: every test here is a containment contract.
"""
import io

import pytest

from aurelia_api.tools.builtin import (
    WebTool, WorkspaceTool, _host_is_private, build_default_registry,
)


# ----------------------------------------------------------------- SSRF guard
def test_private_hosts_are_refused():
    for host in ["localhost", "127.0.0.1", "0.0.0.0", "192.168.1.10",
                 "10.0.0.5", "172.16.3.3", "169.254.1.1", "::1"]:
        assert _host_is_private(host), host


def test_unresolvable_host_fails_closed():
    assert _host_is_private("definitely-not-a-real-host-xyzzy.invalid")


def test_fetch_refuses_private_and_bad_schemes():
    web = WebTool()
    with pytest.raises(ValueError, match="private"):
        web.fetch({"url": "http://127.0.0.1:8484/api/health"})
    with pytest.raises(ValueError, match="private"):
        web.fetch({"url": "http://localhost:11434/api/tags"})
    for url in ["file:///etc/passwd", "ftp://example.com/x", "gopher://x"]:
        with pytest.raises(ValueError, match="http"):
            web.fetch({"url": url})


def test_fetch_extracts_text_and_caps(monkeypatch):
    html = ("<html><head><script>evil()</script><style>x{}</style></head>"
            "<body><h1>Title</h1><p>Hello world</p></body></html>")

    class FakeResp(io.BytesIO):
        headers = {"Content-Type": "text/html"}
        def __enter__(self): return self
        def __exit__(self, *a): return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=0, context=None: FakeResp(html.encode()))
    monkeypatch.setattr("aurelia_api.tools.builtin._host_is_private",
                        lambda h: False)
    out = WebTool().fetch({"url": "https://example.com/x"})
    assert "Title" in out and "Hello world" in out
    assert "evil" not in out and "x{}" not in out


# ------------------------------------------------------------- workspace jail
def test_workspace_round_trip(tmp_path):
    ws = WorkspaceTool(tmp_path)
    assert "11 chars" in ws.write({"path": "plan/q3.md", "content": "hello world"})
    assert ws.read({"path": "plan/q3.md"}) == "hello world"
    assert "plan/q3.md" in ws.list({})


def test_workspace_traversal_is_refused(tmp_path):
    ws = WorkspaceTool(tmp_path)
    for evil in ["../outside.txt", "../../etc/passwd", "a/../../../x",
                 "/etc/passwd"]:
        with pytest.raises(ValueError):
            ws.write({"path": evil, "content": "x"})
        with pytest.raises(ValueError):
            ws.read({"path": evil})


def test_workspace_write_cap(tmp_path):
    ws = WorkspaceTool(tmp_path)
    with pytest.raises(ValueError, match="cap"):
        ws.write({"path": "big.txt", "content": "x" * 200_001})


# ------------------------------------------------------------------- registry
def test_web_tool_is_config_gated(tmp_path):
    on = {t["name"] for t in build_default_registry(tmp_path, enable_web=True).list()}
    off = {t["name"] for t in build_default_registry(tmp_path, enable_web=False).list()}
    assert "web.fetch" in on and "web.fetch" not in off
    assert {"files.read", "files.write", "files.list"} <= on


def test_ssl_context_uses_certifi_and_verifies():
    """Cert verification must be ON and backed by certifi's bundle —
    regression for macOS python.org installs that ship without a trust
    store. Never CERT_NONE."""
    import ssl
    from aurelia_api.tools.builtin import _ssl_context
    ctx = _ssl_context()
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
