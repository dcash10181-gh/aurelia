"""Background tasks: simple schedules, agent-executed, results in chat.

Architectural decisions:
* Schedules are deliberately minimal — "30m" / "2h" intervals or
  "daily HH:MM". Cron syntax is power nobody asked for and a parser
  liability; these two forms cover "summarize HN every morning" and
  "check X every hour", which is the actual use case.
* Each task owns a conversation. Results land there as ordinary
  user/assistant messages, so the existing UI (switcher, transcripts,
  tool steps in meta) is the task inbox — no parallel notification
  system to build or maintain.
* The runner is a single asyncio loop, tasks execute sequentially in a
  worker thread (the agent stack is sync). One slow task delays others;
  it cannot overlap or pile up.
* A task failure is recorded on the task row and never raises out of
  the loop. The scheduler must survive anything a task does.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import time
from typing import Any

from starlette.concurrency import run_in_threadpool

log = logging.getLogger("aurelia.tasks")

CHECK_INTERVAL_S = 20


def parse_schedule(text: str) -> dict[str, Any]:
    """'30m' / '2h' -> interval seconds; 'daily 08:00' -> daily time.
    Raises ValueError with a human-usable message on anything else."""
    t = text.strip().lower()
    if t.startswith("daily"):
        try:
            hh, mm = t.split()[1].split(":")
            hour, minute = int(hh), int(mm)
            assert 0 <= hour < 24 and 0 <= minute < 60
        except Exception:
            raise ValueError("Daily schedule must look like 'daily 08:00'") from None
        return {"kind": "daily", "hour": hour, "minute": minute}
    if t.endswith("m") and t[:-1].isdigit():
        mins = int(t[:-1])
        if mins < 5:
            raise ValueError("Minimum interval is 5m")
        return {"kind": "interval", "seconds": mins * 60}
    if t.endswith("h") and t[:-1].isdigit():
        return {"kind": "interval", "seconds": int(t[:-1]) * 3600}
    raise ValueError("Schedule must be like '30m', '2h', or 'daily 08:00'")


def is_due(task: dict[str, Any], now: float | None = None) -> bool:
    if not task.get("enabled"):
        return False
    now = now if now is not None else time.time()
    sched = parse_schedule(task["schedule"])
    last = task.get("last_run_at")
    if sched["kind"] == "interval":
        return last is None or now - last >= sched["seconds"]
    # daily: due if today's HH:MM has passed and we haven't run since then
    local_now = datetime.datetime.fromtimestamp(now)
    today_at = local_now.replace(hour=sched["hour"], minute=sched["minute"],
                                 second=0, microsecond=0).timestamp()
    if now < today_at:
        return False
    return last is None or last < today_at


def run_task_once(task: dict[str, Any], db, registry, get_provider) -> str | None:
    """Execute one task synchronously. Returns an error string or None.
    Results are persisted into the task's conversation like a normal turn."""
    from ..agent.loop import run_agent_turn
    try:
        provider = get_provider(task.get("provider"))
        conv = task["conversation_id"]
        history = [{"role": m["role"], "content": m["content"]}
                   for m in db.recent_messages(limit=12, conversation_id=conv)]
        db.add_message("user", f"[scheduled] {task['prompt']}", conv)
        result = run_agent_turn(task["prompt"], provider, registry, db, history)
        db.add_message("assistant", result["reply"], conv)
        return None
    except Exception as e:  # noqa: BLE001 — scheduler must survive anything
        log.warning("task %s failed: %s", task["id"], e)
        return str(e)[:500]


async def task_loop(db, registry, get_provider):
    """Forever: find due tasks, run them sequentially off the event loop."""
    log.info("background task loop started")
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL_S)
            for task in db.list_tasks():
                if not is_due(task):
                    continue
                started = time.time()
                err = await run_in_threadpool(
                    run_task_once, task, db, registry, get_provider)
                db.record_task_run(task["id"], started, err)
        except asyncio.CancelledError:
            log.info("background task loop stopped")
            return
        except Exception as e:  # noqa: BLE001
            log.warning("task loop iteration failed: %s", e)
