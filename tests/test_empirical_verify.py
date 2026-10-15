"""Tests for AgentRunner._empirical_verify (opt-in executable validation gate)."""
from pathlib import Path

import pytest

from agent.loop import AgentRunner
from packages.config import settings


def _make_runner(tmp_path: Path) -> AgentRunner:
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)


def test_empirical_verify_off_runs_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "false")
    runner = _make_runner(tmp_path)
    (Path(runner.tools.root) / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    assert runner._empirical_verify(["broken.py"]) == []


def test_empirical_verify_skips_non_python_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "true")
    runner = _make_runner(tmp_path)
    assert runner._empirical_verify(["notes.txt", "config.yaml"]) == []


def test_empirical_verify_flags_compile_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "true")
    runner = _make_runner(tmp_path)
    (Path(runner.tools.root) / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    issues = runner._empirical_verify(["broken.py"])
    assert issues and "byte-compile" in issues[0]


def test_empirical_verify_passes_clean_module_without_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "true")
    runner = _make_runner(tmp_path)
    (Path(runner.tools.root) / "clean.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert runner._empirical_verify(["clean.py"]) == []


def test_empirical_verify_runs_matching_tests_and_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "true")
    runner = _make_runner(tmp_path)
    root = Path(runner.tools.root)
    (root / "mymod.py").write_text("def answer():\n    return 41\n", encoding="utf-8")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mymod.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))\n"
        "from mymod import answer\n\n\n"
        "def test_answer():\n    assert answer() == 42\n",
        encoding="utf-8",
    )
    issues = runner._empirical_verify(["mymod.py"])
    assert issues and "tests failed" in issues[0]


def test_empirical_verify_runs_matching_tests_and_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "true")
    runner = _make_runner(tmp_path)
    root = Path(runner.tools.root)
    (root / "mymod.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_mymod.py").write_text(
        "import sys, pathlib\n"
        "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))\n"
        "from mymod import answer\n\n\n"
        "def test_answer():\n    assert answer() == 42\n",
        encoding="utf-8",
    )
    assert runner._empirical_verify(["mymod.py"]) == []


# ── E2B sandbox path: the checks run where the edits live ─────────────────────

import asyncio
import json


class E2BSandboxSession:
    """Fake named like the real session so empirical_verify.is_sandbox() matches."""

    def __init__(self, results):
        self.results = results  # list of (matcher, exit_code, output)
        self.cmds: list[str] = []

    async def call_tool(self, name, args):
        assert name == "run_command"
        cmd = args["cmd"]
        self.cmds.append(cmd)
        for match, code, out in self.results:
            if match in cmd:
                return json.dumps({"stdout": out, "stderr": "", "exit_code": code})
        return json.dumps({"stdout": "", "stderr": "", "exit_code": 0})


def _sandbox_runner(tmp_path, monkeypatch, results):
    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "true")
    runner = _make_runner(tmp_path)
    runner._mcp = E2BSandboxSession(results)
    return runner


def test_sandbox_path_runs_tests_in_sandbox_not_on_host(tmp_path, monkeypatch):
    runner = _sandbox_runner(tmp_path, monkeypatch, [
        ("ls -1", 0, "tests/test_mymod.py\n"),
        ("pytest -x", 0, "1 passed"),
    ])
    # A file that does not exist on the host: a host run would fail to compile it.
    issues = asyncio.run(runner._empirical_verify_async(["mymod.py"]))
    assert issues == []
    assert runner._last_executed_checks == ["pytest -x tests/test_mymod.py (E2B sandbox): passed"]
    assert any("py_compile mymod.py" in c for c in runner._mcp.cmds)


def test_sandbox_test_failure_blocks_the_step(tmp_path, monkeypatch):
    runner = _sandbox_runner(tmp_path, monkeypatch, [
        ("ls -1", 0, "tests/test_mymod.py\n"),
        ("pytest -x", 1, "FAILED tests/test_mymod.py::test_answer - assert 41 == 42\n1 failed"),
    ])
    issues = asyncio.run(runner._empirical_verify_async(["mymod.py"]))
    assert issues and "tests failed" in issues[0]
    assert runner._last_executed_checks == []


def test_sandbox_missing_dependency_is_not_evidence_and_not_failure(tmp_path, monkeypatch):
    runner = _sandbox_runner(tmp_path, monkeypatch, [
        ("ls -1", 0, "tests/test_mymod.py\n"),
        ("pytest -x", 2, "ImportError while importing test module\nModuleNotFoundError: No module named 'fastapi'"),
    ])
    issues = asyncio.run(runner._empirical_verify_async(["mymod.py"]))
    assert issues == []
    assert runner._last_executed_checks == []


