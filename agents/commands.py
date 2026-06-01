"""SuperClaude Slash Commands — CommandDispatcher with registration, role gating, hooks.

Issue: #265
Branch: fix/quick-note-265-superclaudecommands
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional


class CommandCategory(Enum):
    """Category grouping for discoverability and permission scoping."""

    SYSTEM = "system"
    AGENT = "agent"
    WORKFLOW = "workflow"
    UTILITY = "utility"
    ADMIN = "admin"


@dataclass
class Command:
    """A single slash command with metadata, handler, and lifecycle hooks."""

    name: str
    description: str
    category: CommandCategory = CommandCategory.UTILITY
    handler: Optional[Callable[[List[str]], str]] = None
    roles: List[str] = field(default_factory=list)
    enabled: bool = True
    pre_hook: Optional[Callable[[List[str]], Optional[str]]] = None
    post_hook: Optional[Callable[[List[str], str], str]] = None
    aliases: List[str] = field(default_factory=list)

    def execute(self, args: List[str]) -> str:
        """Execute the command, running pre/post hooks if configured."""
        if not self.enabled:
            return f"Command '{self.name}' is currently disabled."

        if self.pre_hook is not None:
            pre_result = self.pre_hook(args)
            if pre_result is not None:
                return pre_result

        if self.handler is None:
            return f"Command '{self.name}' has no handler registered."

        result = self.handler(args)

        if self.post_hook is not None:
            result = self.post_hook(args, result)

        return result


@dataclass
class CommandDispatcher:
    """Central dispatcher for slash commands with role-based access control."""

    _commands: Dict[str, Command] = field(default_factory=dict)
    _alias_map: Dict[str, str] = field(default_factory=dict)

    def register(self, command: Command) -> None:
        """Register a command and its aliases."""
        if command.name in self._commands:
            raise ValueError(f"Command '{command.name}' is already registered.")
        self._commands[command.name] = command
        for alias in command.aliases:
            if alias in self._alias_map:
                raise ValueError(f"Alias '{alias}' is already mapped.")
            self._alias_map[alias] = command.name

    def unregister(self, name: str) -> None:
        """Remove a command and its aliases from the dispatcher."""
        if name not in self._commands:
            raise KeyError(f"Command '{name}' is not registered.")
        cmd = self._commands.pop(name)
        for alias in cmd.aliases:
            self._alias_map.pop(alias, None)

    def enable(self, name: str) -> None:
        """Enable a command."""
        self._commands[name].enabled = True

    def disable(self, name: str) -> None:
        """Disable a command."""
        self._commands[name].enabled = False

    def resolve(self, input_name: str) -> Optional[str]:
        """Resolve an alias to its canonical command name."""
        if input_name in self._commands:
            return input_name
        return self._alias_map.get(input_name)

    def is_allowed(self, name: str, user_roles: List[str]) -> bool:
        """Check if a user's roles permit executing this command."""
        cmd = self._commands.get(name)
        if cmd is None:
            return False
        if not cmd.roles:
            return True
        return any(role in cmd.roles for role in user_roles)

    def dispatch(self, text: str, user_roles: Optional[List[str]] = None) -> str:
        """Parse and execute a slash command from raw text.

        Args:
            text: Raw command text, e.g. "/help agents"
            user_roles: Roles of the calling user for permission checks.

        Returns:
            Command output string.
        """
        if user_roles is None:
            user_roles = []

        if not text.startswith("/"):
            return f"Not a command: {text}"

        parts = text[1:].split()
        if not parts:
            return "No command specified."

        name = parts[0].lower()
        args = parts[1:]

        resolved = self.resolve(name)
        if resolved is None:
            return f"Unknown command: /{name}"

        if not self.is_allowed(resolved, user_roles):
            return f"Access denied for command '/{resolved}'."

        cmd = self._commands[resolved]
        return cmd.execute(args)

    def list_by_category(self, category: CommandCategory) -> List[Command]:
        """Return all enabled commands in a given category."""
        return [c for c in self._commands.values() if c.category == category and c.enabled]

    def list_all(self) -> List[Command]:
        """Return all registered commands."""
        return list(self._commands.values())

    @property
    def command_count(self) -> int:
        """Number of registered commands."""
        return len(self._commands)
