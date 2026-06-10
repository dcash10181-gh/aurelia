import pytest

from aurelia_api.tools.builtin import build_default_registry, calculator


def test_registry_lists_builtins(client):
    r = client.get("/api/tools")
    names = {t["name"] for t in r.json()}
    assert {"calculator", "time", "notes.write", "notes.read", "notes.list", "shell"} <= names


def test_calculator_tool():
    assert calculator({"expression": "2*(3+4)"}) == "14"
    assert calculator({"expression": "10/4"}) == "2.5"
    with pytest.raises(ValueError):
        calculator({"expression": "__import__('os')"})
    with pytest.raises(ValueError):
        calculator({"expression": "2**99999"})


def test_calculator_via_api(client):
    r = client.post("/api/tools/invoke", json={"name": "calculator",
                                               "args": {"expression": "6*7"}})
    assert r.status_code == 200
    assert r.json()["result"] == "42"


def test_shell_disabled_by_default(client):
    r = client.post("/api/tools/invoke", json={"name": "shell", "args": {"command": "echo hi"}})
    assert r.status_code == 403


def test_notes_sandbox_blocks_traversal(tmp_path):
    reg = build_default_registry(tmp_path)
    with pytest.raises((PermissionError, ValueError)):
        reg.invoke("notes.write", {"name": "../../etc/passwd", "content": "x"})


def test_chat_agent_routes_calculation(client):
    r = client.post("/api/chat", json={"message": "calculate 12*12"})
    assert r.status_code == 200
    body = r.json()
    assert "144" in body["reply"]
    assert body["tool_calls"]


def test_calculator_normalizes_model_noise(tmp_path):
    """Real-model inputs from live testing: currency symbols, unicode
    operators, thousands separators must compute, not raise."""
    from aurelia_api.tools.builtin import calculator
    assert calculator({"expression": "$200 / 4"}) == "50.0"
    assert calculator({"expression": "200 ÷ 4"}) == "50.0"
    assert calculator({"expression": "3 × 4"}) == "12"
    assert calculator({"expression": "1,000 - 250"}) == "750"
    assert calculator({"expression": "2^10"}) == "1024"


def test_calculator_error_is_actionable(tmp_path):
    """The ERROR observation must teach the model how to retry."""
    import pytest
    from aurelia_api.tools.builtin import calculator
    with pytest.raises(ValueError, match="200/4"):
        calculator({"expression": "a quarter of my budget"})


def test_calculator_normalization_is_not_a_safety_hole(tmp_path):
    """Normalization must not let code through the AST allowlist."""
    import pytest
    from aurelia_api.tools.builtin import calculator
    for evil in ["__import__('os')", "(1).__class__", "open('/etc/passwd')"]:
        with pytest.raises(ValueError):
            calculator({"expression": evil})
