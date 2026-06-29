"""packages/tools/__init__.py — Unified Tool Platform.

Every capability is a reusable tool. Agents discover tools via the registry.
"""
from packages.tools.base import Tool, ToolResult, ToolSchema
from packages.tools.registry import ToolRegistry, get_tool_registry

__all__ = ["Tool", "ToolResult", "ToolSchema", "ToolRegistry", "get_tool_registry"]
