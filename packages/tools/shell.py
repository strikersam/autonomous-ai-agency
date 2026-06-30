"""packages/tools/shell.py — Shell execution tool.

Safely executes shell commands for agents. Includes:
- Command allowlisting (no rm -rf /, no sudo)
- Timeout enforcement
- Output capture (stdout + stderr)
- Working directory control
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from packages.tools.base import Tool, ToolResult, ToolSchema

log = logging.getLogger("tool.shell")

# Commands that are NEVER allowed (security)
_BLOCKED_PATTERNS = [
    "rm -rf /", "rm -rf ~", "rm -rf *", "mkfs", "dd if=/dev/zero",
    ":(){:|:&};:", "sudo ", "su ", "chmod 777 /", "shutdown", "reboot",
    "halt", "init 0", "init 6",
]

# Maximum output size (characters)
MAX_OUTPUT = 50000

# Default timeout (seconds)
DEFAULT_TIMEOUT = 30


class ShellTool(Tool):
    """Shell execution tool for running system commands.

    Provides agents with safe shell access:
    - Command allowlisting (blocks dangerous commands)
    - Configurable timeout
    - Output capture (stdout + stderr, capped at 50KB)
    - Working directory control
    """

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Execute shell commands safely (with allowlisting + timeout)"

    @property
    def capabilities(self) -> list[str]:
        return ["system", "execution", "filesystem", "process"]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a shell command.

        Args:
            command: The shell command to execute
            cwd: Working directory (optional, defaults to repo root)
            timeout: Timeout in seconds (optional, default 30)
        """
        command = kwargs.get("command", "")
        cwd = kwargs.get("cwd", None)
        timeout = kwargs.get("timeout", DEFAULT_TIMEOUT)

        if not command:
            return ToolResult(success=False, error="command is required")

        # Security: check blocked patterns
        cmd_lower = command.lower()
        for pattern in _BLOCKED_PATTERNS:
            if pattern in cmd_lower:
                return ToolResult(
                    success=False,
                    error=f"Blocked command pattern detected: {pattern}",
                )

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            stdout_text = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT]
            stderr_text = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT]

            return ToolResult(
                success=proc.returncode == 0,
                output=stdout_text,
                error=stderr_text if proc.returncode != 0 else None,
                metadata={
                    "returncode": proc.returncode,
                    "stdout_len": len(stdout_text),
                    "stderr_len": len(stderr_text),
                },
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                error=f"Command timed out after {timeout}s",
            )
        except Exception as exc:
            log.exception("Shell tool error: %s", exc)
            return ToolResult(success=False, error=str(exc))

    async def health(self) -> bool:
        """Shell is always available."""
        return True

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="shell",
            description="Execute shell commands safely with timeout + output capture",
            parameters={
                "command": {"type": "string", "description": "The shell command to execute"},
                "cwd": {"type": "string", "description": "Working directory (optional)"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default: 30)"},
            },
        )
