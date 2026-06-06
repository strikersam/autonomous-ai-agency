from __future__ import annotations

"""Agent Capability Registry + Dynamic Tool Discovery (A3 roadmap item).

Replaces hardcoded tool lists with a registry where agents advertise
capabilities, tools are auto-discovered via decorators, and capabilities
are negotiated at session start.

Features:
- @agent_tool decorator for auto-registration with JSON schema
- ToolRegistry: register, lookup, search by capability
- Hot-reload: refresh tools without restarting the server
- Capability negotiation: agents declare what they can do at session start
"""

import functools
import importlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("qwen-proxy")


# ── Tool Definition ────────────────────────────────────────────────────────────


class ToolDef:
    """Definition of a registered agent tool."""

    def __init__(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., Any],
        capabilities: list[str] | None = None,
        version: str = "1.0.0",
        cost_tier: int = 1,
        source: str = "decorator",
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler
        self.capabilities = capabilities or []
        self.version = version
        self.cost_tier = cost_tier
        self.source = source

    def to_openai_tool(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "capabilities": self.capabilities,
            "version": self.version,
            "cost_tier": self.cost_tier,
            "source": self.source,
        }


# ── Tool Registry ──────────────────────────────────────────────────────────────


class ToolRegistry:
    """Central registry for agent tools with capability-based discovery.

    Tools are registered via the ``@agent_tool`` decorator or the
    ``register()`` method.  Agents query the registry at session start
    to discover available tools matching their capabilities.

    Usage::

        registry = ToolRegistry()

        @registry.agent_tool(
            name="read_file",
            description="Read a file's contents",
            parameters={"type": "object", "properties": {"path": {"type": "string"}}},
            capabilities=["filesystem", "read"],
        )
        async def read_file(path: str) -> str: ...

        # Discover tools with specific capability
        tools = registry.find_by_capability("filesystem")
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}
        self._by_capability: dict[str, list[str]] = {}  # capability → tool names
        self._loaded_modules: set[str] = set()
        self._last_refresh: float = 0.0

    # ── Registration ────────────────────────────────────────────────────────

    def register(self, tool: ToolDef) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool
        for cap in tool.capabilities:
            if cap not in self._by_capability:
                self._by_capability[cap] = []
            if tool.name not in self._by_capability[cap]:
                self._by_capability[cap].append(tool.name)
        log.debug("Registered tool %s (capabilities: %s)", tool.name, tool.capabilities)

    def agent_tool(
        self,
        *,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
        capabilities: list[str] | None = None,
        version: str = "1.0.0",
        cost_tier: int = 1,
    ) -> Callable:
        """Decorator to register a function as an agent tool.

        Usage::

            @registry.agent_tool(
                name="read_file",
                description="Read a file's contents",
                parameters={"type": "object", "properties": {"path": {"type": "string"}}},
                capabilities=["filesystem"],
            )
            async def read_file(path: str) -> str: ...

        The decorated function is auto-registered and can be discovered
        by other agents via the registry.
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            params = parameters or _infer_parameters_from_func(func)
            tool = ToolDef(
                name=name,
                description=description,
                parameters=params,
                handler=func,
                capabilities=capabilities or [],
                version=version,
                cost_tier=cost_tier,
                source="decorator",
            )
            self.register(tool)

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry. Returns True if removed."""
        tool = self._tools.pop(name, None)
        if tool is None:
            return False
        for cap in tool.capabilities:
            names = self._by_capability.get(cap, [])
            if name in names:
                names.remove(name)
            if not names:
                self._by_capability.pop(cap, None)
        log.debug("Unregistered tool %s", name)
        return True

    # ── Discovery ────────────────────────────────────────────────────────────

    def get(self, name: str) -> ToolDef | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_all(self) -> list[ToolDef]:
        """Return all registered tools."""
        return list(self._tools.values())

    def find_by_capability(self, capability: str) -> list[ToolDef]:
        """Find tools that advertise a specific capability."""
        names = self._by_capability.get(capability, [])
        return [self._tools[n] for n in names if n in self._tools]

    def find_by_capabilities(self, capabilities: list[str]) -> list[ToolDef]:
        """Find tools matching any of the given capabilities."""
        seen: set[str] = set()
        result: list[ToolDef] = []
        for cap in capabilities:
            for name in self._by_capability.get(cap, []):
                if name not in seen:
                    seen.add(name)
                    tool = self._tools.get(name)
                    if tool:
                        result.append(tool)
        return result

    def search(self, query: str) -> list[ToolDef]:
        """Search tools by name or description (case-insensitive substring)."""
        q = query.lower()
        return [
            t for t in self._tools.values()
            if q in t.name.lower() or q in t.description.lower()
        ]

    def capabilities(self) -> list[str]:
        """Return all known capability tags."""
        return sorted(self._by_capability.keys())

    def to_openai_tools(
        self,
        capabilities: list[str] | None = None,
        names: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Export tools as OpenAI-compatible tool definitions.

        Args:
            capabilities: If set, only include tools matching these capabilities.
            names: If set, only include these named tools.
        """
        tools = self.list_all()
        if capabilities:
            tools = self.find_by_capabilities(capabilities)
        if names:
            tools = [t for t in tools if t.name in set(names)]
        return [t.to_openai_tool() for t in tools]

    # ── Auto-discovery ───────────────────────────────────────────────────────

    def discover_module(self, module_path: str) -> int:
        """Discover tools from a Python module by importing it.

        Any ``@agent_tool``-decorated functions in the module are
        auto-registered when the module is imported.

        Returns the number of newly discovered tools.
        """
        if module_path in self._loaded_modules:
            return 0
        before = len(self._tools)
        try:
            importlib.import_module(module_path)
        except Exception as exc:
            log.warning("Could not discover tools from %s: %s", module_path, exc)
            return 0
        self._loaded_modules.add(module_path)
        return len(self._tools) - before

    def discover_directory(self, directory: str | Path) -> int:
        """Discover tools from all .py files in a directory.

        Skips __init__.py and files starting with _.
        The parent of *directory* is added to ``sys.path`` so modules can
        be imported by their directory-relative names.
        """
        import sys
        import time
        dir_path = Path(directory).resolve()
        if not dir_path.is_dir():
            log.warning("Tool discovery directory not found: %s", directory)
            return 0

        # Ensure the parent is on sys.path so importlib can find the modules
        parent = str(dir_path.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)

        count = 0
        for py_file in sorted(dir_path.glob("*.py")):
            if py_file.name.startswith("_") or py_file.name == "__init__.py":
                continue
            module_name = py_file.stem
            # Build a module path relative to the directory
            mod_path = f"{dir_path.name}.{module_name}"
            count += self.discover_module(mod_path)

        self._last_refresh = time.time()
        return count

    def hot_reload(self) -> int:
        """Refresh the tool registry by re-discovering all loaded modules.

        Returns the net change in tool count.
        """
        before = len(self._tools)
        loaded = list(self._loaded_modules)
        self._loaded_modules.clear()
        for mod_path in loaded:
            self.discover_module(mod_path)
        after = len(self._tools)
        return after - before

    # ── Capability negotiation ───────────────────────────────────────────────

    def negotiate(
        self,
        requested_capabilities: list[str],
    ) -> dict[str, Any]:
        """Negotiate available tools for a set of requested capabilities.

        Returns a dict with matched tools and any gaps.
        """
        matched = self.find_by_capabilities(requested_capabilities)
        found_caps = set()
        for t in matched:
            found_caps.update(t.capabilities)
        missing = [c for c in requested_capabilities if c not in found_caps]
        return {
            "matched_tools": [t.to_dict() for t in matched],
            "matched_count": len(matched),
            "missing_capabilities": missing,
            "all_capabilities": self.capabilities(),
        }


