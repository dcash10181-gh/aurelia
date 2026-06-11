"""ReAct loop: multi-step decide→act→observe with hard guards."""
from aurelia_api.agent.loop import run_agent_turn, run_agent_turn_stream
from aurelia_api.services.providers import Provider
from aurelia_api.storage.db import Database
from aurelia_api.tools.builtin import build_default_registry


class SequencedProvider(Provider):
    """Returns scripted decisions in order; records observations it was shown."""
    name = "seq"
    supports_tool_selection = True

    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.seen_observations = []
        self.decision_calls = 0

    def tool_decision(self, message, tools, observations=None):
        self.decision_calls += 1
        self.seen_observations.append(list(observations or []))
        if self.decisions:
            return self.decisions.pop(0)
        return {"tool": None, "args": {}}

    def generate(self, prompt, history=None):
        return f"final answer composed from: {prompt[-80:]}"


def setup(tmp_path):
    db = Database(tmp_path / "r.db")
    return db, build_default_registry(tmp_path, enable_shell=False, db=db)


def test_chained_calls_with_observation_feedback(tmp_path):
    """The defining ReAct behavior: step 2's decision sees step 1's result."""
    db, reg = setup(tmp_path)
    db.create_memory("User's monthly budget is 120", [])
    p = SequencedProvider([
        {"tool": "memory.search", "args": {"query": "budget"}},
        {"tool": "calculator", "args": {"expression": "120/4"}},
        {"tool": None, "args": {}},
    ])
    out = run_agent_turn("what's my weekly budget?", p, reg, db)
    assert [c["tool"] for c in out["tool_calls"]] == ["memory.search", "calculator"]
    assert out["tool_calls"][1]["result"] in ("30", "30.0")
    assert out["provider"] == "seq+memory.search+calculator"
    # Decision pass 2 was shown observation 1:
    assert p.seen_observations[1][0]["tool"] == "memory.search"
    assert "120" in p.seen_observations[1][0]["result"]


def test_step_cap_enforced(tmp_path, monkeypatch):
    from aurelia_api import config
    monkeypatch.setattr(config.settings, "agent_max_steps", 3)
    db, reg = setup(tmp_path)
    # Endless distinct calculator calls; the cap must cut them off.
    p = SequencedProvider([
        {"tool": "calculator", "args": {"expression": f"1+{i}"}} for i in range(10)
    ])
    out = run_agent_turn("count forever", p, reg, db)
    assert len(out["tool_calls"]) == 3


def test_identical_repeat_breaks_loop(tmp_path):
    db, reg = setup(tmp_path)
    same = {"tool": "calculator", "args": {"expression": "2+2"}}
    p = SequencedProvider([same, dict(same), dict(same)])
    out = run_agent_turn("loop forever", p, reg, db)
    assert len(out["tool_calls"]) == 1  # stuck model detected, loop broken


def test_tool_error_becomes_observation_and_model_can_adapt(tmp_path):
    db, reg = setup(tmp_path)
    p = SequencedProvider([
        {"tool": "calculator", "args": {"expression": "not math"}},
        {"tool": "calculator", "args": {"expression": "6*7"}},
        {"tool": None, "args": {}},
    ])
    out = run_agent_turn("six times seven", p, reg, db)
    assert out["tool_calls"][0]["result"].startswith("ERROR:")
    assert out["tool_calls"][1]["result"] == "42"
    # The retry decision saw the error:
    assert p.seen_observations[1][0]["result"].startswith("ERROR:")


def test_disabled_shell_is_refused_but_visible(tmp_path):
    """SECURITY: a shell request never executes; the registry's refusal is
    recorded as an ERROR observation (transparent, not hidden)."""
    db, reg = setup(tmp_path)
    p = SequencedProvider([
        {"tool": "shell", "args": {"command": "rm -rf /"}},
        {"tool": None, "args": {}},
    ])
    out = run_agent_turn("hello", p, reg, db)
    shell_calls = [c for c in out["tool_calls"] if c["tool"] == "shell"]
    assert len(shell_calls) == 1
    assert shell_calls[0]["result"].startswith("ERROR:")
    assert "disabled" in shell_calls[0]["result"]


def test_stream_emits_tool_event_frames(tmp_path):
    db, reg = setup(tmp_path)
    p = SequencedProvider([
        {"tool": "calculator", "args": {"expression": "3*3"}},
        {"tool": None, "args": {}},
    ])
    # Provider.stream default chunks generate()'s output.
    frames = list(run_agent_turn_stream("three squared", p, reg, db))
    events = [f["tool_event"] for f in frames if "tool_event" in f]
    assert len(events) == 1 and events[0]["result"] == "9"
    assert frames[-1]["meta"]["tool_calls"] == events


def test_decline_on_first_pass_falls_through(tmp_path):
    db, reg = setup(tmp_path)
    p = SequencedProvider([{"tool": None, "args": {}}])
    frames = list(run_agent_turn_stream("calculate 9*9", p, reg, db))
    assert frames[-1]["meta"]["provider"] == "agent+calculator"  # regex tier
    assert p.decision_calls == 1


def test_near_duplicate_save_is_idempotent(tmp_path):
    """Live-test regression: model requested the same save twice with
    trivially different args; both executed and duplicated the memory.
    The tool layer must self-protect — only one row may land."""
    db, reg = setup(tmp_path)
    p = SequencedProvider([
        {"tool": "memory.save", "args": {"content": "monthly budget is $200"}},
        {"tool": "memory.save", "args": {"content": "monthly budget is $200",
                                         "tags": ""}},
        {"tool": None, "args": {}},
    ])
    out = run_agent_turn("remember my budget is $200", p, reg, db)
    hits = db.search_memories("budget", match_any=True)
    assert len(hits) == 1
    assert "Already in memory" in out["tool_calls"][1]["result"]


def test_identical_result_breaks_loop(tmp_path):
    """Near-duplicate args evade the (tool, args) guard; an identical result
    from the same tool means no new information — loop must stop there."""
    db, reg = setup(tmp_path)
    p = SequencedProvider([
        {"tool": "calculator", "args": {"expression": "2+2"}},
        {"tool": "calculator", "args": {"expression": "2 + 2"}},  # same result
        {"tool": "calculator", "args": {"expression": "5+5"}},    # must not run
    ])
    out = run_agent_turn("math spam", p, reg, db)
    assert len(out["tool_calls"]) == 2
    assert all(c["result"] == "4" for c in out["tool_calls"])


def test_compose_prompt_focuses_latest_message():
    """Context-bleed regression: the composed answer must be steered to the
    latest message, with history demoted to background."""
    from aurelia_api.agent.loop import _compose_react_prompt
    p = _compose_react_prompt("remember X", [
        {"tool": "memory.save", "args": {}, "result": "Saved"}])
    assert "LATEST message" in p
    assert "background context" in p
    assert "confirm what was saved" in p.lower() or "confirm what" in p
