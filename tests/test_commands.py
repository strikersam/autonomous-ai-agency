"""Tests for agents/commands.py — SuperClaude Slash Commands.

Uses importlib to load the module directly, bypassing agents/__init__.py deps.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    path = Path(__file__).parent.parent / "agents" / "commands.py"
    spec = importlib.util.spec_from_file_location("commands", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["commands"] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()
CommandDispatcher = mod.CommandDispatcher
Command = mod.Command
CommandCategory = mod.CommandCategory


class TestCommand:
    """Tests for the Command dataclass."""

    def test_create_command(self):
        cmd = Command(name="test", description="A test command")
        assert cmd.name == "test"
        assert cmd.description == "A test command"
        assert cmd.category == CommandCategory.UTILITY
        assert cmd.enabled is True

    def test_execute_disabled(self):
        cmd = Command(name="test", description="test", enabled=False)
        result = cmd.execute([])
        assert "disabled" in result.lower()

    def test_execute_no_handler(self):
        cmd = Command(name="test", description="test")
        result = cmd.execute([])
        assert "no handler" in result.lower()

    def test_execute_with_handler(self):
        cmd = Command(
            name="test",
            description="test",
            handler=lambda args: f"Got {len(args)} args",
        )
        assert cmd.execute(["a", "b"]) == "Got 2 args"

    def test_execute_with_roles(self):
        cmd = Command(
            name="admin_cmd",
            description="test",
            handler=lambda args: "ok",
            roles=["admin"],
        )
        assert cmd.execute([]) == "ok"

    def test_pre_hook_short_circuits(self):
        cmd = Command(
            name="test",
            description="test",
            handler=lambda args: "handler",
            pre_hook=lambda args: "blocked",
        )
        assert cmd.execute([]) == "blocked"

    def test_pre_hook_allows(self):
        cmd = Command(
            name="test",
            description="test",
            handler=lambda args: "handler",
            pre_hook=lambda args: None,
        )
        assert cmd.execute([]) == "handler"

    def test_post_hook_transforms(self):
        cmd = Command(
            name="test",
            description="test",
            handler=lambda args: "raw",
            post_hook=lambda args, result: f"[{result}]",
        )
        assert cmd.execute([]) == "[raw]"

    def test_aliases_stored(self):
        cmd = Command(
            name="greet",
            description="test",
            aliases=["hello", "hi"],
        )
        assert "hello" in cmd.aliases
        assert "hi" in cmd.aliases


class TestCommandDispatcher:
    """Tests for the CommandDispatcher."""

    def test_register_and_resolve(self):
        d = CommandDispatcher()
        cmd = Command(name="test", description="test")
        d.register(cmd)
        assert d.resolve("test") == "test"
        assert d.command_count == 1

    def test_register_duplicate_raises(self):
        d = CommandDispatcher()
        d.register(Command(name="test", description="test"))
        try:
            d.register(Command(name="test", description="dup"))
            assert False, "Expected ValueError"
        except ValueError:
            pass

    def test_alias_resolution(self):
        d = CommandDispatcher()
        d.register(Command(name="greet", description="test", aliases=["hello"]))
        assert d.resolve("hello") == "greet"

    def test_unregister(self):
        d = CommandDispatcher()
        d.register(Command(name="test", description="test",
                          aliases=["t"]))
        d.unregister("test")
        assert d.resolve("test") is None
        assert d.resolve("t") is None
        assert d.command_count == 0

    def test_unregister_missing_raises(self):
        d = CommandDispatcher()
        try:
            d.unregister("nope")
            assert False, "Expected KeyError"
        except KeyError:
            pass

    def test_enable_disable(self):
        d = CommandDispatcher()
        d.register(Command(name="test", description="test",
                          handler=lambda args: "ok"))
        d.disable("test")
        result = d.dispatch("/test", [])
        assert "disabled" in result.lower()
        d.enable("test")
        assert d.dispatch("/test", []) == "ok"

    def test_dispatch_unknown(self):
        d = CommandDispatcher()
        result = d.dispatch("/nope", [])
        assert "unknown" in result.lower()

    def test_dispatch_role_gated(self):
        d = CommandDispatcher()
        d.register(Command(
            name="admin", description="test",
            handler=lambda args: "ok", roles=["admin"],
        ))
        assert "denied" in d.dispatch("/admin", []).lower()
        assert d.dispatch("/admin", ["admin"]) == "ok"

    def test_dispatch_no_roles_always_ok(self):
        d = CommandDispatcher()
        d.register(Command(
            name="help", description="test",
            handler=lambda args: "help text",
        ))
        assert d.dispatch("/help", []) == "help text"
        assert d.dispatch("/help", ["guest"]) == "help text"

    def test_list_by_category(self):
        d = CommandDispatcher()
        d.register(Command(name="a", description="", category=CommandCategory.SYSTEM))
        d.register(Command(name="b", description="", category=CommandCategory.ADMIN))
        d.register(Command(name="c", description="", category=CommandCategory.SYSTEM))
        system = d.list_by_category(CommandCategory.SYSTEM)
        assert len(system) == 2

    def test_list_all(self):
        d = CommandDispatcher()
        d.register(Command(name="a", description=""))
        d.register(Command(name="b", description=""))
        assert len(d.list_all()) == 2