# ── Helpers ────────────────────────────────────────────────────────────────────


def _infer_parameters_from_func(func: Callable) -> dict[str, Any]:
    """Infer a basic JSON Schema from a function's signature."""
    import inspect
    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return {"type": "object", "properties": {}}
    props: dict[str, Any] = {}
    required: list[str] = []
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        param_type = "string"
        if param.annotation is not inspect.Parameter.empty:
            annotation = param.annotation
            # Handle from __future__ import annotations (string annotations)
            if isinstance(annotation, str):
                annotation_str = annotation
            elif hasattr(annotation, "__name__"):
                annotation_str = annotation.__name__
            else:
                annotation_str = str(annotation)
            if annotation_str in ("int", "integer"):
                param_type = "integer"
            elif annotation_str in ("float", "number"):
                param_type = "number"
            elif annotation_str in ("bool", "boolean"):
                param_type = "boolean"
            elif annotation_str in ("list", "array"):
                param_type = "array"
        props[param_name] = {"type": param_type, "description": f"Parameter: {param_name}"}
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    schema: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


# ── Module-level singleton ─────────────────────────────────────────────────────

_tool_registry: ToolRegistry | None = None


def get_tool_registry(workspace_root: str | None = None) -> ToolRegistry:
    """Return the module-level ToolRegistry singleton.

    On first call, registers built-in tools.  Pass ``workspace_root`` to
    set the workspace directory for filesystem tools (default: ``.``).
    """
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
        _register_builtin_tools(_tool_registry, workspace_root)
    return _tool_registry


def _register_builtin_tools(registry: ToolRegistry, workspace_root: str | None = None) -> None:
    """Register the built-in agent tools that are always available."""
    from agent.tools import WorkspaceTools

    ws = WorkspaceTools(workspace_root or os.environ.get("AGENT_WORKSPACE_ROOT", "."))

    @registry.agent_tool(
        name="read_file",
        description="Read the contents of a file in the workspace",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
            },
            "required": ["path"],
        },
        capabilities=["filesystem", "read"],
    )
    def _read_file_tool(path: str) -> str:
        return ws.read_file(path)

    @registry.agent_tool(
        name="write_file",
        description="Write content to a file in the workspace",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
        capabilities=["filesystem", "write"],
    )
    def _write_file_tool(path: str, content: str) -> str:
        return ws.write_file(path, content)

    @registry.agent_tool(
        name="search_code",
        description="Search for patterns in the codebase",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 20},
            },
            "required": ["query"],
        },
        capabilities=["code", "search"],
    )
    def _search_code_tool(query: str, limit: int = 20) -> list:
        return ws.search_code(query, limit)

    @registry.agent_tool(
        name="list_files",
        description="List files in a directory",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path", "default": "."},
                "limit": {"type": "integer", "description": "Max entries", "default": 200},
            },
            "required": [],
        },
        capabilities=["filesystem", "read"],
    )
    def _list_files_tool(path: str = ".", limit: int = 200) -> list:
        return ws.list_files(path, limit)

    @registry.agent_tool(
        name="apply_diff",
        description="Apply a diff to a file in the workspace",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path to the file"},
                "new_content": {"type": "string", "description": "Full new file content"},
            },
            "required": ["path", "new_content"],
        },
        capabilities=["filesystem", "write", "edit"],
    )
    def _apply_diff_tool(path: str, new_content: str) -> dict:
        return ws.apply_diff(path, new_content)

    @registry.agent_tool(
        name="finish",
        description="Signal completion of the current step",
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why the step is complete"},
            },
            "required": ["reason"],
        },
        capabilities=["control"],
    )
    def _finish_tool(reason: str) -> str:
        return reason
