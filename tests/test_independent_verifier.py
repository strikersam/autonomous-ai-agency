"""Rule 49 for runtimes that have no judge of their own.

Claude Code, Hermes and the other external runtimes return prose. The
independent verifier checks out the pull request they opened in an E2B
sandbox, runs the matching tests, screenshots changed pages and asks a
reviewer model for a verdict; the task service then applies the usual rules.
"""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from agent import empirical_verify
from packages.config import control_overrides, settings
from runtimes.base import TaskResult
from tasks import independent_verifier as iv
from tasks.models import Task, TaskStatus
from tasks.verification import verification_from_run

PR = "https://github.com/acme/shop/pull/42"


def _result(output=f"Opened {PR}", runtime="claude_code"):
    return TaskResult(runtime_id=runtime, task_id="t1", success=True, output=output)


def _task():
    return Task(owner_id="o@x.com", title="Fix the cart total", status=TaskStatus.IN_PROGRESS, agent_id="dev")


@pytest.fixture(autouse=True)
def _controls():
    control_overrides.apply_overrides({})
    yield
    control_overrides.apply_overrides({})


def _stub(monkeypatch, *, verdict="APPROVED", checks=("pytest -x tests/test_cart.py (E2B sandbox): passed",),
          issues=(), files=("cart.py",), gap=None, ui=()):
    async def exercise(pr):
        if gap:
            return {"gap": gap}
        return {"files": list(files), "diff": "+fixed", "ui": list(ui),
                "checks": empirical_verify.CheckOutcome(issues=list(issues), checks=list(checks))}

    briefs = []

    async def judge(brief):
        briefs.append(brief)
        return {"verdict": verdict, "security": "PASS", "correctness": "PASS", "notes": "reviewed"} if verdict else None

    monkeypatch.setattr(iv, "_exercise", exercise)
    monkeypatch.setattr(iv, "_judge", judge)
    return briefs


# ── who needs it ──────────────────────────────────────────────────────────────

def test_only_runtimes_without_a_judge_need_it():
    assert iv.needs_independent_check("claude_code", None)
    assert iv.needs_independent_check("hermes", {"output": "x"})
    assert not iv.needs_independent_check("internal_agent", None)
    assert not iv.needs_independent_check("e2b", None)
    assert not iv.needs_independent_check("claude_code", {"judge": {"verdict": "APPROVED"}})


def test_finds_the_pull_request_in_output_metadata_or_artifacts():
    assert iv.find_pull_request(_result()) == ("https://github.com/acme/shop", 42)
    meta = TaskResult(runtime_id="hermes", task_id="t", success=True, output="done", metadata={"pr": PR})
    assert iv.find_pull_request(meta) == ("https://github.com/acme/shop", 42)
    art = TaskResult(runtime_id="hermes", task_id="t", success=True, output="done", artifacts=[{"url": PR}])
    assert iv.find_pull_request(art) == ("https://github.com/acme/shop", 42)
    assert iv.find_pull_request(_result(output="all good")) is None


def test_token_only_goes_to_the_platforms_own_repo(monkeypatch):
    import agent.agency as ag

    monkeypatch.setattr(ag, "_gh_repo", lambda: "acme/shop")
    monkeypatch.setattr(ag, "_gh_token", lambda: "ghp_x")
    assert iv._token_for("https://github.com/acme/shop") == "ghp_x"
    assert iv._token_for("https://github.com/evil/repo") is None


# ── verdicts ─────────────────────────────────────────────────────────────────

def test_approved_with_passing_tests_is_a_pass(monkeypatch):
    briefs = _stub(monkeypatch)
    run = asyncio.run(iv.verify(_task(), _result()))
    v = verification_from_run(run)
    assert v.verdict == "PASS"
    assert any("E2B sandbox): passed" in c for c in v.checked)
    assert f"Pull request {PR}" in v.evidence
    assert "Fix the cart total" in briefs[0] and "Opened" in briefs[0]


def test_failing_tests_are_a_fail_whatever_the_reviewer_says(monkeypatch):
    _stub(monkeypatch, checks=(), issues=("Scoped tests failed: assert 41 == 42",))
    v = verification_from_run(asyncio.run(iv.verify(_task(), _result())))
    assert v.verdict == "FAIL"
    assert any("41 == 42" in d for d in v.defects_found)


def test_approval_without_executed_tests_waits_for_a_person(monkeypatch):
    _stub(monkeypatch, checks=())
    assert verification_from_run(asyncio.run(iv.verify(_task(), _result()))) is None