def test_sandbox_compile_error_blocks_the_step(tmp_path, monkeypatch):
    runner = _sandbox_runner(tmp_path, monkeypatch, [("py_compile", 1, "SyntaxError: invalid syntax")])
    issues = asyncio.run(runner._empirical_verify_async(["mymod.py"]))
    assert issues and "byte-compile" in issues[0]


def test_sandbox_filenames_are_shell_quoted(tmp_path, monkeypatch):
    runner = _sandbox_runner(tmp_path, monkeypatch, [])
    asyncio.run(runner._empirical_verify_async(["a; rm -rf ~.py"]))
    assert all("; rm -rf ~.py" not in c.replace("'a; rm -rf ~.py'", "") for c in runner._mcp.cmds)


def test_host_checks_get_no_secrets(tmp_path, monkeypatch):
    from agent.loop import _check_env

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-secret")
    env = _check_env()
    assert "NVIDIA_API_KEY" not in env and env["TESTING"] == "true"


def test_control_is_live_and_on_by_default():
    from packages.config import control_overrides
    from packages.config.control_registry import get_control

    assert get_control("AGENT_EMPIRICAL_VERIFY").live is True
    assert get_control("AGENT_EMPIRICAL_VERIFY").default == "true"
    try:
        control_overrides.apply_overrides({"AGENT_EMPIRICAL_VERIFY": "false"})
        assert settings.agent_empirical_verify is False
    finally:
        control_overrides.apply_overrides({})
    assert settings.agent_empirical_verify is True


# ── project dependencies in the sandbox ───────────────────────────────────────

def test_sandbox_installs_requirements_once_before_tests(tmp_path, monkeypatch):
    runner = _sandbox_runner(tmp_path, monkeypatch, [
        ("ls -1", 0, "tests/test_mymod.py\n"),
        ("pytest -x", 0, "1 passed"),
    ])
    asyncio.run(runner._empirical_verify_async(["mymod.py"]))
    asyncio.run(runner._empirical_verify_async(["mymod.py"]))
    installs = [c for c in runner._mcp.cmds if "pip install -q --disable-pip-version-check" in c]
    assert len(installs) == 1 and "requirements.txt" in installs[0]
    first_test = next(i for i, c in enumerate(runner._mcp.cmds) if "pytest -x" in c)
    assert runner._mcp.cmds.index(installs[0]) < first_test


def test_failed_install_is_noted_and_not_retried(tmp_path, monkeypatch):
    from agent import empirical_verify as ev

    runner = _sandbox_runner(tmp_path, monkeypatch, [("--disable-pip-version-check", 1, "No matching distribution")])
    note = asyncio.run(ev.ensure_dependencies(runner._mcp))
    assert note and "failed (exit 1)" in note
    assert asyncio.run(ev.ensure_dependencies(runner._mcp)) == note
    assert len([c for c in runner._mcp.cmds if "--disable-pip-version-check" in c]) == 1


def test_no_requirements_file_is_not_a_failure(tmp_path, monkeypatch):
    from agent import empirical_verify as ev

    runner = _sandbox_runner(tmp_path, monkeypatch, [("--disable-pip-version-check", 3, "")])
    assert asyncio.run(ev.ensure_dependencies(runner._mcp)) is None


def test_install_control_off_skips_it(tmp_path, monkeypatch):
    from agent import empirical_verify as ev
    from packages.config import control_overrides
    from packages.config.control_registry import get_control

    assert get_control("AGENT_SANDBOX_INSTALL_DEPS").live is True
    runner = _sandbox_runner(tmp_path, monkeypatch, [])
    try:
        control_overrides.apply_overrides({"AGENT_SANDBOX_INSTALL_DEPS": "false"})
        assert asyncio.run(ev.ensure_dependencies(runner._mcp)) is None
        assert runner._mcp.cmds == []
    finally:
        control_overrides.apply_overrides({})


def test_install_timeout_is_cached_not_retried(tmp_path, monkeypatch):
    from agent import empirical_verify as ev

    runner = _sandbox_runner(tmp_path, monkeypatch, [])
    calls = []

    async def boom(name, args):
        calls.append(args["cmd"])
        raise RuntimeError("command timed out")

    runner._mcp.call_tool = boom
    note = asyncio.run(ev.ensure_dependencies(runner._mcp))
    assert note and "timed out" in note
    assert asyncio.run(ev.ensure_dependencies(runner._mcp)) == note
    assert len(calls) == 1


