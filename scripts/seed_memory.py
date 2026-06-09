"""Seed the local memory store with example entries (idempotent-ish demo)."""
from aurelia_api.config import settings
from aurelia_api.storage.db import Database

SEEDS = [
    ("AURELIA runs entirely locally; nothing leaves this machine.", ["meta"]),
    ("The shell tool is disabled by default for safety.", ["security"]),
    ("Press Cmd/Ctrl+K in the UI for the command palette.", ["ui"]),
]

db = Database(settings.db_path)
existing = {m["content"] for m in db.list_memories(500)}
for content, tags in SEEDS:
    if content not in existing:
        db.create_memory(content, tags)
        print("seeded:", content)
print("done.")
