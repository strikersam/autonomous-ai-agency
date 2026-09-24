"""agent/code_graph.py — structural code queries via codebase-memory-mcp (#1569).

Hermetic: a fake runner stands in for the binary. The JSON shapes it returns
were captured from codebase-memory-mcp 0.11.0 on a Python + JavaScript repo.
"""
from __future__ import annotations

import asyncio
import json
import subprocess

import pytest

from agent import code_graph as cg

INDEX = {"project": "demo-proj", "nodes": 23, "edges": 26, "status": "indexed"}
TRACE = {
    "function": "helper", "direction": "inbound", "callers_total": 2,
    "callers": {"cols": ["name", "hop"],
                "groups": [{"qn_prefix": "demo-proj.app", "rows": [["process", 1], ["main", 2]]}]},
}
IMPACT = {"base": "main", "changed_files": ["app.py"], "impacted_total": 2}


class FakeRunner:
    """Records argv; answers git and each CLI tool with canned output."""

    def __init__(self, head: str = "abc") -> None:
        self.calls: list[list[str]] = []
        self.head = head
        self.fail_with: str | None = None

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[0] == "git":
            out = self.head if argv[1] == "rev-parse" else ""
            return subprocess.CompletedProcess(argv, 0, out, "")
        if self.fail_with:
            return subprocess.CompletedProcess(argv, 1, "", self.fail_with)
        tool = argv[3]
        body = {"index_repository": INDEX, "trace_path": TRACE,
                "detect_changes": IMPACT, "search_graph": {"total": 1}}[tool]
        return subprocess.CompletedProcess(argv, 0, json.dumps(body), "")

    def tool_calls(self, name: str) -> list[list[str]]:
        return [c for c in self.calls if c[0] != "git" and c[3] == name]


@pytest.fixture()
def runner() -> FakeRunner:
    return FakeRunner()


@pytest.fixture()
def graph(tmp_path, runner) -> cg.CodeGraph:
    return cg.CodeGraph(tmp_path, binary="cbm", runner=runner)


class TestQueries:
    def test_trace_indexes_then_queries_with_list_argv(self, graph, runner) -> None:
        result = graph.trace("helper", "inbound", 2)
        assert result["callers_total"] == 2
        index_call = runner.tool_calls("index_repository")[0]
        assert index_call[:4] == ["cbm", "cli", "--quiet", "index_repository"]
        trace_call = runner.tool_calls("trace_path")[0]
        assert trace_call[trace_call.index("--project") + 1] == "demo-proj"
        assert trace_call[trace_call.index("--depth") + 1] == "2"
        assert trace_call[-2:] == ["--format", "json"]

    def test_index_is_reused_until_the_workspace_changes(self, graph, runner) -> None:
        graph.trace("helper")
        graph.search(".*Handler.*", "Function")
        assert len(runner.tool_calls("index_repository")) == 1
        runner.head = "def"  # a new commit
        graph.impact("main")
        assert len(runner.tool_calls("index_repository")) == 2

    def test_depth_and_limit_are_clamped(self, graph, runner) -> None:
        graph.trace("helper", "both", 99)
        call = runner.tool_calls("trace_path")[0]
        assert call[call.index("--depth") + 1] == "5"
        graph.search("x", None, 10_000)
        call = runner.tool_calls("search_graph")[0]
        assert call[call.index("--limit") + 1] == "100"


class TestInputNeverBecomesAFlag:
    @pytest.mark.parametrize("name", ["--help", "-x", "", "a b", "x" * 201])
    def test_bad_symbol(self, graph, runner, name) -> None:
        with pytest.raises(cg.CodeGraphError):
            graph.trace(name)
        assert runner.tool_calls("trace_path") == []

    def test_bad_direction_and_label(self, graph) -> None:
        with pytest.raises(cg.CodeGraphError):
            graph.trace("helper", "sideways")
        with pytest.raises(cg.CodeGraphError):
            graph.search("x", "Table")

    @pytest.mark.parametrize("ref", ["-main", "a..b", "a b", "main;rm"])
    def test_bad_ref(self, graph, ref) -> None:
        with pytest.raises(cg.CodeGraphError):
            graph.impact(ref)


class TestFailuresAreData:
    def test_cli_failure_is_reported(self, graph, runner) -> None:
        runner.fail_with = "boom\nproject not found"
        result = asyncio.run(cg.run_query(graph.trace, "helper"))
        assert result == {"error": "project not found"}

    def test_missing_binary_is_reported(self, tmp_path) -> None:
        def missing(argv, **kwargs):
            if argv[0] == "git":
                return subprocess.CompletedProcess(argv, 0, "", "")
            raise FileNotFoundError(argv[0])
        g = cg.CodeGraph(tmp_path, binary="nope", runner=missing)
        result = asyncio.run(cg.run_query(g.trace, "helper"))
        assert "not installed" in result["error"]

    def test_non_json_output_is_an_error(self, graph, runner, monkeypatch) -> None:
        def text_runner(argv, **kwargs):
            if argv[0] == "git":
                return subprocess.CompletedProcess(argv, 0, "", "")
            return subprocess.CompletedProcess(argv, 0, "not json", "")
        graph._run = text_runner
        with pytest.raises(cg.CodeGraphError):
            graph.trace("helper")


class TestOptIn:
    @pytest.fixture()
    def enabled(self, monkeypatch):
        from packages.config import settings

        monkeypatch.setattr(settings, "code_graph_enabled_raw", "true")
        monkeypatch.setattr(cg.shutil, "which", lambda b: f"/usr/bin/{b}")

    def test_disabled_by_default(self) -> None:
        from packages.config import settings

        assert settings.code_graph_enabled is False
        assert cg.code_graph_enabled() is False

    def test_enabled_needs_the_binary(self, monkeypatch) -> None:
        from packages.config import settings

        monkeypatch.setattr(settings, "code_graph_enabled_raw", "true")
        monkeypatch.setattr(cg.shutil, "which", lambda b: None)
        assert cg.code_graph_enabled() is False

    def test_tools_registered_and_advertised_only_when_enabled(self, enabled, tmp_path) -> None:
        from agent.capability_registry import ToolRegistry, _register_code_graph_tools
        from agent.prompts import _code_graph_tool_lines

        registry = ToolRegistry()
        _register_code_graph_tools(registry, tmp_path)
        for name in ("code_trace", "code_search", "code_impact"):
            assert registry.get(name) is not None, name
        assert "code_trace(function_name" in _code_graph_tool_lines()

    def test_nothing_registered_or_advertised_when_disabled(self, tmp_path) -> None:
        from agent.capability_registry import ToolRegistry, _register_code_graph_tools
        from agent.prompts import _code_graph_tool_lines

        registry = ToolRegistry()
        _register_code_graph_tools(registry, tmp_path)
        assert registry.get("code_trace") is None
        assert _code_graph_tool_lines() == ""

    def test_mcp_registry_lists_it_with_the_reason(self) -> None:
        from packages.integrations.mcp_registry import _specs

        spec = next(s for s in _specs() if s.server_id == "codebase-memory")
        configured, reason = spec.is_configured()
        assert configured is False and "CODE_GRAPH_ENABLED" in reason