def test_sandbox_pass_and_failure_are_logged(tmp_path, monkeypatch, caplog):
    # A passing run must leave a trace in the service logs, not only in the report.
    caplog.set_level("INFO", logger="qwen-proxy")
    runner = _sandbox_runner(tmp_path, monkeypatch, [
        ("ls -1", 0, "tests/test_mymod.py\n"),
        ("pytest -x", 0, "1 passed"),
    ])
    asyncio.run(runner._empirical_verify_async(["mymod.py"]))
    assert "sandbox tests passed (tests/test_mymod.py)" in caplog.text

    caplog.clear()
    runner = _sandbox_runner(tmp_path, monkeypatch, [
        ("ls -1", 0, "tests/test_mymod.py\n"),
        ("pytest -x", 1, "1 failed"),
    ])
    asyncio.run(runner._empirical_verify_async(["mymod.py"]))
    assert "sandbox tests failed (exit 1, tests/test_mymod.py)" in caplog.text


def test_sandbox_diff_reads_the_edits_from_the_sandbox(tmp_path, monkeypatch):
    from agent import empirical_verify as ev

    session = E2BSandboxSession([("git diff", 0, "diff --git a/mymod.py b/mymod.py\n+fixed\n")])
    assert "+fixed" in asyncio.run(ev.sandbox_diff(session))
    assert "ls-files -z --others" in session.cmds[0]  # new files are included too
    long = E2BSandboxSession([("git diff", 0, "x" * 50)])
    assert asyncio.run(ev.sandbox_diff(long, max_chars=10)).endswith("diff truncated (50 chars total)")


def test_judge_sees_the_sandbox_diff_not_unavailable(tmp_path, monkeypatch):
    # Production 2026-10-11: every sandbox run was REJECTED with "The diff is
    # unavailable", because the judge brief only read the host repository.
    from agent.models import AgentPlan, AgentStep

    runner = _sandbox_runner(tmp_path, monkeypatch, [("git diff", 0, "diff --git a/mymod.py b/mymod.py\n+fixed\n")])
    plan = AgentPlan(goal="fix mymod", steps=[AgentStep(id=1, description="d", files=["mymod.py"], type="edit")])
    brief = asyncio.run(runner._judge_brief(plan, [{"status": "applied", "changed_files": ["mymod.py"]}], []))
    assert "+fixed" in brief and "(unavailable)" not in brief


def test_a_dead_sandbox_gives_no_diff_instead_of_raising():
    from agent import empirical_verify as ev

    class Dead(E2BSandboxSession):
        async def call_tool(self, name, args):
            raise RuntimeError("sandbox gone")

    assert asyncio.run(ev.sandbox_diff(Dead([]))) == ""


def test_sandbox_diff_uses_the_commit_recorded_at_seed_time():
    # A shallow clone's "root" commit is arbitrary; the judge saw weeks of
    # unrelated history (production 2026-10-15). The seed-time HEAD is the base.
    from agent import empirical_verify as ev

    session = E2BSandboxSession([("git diff", 0, "diff --git a/x.py b/x.py\n+y\n")])
    session._base_sha = "a" * 40
    asyncio.run(ev.sandbox_diff(session))
    assert session.cmds[0].startswith("git diff --stat --patch " + "a" * 40)
    unknown = E2BSandboxSession([])
    asyncio.run(ev.sandbox_diff(unknown))
    assert unknown.cmds[0].startswith("git diff --stat --patch HEAD") and "max-parents" not in unknown.cmds[0]


def test_judge_sees_changed_files_content_when_git_has_no_diff(tmp_path, monkeypatch):
    # Production 2026-10-12..15: "Diff: (unavailable)" on every sandbox run, so
    # every task was rejected. A changed file git cannot diff is shown as content.
    from agent.models import AgentPlan, AgentStep

    runner = _sandbox_runner(tmp_path, monkeypatch, [("git diff", 0, "")])

    async def call_tool(name, args, _orig=runner._mcp.call_tool):
        if name == "read_file":
            return "def fixed():\n    return 1\n"
        return await _orig(name, args)

    runner._mcp.call_tool = call_tool
    plan = AgentPlan(goal="fix mymod", steps=[AgentStep(id=1, description="d", files=["mymod.py"], type="edit")])
    steps = [{"status": "applied", "changed_files": ["./mymod.py"]}]
    brief = asyncio.run(runner._judge_brief(plan, steps, []))
    assert "(unavailable)" not in brief
    assert "--- mymod.py (current content" in brief and "def fixed()" in brief


def test_judge_never_reads_files_outside_the_repo(tmp_path, monkeypatch):
    runner = _sandbox_runner(tmp_path, monkeypatch, [("git diff", 0, "")])
    read: list = []

    async def call_tool(name, args, _orig=runner._mcp.call_tool):
        if name == "read_file":
            read.append(args["path"])
            return "secret"
        return await _orig(name, args)

    runner._mcp.call_tool = call_tool
    out = asyncio.run(runner._changed_content(["/etc/passwd", "../../x", "a/../../b", "~/.ssh/id", "ok.py"]))
    assert read == ["ok.py"] and "ok.py" in out
