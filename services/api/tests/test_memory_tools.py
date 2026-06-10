"""Agent-facing memory tools: durable, user-visible, registry-enforced."""
import pytest

from aurelia_api.agent.loop import run_agent_turn
from aurelia_api.services.providers import OllamaProvider, Provider
from aurelia_api.storage.db import Database
from aurelia_api.tools.builtin import build_default_registry


class ScriptedProvider(Provider):
    name = "scripted"
    supports_tool_selection = True

    def __init__(self, decision):
        self.decision = decision

    def tool_decision(self, message, tools):
        return self.decision

    def generate(self, prompt, history=None):
        return f"composed: {prompt[-60:]}"


def setup(tmp_path):
    db = Database(tmp_path / "t.db")
    reg = build_default_registry(tmp_path, enable_shell=False, db=db)
    return db, reg


def test_memory_tools_registered_only_with_db(tmp_path):
    names = {t["name"] for t in build_default_registry(tmp_path, db=None).list()}
    assert "memory.save" not in names
    db, reg = setup(tmp_path)
    names = {t["name"] for t in reg.list()}
    assert {"memory.save", "memory.search"} <= names


def test_agent_saved_memory_is_durable_and_user_visible(tmp_path):
    """The defining property: an agent save outlives any history window and
    appears in the same store the UI panel reads."""
    db, reg = setup(tmp_path)
    p = ScriptedProvider({"tool": "memory.save",
                          "args": {"content": "User's dog is named Biscuit",
                                   "tags": "pets"}})
    out = run_agent_turn("remember my dog's name is Biscuit", p, reg, db)
    assert out["provider"] == "scripted+memory.save"
    # Durable: present in the DB via FTS recall — no conversation needed.
    hits = db.search_memories("dog name", match_any=True)
    assert hits and "Biscuit" in hits[0]["content"]
    assert hits[0]["tags"] == ["pets"]


def test_memory_search_tool_round_trip(tmp_path):
    db, reg = setup(tmp_path)
    db.create_memory("User's cat is named Muffin", ["pets"])
    p = ScriptedProvider({"tool": "memory.search", "args": {"query": "cat"}})
    out = run_agent_turn("what's my cat called?", p, reg, db)
    assert "Muffin" in out["tool_calls"][0]["result"]


def test_memory_save_validation(tmp_path):
    db, reg = setup(tmp_path)
    with pytest.raises(ValueError):
        reg.invoke("memory.save", {"content": "   "})
    with pytest.raises(ValueError):
        reg.invoke("memory.save", {"content": "x" * 2001})
    with pytest.raises(ValueError):
        reg.invoke("memory.search", {})


def test_decision_prompt_contract():
    """The restraint rules the live model is steered by must stay present.
    Guards against someone 'simplifying' the prompt and reintroducing the
    trigger-happy persistence behavior observed in live testing."""
    p = OllamaProvider._DECISION_PROMPT
    assert "MUST be null" in p
    assert "NEVER persist" in p
    assert "memory.save" in p and "notes.write" in p
    assert "suggest a name" in p  # the negative example stays


def test_memory_endpoint_integration(client):
    """memory.* tools appear in /api/tools when the app wires its db."""
    names = {t["name"] for t in client.get("/api/tools").json()}
    assert {"memory.save", "memory.search"} <= names
