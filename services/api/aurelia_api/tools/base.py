"""Tool/plugin architecture.

A Tool is a named callable with a JSON-ish argument dict and a string result.
The registry is the single integration point: the agent loop, the /tools API
and the CLI all consume the same registry, so adding a plugin in one place
exposes it everywhere. See docs/plugin_api.md.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    handler: Callable[[dict[str, Any]], str]
    # Schema is advisory documentation for UIs/LLMs, not enforced validation.
    args_schema: dict[str, str] = field(default_factory=dict)
    enabled: bool = True

    def invoke(self, args: dict[str, Any]) -> str:
        if not self.enabled:
            raise PermissionError(f"Tool '{self.name}' is disabled by configuration.")
        return self.handler(args)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise KeyError(f"Unknown tool '{name}'")
        return self._tools[name]

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "args": t.args_schema,
                "enabled": t.enabled,
            }
            for t in self._tools.values()
        ]

    def invoke(self, name: str, args: dict[str, Any]) -> str:
        return self.get(name).invoke(args)
