"""packages/tools/base.py — Abstract Tool interface.

Every capability (browser, github, shell, search, memory, etc.) implements
this interface. Tools are registered in the ToolRegistry and discovered by
agents via capability search.

Design inspired by anywhere-agents (agent capability discovery) and
browser-harness (tool invocation patterns), but implemented natively
using the existing packages/ architecture.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    output: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: int = 0


@dataclass
class ToolSchema:
    """Schema describing a tool's interface for LLM function-calling."""
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)
    returns: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    """Abstract base class for all platform tools.

    Every capability (browser automation, GitHub operations, shell execution,
    web search, memory operations, etc.) implements this interface. Tools are
    registered in ToolRegistry and discovered by agents via capability search.

    Usage:
        class BrowserTool(Tool):
            @property
            def name(self) -> str:
                return "browser"

            async def execute(self, action: str, **kwargs) -> ToolResult:
                ...

        registry.register(BrowserTool())
        result = await registry.execute("browser", action="navigate", url="...")
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name (e.g. 'browser', 'github', 'shell')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""
        ...

    @property
    def capabilities(self) -> list[str]:
        """List of capability tags (e.g. ['web', 'navigation', 'extraction'])."""
        return []

    @property
    def requires_auth(self) -> bool:
        """Whether this tool requires authentication."""
        return False

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with the given parameters.

        Returns a ToolResult with success/failure + output.
        """
        ...

    @abstractmethod
    def schema(self) -> ToolSchema:
        """Return the tool's schema for LLM function-calling."""
        ...

    async def health(self) -> bool:
        """Check if the tool is healthy and ready to use."""
        return True

    def to_openai_function(self) -> dict[str, Any]:
        """Convert to OpenAI function-calling format."""
        s = self.schema()
        return {
            "name": s.name,
            "description": s.description,
            "parameters": {
                "type": "object",
                "properties": s.parameters,
            },
        }