def test_no_pull_request_means_approval_cannot_pass(monkeypatch):
    _stub(monkeypatch)
    run = asyncio.run(iv.verify(_task(), _result(output="I think it is done")))
    assert run["verifier_gap"] and verification_from_run(run) is None


def test_ui_change_needs_screenshots_here_too(monkeypatch):
    _stub(monkeypatch, files=("index.html", "cart.py"), ui=({"page": "index.html", "error": "browser down"},))
    assert verification_from_run(asyncio.run(iv.verify(_task(), _result()))) is None
    _stub(monkeypatch, files=("index.html", "cart.py"),
          ui=({"page": "index.html", "url": "https://h/index.html", "shot_id": "shot_0123456789abcdef"},))
    v = verification_from_run(asyncio.run(iv.verify(_task(), _result())))
    assert v.verdict == "PASS" and any(e.startswith("screenshot:shot_0123456789abcdef") for e in v.evidence)


def test_no_reviewer_model_means_no_verdict(monkeypatch):
    _stub(monkeypatch, verdict=None)
    assert asyncio.run(iv.verify(_task(), _result())) is None


def test_never_raises(monkeypatch):
    async def boom(pr):
        raise RuntimeError("sandbox exploded")

    monkeypatch.setattr(iv, "_exercise", boom)
    assert asyncio.run(iv.verify(_task(), _result())) is None


def test_judge_output_parsing():
    assert iv._parse_json('noise {"verdict": "APPROVED", "notes": "ok"} tail')["verdict"] == "APPROVED"
    assert iv._parse_json("no json") is None
    assert iv._parse_json('{"notes": "no verdict"}') is None


# ── task service wiring ──────────────────────────────────────────────────────

def _service():
    from tasks.service import TaskExecutionCoordinator

    svc = TaskExecutionCoordinator.__new__(TaskExecutionCoordinator)
    return svc


def test_service_uses_the_verifier_for_external_runtimes(monkeypatch):
    _stub(monkeypatch)
    task = _task()
    raw = asyncio.run(_service()._independent_check(task, _result(), None))
    assert raw["judge"]["verdict"] == "APPROVED"
    assert any(e.event_type == "verification_run" for e in task.execution_log)


def test_service_skips_it_when_the_control_is_off_or_the_runtime_judged_itself(monkeypatch):
    _stub(monkeypatch)
    svc = _service()
    assert asyncio.run(svc._independent_check(_task(), _result(runtime="internal_agent"), {"x": 1})) == {"x": 1}
    control_overrides.apply_overrides({"TASK_INDEPENDENT_VERIFIER": "false"})
    assert settings.task_independent_verifier is False
    assert asyncio.run(svc._independent_check(_task(), _result(), None)) is None


def test_control_is_live_and_on_by_default():
    from packages.config.control_registry import get_control

    assert get_control("TASK_INDEPENDENT_VERIFIER").live is True
    assert settings.task_independent_verifier is True


# ── sandbox PR checkout ──────────────────────────────────────────────────────

class _Sb:
    def __init__(self):
        self.cmds = []
        self.commands = SimpleNamespace(run=self.run)

    async def run(self, cmd, timeout=60):
        self.cmds.append(cmd)
        if "--name-only" in cmd:
            return SimpleNamespace(stdout="cart.py\nindex.html\n", stderr="", exit_code=0)
        if "| head -c" in cmd:
            return SimpleNamespace(stdout="diff --git a/cart.py", stderr="", exit_code=0)
        return SimpleNamespace(stdout="", stderr="", exit_code=0)

    async def set_timeout(self, t):
        return None


def test_checkout_pull_request_scrubs_the_token():
    from services.e2b_config import E2BConfig
    from services.e2b_sandbox import E2BSandboxSession

    s = E2BSandboxSession(E2BConfig(api_key="e2b_x"))
    s._sandbox = _Sb()
    out = asyncio.run(s.checkout_pull_request("https://github.com/acme/shop", 42, "ghp_secret"))
    assert out == {"changed_files": ["cart.py", "index.html"], "diff": "diff --git a/cart.py"}
    clone = s._sandbox.cmds[0]
    assert "pull/42/head" in clone and "remote set-url origin https://github.com/acme/shop 2>/dev/null; exit $rc" in clone
    assert all("ghp_secret" not in c for c in s._sandbox.cmds[1:])
