"""Pre-PR checks (agent/pr_gate.py) and how their result decides a task's outcome.

Regression for the first agent PRs on GitHub (2026-10-04): #1656 shipped a test
importing a module that was never written; #1658–#1660 were three root-level
async_queue.py files with no tests and no changelog, one per retry.
"""
from __future__ import annotations

from pathlib import Path

from agent.pr_gate import pr_blockers
from runtimes.adapters.delivery import assess_delivery


def _repo(tmp_path: Path, files: dict[str, str]) -> Path:
    for rel, body in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return tmp_path


_CL = "## [Unreleased]\n- entry\n"


def test_code_without_tests_or_changelog_is_blocked(tmp_path):
    root = _repo(tmp_path, {"async_queue.py": "X = 1\n"})
    blockers = pr_blockers(root, ["async_queue.py"])
    assert any("without tests" in b for b in blockers)
    assert any("changelog" in b for b in blockers)


def test_test_importing_a_missing_module_is_blocked(tmp_path):
    root = _repo(tmp_path, {"tests/test_bus.py": "from portfolio.message_bus import MessageBus\n\n"
                                                  "def test_x():\n    MessageBus()\n"})
    assert any("Tests fail" in b for b in pr_blockers(root, ["tests/test_bus.py"]))


def test_syntax_error_is_blocked(tmp_path):
    root = _repo(tmp_path, {"mod.py": "def broken(:\n"})
    assert pr_blockers(root, ["mod.py"])[0].startswith("Changed files do not compile")


def test_complete_change_passes(tmp_path):
    root = _repo(tmp_path, {
        "pkg/__init__.py": "",
        "pkg/mod.py": "def add(a, b):\n    return a + b\n",
        "tests/test_mod.py": "from pkg.mod import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        "CHANGELOG.md": _CL, "docs/changelog.md": _CL,
    })
    changed = ["pkg/mod.py", "tests/test_mod.py", "CHANGELOG.md", "docs/changelog.md"]
    assert pr_blockers(root, changed) == []


def test_docs_only_change_needs_nothing(tmp_path):
    root = _repo(tmp_path, {"docs/guide.md": "# hi\n"})
    assert pr_blockers(root, ["docs/guide.md"]) == []


def _assess(**over):
    args = dict(did_work=True, output="r", auto_commit=True, task_type="portfolio_initiative",
                changed_files=["a.py"], commits=["c"], pr_url=None, judge_verdict="",
                pr_blockers=["Tests fail: x"])
    args.update(over)
    return assess_delivery(**args)


def test_blocked_pr_fails_with_the_reasons():
    out = _assess()
    assert out.success is False
    assert "pre-PR checks" in out.output and "Tests fail" in out.output


def test_opened_pr_with_failed_steps_goes_to_review_not_retry():
    out = _assess(did_work=False, pr_url="https://github.com/o/r/pull/9", pr_blockers=[])
    assert out.success is True and out.task_status == "in_review"
    assert "pull/9" in out.review_reason


async def test_runner_gates_only_the_files_its_applied_steps_changed(tmp_path):
    from agent.loop import AgentRunner

    _repo(tmp_path, {"async_queue.py": "X = 1\n"})
    runner = AgentRunner(ollama_base="http://localhost:1", workspace_root=str(tmp_path))
    steps = [
        {"status": "applied", "changed_files": ["async_queue.py"]},
        {"status": "failed", "changed_files": ["ignored.py"]},
    ]
    blockers = await runner._pr_blockers(steps)
    assert any("without tests" in b for b in blockers)
    assert await runner._pr_blockers([]) == []
