"""Background tasks: schedule parsing, due logic, execution, resilience."""
import time

import pytest

from aurelia_api.services.tasks import is_due, parse_schedule, run_task_once
from aurelia_api.services.providers import RuleBasedProvider
from aurelia_api.storage.db import Database
from aurelia_api.tools.builtin import build_default_registry


# ------------------------------------------------------------------ schedules
def test_parse_schedules():
    assert parse_schedule("30m") == {"kind": "interval", "seconds": 1800}
    assert parse_schedule("2h") == {"kind": "interval", "seconds": 7200}
    assert parse_schedule("daily 08:00") == {"kind": "daily", "hour": 8, "minute": 0}
    for bad in ["", "soon", "daily 25:00", "0m", "3m", "every tuesday"]:
        with pytest.raises(ValueError):
            parse_schedule(bad)


def test_interval_due_logic():
    t = {"enabled": 1, "schedule": "30m", "last_run_at": None}
    assert is_due(t)                                  # never run -> due
    t["last_run_at"] = time.time() - 100
    assert not is_due(t)                              # ran recently
    t["last_run_at"] = time.time() - 1801
    assert is_due(t)                                  # interval elapsed
    t["enabled"] = 0
    assert not is_due(t)                              # disabled never due


def test_daily_due_logic():
    import datetime
    # Fix "now" at 09:00 local; a 'daily 08:00' task is due if not run
    # since 08:00 today.
    now = datetime.datetime.now().replace(hour=9, minute=0).timestamp()
    eight = datetime.datetime.now().replace(hour=8, minute=0, second=0,
                                            microsecond=0).timestamp()
    t = {"enabled": 1, "schedule": "daily 08:00", "last_run_at": None}
    assert is_due(t, now)
    t["last_run_at"] = eight + 60                     # ran at 08:01
    assert not is_due(t, now)
    t["last_run_at"] = eight - 3600                   # last ran yesterday-ish
    assert is_due(t, now)
    seven = datetime.datetime.now().replace(hour=7, minute=0).timestamp()
    t["last_run_at"] = None
    assert not is_due(t, seven)                       # before 08:00 -> not due


# ------------------------------------------------------------------ execution
def test_run_task_once_persists_into_conversation(tmp_path):
    db = Database(tmp_path / "t.db")
    reg = build_default_registry(tmp_path, db=db, enable_web=False)
    conv = db.create_conversation(title="⏱ test task")
    task = db.create_task("calculate 6*7", "30m", None, conv["id"])
    err = run_task_once(task, db, reg, lambda name: RuleBasedProvider())
    assert err is None
    msgs = db.recent_messages(conversation_id=conv["id"])
    assert msgs[0]["content"].startswith("[scheduled]")
    assert "42" in msgs[-1]["content"]


def test_task_failure_is_recorded_not_raised(tmp_path):
    db = Database(tmp_path / "t.db")
    reg = build_default_registry(tmp_path, db=db, enable_web=False)
    conv = db.create_conversation()
    task = db.create_task("anything", "30m", None, conv["id"])

    def exploding_provider(name):
        raise RuntimeError("provider on fire")

    err = run_task_once(task, db, reg, exploding_provider)
    assert err and "on fire" in err
    db.record_task_run(task["id"], time.time(), err)
    stored = db.list_tasks()[0]
    assert stored["last_error"] and stored["last_run_at"]


# ------------------------------------------------------------------ endpoints
def test_task_endpoints(client):
    r = client.post("/api/tasks", json={"prompt": "check things", "schedule": "1h"})
    assert r.status_code == 200
    tid = r.json()["id"]
    listed = client.get("/api/tasks").json()
    assert any(t["id"] == tid and "due" in t for t in listed)
    assert client.patch(f"/api/tasks/{tid}", json={"enabled": False}).status_code == 200
    assert client.delete(f"/api/tasks/{tid}").status_code == 200
    # bad schedule rejected with a usable message
    r = client.post("/api/tasks", json={"prompt": "x", "schedule": "whenever"})
    assert r.status_code == 400 and "30m" in r.json()["detail"]


def test_conversation_rename_endpoint(client):
    c = client.post("/api/conversations").json()
    r = client.patch(f"/api/conversations/{c['id']}", json={"title": "Renamed"})
    assert r.status_code == 200
    titles = {x["id"]: x["title"] for x in client.get("/api/conversations").json()}
    assert titles[c["id"]] == "Renamed"
