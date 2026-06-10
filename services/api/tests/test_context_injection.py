"""Context injection: conversation history + memory auto-recall."""
from aurelia_api.agent.loop import build_context, run_agent_turn
from aurelia_api.services.providers import OllamaProvider, Provider
from aurelia_api.storage.db import Database
from aurelia_api.tools.builtin import build_default_registry


class RecordingProvider(Provider):
    """Captures the context (history arg) it was handed."""
    name = "recording"

    def __init__(self):
        self.seen_history = None

    def generate(self, prompt, history=None):
        self.seen_history = history
        return "ok"


def test_memories_recalled_into_system_message(tmp_path):
    db = Database(tmp_path / "m.db")
    db.create_memory("user's favorite color is teal", ["prefs"])
    db.create_memory("user lives in Texas", ["prefs"])
    db.create_memory("unrelated fact about gardening", [])
    ctx = build_context("what is my favorite color?", memory=db)
    assert ctx and ctx[0]["role"] == "system"
    assert "teal" in ctx[0]["content"]
    assert "gardening" not in ctx[0]["content"]  # only relevant hits injected


def test_no_matching_memories_means_no_system_message(tmp_path):
    db = Database(tmp_path / "m.db")
    db.create_memory("user's favorite color is teal", [])
    ctx = build_context("completely unrelated query xyzzy", memory=db)
    assert ctx == []


def test_history_is_trimmed_and_capped(tmp_path):
    history = [{"role": "user", "content": f"msg {i}"} for i in range(40)]
    history.append({"role": "user", "content": "x" * 10_000})
    ctx = build_context("hi", memory=None, history=history)
    assert len(ctx) == 12                      # _MAX_HISTORY_MSGS
    assert len(ctx[-1]["content"]) == 1200     # _MAX_MSG_CHARS
    assert ctx[0]["content"] == "msg 29"       # most recent window kept


def test_agent_turn_passes_context_to_provider(tmp_path):
    db = Database(tmp_path / "m.db")
    db.create_memory("the project codename is NIGHTJAR", [])
    p = RecordingProvider()
    history = [{"role": "user", "content": "earlier message"},
               {"role": "assistant", "content": "earlier reply"}]
    run_agent_turn("tell me about project nightjar", p,
                   build_default_registry(tmp_path), db, history)
    roles = [m["role"] for m in p.seen_history]
    assert roles[0] == "system" and "NIGHTJAR" in p.seen_history[0]["content"]
    assert roles[1:] == ["user", "assistant"]


def test_memory_failure_never_kills_turn(tmp_path):
    class BrokenMemory:
        def search_memories(self, *a, **k):
            raise RuntimeError("disk on fire")
    p = RecordingProvider()
    out = run_agent_turn("hello", p, build_default_registry(tmp_path),
                         BrokenMemory(), [])
    assert out["reply"] == "ok"


def test_ollama_chat_payload_shape():
    msgs = OllamaProvider.build_messages(
        "current question",
        [{"role": "system", "content": "memories"},
         {"role": "user", "content": "prior"}])
    assert msgs[0] == {"role": "system", "content": "memories"}
    assert msgs[-1] == {"role": "user", "content": "current question"}
    assert OllamaProvider.build_messages("q", None) == [
        {"role": "user", "content": "q"}]


def test_endpoint_history_excludes_current_message(client):
    # First turn establishes history; second turn's context must contain the
    # first exchange but NOT an echo of the in-flight message.
    client.post("/api/chat", json={"message": "alpha bravo", "provider": "echo"})
    r = client.post("/api/chat", json={"message": "charlie delta", "provider": "echo"})
    assert r.status_code == 200
    msgs = client.get("/api/messages").json()
    contents = [m["content"] for m in msgs]
    assert "alpha bravo" in contents and "charlie delta" in contents
