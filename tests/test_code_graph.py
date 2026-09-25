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
        self.diff = ""
        self.origin_head: str | None = None
        self.branches: set[str] = set()
        self.fail_with: str | None = None

    def _git(self, argv):
        sub = argv[1]
        if sub == "rev-parse" and "--verify" in argv:
            return (0, argv[-1]) if argv[-1] in self.branches else (1, "")
        if sub == "rev-parse":
            return 0, self.head
        if sub == "diff":
            return 0, self.diff
        if sub == "symbolic-ref":
            return (0, self.origin_head + "\n") if self.origin_head else (1, "")
        return 0, ""

    def __call__(self, argv, **kwargs):
        self.calls.append(argv)
        if argv[0] == "git":
            code, out = self._git(argv)
            return subprocess.CompletedProcess(argv, code, out, "")
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

    def test_a_second_edit_to_a_dirty_file_reindexes(self, graph, runner) -> None:
        """git status would not change here; the diff content does."""
        runner.diff = "+x = 1"
        graph.trace("helper")
        runner.diff = "+x = 2"
        graph.trace("helper")
        assert len(runner.tool_calls("index_repository")) == 2

    def test_a_new_untracked_file_reindexes(self, graph, runner, tmp_path) -> None:
        graph.trace("helper")
        (tmp_path / "new.py").write_text("def f(): pass\n")
        orig = runner._git
        runner._git = lambda argv: (0, "new.py\n") if argv[1] == "ls-files" else orig(argv)
        graph.trace("helper")
        assert len(runner.tool_calls("index_repository")) == 2

    def test_outside_git_always_reindexes(self, tmp_path) -> None:
        runner = FakeRunner()
        runner._git = lambda argv: (128, "")
        g = cg.CodeGraph(tmp_path, binary="cbm", runner=runner)
        g.trace("helper")
        g.trace("helper")
        assert len(runner.tool_calls("index_repository")) == 2

    def test_concurrent_queries_index_once(self, graph, runner) -> None:
        import threading

        barrier = threading.Barrier(4)

        def worker():
            barrier.wait()
            graph.trace("helper")

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(runner.tool_calls("index_repository")) == 1

    @pytest.mark.parametrize("origin,branches,expected", [
        ("origin/trunk", set(), "origin/trunk"),
        (None, {"master"}, "master"),
        (None, {"main", "master"}, "main"),
        (None, set(), "HEAD~1"),
    ])
    def test_impact_defaults_to_the_repos_own_base(
        self, graph, runner, origin, branches, expected,
    ) -> None:
        runner.origin_head, runner.branches = origin, branches
        graph.impact()
        call = runner.tool_calls("detect_changes")[0]
        assert call[call.index("--base-branch") + 1] == expected

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


class TestRunnerWorkspace:
    """Registry handlers get the runner's own workspace, never a model's choice."""

    def test_workspace_root_is_injected_and_overrides_the_model(self, tmp_path) -> None:
        from agent.capability_registry import ToolRegistry
        from agent.loop import AgentRunner

        seen: dict = {}
        registry = ToolRegistry()

        @registry.agent_tool(name="probe", description="p", parameters={})
        async def _probe(name: str, workspace_root: str | None = None) -> dict:
            seen.update(name=name, root=workspace_root)
            return {"ok": True}

        runner = AgentRunner.__new__(AgentRunner)
        runner.tools = type("T", (), {"root": tmp_path})()
        runner._tool_registry = registry
        result = asyncio.run(runner._dispatch_tool_unguarded(
            "probe", {"name": "x", "workspace_root": "/etc"}))
        assert result == {"ok": True}
        assert seen == {"name": "x", "root": str(tmp_path)}

    def test_handlers_without_the_parameter_are_untouched(self) -> None:
        from agent import loop

        def plain(url: str) -> dict:
            return {}

        assert "workspace_root" not in loop._handler_params(plain)
        assert loop._handler_params(object()) == frozenset()


