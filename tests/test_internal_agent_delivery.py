"""Regression: a ship-code task is DONE only when its work reached GitHub.

Production builds exclude ``.git`` (``.dockerignore``), so the agent used to work
in a git-less copy of the app: commits failed, nothing was pushed, the copy was
deleted, and the task still went DONE. No ``agent/task-*`` PR ever opened.
"""

from __future__ import annotations

import tempfile

import pytest

from runtimes.adapters import delivery
from runtimes.adapters.delivery import assess_delivery, clone_repo_workspace, parse_github_repo
from runtimes.base import TaskSpec


def _assess(**over):
    args = dict(
        did_work=True, output="report", auto_commit=True, task_type="portfolio_initiative",
        changed_files=["a.py"], commits=["abc"], pr_url="https://github.com/o/r/pull/1",
        judge_verdict="APPROVED",
    )
    args.update(over)
    return assess_delivery(**args)


def test_delivered_pr_is_done():
    out = _assess()
    assert out.success is True and out.task_status is None


def test_changes_without_pr_fail_with_stage():
    out = _assess(pr_url=None)
    assert out.success is False
    assert "committed but never pushed" in out.output
    assert "never committed" in _assess(pr_url=None, commits=[]).output


def test_no_change_code_task_goes_to_review():
    out = _assess(changed_files=[], commits=[], pr_url=None)
    assert out.success is True and out.task_status == "in_review"


def test_no_change_general_task_unchanged():
    out = _assess(changed_files=[], commits=[], pr_url=None, task_type="general")
    assert out.success is True and out.task_status is None


def test_report_only_run_unchanged():
    out = _assess(auto_commit=False, pr_url=None, commits=[])
    assert out.success is True and out.task_status is None


def test_judge_rejected_goes_to_review():
    assert _assess(judge_verdict="rejected").task_status == "in_review"


def test_failed_run_stays_failed():
    assert _assess(did_work=False).success is False


@pytest.mark.parametrize("url", [
    "https://evil.com/o/r", "http://github.com/o/r", "https://github.com/o", "file:///etc",
    "https://github.com/o/r/../../x",
])
def test_parse_rejects_non_github(url):
    assert parse_github_repo(url) is None


async def test_clone_keeps_token_out_of_url_and_config(monkeypatch):
    calls: list[tuple] = []

    async def _fake_git(*args, cwd=None):
        calls.append(args)
        return 0, ""

    monkeypatch.setattr(delivery, "_git", _fake_git)
    tmp = await clone_repo_workspace("https://github.com/o/r", "master", "tok123", "t1")
    try:
        assert tmp is not None
        clone = calls[0]
        assert "https://github.com/o/r.git" in clone
        assert not any("tok123" in a for a in clone)  # only base64 in a one-off -c header
        assert any(a.startswith("http.https://github.com/.extraheader=") for a in clone)
        assert ("config", "user.email", delivery.AGENT_GIT_EMAIL) in calls
    finally:
        tmp.cleanup()


async def test_clone_failure_returns_none(monkeypatch):
    async def _fake_git(*args, cwd=None):
        return 128, "fatal: auth failed for tok123"

    monkeypatch.setattr(delivery, "_git", _fake_git)
    assert await clone_repo_workspace("https://github.com/o/r", "master", "tok123", "t1") is None


async def test_adapter_fails_task_whose_changes_never_shipped(monkeypatch):
    """End-to-end through the real adapter: files changed, no PR → not success."""
    from runtimes.adapters import internal_agent
    from runtimes.adapters.internal_agent import InternalAgentAdapter

    async def _fake_run(self, *args, **kwargs):  # noqa: ANN001
        return {
            "steps": [{"status": "applied", "changed_files": ["x.py"]}],
            "report": "changed x.py", "commits": [], "pr_url": None,
            "judge": {"verdict": "APPROVED"},
        }

    async def _no_clone(*a, **k):
        return None

    # Patch the class the adapter imported: other tests reload agent.loop.
    monkeypatch.setattr(internal_agent.AgentRunner, "run", _fake_run)
    monkeypatch.setattr(
        "runtimes.adapters.internal_agent.clone_repo_workspace", _no_clone, raising=False
    )
    with tempfile.TemporaryDirectory() as tmp:
        adapter = InternalAgentAdapter({"workspace_root": tmp})
        spec = TaskSpec(
            task_id="t-ship", instruction="x", workspace_path=tmp,
            task_type="portfolio_initiative",
            context={"auto_commit": True, "repo_url": "https://github.com/o/r"},
        )
        result = await adapter.execute(spec)
    assert result.success is False
    assert result.output.startswith("Not delivered")
