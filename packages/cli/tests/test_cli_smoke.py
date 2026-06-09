from typer.testing import CliRunner

from aurelia_cli.main import app

runner = CliRunner()


def test_version():
    r = runner.invoke(app, ["version"])
    assert r.exit_code == 0
    assert "aurelia" in r.output


def test_help_lists_commands():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for cmd in ("start", "chat", "memory", "train-mini-llm", "generate"):
        assert cmd in r.output


def test_status_fails_gracefully_when_api_down(monkeypatch):
    monkeypatch.setenv("AURELIA_API_URL", "http://127.0.0.1:1")
    import importlib

    import aurelia_cli.main as m
    importlib.reload(m)
    r = runner.invoke(m.app, ["status"])
    assert r.exit_code == 1
    assert "not reachable" in r.output
