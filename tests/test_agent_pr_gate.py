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


# ── 2026-10-08: the gate saw only .py files (#1694, #1696, #1695, #1697) ──────

import subprocess  # noqa: E402  # nosec B404 - fixed git argv in a tmp repo

import pytest  # noqa: E402

from agent.models import AgentPlan, AgentStep  # noqa: E402
from agent.pr_gate import (  # noqa: E402
    judge_blockers,
    render_pr_body,
    resolve_base,
    review_diff,
    run_pr_gate,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(  # nosec B603 B607 - fixed git argv
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=root, check=True, capture_output=True, text=True,
    ).stdout.strip()


def _based_repo(tmp_path: Path, before: dict[str, str], after: dict[str, str | None]) -> tuple[Path, str]:
    """A git repo whose first commit is ``before``; ``after`` is applied and committed on top."""
    _repo(tmp_path, before)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    base = _git(tmp_path, "rev-parse", "HEAD")
    for rel, body in after.items():
        if body is None:
            (tmp_path / rel).unlink()
        else:
            _repo(tmp_path, {rel: body})
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "agent")
    return tmp_path, base


_LINES = "".join(f"<p>line {i}</p>\n" for i in range(200))


def test_replay_1696_app_shell_rewrite_is_blocked(tmp_path):
    root, base = _based_repo(
        tmp_path,
        {"frontend/src/App.js": _LINES, "index.html": _LINES},
        {"frontend/src/App.js": "export default () => null;\n", "index.html": "<!doctype html>\n"},
    )
    report = run_pr_gate(root, ["frontend/src/App.js", "index.html"],
                         goal="Identify pages that lack internal links and add relevant internal links",
                         planned_files=["index.html"], base_ref=base)
    text = "\n".join(report.blockers)
    assert "Protected paths changed" in text and "frontend/src/App.js" in text
    assert "removes far more than it adds" in text and "index.html (-200/+1)" in text
    assert "plan did not name: frontend/src/App.js" in text


def test_replay_1694_root_text_files_need_a_changelog(tmp_path):
    root = _repo(tmp_path, {"llms.txt": "# x\n", "robots.txt": "Sitemap: /s.xml\n"})
    assert any("changelog" in b for b in run_pr_gate(root, ["llms.txt", "robots.txt"]).blockers)


def test_gutting_an_unprotected_file_is_blocked_unless_the_goal_asks(tmp_path):
    path = "frontend/src/v5/screens/Home.jsx"
    root, base = _based_repo(tmp_path, {path: _LINES}, {path: "x\n"})
    blocked = run_pr_gate(root, [path], goal="add a footer link", planned_files=[path], base_ref=base)
    assert any("removes far more" in b for b in blocked.blockers)
    asked = run_pr_gate(root, [path], goal="Remove the legacy Home screen",
                        planned_files=[path], base_ref=base)
    assert not any("removes far more" in b for b in asked.blockers)


def test_deleting_a_file_is_blocked(tmp_path):
    root, base = _based_repo(tmp_path, {"svc/a.py": "X = 1\n"}, {"svc/a.py": None})
    report = run_pr_gate(root, ["svc/a.py"], goal="tidy svc", base_ref=base)
    assert any("svc/a.py (-1/+0, deleted)" in b for b in report.blockers)


def test_additive_change_passes_with_evidence(tmp_path):
    cl = "## [Unreleased]\n- entry\n"
    root, base = _based_repo(
        tmp_path,
        {"pkg/__init__.py": "", "pkg/mod.py": "def add(a, b):\n    return a + b\n",
         "CHANGELOG.md": "## [Unreleased]\n", "docs/changelog.md": "## [Unreleased]\n"},
        {"pkg/mod.py": "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n",
         "tests/test_mod.py": "from pkg.mod import sub\n\ndef test_sub():\n    assert sub(3, 1) == 2\n",
         "CHANGELOG.md": cl, "docs/changelog.md": cl},
    )
    changed = ["pkg/mod.py", "tests/test_mod.py", "CHANGELOG.md", "docs/changelog.md"]
    report = run_pr_gate(root, changed, goal="add sub", planned_files=["pkg/"], base_ref=base)
    assert report.ok, report.blockers
    joined = "\n".join(report.evidence)
    assert "nothing gutted" in joined and "1 passed" in joined
    assert "all changes inside the 1 planned path(s)" in joined


