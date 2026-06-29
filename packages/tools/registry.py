"""packages/tools/registry.py — Tool registry + capability discovery.

Central registry where tools are registered and discovered by agents.
Supports:
  - Registration by name + capability tags
  - Capability-based search (find tools that can do 'web' or 'code')
  - Batch execution with error isolation
  - Health checking for all registered tools
"""
from __future__ import annotations

import logging
from typing import Any

from packages.tools.base import Tool, ToolResult, ToolSchema

log = logging.getLogger("tool-registry")


class ToolRegistry:
    """Central registry for all platform tools.

    Every agent, runtime, and workflow uses this registry to discover and
    execute tools. No tool is hardcoded inside individual agents — they all
    go through the registry.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._by_capability: dict[str, list[str]] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool. Overwrites if name already exists."""
        name = tool.name
        self._tools[name] = tool
        for cap in tool.capabilities:
            self._by_capability.setdefault(cap, []).append(name)
        log.info("Tool registered: %s (capabilities: %s)", name, tool.capabilities)

    def unregister(self, name: str) -> None:
        """Remove a tool from the registry."""
        tool = self._tools.pop(name, None)
        if tool:
            for cap in tool.capabilities:
                if cap in self._by_capability:
                    self._by_capability[cap] = [
                        n for n in self._by_capability[cap] if n != name
                    ]

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def all_tools(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def find_by_capability(self, capability: str) -> list[Tool]:
        """Find all tools that have a given capability tag."""
        names = self._by_capability.get(capability, [])
        return [self._tools[n] for n in names if n in self._tools]

    def find(self, query: str) -> list[Tool]:
        """Search tools by name or description (case-insensitive substring)."""
        query = query.lower()
        return [
            t for t in self._tools.values()
            if query in t.name.lower() or query in t.description.lower()
        ]

    async def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name. Returns ToolResult."""
        tool = self._tools.get(tool_name)
        if tool is None:
            return ToolResult(success=False, error=f"Tool '{tool_name}' not found")
        try:
            return await tool.execute(**kwargs)
        except Exception as exc:
            log.exception("Tool %s execution failed", tool_name)
            return ToolResult(success=False, error=str(exc))

    async def execute_batch(
        self, calls: list[dict[str, Any]]
    ) -> list[ToolResult]:
        """Execute multiple tool calls. Errors in one don't affect others.

        Args:
            calls: List of {"tool": "name", "kwargs": {...}}
        """
        import asyncio

        async def _safe_call(call: dict) -> ToolResult:
            tool_name = call.get("tool", "")
            kwargs = call.get("kwargs", {})
            return await self.execute(tool_name, **kwargs)

        return await asyncio.gather(*[_safe_call(c) for c in calls])

    async def health_all(self) -> dict[str, bool]:
        """Check health of all registered tools."""
        import asyncio

        async def _check(tool: Tool) -> tuple[str, bool]:
            try:
                return tool.name, await tool.health()
            except Exception:
                return tool.name, False

        results = await asyncio.gather(*[_check(t) for t in self._tools.values()])
        return dict(results)

    def to_openai_functions(self) -> list[dict[str, Any]]:
        """Convert all tools to OpenAI function-calling format."""
        return [t.to_openai_function() for t in self._tools.values()]

    def schemas(self) -> list[ToolSchema]:
        """Return schemas for all registered tools."""
        return [t.schema() for t in self._tools.values()]


# Singleton
_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return the global tool registry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry
