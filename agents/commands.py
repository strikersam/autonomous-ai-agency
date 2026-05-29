"""
SuperClaude Slash Commands Integration

Inspired by SuperClaude Framework's 30+ slash commands pattern.
Implements a dispatcher system for agent commands like:
- /plan, /implement, /test, /review, /document
- /task, /spawn, /workflow, /design, /analyze
- /research, /troubleshoot, /improve, /cleanup
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional

log = logging.getLogger("slash_commands")


class CommandCategory(str, Enum):
    """Command categories inspired by SuperClaude"""

    PLANNING = "planning"  # /plan, /brainstorm, /design
    EXECUTION = "execution"  # /implement, /task, /spawn
    TESTING = "testing"  # /test, /analyze, /troubleshoot
    IMPROVEMENT = "improvement"  # /improve, /refactor, /cleanup
    DOCUMENTATION = "documentation"  # /document, /explain, /comment
    OPERATIONS = "operations"  # /build, /deploy, /git
    REVIEW = "review"  # /review, /spec-panel, /business-panel
    RESEARCH = "research"  # /research, /analyze-market


@dataclass
class Command:
    """A slash command definition"""

    name: str  # e.g., "plan"
    category: CommandCategory
    description: str
    usage: str  # e.g., "/plan {task} {context}"
    handler: Callable  # Function to execute
    aliases: list[str] = None  # Alternative names


class CommandDispatcher:
    """
    Dispatch slash commands to handlers.

    Modeled after SuperClaude's 30-command system, simplified for local-llm-server.
    """

    def __init__(self):
        self.commands: dict[str, Command] = {}
        self._register_builtin_commands()

    def _register_builtin_commands(self):
        """Register built-in commands inspired by SuperClaude"""

        # Planning commands
        self.register(
            Command(
                name="plan",
                category=CommandCategory.PLANNING,
                description="Create an implementation plan with structured steps",
                usage="/plan <goal> [context]",
                handler=self._cmd_plan,
                aliases=["design", "architecture"],
            )
        )

        self.register(
            Command(
                name="task",
                category=CommandCategory.EXECUTION,
                description="Create and track a discrete task",
                usage="/task <title> [description]",
                handler=self._cmd_task,
                aliases=["todo", "work"],
            )
        )

        self.register(
            Command(
                name="implement",
                category=CommandCategory.EXECUTION,
                description="Execute implementation of a feature or fix",
                usage="/implement <spec> [files]",
                handler=self._cmd_implement,
                aliases=["exec", "build"],
            )
        )

        self.register(
            Command(
                name="test",
                category=CommandCategory.TESTING,
                description="Write or run tests",
                usage="/test [test_type]",
                handler=self._cmd_test,
                aliases=["validate", "verify"],
            )
        )

        self.register(
            Command(
                name="review",
                category=CommandCategory.REVIEW,
                description="Code review with structured feedback",
                usage="/review [files]",
                handler=self._cmd_review,
                aliases=["audit", "inspect"],
            )
        )

        self.register(
            Command(
                name="document",
                category=CommandCategory.DOCUMENTATION,
                description="Generate documentation or comments",
                usage="/document [target]",
                handler=self._cmd_document,
                aliases=["doc", "explain"],
            )
        )

        self.register(
            Command(
                name="research",
                category=CommandCategory.RESEARCH,
                description="Research a topic or codebase area",
                usage="/research <topic> [depth]",
                handler=self._cmd_research,
                aliases=["investigate", "analyze"],
            )
        )

        self.register(
            Command(
                name="troubleshoot",
                category=CommandCategory.TESTING,
                description="Diagnose and fix an issue",
                usage="/troubleshoot [symptom]",
                handler=self._cmd_troubleshoot,
                aliases=["debug", "fix"],
            )
        )

    def register(self, command: Command):
        """Register a command"""
        self.commands[command.name] = command
        if command.aliases:
            for alias in command.aliases:
                self.commands[alias] = command
        log.debug(f"Registered command: /{command.name}")

    def dispatch(self, command_line: str, context: Optional[dict] = None) -> Any:
        """Dispatch a slash command"""
        if not command_line.startswith("/"):
            return None

        parts = command_line.split(maxsplit=1)
        command_name = parts[0][1:]  # Remove leading /
        args = parts[1] if len(parts) > 1 else ""

        if command_name not in self.commands:
            log.warning(f"Unknown command: /{command_name}")
            return {"error": f"Unknown command: /{command_name}"}

        command = self.commands[command_name]
        return command.handler(args, context or {})

    def list_commands(self, category: Optional[CommandCategory] = None) -> list[dict]:
        """List available commands"""
        commands = []
        seen = set()

        for name, cmd in self.commands.items():
            if cmd.name in seen:
                continue
            if category and cmd.category != category:
                continue

            seen.add(cmd.name)
            commands.append(
                {
                    "name": cmd.name,
                    "category": cmd.category.value,
                    "description": cmd.description,
                    "usage": cmd.usage,
                    "aliases": cmd.aliases or [],
                }
            )

        return sorted(commands, key=lambda c: c["name"])

    # Command handlers
    def _cmd_plan(self, args: str, context: dict) -> dict:
        """Handle /plan command"""
        return {
            "command": "plan",
            "goal": args,
            "status": "creating_plan",
            "context": context,
        }

    def _cmd_task(self, args: str, context: dict) -> dict:
        """Handle /task command"""
        return {"command": "task", "title": args, "status": "created"}

    def _cmd_implement(self, args: str, context: dict) -> dict:
        """Handle /implement command"""
        return {"command": "implement", "spec": args, "status": "executing"}

    def _cmd_test(self, args: str, context: dict) -> dict:
        """Handle /test command"""
        return {"command": "test", "type": args or "auto", "status": "running"}

    def _cmd_review(self, args: str, context: dict) -> dict:
        """Handle /review command"""
        return {"command": "review", "target": args, "status": "reviewing"}

    def _cmd_document(self, args: str, context: dict) -> dict:
        """Handle /document command"""
        return {"command": "document", "target": args, "status": "generating"}

    def _cmd_research(self, args: str, context: dict) -> dict:
        """Handle /research command"""
        return {"command": "research", "topic": args, "status": "searching"}

    def _cmd_troubleshoot(self, args: str, context: dict) -> dict:
        """Handle /troubleshoot command"""
        return {"command": "troubleshoot", "symptom": args, "status": "diagnosing"}


# Singleton instance
_dispatcher = None


def get_dispatcher() -> CommandDispatcher:
    """Get or create command dispatcher"""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = CommandDispatcher()
    return _dispatcher
