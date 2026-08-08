"""tests/test_daily_automation_2026_08_08.py — Daily automation (2026-08-08).

Covers two ecosystem improvements shipped today:

  1. agent/tools.py — F1: Precise Search/Replace File Editing
     ``WorkspaceTools.search_replace_file(path, search_string, replacement_string)``
     performs a surgical search-and-replace, failing fast when the target
     string is absent or ambiguous.  Inspired by Codebuff-style diff
     application and Claude Code's own ``Edit`` tool pattern.

  2. packages/llm/providers/anthropic.py — C6 extension: Tool-list Prompt Caching
     When ``prompt_caching`` is enabled (the default), ``build_payload`` now
     appends ``cache_control: {type: ephemeral}`` to the last entry of the
     ``tools`` array.  Anthropic caches the full tool list up to that
     breakpoint, reducing token costs on repeated agent calls by up to 80%.
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── 1. WorkspaceTools.search_replace_file ────────────────────────────────────


class TestSearchReplaceFile:
    """Unit tests for WorkspaceTools.search_replace_file (F1)."""

    def _make_tools(self, tmp_path: Path):
        root = tmp_path / "repo"
        root.mkdir()
        from agent.tools import WorkspaceTools
        return WorkspaceTools(root), root

    # ── happy path ──────────────────────────────────────────────────────────

    def test_replaces_exact_match(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        (root / "app.py").write_text("def foo():\n    return 1\n", encoding="utf-8")
        result = tools.search_replace_file("app.py", "return 1", "return 42")
        assert (root / "app.py").read_text() == "def foo():\n    return 42\n"
        assert result["replacements"] == 1
        assert "app.py" in result["path"]

    def test_diff_shows_change(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        (root / "f.py").write_text("x = 1\n", encoding="utf-8")
        result = tools.search_replace_file("f.py", "x = 1", "x = 99")
        assert "-x = 1" in result["diff"]
        assert "+x = 99" in result["diff"]

    def test_replaces_multiline_block(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        original = "def greet():\n    print('hello')\n    return True\n"
        (root / "g.py").write_text(original, encoding="utf-8")
        result = tools.search_replace_file(
            "g.py",
            "    print('hello')\n    return True",
            "    print('hi')\n    return False",
        )
        assert "print('hi')" in (root / "g.py").read_text()
        assert result["replacements"] == 1

    def test_replaces_only_first_when_unique(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        content = "a = 1\nb = 2\nc = 3\n"
        (root / "vars.py").write_text(content, encoding="utf-8")
        result = tools.search_replace_file("vars.py", "b = 2", "b = 20")
        after = (root / "vars.py").read_text()
        assert "b = 20" in after
        assert "a = 1" in after
        assert "c = 3" in after

    def test_works_with_nested_subdirectory(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        (root / "pkg").mkdir()
        (root / "pkg" / "mod.py").write_text("VALUE = 'old'\n", encoding="utf-8")
        tools.search_replace_file("pkg/mod.py", "VALUE = 'old'", "VALUE = 'new'")
        assert (root / "pkg" / "mod.py").read_text() == "VALUE = 'new'\n"

    # ── error cases ─────────────────────────────────────────────────────────

    def test_raises_when_search_string_not_found(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        (root / "f.py").write_text("x = 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="not found"):
            tools.search_replace_file("f.py", "y = 2", "y = 99")

    def test_raises_when_search_string_ambiguous(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        (root / "f.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
        with pytest.raises(ValueError, match="appears 2 times"):
            tools.search_replace_file("f.py", "x = 1", "x = 99")

    def test_raises_on_path_traversal(self, tmp_path: Path):
        tools, _ = self._make_tools(tmp_path)
        with pytest.raises(ValueError, match="traversal"):
            tools.search_replace_file("../../etc/passwd", "root", "evil")

    def test_file_unchanged_after_not_found_error(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        original = "important = True\n"
        (root / "important.py").write_text(original, encoding="utf-8")
        with pytest.raises(ValueError):
            tools.search_replace_file("important.py", "missing_string", "x")
        assert (root / "important.py").read_text() == original

    # ── return shape ────────────────────────────────────────────────────────

    def test_returns_path_diff_replacements_keys(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        (root / "r.py").write_text("N = 0\n", encoding="utf-8")
        result = tools.search_replace_file("r.py", "N = 0", "N = 1")
        assert set(result.keys()) == {"path", "diff", "replacements"}

    def test_replacements_is_always_one_on_success(self, tmp_path: Path):
        tools, root = self._make_tools(tmp_path)
        (root / "x.py").write_text("v = 'a'\n", encoding="utf-8")
        result = tools.search_replace_file("x.py", "v = 'a'", "v = 'b'")
        assert result["replacements"] == 1


# ── 2. Agent loop dispatch for search_replace_file ───────────────────────────


class TestSearchReplaceFileDispatch:
    """Verify that _dispatch_tool_unguarded routes search_replace_file."""

    def _make_runner(self, tmp_path: Path):
        """Minimal AgentRunner with a real WorkspaceTools over tmp_path."""
        from agent.tools import WorkspaceTools
        runner = MagicMock()
        runner._mcp = None
        runner.tools = WorkspaceTools(tmp_path)
        from agent.loop import AgentRunner
        return runner, AgentRunner._dispatch_tool_unguarded

    def test_dispatch_search_replace_file_success(self, tmp_path: Path):
        import asyncio
        (tmp_path / "f.py").write_text("X = 1\n", encoding="utf-8")

        from agent.tools import WorkspaceTools
        tools = WorkspaceTools(tmp_path)

        async def run():
            from agent.loop import AgentRunner
            runner = MagicMock(spec=AgentRunner)
            runner._mcp = None
            runner.tools = tools
            runner._get_tool_registry = MagicMock(return_value=None)
            return await AgentRunner._dispatch_tool_unguarded(
                runner,
                "search_replace_file",
                {"path": "f.py", "search_string": "X = 1", "replacement_string": "X = 99"},
            )

        result = asyncio.run(run())
        assert isinstance(result, dict)
        assert result.get("replacements") == 1
        assert (tmp_path / "f.py").read_text() == "X = 99\n"

    def test_dispatch_search_replace_file_not_found(self, tmp_path: Path):
        import asyncio
        (tmp_path / "f.py").write_text("X = 1\n", encoding="utf-8")

        from agent.tools import WorkspaceTools
        tools = WorkspaceTools(tmp_path)

        async def run():
            from agent.loop import AgentRunner
            runner = MagicMock(spec=AgentRunner)
            runner._mcp = None
            runner.tools = tools
            runner._get_tool_registry = MagicMock(return_value=None)
            return await AgentRunner._dispatch_tool_unguarded(
                runner,
                "search_replace_file",
                {"path": "f.py", "search_string": "MISSING", "replacement_string": "x"},
            )

        result = asyncio.run(run())
        assert isinstance(result, str)
        assert "search_replace_file error" in result
        assert "not found" in result


# ── 3. Tool prompt includes search_replace_file ──────────────────────────────


class TestToolPromptIncludesSearchReplaceFile:
    """The executor sees search_replace_file in its tool list."""

    def test_build_tool_prompt_contains_search_replace_file(self):
        from agent.prompts import build_tool_prompt
        messages = build_tool_prompt(
            goal="test goal",
            step={"id": "s1", "description": "update a line"},
            observations=[],
            remaining_calls=5,
        )
        system_content = next(
            m["content"] for m in messages if m.get("role") == "system"
        )
        assert "search_replace_file" in system_content

    def test_prompt_documents_parameters(self):
        from agent.prompts import build_tool_prompt
        messages = build_tool_prompt(
            goal="g", step={"id": "s", "description": "d"}, observations=[], remaining_calls=3
        )
        sys_text = next(m["content"] for m in messages if m["role"] == "system")
        assert "search_string" in sys_text
        assert "replacement_string" in sys_text


# ── 4. Anthropic tool-list prompt caching ────────────────────────────────────


class TestAnthropicToolListCaching:
    """AnthropicProvider.build_payload caches the tool list when prompt_caching=True (C6)."""

    def _make_provider(self, prompt_caching: bool = True):
        from packages.llm.config import ProviderConfig
        from packages.llm.providers.anthropic import AnthropicProvider
        cfg = ProviderConfig(
            id="anthropic-test",
            kind="anthropic",
            base_url="https://api.anthropic.com",
            prompt_caching=prompt_caching,
        )
        return AnthropicProvider(cfg)

    def _make_request(self, tools: list[dict] | None = None):
        from packages.llm.types import LLMRequest
        return LLMRequest(
            messages=[{"role": "user", "content": "hello"}],
            model="claude-sonnet-4-6",
            tools=tools,
        )

    def test_last_tool_gets_cache_control_when_enabled(self):
        provider = self._make_provider(prompt_caching=True)
        tools = [
            {"name": "read_file", "description": "r", "input_schema": {"type": "object", "properties": {}}},
            {"name": "write_file", "description": "w", "input_schema": {"type": "object", "properties": {}}},
        ]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert "tools" in payload
        assert len(payload["tools"]) == 2
        last = payload["tools"][-1]
        assert last.get("cache_control") == {"type": "ephemeral"}, (
            "Last tool must have cache_control: {type: ephemeral}"
        )

    def test_non_last_tools_have_no_cache_control(self):
        provider = self._make_provider(prompt_caching=True)
        tools = [
            {"name": "read_file", "description": "r", "input_schema": {"type": "object"}},
            {"name": "search_code", "description": "s", "input_schema": {"type": "object"}},
            {"name": "write_file", "description": "w", "input_schema": {"type": "object"}},
        ]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        for tool in payload["tools"][:-1]:
            assert "cache_control" not in tool, (
                f"Only the last tool should have cache_control, found it on {tool.get('name')}"
            )

    def test_no_cache_control_when_prompt_caching_disabled(self):
        provider = self._make_provider(prompt_caching=False)
        tools = [{"name": "tool_a", "description": "a", "input_schema": {"type": "object"}}]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert "tools" in payload
        for tool in payload["tools"]:
            assert "cache_control" not in tool

    def test_single_tool_gets_cache_control(self):
        provider = self._make_provider(prompt_caching=True)
        tools = [{"name": "only_tool", "description": "o", "input_schema": {"type": "object"}}]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert payload["tools"][0].get("cache_control") == {"type": "ephemeral"}

    def test_no_tools_no_tools_key(self):
        provider = self._make_provider(prompt_caching=True)
        request = self._make_request(tools=None)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert "tools" not in payload

    def test_original_tool_dict_not_mutated(self):
        provider = self._make_provider(prompt_caching=True)
        original_tool = {"name": "t", "description": "d", "input_schema": {"type": "object"}}
        tools = [original_tool]
        request = self._make_request(tools=tools)
        provider.build_payload(request, "claude-sonnet-4-6")
        assert "cache_control" not in original_tool, (
            "build_payload must not mutate the caller's tool dicts"
        )

    def test_cache_control_type_is_ephemeral(self):
        provider = self._make_provider(prompt_caching=True)
        tools = [{"name": "x", "description": "x", "input_schema": {"type": "object"}}]
        request = self._make_request(tools=tools)
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        cc = payload["tools"][-1].get("cache_control", {})
        assert cc.get("type") == "ephemeral"

    def test_tools_not_in_payload_without_request_tools(self):
        provider = self._make_provider(prompt_caching=True)
        request = self._make_request(tools=[])
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        assert "tools" not in payload

    def test_native_anthropic_tool_format_preserved(self):
        """input_schema passthrough — native Anthropic tools should not be wrapped again."""
        provider = self._make_provider(prompt_caching=True)
        native_tool = {
            "name": "native",
            "description": "native tool",
            "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
        }
        request = self._make_request(tools=[native_tool])
        payload = provider.build_payload(request, "claude-sonnet-4-6")
        built = payload["tools"][0]
        assert built["name"] == "native"
        assert "input_schema" in built
        assert built.get("cache_control") == {"type": "ephemeral"}
