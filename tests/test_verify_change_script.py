"""Tests for scripts/verify_change.py — the local/CI verification harness.

Runs the real harness (real py_compile and pytest subprocesses) on a scratch repo.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import verify_change

TEST = ("import sys, pathlib\nsys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))\n"
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(TEST, encoding="utf-8")
    return tmp_path


def _run(repo: Path, *files: str) -> tuple[int, dict]:
    out = repo / "out.json"
    code = verify_change.main(["--root", str(repo), "--files", *files, "--out", str(out)])
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_passing_change_exits_zero_but_is_not_called_verified(repo):
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    code, result = _run(repo, "calc.py")
    assert code == 0 and result["checks_ok"] is True
    assert {c["status"] for c in result["report"]["checks"]} == {"passed"}
    assert result["report"]["verdict"] == "BLOCKED"  # no reviewer here, so never VERIFIED


def test_failing_change_exits_one_with_real_output(repo):
    (repo / "calc.py").write_text("def add(a, b):\n    return a * b\n", encoding="utf-8")
    code, result = _run(repo, "calc.py")
    assert code == 1
    unit = [c for c in result["report"]["checks"] if c["strategy"] == "unit"][0]
    assert unit["status"] == "failed" and "assert" in unit["output_tail"]


def test_missing_tests_exit_two(repo):
    (repo / "other.py").write_text("X = 1\n", encoding="utf-8")
    code, result = _run(repo, "other.py")
    assert code == 2 and not result["checks_ok"]
    assert any("no passing unit check" in f["message"] for f in result["report"]["findings"])


def test_invalid_yaml_is_a_failed_static_check(repo):
    (repo / "conf.yaml").write_text("a: [1, 2\n", encoding="utf-8")
    code, result = _run(repo, "conf.yaml")
    assert code == 1
    assert result["report"]["checks"][0]["check_id"] == "static:parse:conf.yaml"


def test_from_report_reproduces_the_same_files(repo):
    (repo / "calc.py").write_text("def add(a, b):\n    return a * b\n", encoding="utf-8")
    _, first = _run(repo, "calc.py")
    (repo / "prior.json").write_text(json.dumps(first), encoding="utf-8")
    code = verify_change.main(["--root", str(repo), "--from-report", str(repo / "prior.json"),
                               "--out", str(repo / "again.json")])
    again = json.loads((repo / "again.json").read_text(encoding="utf-8"))
    assert code == 1 and again["files"] == first["files"]


def test_cli_runs_as_a_script(repo):
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    proc = subprocess.run([sys.executable, str(Path(verify_change.__file__)), "--root", str(repo),  # nosec B603 - fixed interpreter argv
                           "--files", "calc.py"], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert json.loads(proc.stdout)["checks_ok"] is True


def test_missing_requested_file_is_not_silently_dropped(repo):
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    code, result = _run(repo, "calc.py", "gone.py")
    assert code == 2 and not result["checks_ok"]
    missing = [c for c in result["report"]["checks"] if c["check_id"] == "static:exists:gone.py"]
    assert missing and missing[0]["status"] == "unavailable"


def test_file_rewritten_during_the_checks_invalidates_them(repo):
    """A check binds to the content it ran on; a test that rewrites the source
    leaves passes that prove nothing about the final content."""
    (repo / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "tests" / "test_calc.py").write_text(
        TEST + "\n\ndef test_rewrite():\n    import pathlib\n"
        "    p = pathlib.Path(__file__).resolve().parent.parent / 'calc.py'\n"
        "    p.write_text(p.read_text() + '\\n# changed\\n')\n", encoding="utf-8")
    code, result = _run(repo, "calc.py")
    assert code == 2
    assert any(c["status"] == "untrusted" and "changed while the checks ran" in c["reason"]
               for c in result["report"]["checks"])