def test_files_outside_the_plan_are_blocked_but_tests_and_changelogs_are_not(tmp_path):
    root = _repo(tmp_path, {"a/x.txt": "1\n", "b/y.txt": "2\n"})
    changed = ["a/x.txt", "b/y.txt", "tests/test_x.py", "CHANGELOG.md"]
    blockers = run_pr_gate(root, changed, planned_files=["./a/x.txt"]).blockers
    assert any(b.startswith("Changed files the plan did not name: b/y.txt.") for b in blockers)


def test_model_config_change_runs_the_catalogue_guard_suite(tmp_path):
    root = _repo(tmp_path, {
        "config/models.yaml": "x: 1\n",
        "tests/test_one_model_catalogue.py": "def test_no_retired_ids():\n    assert False, 'retired id'\n",
    })
    blockers = run_pr_gate(root, ["config/models.yaml"]).blockers
    assert any("Tests fail" in b and "retired id" in b for b in blockers)


def test_frontend_change_without_node_modules_says_tests_were_not_run(tmp_path):
    root = _repo(tmp_path, {"frontend/src/v5/X.jsx": "export const X = 1;\n"})
    report = run_pr_gate(root, ["frontend/src/v5/X.jsx"])
    assert any("NOT run" in e for e in report.evidence)


def test_the_gate_protects_itself():
    from agent.pr_gate import PROTECTED_PATHS
    assert {"agent/pr_gate.py", "tests/test_agent_pr_gate.py"} <= set(PROTECTED_PATHS)


@pytest.mark.parametrize("judge,blocked", [
    ({"verdict": "APPROVED", "correctness": "PASS", "security": "PASS"}, False),
    ({"verdict": "APPROVED_WITH_CONDITIONS", "correctness": "WARN"}, False),
    ({"verdict": "REJECTED", "notes": "rewrote App.js"}, True),
    ({"verdict": "BLOCKED", "notes": "no output"}, True),
    ({"verdict": "APPROVED", "correctness": "FAIL"}, True),
    ({}, False),
])
def test_judge_blockers(judge, blocked):
    assert bool(judge_blockers(judge)) is blocked


def test_resolve_base_and_review_diff(tmp_path):
    root, base = _based_repo(tmp_path, {"a.txt": "1\n"}, {"a.txt": "2\n"})
    assert resolve_base(root, "master", 1) == base
    assert resolve_base(root, "master", 0) is None
    diff = review_diff(root, base)
    assert "-1" in diff and "+2" in diff
    assert review_diff(root, None) == "" and review_diff(root, "nope") == ""


def test_pr_body_carries_plan_evidence_and_verdict():
    plan = AgentPlan(goal="g", steps=[AgentStep(id=1, description="do it", files=["a.py"],
                                                type="edit", acceptance="test passes")])
    from agent.pr_gate import GateReport
    body = render_pr_body("g", plan, GateReport(evidence=["pytest tests/t.py: 1 passed"]),
                          {"verdict": "APPROVED", "correctness": "PASS", "security": "PASS"}, ["abcdef123"])
    assert "1. do it — `a.py` (done when: test passes)" in body
    assert "- pytest tests/t.py: 1 passed" in body and "verdict: APPROVED" in body and "`abcdef1`" in body


