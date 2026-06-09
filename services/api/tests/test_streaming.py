"""Token streaming tests: SSE endpoint contract + agent stream behavior."""
import json

from aurelia_api.agent.loop import run_agent_turn_stream
from aurelia_api.services.providers import Provider, RuleBasedProvider
from aurelia_api.tools.builtin import build_default_registry


def parse_frames(body: str) -> list:
    out = []
    for frame in body.strip().split("\n\n"):
        data = frame.replace("data: ", "", 1)
        out.append("[DONE]" if data == "[DONE]" else json.loads(data))
    return out


def test_stream_endpoint_contract(client):
    with client.stream("POST", "/api/chat/stream",
                       json={"message": "hello there", "provider": "echo"}) as r:
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/event-stream")
        frames = parse_frames(r.read().decode())

    assert frames[-1] == "[DONE]"
    assert "meta" in frames[-2] and frames[-2]["meta"]["provider"] == "echo"
    tokens = [f["token"] for f in frames if isinstance(f, dict) and "token" in f]
    assert len(tokens) > 1, "reply must arrive in multiple frames"
    reply = "".join(tokens)
    assert "AURELIA" in reply


def test_stream_endpoint_tool_route(client):
    with client.stream("POST", "/api/chat/stream",
                       json={"message": "calculate 7*6", "provider": "echo"}) as r:
        frames = parse_frames(r.read().decode())
    tokens = "".join(f["token"] for f in frames if isinstance(f, dict) and "token" in f)
    meta = next(f["meta"] for f in frames if isinstance(f, dict) and "meta" in f)
    assert "42" in tokens
    assert meta["provider"] == "agent+calculator"
    assert meta["tool_calls"][0]["tool"] == "calculator"


def test_stream_persists_full_reply(client):
    with client.stream("POST", "/api/chat/stream",
                       json={"message": "calculate 2+2", "provider": "echo"}) as r:
        frames = parse_frames(r.read().decode())
    streamed = "".join(f["token"] for f in frames if isinstance(f, dict) and "token" in f)
    msgs = client.get("/api/messages").json()
    assert msgs[-1]["role"] == "assistant" and msgs[-1]["content"] == streamed


class _CountingProvider(Provider):
    """Fails the test if generate() is called more than once per turn."""
    name = "counting"

    def __init__(self):
        self.calls = 0

    def generate(self, prompt, history=None):
        self.calls += 1
        return "fallback reply"


def test_no_double_generation_when_tool_intent_falls_through(tmp_path):
    # "calculate" intent with an expression the calculator rejects (letters)
    registry = build_default_registry(tmp_path, enable_shell=False)
    provider = _CountingProvider()
    frames = list(run_agent_turn_stream("what is 5 % 0", provider, registry))
    assert provider.calls <= 1, "tool fall-through must not generate twice"
    assert "meta" in frames[-1]


def test_default_stream_reconstructs_generate():
    p = RuleBasedProvider()
    prompt = "who are you"
    assert "".join(p.stream(prompt)) == p.generate(prompt)
