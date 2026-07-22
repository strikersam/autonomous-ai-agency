"""Tests for AgentRunner._empirical_verify (opt-in executable validation gate)."""
from pathlib import Path

import pytest

from agent.loop import AgentRunner


def _make_runner(tmp_path: Path) -> AgentRunner:
    root = tmp_path / "repo"
    root.mkdir(exist_ok=True)
    return AgentRunner(ollama_base="http://localhost:11434", workspace_root=root)


def test_empirical_verify_disabled_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AGENT_EMPIRICAL_VERIFY", raising=False)
    runner = _make_runner(tmp_path)
    (Path(runner.tools.root) / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    assert runner._empirical_verify(["broken.py"]) == []


def test_empirical_verify_skips_non_python_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_EMPIRICAL_VERIFY", "true")
    runner = _make_runner(tmp_path)
    assert runner._empirical_verify(["notes.txt", "config.yaml"]) == []


def test_empirical_verify_flags_compile_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_EMPIRICAL_VERIFY", "true")
    runner = _make_runner(tmp_path)
    (Path(runner.tools.root) / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    issues = runner._empirical_verify(["broken.py"])
    assert issues and "byte-compile" in issues[0]


def test_empirical_verify_passes_clean_module_without_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AGENT_EMPIRICAL_VERIFY", "true")
    runner = _make_runner(tmp_path)
    (Path(runner.tools.root) / "clean.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert runner._empirical_verify(["clean.py"]) == []


def test_empirical_verify_runs_matching_tests_and_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("AGENT_EMPIRICAL_VERIFY", "true")
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
    monkeypatch.setenv("AGENT_EMPIRICAL_VERIFY", "true")
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
