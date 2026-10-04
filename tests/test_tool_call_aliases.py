"""Executor tool calls in the shapes production models actually return.

Production logs (2026-10-04, gpt-oss-20b on Bedrock and Nemotron on NVIDIA) showed
tool selection rejected for `{"command": "list_files", "args": {...}}` and for
`{"tool": "read_file", "args": {"operation": "list_files", ...}}`: each rejection
cost one of the step's four attempts.
"""
from __future__ import annotations

import pytest

from agent.loop import AgentRunner


@pytest.fixture
def runner(tmp_path) -> AgentRunner:
    return AgentRunner(ollama_base="http://localhost:1", workspace_root=str(tmp_path))


@pytest.mark.parametrize("alias", ["command", "action", "function", "tool_name", "operation"])
def test_alias_key_names_the_tool(runner, alias):
    call = runner._coerce_tool_call({alias: "list_files", "args": {"path": "."}})
    assert call.tool == "list_files" and call.args == {"path": "."}


def test_alias_with_flat_args(runner):
    call = runner._coerce_tool_call({"command": "search_code", "query": "TaskDispatcher"})
    assert call.tool == "search_code" and call.args == {"query": "TaskDispatcher"}


def test_operation_inside_args_overrides_the_wrong_tool(runner):
    call = runner._coerce_tool_call(
        {"tool": "read_file", "args": {"operation": "list_files", "path": ".", "limit": 200}}
    )
    assert call.tool == "list_files" and call.args == {"path": ".", "limit": 200}


def test_shell_command_is_not_mistaken_for_a_tool(runner):
    call = runner._coerce_tool_call(
        {"tool": "run_command", "args": {"workspace_id": "w", "command": "ls -la"}}
    )
    assert call.tool == "run_command" and call.args["command"] == "ls -la"


def test_unknown_alias_value_still_errors(runner):
    with pytest.raises(ValueError):
        runner._coerce_tool_call({"command": "do_magic", "x": 1})
