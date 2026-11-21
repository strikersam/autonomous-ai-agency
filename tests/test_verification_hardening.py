"""Brief section 9 "must never" rules, exercised against the real code paths.

A verifier rejection blocks done, a missing test result is not a pass, a verifier
error is not a pass, and the reviewer model is called with no tools at all.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from agent import empirical_verify
from packages.config import control_overrides
from runtimes.base import TaskResult
from tasks import independent_verifier as iv
from tasks.models import Task, TaskStatus
from tasks.verification import settle_success, verification_from_run

PR = "https://github.com/acme/shop/pull/42"


@pytest.fixture(autouse=True)
def _controls():
    control_overrides.apply_overrides({})
    yield
    control_overrides.apply_overrides({})


def _task() -> Task:
    return Task(owner_id="o@x.com", title="Fix the cart", status=TaskStatus.IN_PROGRESS, agent_id="dev")


def _result() -> TaskResult:
    return TaskResult(runtime_id="claude_code", task_id="t1", success=True, output=f"Opened {PR}")


def _stub(monkeypatch, *, verdict="APPROVED", checks=("pytest -x: passed",), issues=()):
    async def exercise(pr):
        return {"files": ["cart.py"], "diff": "+x", "ui": [],
                "checks": empirical_verify.CheckOutcome(issues=list(issues), checks=list(checks))}

    async def judge(brief):
        return {"verdict": verdict, "security": "PASS", "correctness": "PASS", "notes": "n"}

    monkeypatch.setattr(iv, "_exercise", exercise)
    monkeypatch.setattr(iv, "_judge", judge)


def _settle(monkeypatch, **stub) -> Task:
    _stub(monkeypatch, **stub)
    run = asyncio.run(iv.verify(_task(), _result()))
    task = _task()
    settle_success(task, run, actor="runtime:claude_code")
    return task


def test_verifier_rejection_blocks_done(monkeypatch):
    task = _settle(monkeypatch, verdict="REJECTED")
    assert task.status is not TaskStatus.DONE
    assert task.verification is not None and task.verification.verdict == "FAIL"


def test_failing_tests_block_done_even_when_the_reviewer_approves(monkeypatch):
    task = _settle(monkeypatch, checks=(), issues=("tests failed: 1 != 2",))
    assert task.status is not TaskStatus.DONE


def test_missing_test_result_is_not_a_pass(monkeypatch):
    task = _settle(monkeypatch, checks=())
    assert task.status is TaskStatus.IN_REVIEW
    assert task.verification is None


def test_control_baseline_a_real_pass_does_reach_done(monkeypatch):
    task = _settle(monkeypatch)
    assert task.status is TaskStatus.DONE and task.verification.verdict == "PASS"


@pytest.mark.parametrize("broken", ["exercise", "judge"])
def test_verifier_error_is_not_a_pass(monkeypatch, broken):
    _stub(monkeypatch)

    async def boom(*_a, **_k):
        raise RuntimeError("sandbox exploded")

    monkeypatch.setattr(iv, "_" + broken, boom)
    run = asyncio.run(iv.verify(_task(), _result()))
    assert run is None and verification_from_run(run) is None
    task = _task()
    settle_success(task, run, actor="runtime:claude_code")
    assert task.status is TaskStatus.IN_REVIEW


def test_reviewer_model_is_called_without_tools(monkeypatch):
    """The judge only gets chat messages: it has no tool, so it cannot write anything."""
    import agent.loop as loop_mod
    import packages.ai.failover_client as fc

    seen: list[dict] = []

    async def fake_chat(payload, timeout_sec=0.0):
        seen.append(payload)
        return SimpleNamespace(text='{"verdict": "APPROVED"}')

    monkeypatch.setattr(fc, "failover_chat_completion", fake_chat)
    monkeypatch.setattr(loop_mod, "_resolve_role_model", lambda role: "m")
    assert asyncio.run(iv._judge("brief"))["verdict"] == "APPROVED"
    assert len(seen) == 1
    assert not {"tools", "tool_choice", "functions", "function_call"} & set(seen[0])
    assert {m["role"] for m in seen[0]["messages"]} == {"system", "user"}


def test_verification_cannot_be_forged_by_an_agent_actor():
    from tasks.verification import is_human_actor

    assert not is_human_actor("agent:dev") and not is_human_actor("runtime:claude_code")