class TestIndexMode:
    """CODE_GRAPH_MODE: full does not fit the 512MB / 0.15-CPU Render tier."""

    def test_default_mode_is_full_and_is_passed_to_the_indexer(self, graph, runner) -> None:
        graph.trace("helper")
        call = runner.tool_calls("index_repository")[0]
        assert call[call.index("--mode") + 1] == "full"

    def test_fast_mode_is_passed_to_the_indexer(self, tmp_path, runner) -> None:
        cg.CodeGraph(tmp_path, binary="cbm", runner=runner, mode="fast").trace("helper")
        call = runner.tool_calls("index_repository")[0]
        assert call[call.index("--mode") + 1] == "fast"

    def test_unknown_mode_is_rejected(self, tmp_path, runner) -> None:
        with pytest.raises(cg.CodeGraphError):
            cg.CodeGraph(tmp_path, binary="cbm", runner=runner, mode="--help")

    def test_settings_mode_reaches_the_graph_and_bad_values_fall_back(self, tmp_path, monkeypatch) -> None:
        from packages.config import settings

        monkeypatch.setattr(cg, "_graphs", {})
        monkeypatch.setattr(settings, "code_graph_mode", "fast")
        assert cg.get_code_graph(tmp_path).mode == "fast"
        monkeypatch.setattr(cg, "_graphs", {})
        monkeypatch.setattr(settings, "code_graph_mode", "turbo")
        assert cg.get_code_graph(tmp_path).mode == "full"


class TestImageInstall:
    """Dockerfile INSTALL_CODE_GRAPH build arg (Render passes env vars as build args)."""

    # Render builds Dockerfile.backend (render.yaml dockerfilePath).
    DOCKERFILE = (cg.Path(__file__).resolve().parent.parent / "Dockerfile.backend").read_text()

    def test_off_by_default(self) -> None:
        assert "ARG INSTALL_CODE_GRAPH=false" in self.DOCKERFILE

    def test_pins_the_version_and_prefetches_the_binary(self) -> None:
        block = self.DOCKERFILE.split("ARG INSTALL_CODE_GRAPH=false", 1)[1].split("\n\n", 1)[0]
        assert 'if [ "$INSTALL_CODE_GRAPH" = "true" ]' in block
        assert "codebase-memory-mcp==0.11.0" in block
        assert "codebase-memory-mcp --version" in block

    def test_new_settings_are_documented(self) -> None:
        root = cg.Path(__file__).resolve().parent.parent
        docs = (root / "docs/configuration-reference.md").read_text()
        env = (root / ".env.example").read_text()
        for name in ("CODE_GRAPH_MODE", "INSTALL_CODE_GRAPH"):
            assert f"`{name}`" in docs and name in env, name


class TestWarmUp:
    """start_warm_up pre-builds the index so the first agent query does not pay for it."""

    def test_disabled_does_nothing(self, tmp_path) -> None:
        assert cg.start_warm_up(tmp_path) is None

    def test_enabled_indexes_once_and_logs(self, tmp_path, monkeypatch, caplog) -> None:
        runner = FakeRunner()
        graph = cg.CodeGraph(tmp_path, binary="cbm", runner=runner, mode="fast")
        monkeypatch.setattr(cg, "code_graph_enabled", lambda: True)
        monkeypatch.setattr(cg, "get_code_graph", lambda root: graph)
        with caplog.at_level("INFO", logger="qwen-proxy"):
            cg.start_warm_up(tmp_path).join(5)
        call = runner.tool_calls("index_repository")[0]
        assert call[call.index("--mode") + 1] == "fast"
        assert "code_graph: indexed" in caplog.text and "mode=fast" in caplog.text

    def test_failure_is_logged_not_raised(self, tmp_path, monkeypatch, caplog) -> None:
        runner = FakeRunner()
        runner.fail_with = "out of memory"
        graph = cg.CodeGraph(tmp_path, binary="cbm", runner=runner)
        monkeypatch.setattr(cg, "code_graph_enabled", lambda: True)
        monkeypatch.setattr(cg, "get_code_graph", lambda root: graph)
        with caplog.at_level("WARNING", logger="qwen-proxy"):
            cg.start_warm_up(tmp_path).join(5)
        assert "warm-up index" in caplog.text and "out of memory" in caplog.text

    def test_background_services_start_it(self) -> None:
        src = (cg.Path(__file__).resolve().parent.parent / "services/background.py").read_text()
        body = src.split("async def start_background_services", 1)[1].split("\ndef ", 1)[0]
        assert "_start_code_graph_warm_up(workspace_root)" in body
