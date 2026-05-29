"""Tests for slash command dispatcher"""

import pytest

from agents.commands import Command, CommandCategory, CommandDispatcher, get_dispatcher


class TestCommandDispatcher:
    """Test slash command dispatcher"""

    def test_dispatcher_singleton(self):
        """Should return same dispatcher instance"""
        d1 = get_dispatcher()
        d2 = get_dispatcher()
        assert d1 is d2

    def test_builtin_commands_registered(self):
        """Should have built-in commands registered"""
        dispatcher = CommandDispatcher()
        commands = dispatcher.list_commands()
        
        assert len(commands) > 0
        names = [c["name"] for c in commands]
        assert "plan" in names
        assert "task" in names
        assert "implement" in names

    def test_command_categories(self):
        """Should have commands in multiple categories"""
        dispatcher = CommandDispatcher()
        
        planning = dispatcher.list_commands(CommandCategory.PLANNING)
        execution = dispatcher.list_commands(CommandCategory.EXECUTION)
        testing = dispatcher.list_commands(CommandCategory.TESTING)
        
        assert len(planning) > 0
        assert len(execution) > 0
        assert len(testing) > 0

    def test_dispatch_plan_command(self):
        """Should dispatch /plan command"""
        dispatcher = CommandDispatcher()
        result = dispatcher.dispatch("/plan create a caching layer")
        
        assert result["command"] == "plan"
        assert "create a caching layer" in result["goal"]

    def test_dispatch_task_command(self):
        """Should dispatch /task command"""
        dispatcher = CommandDispatcher()
        result = dispatcher.dispatch("/task implement auth middleware")
        
        assert result["command"] == "task"
        assert "implement auth middleware" in result["title"]

    def test_dispatch_implement_command(self):
        """Should dispatch /implement command"""
        dispatcher = CommandDispatcher()
        result = dispatcher.dispatch("/implement feature spec")
        
        assert result["command"] == "implement"
        assert result["status"] == "executing"

    def test_dispatch_test_command(self):
        """Should dispatch /test command"""
        dispatcher = CommandDispatcher()
        result = dispatcher.dispatch("/test unit")
        
        assert result["command"] == "test"
        assert result["status"] == "running"

    def test_dispatch_with_aliases(self):
        """Should accept command aliases"""
        dispatcher = CommandDispatcher()
        
        # /exec should map to /implement
        result1 = dispatcher.dispatch("/exec spec")
        result2 = dispatcher.dispatch("/implement spec")
        
        assert result1["command"] == result2["command"] == "implement"

    def test_dispatch_unknown_command(self):
        """Should handle unknown commands gracefully"""
        dispatcher = CommandDispatcher()
        result = dispatcher.dispatch("/unknown")
        
        assert "error" in result

    def test_dispatch_non_slash_input(self):
        """Should ignore non-slash input"""
        dispatcher = CommandDispatcher()
        result = dispatcher.dispatch("hello world")
        
        assert result is None

    def test_custom_command_registration(self):
        """Should allow registering custom commands"""
        dispatcher = CommandDispatcher()
        
        def my_handler(args, context):
            return {"custom": True, "args": args}
        
        custom = Command(
            name="custom",
            category=CommandCategory.EXECUTION,
            description="Custom command",
            usage="/custom <args>",
            handler=my_handler,
        )
        
        dispatcher.register(custom)
        
        result = dispatcher.dispatch("/custom test")
        assert result["custom"] is True
        assert "test" in result["args"]

    def test_command_with_context(self):
        """Should pass context to handlers"""
        dispatcher = CommandDispatcher()
        context = {"user": "test", "repo": "local-llm-server"}
        
        result = dispatcher.dispatch("/plan something", context=context)
        assert result["context"] == context

    def test_list_commands_by_category(self):
        """Should filter commands by category"""
        dispatcher = CommandDispatcher()
        
        planning = dispatcher.list_commands(CommandCategory.PLANNING)
        execution = dispatcher.list_commands(CommandCategory.EXECUTION)
        
        # Should have no overlap
        planning_names = {c["name"] for c in planning}
        execution_names = {c["name"] for c in execution}
        
        assert len(planning_names & execution_names) == 0

    def test_command_usage_help(self):
        """Commands should have usage information"""
        dispatcher = CommandDispatcher()
        commands = dispatcher.list_commands()
        
        for cmd in commands:
            assert "usage" in cmd
            assert cmd["usage"].startswith("/")

    def test_command_aliases_work(self):
        """Aliases should work as alternatives"""
        dispatcher = CommandDispatcher()
        
        # /research and /investigate should both work
        result1 = dispatcher.dispatch("/research python caching")
        result2 = dispatcher.dispatch("/investigate python caching")
        
        assert result1["command"] == "research"
        assert result2["command"] == "research"
