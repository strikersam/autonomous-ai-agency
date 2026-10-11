"""Rule 49 — a task is done only with an independent verdict.

Covers the report built from an agent run (what was checked, what broke, what
got fixed), the state-machine gate, the direct-assignment path in the CEO
dispatcher, the live control, and POST /api/tasks/{id}/verification.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from packages.config import control_overrides, settings
from tasks.api import task_router
from tasks.models import Task, TaskStatus
from tasks.service import TaskWorkflowService
from tasks.store import TaskStore, set_task_store
from tasks.verification import (
    WAITING_REASON,
    TaskVerification,
    settle_success,
    verification_from_run,
)

RUN = {
    "steps": [
        {"description": "add retry", "status": "applied", "changed_files": ["a.py"],
         "resolved_issues": ["a.py: missing import of time"],
         "executed_checks": ["pytest -x tests/test_a.py: passed"]},
        {"description": "docs", "status": "applied", "changed_files": []},
    ],
    "judge": {"verdict": "APPROVED", "security": "PASS", "correctness": "PASS", "notes": "ok"},
    "commits": ["abc123"],
}


@pytest.fixture(autouse=True)
def _gate_on():
    control_overrides.apply_overrides({})
    yield
    control_overrides.apply_overrides({})


@pytest.fixture()
def store() -> TaskStore:
    s = TaskStore()
    set_task_store(s)
    return s


def _task(status: TaskStatus = TaskStatus.IN_PROGRESS) -> Task:
    return Task(owner_id="owner@x.com", title="t", status=status, agent_id="dev")


# ── report built from a run ──────────────────────────────────────────────────

def test_judge_approval_becomes_pass_with_checked_defects_and_fixes():
    v = verification_from_run(RUN)
    assert v.verdict == "PASS" and v.verifier == "agent:judge"
    assert any("passed the step verifier (1 file(s))" in c for c in v.checked)
    assert any("missing import of time" in d for d in v.defects_found)
    assert any("fixed on retry" in f for f in v.fixed)
    assert "Commit abc123" in v.evidence


@pytest.mark.parametrize("judge,expected", [
    ({"verdict": "APPROVED", "correctness": "WARN"}, "PASS+NOTES"),
    ({"verdict": "APPROVED_WITH_CONDITIONS"}, "PASS+NOTES"),
    ({"verdict": "REJECTED", "notes": "touches unplanned files"}, "FAIL"),
    ({"verdict": "BLOCKED"}, "FAIL"),
])
def test_judge_verdicts_map_onto_rule_49_verdicts(judge, expected):
    run = {"steps": RUN["steps"], "judge": judge}
    assert verification_from_run(run).verdict == expected


def test_no_judge_means_no_verdict():
    assert verification_from_run({"steps": [{"status": "applied"}]}) is None
    assert verification_from_run(None) is None


def test_an_approving_review_with_nothing_executed_is_not_a_pass():
    from tasks.verification import unbacked_note
    run = {"steps": [{"description": "x", "status": "applied", "changed_files": ["a.py"]}],
           "judge": {"verdict": "APPROVED"}}
    assert verification_from_run(run) is None
    assert "no tests or checks were run" in unbacked_note(run)
    assert unbacked_note(RUN) is None


def test_executed_checks_are_listed_as_what_was_checked():
    assert any("ran pytest -x tests/test_a.py: passed" in c for c in verification_from_run(RUN).checked)


def test_rejection_notes_are_listed_as_a_defect():
    v = verification_from_run({"steps": [], "judge": {"verdict": "REJECTED", "notes": "breaks login"}})
    assert "Judge: breaks login" in v.defects_found


# ── the state-machine gate ───────────────────────────────────────────────────

def test_agent_cannot_mark_done_without_a_verdict():
    task = _task()
    TaskWorkflowService(store=TaskStore()).transition(task, TaskStatus.DONE, actor="agent:dev")
    assert task.status is TaskStatus.IN_REVIEW
    assert task.review_reason == WAITING_REASON
    assert task.completed_at is None


def test_agent_reaches_done_with_a_passing_verdict():
    task = _task()
    task.verification = verification_from_run(RUN)
    TaskWorkflowService(store=TaskStore()).transition(task, TaskStatus.DONE, actor="agent:dev")
    assert task.status is TaskStatus.DONE


def _reject():
    return TaskVerification(verdict="FAIL", verifier="agent:judge", defects_found=["breaks login"])


def test_a_judge_fail_sends_work_back_with_the_defects_as_a_comment():
    task = _task()
    task.verification = _reject()
    TaskWorkflowService(store=TaskStore()).transition(task, TaskStatus.DONE, actor="agent:dev")
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.pending_agent_run is True
    assert any("breaks login" in c.body for c in task.comments)


def test_repeated_fails_park_for_a_person_instead_of_looping():
    wf = TaskWorkflowService(store=TaskStore())
    task = _task()
    for _ in range(2):
        task.verification = _reject()
        wf.transition(task, TaskStatus.DONE, actor="agent:dev")
        assert task.status is TaskStatus.IN_PROGRESS
    task.verification = _reject()
    wf.transition(task, TaskStatus.DONE, actor="agent:dev")
    assert task.status is TaskStatus.IN_REVIEW
    assert "needs a person" in task.review_reason


def test_a_person_acting_resets_the_rework_budget():
    from tasks.verification import _automatic_failures
    wf = TaskWorkflowService(store=TaskStore())
    task = _task()
    for _ in range(2):
        task.verification = _reject()
        wf.transition(task, TaskStatus.DONE, actor="agent:dev")
    task.add_log("comment", actor="priya@x.com")
    assert _automatic_failures(task) == 0


def test_settle_success_requeues_a_rejected_ceo_run():
    task = _task()
    settle_success(task, {"steps": [], "judge": {"verdict": "REJECTED", "notes": "wrong file"}},
                   actor="runtime:internal_agent")
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.pending_agent_run is True


def test_failed_verdict_from_review_sends_work_back():
    task = _task(TaskStatus.IN_REVIEW)
    task.review_reason = "x"
    task.verification = TaskVerification(verdict="FAIL", verifier="agent:judge")
    TaskWorkflowService(store=TaskStore()).transition(task, TaskStatus.DONE, actor="agent:dev")
    assert task.status is TaskStatus.IN_PROGRESS
    assert task.pending_agent_run is True


def test_a_person_marking_done_is_recorded_as_the_verifier():
    task = _task(TaskStatus.IN_REVIEW)
    task.review_reason = "x"
    TaskWorkflowService(store=TaskStore()).transition(task, TaskStatus.DONE, actor="priya@x.com")
    assert task.status is TaskStatus.DONE
    assert task.verification.verifier == "priya@x.com"
    assert task.verification.verdict == "PASS"


def test_control_off_restores_agent_self_completion():
    control_overrides.apply_overrides({"TASK_VERIFICATION_REQUIRED": "false"})
    assert settings.task_verification_required is False
    task = _task()
    TaskWorkflowService(store=TaskStore()).transition(task, TaskStatus.DONE, actor="agent:dev")
    assert task.status is TaskStatus.DONE


def test_control_is_live_and_on_by_default():
    from packages.config.control_registry import get_control

    assert get_control("TASK_VERIFICATION_REQUIRED").live is True
    assert settings.task_verification_required is True


# ── direct-assignment path (CEO dispatcher in backend/server.py) ────────────

def test_settle_success_with_judge_approval_is_done():
    task = _task()
    settle_success(task, RUN, actor="runtime:internal_agent")
    assert task.status is TaskStatus.DONE
    assert task.verification.verdict == "PASS"


def test_settle_success_without_a_verdict_waits_in_review():
    task = _task()
    settle_success(task, {"steps": []}, actor="runtime:internal_agent")
    assert task.status is TaskStatus.IN_REVIEW
    assert task.review_reason == WAITING_REASON


# ── POST /api/tasks/{id}/verification ────────────────────────────────────────

def _client(email: str = "priya@x.com", role: str = "admin") -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def inject_user(request: Request, call_next):
        request.state.user = SimpleNamespace(email=email, role=role)
        return await call_next(request)

    app.include_router(task_router)
    return TestClient(app)


@pytest.mark.asyncio
async def test_pass_on_a_waiting_task_completes_it_with_the_report(store):
    task = _task(TaskStatus.IN_REVIEW)
    task.review_reason = WAITING_REASON
    await store.create(task)
    body = {"verdict": "PASS", "checked": ["Ran the checkout flow on mobile"],
            "defects_found": ["Pay button overlapped"], "fixed": ["Pay button spacing"],
            "evidence": ["https://example.com/after.png"]}
    resp = _client().post(f"/api/tasks/{task.task_id}/verification", json=body)
    assert resp.status_code == 200, resp.text
    saved = resp.json()["task"]
    assert saved["status"] == "done"
    assert saved["verification"]["verifier"] == "priya@x.com"
    assert saved["verification"]["fixed"] == ["Pay button spacing"]


@pytest.mark.asyncio
async def test_fail_on_a_done_task_reopens_it_for_rework(store):
    task = _task(TaskStatus.DONE)
    await store.create(task)
    resp = _client().post(f"/api/tasks/{task.task_id}/verification",
                          json={"verdict": "FAIL", "defects_found": ["Totals wrong"]})
    assert resp.status_code == 200, resp.text
    assert resp.json()["task"]["status"] == "in_progress"
    assert resp.json()["requeued"] is True


@pytest.mark.asyncio
async def test_unknown_verdict_is_rejected(store):
    task = _task(TaskStatus.IN_REVIEW)
    task.review_reason = WAITING_REASON
    await store.create(task)
    resp = _client().post(f"/api/tasks/{task.task_id}/verification", json={"verdict": "LGTM"})
    assert resp.status_code == 422


def test_verification_requires_a_signed_in_user(store):
    app = FastAPI()
    app.include_router(task_router)
    resp = TestClient(app).post("/api/tasks/task_x/verification", json={"verdict": "PASS"})
    assert resp.status_code == 401


# ── regressions from the adversarial verification round ─────────────────────

def test_retry_retires_the_old_pass_so_new_work_needs_a_new_verdict():
    wf = TaskWorkflowService(store=TaskStore())
    task = _task()
    task.verification = verification_from_run(RUN)
    wf.transition(task, TaskStatus.DONE, actor="agent:dev")
    assert task.status is TaskStatus.DONE
    wf.retry(task, actor="priya@x.com")
    assert task.verification is None
    assert any(e.event_type == "verification_retired" for e in task.execution_log)
    wf.transition(task, TaskStatus.DONE, actor="agent:dev")
    assert task.status is TaskStatus.IN_REVIEW


def test_settle_success_ignores_a_verdict_from_earlier_work():
    task = _task()
    task.verification = verification_from_run(RUN)
    settle_success(task, {"steps": []}, actor="runtime:internal_agent")
    assert task.status is TaskStatus.IN_REVIEW
    assert task.verification is None


@pytest.mark.asyncio
async def test_an_agent_cannot_create_a_task_already_done():
    wf = TaskWorkflowService(store=TaskStore())
    task = Task(owner_id="o", title="t", status=TaskStatus.DONE)
    await wf.create_task(task, actor="agent:dev")
    assert task.status is TaskStatus.IN_REVIEW


@pytest.mark.asyncio
async def test_a_verdict_on_unfinished_work_is_refused(store):
    task = _task(TaskStatus.IN_PROGRESS)
    await store.create(task)
    resp = _client().post(f"/api/tasks/{task.task_id}/verification", json={"verdict": "PASS"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_fail_posts_the_defects_as_a_comment_for_the_rework_run(store):
    task = _task(TaskStatus.DONE)
    await store.create(task)
    resp = _client().post(f"/api/tasks/{task.task_id}/verification",
                          json={"verdict": "FAIL", "defects_found": ["Totals wrong"]})
    bodies = [c["body"] for c in resp.json()["task"]["comments"]]
    assert any("Totals wrong" in b for b in bodies)


@pytest.mark.parametrize("actor", ["agent:dev", "agent-123", "runtime:x", "system:cron", "ceo", "system", "judge:x",
                                   "internal_agent", "service:telegram", "api_key:abc"])
def test_software_actors_are_never_counted_as_the_human_verifier(actor):
    from tasks.verification import is_human_actor
    assert is_human_actor(actor) is False


@pytest.mark.parametrize("actor", ["priya@x.com", "64b7f0c2e1a2b3c4d5e6f7a8", "telegram_bot"])
def test_people_and_relayed_human_approvals_count(actor):
    from tasks.verification import is_human_actor
    assert is_human_actor(actor) is True
