"""Built-in tools: notes (sandboxed filesystem), time, calculator, shell (opt-in).

Security notes
--------------
* notes_*: every path is resolved and verified to remain inside the
  configured data directory; path traversal ('../') is rejected.
* calculator: parsed with ast and evaluated against an operator allowlist —
  no eval()/exec().
* shell: DISABLED by default (AURELIA_ENABLE_SHELL_TOOL=true to enable),
  runs via subprocess with shell=False semantics (shlex split), a timeout,
  and no shell metacharacter interpretation.
"""
from __future__ import annotations

import ast
import datetime
import operator
import shlex
import subprocess
from pathlib import Path
from typing import Any

from .base import Tool, ToolRegistry

# ---------------------------------------------------------------- calculator
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_ALLOWED_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left, right = _safe_eval(node.left), _safe_eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(left) > 1e6 or abs(right) > 1e3):
            raise ValueError("exponent too large")
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARY:
        return _ALLOWED_UNARY[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Disallowed expression element: {type(node).__name__}")


def calculator(args: dict[str, Any]) -> str:
    expr = str(args.get("expression", "")).strip()
    if not expr:
        raise ValueError("Missing 'expression'")
    if len(expr) > 500:
        raise ValueError("Expression too long")
    result = _safe_eval(ast.parse(expr, mode="eval"))
    return str(result)


# ---------------------------------------------------------------------- time
def local_time(args: dict[str, Any]) -> str:
    fmt = str(args.get("format", "%Y-%m-%d %H:%M:%S %Z")).strip() or "%Y-%m-%d %H:%M:%S %Z"
    return datetime.datetime.now().astimezone().strftime(fmt)


# --------------------------------------------------------------------- notes
class NotesTool:
    """Filesystem notes scoped to <data_dir>/notes. Nothing outside it is touched."""

    def __init__(self, data_dir: str | Path):
        self.root = (Path(data_dir) / "notes").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_path(self, name: str) -> Path:
        if not name or any(c in name for c in ("\x00",)):
            raise ValueError("Invalid note name")
        p = (self.root / f"{name}.md").resolve()
        if self.root not in p.parents and p != self.root:
            raise PermissionError("Path escapes the notes sandbox")
        return p

    def write(self, args: dict[str, Any]) -> str:
        p = self._safe_path(str(args.get("name", "")))
        p.write_text(str(args.get("content", "")), encoding="utf-8")
        return f"Saved note '{p.stem}' ({p.stat().st_size} bytes)"

    def read(self, args: dict[str, Any]) -> str:
        p = self._safe_path(str(args.get("name", "")))
        if not p.exists():
            raise FileNotFoundError(f"Note '{p.stem}' not found")
        return p.read_text(encoding="utf-8")

    def list(self, args: dict[str, Any]) -> str:
        names = sorted(f.stem for f in self.root.glob("*.md"))
        return "\n".join(names) if names else "(no notes yet)"


# --------------------------------------------------------------------- shell
def make_shell_tool(enabled: bool) -> Tool:
    def run(args: dict[str, Any]) -> str:
        cmd = str(args.get("command", "")).strip()
        if not cmd:
            raise ValueError("Missing 'command'")
        # shlex.split + list-args subprocess: no shell interpretation at all.
        proc = subprocess.run(
            shlex.split(cmd), capture_output=True, text=True, timeout=15, check=False
        )
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        tail = "\n" + err if err else ""
        return f"exit={proc.returncode}\n{out}{tail}"

    return Tool(
        name="shell",
        description=(
            "Run a local command (no shell metacharacters). DISABLED by default; "
            "set AURELIA_ENABLE_SHELL_TOOL=true to enable. Use with care."
        ),
        handler=run,
        args_schema={"command": "string — command and arguments"},
        enabled=enabled,
    )


class MemoryTools:
    """Agent-facing handles on the durable memory store.

    Architectural decision: the model gets memory as *tools*, not magic —
    saves and searches go through the same Database (and the same FTS5
    index) as the UI's Memory panel, so anything the agent remembers is
    visible, searchable, and deletable by the user. No hidden state.
    """

    def __init__(self, db):
        self.db = db

    def save(self, args: dict[str, Any]) -> str:
        content = str(args.get("content", "")).strip()
        if not content:
            raise ValueError("memory.save requires non-empty 'content'")
        if len(content) > 2000:
            raise ValueError("memory content too long (max 2000 chars)")
        tags = args.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        mem = self.db.create_memory(content, [str(t) for t in tags][:8])
        return f"Saved to memory: \u201c{mem['content']}\u201d"

    def search(self, args: dict[str, Any]) -> str:
        query = str(args.get("query", "")).strip()
        if not query:
            raise ValueError("memory.search requires 'query'")
        hits = self.db.search_memories(query, limit=5, match_any=True)
        if not hits:
            return "No saved memories match that query."
        return "\n".join(f"- {h['content']}" for h in hits)


def build_default_registry(data_dir: str | Path, enable_shell: bool = False,
                           db=None) -> ToolRegistry:
    reg = ToolRegistry()
    notes = NotesTool(data_dir)
    reg.register(Tool("calculator", "Evaluate an arithmetic expression safely.",
                      calculator, {"expression": "string — e.g. '2*(3+4)'"}))
    reg.register(Tool("time", "Current local date/time.", local_time,
                      {"format": "optional strftime format"}))
    reg.register(Tool("notes.write", "Save a markdown note in the sandboxed data dir.",
                      notes.write, {"name": "string", "content": "string"}))
    reg.register(Tool("notes.read", "Read a saved note.", notes.read, {"name": "string"}))
    reg.register(Tool("notes.list", "List saved notes.", notes.list, {}))
    if db is not None:
        mem = MemoryTools(db)
        reg.register(Tool(
            "memory.save",
            "Save a durable fact about the user for future conversations. "
            "Use ONLY when the user explicitly asks to remember/save something.",
            mem.save, {"content": "string", "tags": "string (comma-separated, optional)"}))
        reg.register(Tool(
            "memory.search",
            "Search the user's saved long-term memories.",
            mem.search, {"query": "string"}))
    reg.register(make_shell_tool(enabled=enable_shell))
    return reg