async def test_runner_sizes_and_scopes_against_the_plan(tmp_path):
    from agent.loop import AgentRunner

    root, _ = _based_repo(tmp_path, {"svc/a.txt": _LINES}, {"svc/a.txt": "gone\n", "svc/b.txt": "new\n"})
    runner = AgentRunner(ollama_base="http://localhost:1", workspace_root=str(root))
    plan = AgentPlan(goal="tweak a", steps=[AgentStep(id=1, description="d", files=["svc/a.txt"], type="edit")])
    steps = [{"status": "applied", "changed_files": ["svc/a.txt", "svc/b.txt"]}]
    blockers = await runner._pr_blockers(steps, plan, ["c1"])
    assert any("removes far more" in b for b in blockers)
    assert any("plan did not name: svc/b.txt" in b for b in blockers)
    brief = await runner._judge_brief(plan, steps, ["c1"])
    assert "Planned files: svc/a.txt" in brief and "+gone" in brief


# ── 2026-10-08: playbook artifacts — plan.md, REVIEW.md, protected feedback loop ──

def test_plan_artifact_is_a_reviewable_plan_file():
    from agent.pr_gate import plan_artifact

    plan = AgentPlan(goal="Add a footer link!", risks=["nav breaks"], steps=[
        AgentStep(id=1, description="edit footer", files=["web/footer.js"], type="edit", acceptance="link renders")])
    rel, body = plan_artifact(plan, "2026-10-08")
    assert rel == "docs/plans/agent/2026-10-08-add-a-footer-link.md"
    assert body.startswith("# Plan: Add a footer link!")
    assert "- `web/footer.js`" in body and "1. edit footer Done when: link renders" in body
    assert "- nav breaks" in body


def test_the_plan_file_is_outside_scope_and_changelog_checks(tmp_path):
    root = _repo(tmp_path, {"docs/plans/agent/x.md": "# Plan\n"})
    assert run_pr_gate(root, ["docs/plans/agent/x.md"], planned_files=["src/a.py"]).ok


def test_review_policy_is_read_and_truncated(tmp_path):
    from agent.pr_gate import review_policy

    assert review_policy(tmp_path) == ""
    (tmp_path / "REVIEW.md").write_text("x" * 5000)
    assert review_policy(tmp_path).endswith("(truncated)")


def test_assertions_removed_from_an_existing_test_block_the_pr(tmp_path):
    root, base = _based_repo(
        tmp_path,
        {"tests/test_a.py": "def test_a():\n    assert 1\n    assert 2\n"},
        {"tests/test_a.py": "def test_a():\n    assert 1\n"},
    )
    blockers = run_pr_gate(root, ["tests/test_a.py"], base_ref=base).blockers
    assert any("tests/test_a.py (assertions -1/+0, skips added: 0)" in b for b in blockers)


def test_jest_skip_in_an_existing_test_blocks_the_pr(tmp_path):
    path = "frontend/src/__tests__/x.test.js"
    root, base = _based_repo(tmp_path, {path: "test('a', () => { expect(1).toBe(1); });\n"},
                             {path: "test.skip('a', () => { expect(1).toBe(1); });\n"})
    assert any("skips added: 1" in b for b in run_pr_gate(root, [path], base_ref=base).blockers)


async def test_runner_commits_the_plan_and_shows_review_policy_to_the_judge(tmp_path):
    from agent.loop import AgentRunner

    root, _ = _based_repo(tmp_path, {"REVIEW.md": "## Passes\n- Bugs\n"}, {"a.txt": "1\n"})
    runner = AgentRunner(ollama_base="http://localhost:1", workspace_root=str(root))
    plan = AgentPlan(goal="tweak a", steps=[AgentStep(id=1, description="d", files=["a.txt"], type="edit")])
    shas = await runner._commit_plan_artifact(plan)
    assert len(shas) == 1
    assert "docs/plans/agent/" in _git(root, "show", "--name-only", "--format=", shas[0])
    brief = await runner._judge_brief(plan, [{"status": "applied"}], ["c"])
    assert "Review policy (REVIEW.md in this repository):" in brief and "- Bugs" in brief
