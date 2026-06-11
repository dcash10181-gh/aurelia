"""LLM-driven tool selection: routing tiers, validation, and security.

Uses a scripted provider so every branch is testable without a live Ollama.
"""
from aurelia_api.agent.loop import run_agent_turn, run_agent_turn_stream
from aurelia_api.services.providers import Provider, RuleBasedProvider
from aurelia_api.tools.builtin import build_default_registry


class ScriptedProvider(Provider):
    """Provider with a canned tool decision and countable generate calls.

    Under the ReAct loop the same decision repeating is detected as a stuck
    loop after one execution, so single-decision scripts behave like the old
    single-shot selection: one tool call, then compose.
    """
    name = "scripted"
    supports_tool_selection = True

    def __init__(self, decision):
        self.decision = decision
        self.decision_calls = 0
        self.generate_calls = 0
        self.last_prompt = None

    def tool_decision(self, message, tools, observations=None, memories=None):
        self.decision_calls += 1
        return self.decision

    def generate(self, prompt, history=None):
        self.generate_calls += 1
        self.last_prompt = prompt
        return f"composed answer from: {prompt[-40:]}"


def reg(tmp_path, shell=False):
    return build_default_registry(tmp_path, enable_shell=shell)


def test_llm_selected_tool_executes_and_composes(tmp_path):
    p = ScriptedProvider({"tool": "calculator", "args": {"expression": "6*7"}})
    out = run_agent_turn("six times seven please", p, reg(tmp_path))
    assert out["provider"] == "scripted+calculator"
    assert out["tool_calls"][0]["result"] == "42"
    assert "42" in p.last_prompt  # tool result fed into the compose pass


def test_llm_selection_streams_composed_answer(tmp_path):
    p = ScriptedProvider({"tool": "calculator", "args": {"expression": "2+3"}})
    frames = list(run_agent_turn_stream("add them", p, reg(tmp_path)))
    meta = frames[-1]["meta"]
    assert meta["provider"] == "scripted+calculator"
    assert meta["tool_calls"][0]["result"] == "5"
    assert any("token" in f for f in frames[:-1])


def test_null_decision_falls_back_without_double_pass(tmp_path):
    # Message matches the calc regex; provider declines → regex must route,
    # and the decision pass must run exactly once in the streaming path.
    p = ScriptedProvider({"tool": None, "args": {}})
    frames = list(run_agent_turn_stream("calculate 9*9", p, reg(tmp_path)))
    meta = frames[-1]["meta"]
    assert meta["provider"] == "agent+calculator"  # regex tier took it
    assert p.decision_calls == 1


def test_unknown_tool_falls_back(tmp_path):
    p = ScriptedProvider({"tool": "rm_rf_everything", "args": {}})
    out = run_agent_turn("calculate 4+4", p, reg(tmp_path))
    assert out["provider"] == "agent+calculator"
    assert out["tool_calls"][0]["result"] == "8"


def test_disabled_shell_selection_is_blocked(tmp_path):
    """SECURITY: model requests the shell tool; the registry refuses. Under
    ReAct the refusal is recorded as an ERROR observation — transparent in
    the transcript, but the command NEVER executes."""
    p = ScriptedProvider({"tool": "shell", "args": {"command": "rm -rf /"}})
    out = run_agent_turn("hello", p, reg(tmp_path, shell=False))
    shell = [c for c in out["tool_calls"] if c["tool"] == "shell"]
    assert all(c["result"].startswith("ERROR:") for c in shell)
    assert out["reply"]  # turn still completed


def test_malformed_args_become_error_observation(tmp_path):
    p = ScriptedProvider({"tool": "calculator", "args": {"expression": "DROP TABLE"}})
    out = run_agent_turn("calculate 5+5", p, reg(tmp_path))
    # Under ReAct a failed call is an ERROR observation the model is told
    # to work around in the composed answer (see test_react_loop for the
    # successful-retry path).
    assert out["tool_calls"][0]["result"].startswith("ERROR:")
    assert out["reply"]


def test_non_capable_provider_never_asked(tmp_path):
    p = RuleBasedProvider()
    out = run_agent_turn("calculate 3*3", p, reg(tmp_path))
    assert out["provider"] == "agent+calculator"  # regex tier, as before


def test_selection_can_be_disabled_by_config(tmp_path, monkeypatch):
    from aurelia_api import config
    monkeypatch.setattr(config.settings, "llm_tool_selection", False)
    p = ScriptedProvider({"tool": "calculator", "args": {"expression": "6*7"}})
    out = run_agent_turn("calculate 6*7", p, reg(tmp_path))
    assert p.decision_calls == 0
    assert out["provider"] == "agent+calculator"
