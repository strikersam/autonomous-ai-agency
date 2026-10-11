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
