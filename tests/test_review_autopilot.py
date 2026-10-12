"""tasks/review_autopilot.py — a verifier clears the review queue (operator request 2026-10-12)."""

from __future__ import annotations

import pytest

from packages.config import control_overrides
from tasks import review_autopilot as ra
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore
from tasks.verification import TaskVerification

PR = "https://github.com/acme/shop/pull/7"


@pytest.fixture(autouse=True)
def _controls():
    control_overrides.apply_overrides({})
    yield
    control_overrides.apply_overrides({})


@pytest.fixture
def store() -> TaskStore:
    return TaskStore()


def _parked(title: str = "Add retry to the webhook sender", **kw) -> Task:
    return Task(owner_id="o@x.com", title=title, description="Retry 3 times with backoff.",
                requires_approval=True, pending_agent_run=False, **kw)


def _in_review(**kw) -> Task:
    task = Task(owner_id="o@x.com", title="Fix the cart total", agent_id="dev",
                status=TaskStatus.IN_REVIEW, review_reason="Waiting", execution_approved=True, **kw)
    return task


def _judge(monkeypatch, verdict: str | None, calls: list | None = None):
    async def judge(task):
        if calls is not None:
            calls.append(task.task_id)
        return None if verdict is None else {"verdict": verdict, "notes": f"{verdict.lower()} because"}

    monkeypatch.setattr(ra, "_judge_plan", judge)


# ── before a run ─────────────────────────────────────────────────────────────

async def test_a_clear_task_is_approved_and_queued(store, monkeypatch):
    _judge(monkeypatch, "APPROVED")
    task = await store.create(_parked())
    result = await ra.run_review_autopilot(store)
    saved = await store.get(task.task_id)
    assert result.approved == 1
    assert saved.execution_approved and saved.status is TaskStatus.IN_PROGRESS and saved.pending_agent_run
    assert any(e.actor == ra.ACTOR and e.event_type == "review_autopilot_approved" for e in saved.execution_log)


async def test_a_sloppy_task_stays_for_a_person_with_the_reason_and_is_not_asked_again(store, monkeypatch):
    calls: list = []
    _judge(monkeypatch, "REJECTED", calls)
    task = await store.create(_parked("do stuff"))
    await ra.run_review_autopilot(store)
    await ra.run_review_autopilot(store)
    saved = await store.get(task.task_id)
    assert not saved.execution_approved and saved.status is not TaskStatus.WONT_DO
    assert any("Not approved automatically: rejected because" in c.body for c in saved.comments)
    assert calls == [task.task_id]  # judged once, then left alone


async def test_outward_facing_work_is_never_touched(store, monkeypatch):
    calls: list = []
    _judge(monkeypatch, "APPROVED", calls)
    deploy = await store.create(_parked("Deploy v5", task_type="deploy"))
    risky = await store.create(_parked("Rotate keys", tags=["risk:secrets"]))
    await ra.run_review_autopilot(store)
    assert calls == []
    assert not (await store.get(deploy.task_id)).execution_approved
    assert not (await store.get(risky.task_id)).execution_approved


async def test_no_reviewer_model_leaves_the_task_for_the_next_pass(store, monkeypatch):
    _judge(monkeypatch, None)
    task = await store.create(_parked())
    await ra.run_review_autopilot(store)
    saved = await store.get(task.task_id)
    assert not saved.execution_approved and not saved.comments


async def test_control_off_does_nothing(store, monkeypatch):
    control_overrides.apply_overrides({"AGENCY_REVIEW_AUTOPILOT": "false"})
    calls: list = []
    _judge(monkeypatch, "APPROVED", calls)
    await store.create(_parked())
    result = await ra.run_review_autopilot(store)
    assert calls == [] and result.approved == 0


# ── after a run ──────────────────────────────────────────────────────────────

async def test_a_review_task_with_a_passing_verdict_is_completed(store):
    task = _in_review()
    task.verification = TaskVerification(verdict="PASS", verifier="agent:judge", checked=["pytest: passed"])
    await store.create(task)
    await ra.run_review_autopilot(store)
    assert (await store.get(task.task_id)).status is TaskStatus.DONE


def _verifier(monkeypatch, verdict: str, *, tests_passed: bool = True):
    from tasks import independent_verifier as iv

    async def verify(task, result):
        assert PR in result.output  # the stored output is what the verifier reads
        checks = ["pytest -x tests/test_cart.py (E2B sandbox): passed"] if tests_passed else []
        return {"judge": {"verdict": verdict, "notes": "looked at it"}, "pr_url": PR, "commits": [],
                "steps": [{"description": "change", "status": "applied", "changed_files": ["cart.py"],
                           "executed_checks": checks}], "ui_evidence": []}

    monkeypatch.setattr(iv, "verify", verify)


async def test_a_linked_pr_that_the_verifier_passes_is_completed(store, monkeypatch):
    _verifier(monkeypatch, "APPROVED")
    task = await store.create(_in_review(result=f"Opened {PR}"))
    await ra.run_review_autopilot(store)
    saved = await store.get(task.task_id)
    assert saved.status is TaskStatus.DONE
    assert saved.verification.verdict == "PASS" and saved.verification.verifier == ra.ACTOR


async def test_a_linked_pr_without_proof_stays_for_a_person(store, monkeypatch):
    _verifier(monkeypatch, "APPROVED", tests_passed=False)  # approval with no tests run is not proof
    task = await store.create(_in_review(result=f"Opened {PR}"))
    await ra.run_review_autopilot(store)
    saved = await store.get(task.task_id)
    assert saved.status is TaskStatus.IN_REVIEW
    assert any(c.body.startswith("Not completed automatically") for c in saved.comments)


async def test_a_review_task_with_nothing_to_check_gets_one_fresh_run(store):
    task = await store.create(_in_review(result="I fixed it."))
    await ra.run_review_autopilot(store)
    saved = await store.get(task.task_id)
    assert saved.status is TaskStatus.IN_PROGRESS and saved.pending_agent_run
    # Parked again later: no second automatic re-run.
    saved.status = TaskStatus.IN_REVIEW
    saved.pending_agent_run = False
    await store.update(saved)
    result = await ra.run_review_autopilot(store)
    assert result.requeued == 0


async def test_the_fresh_run_gets_a_fresh_rework_budget():
    from tasks.verification import _automatic_failures

    task = _in_review()
    for _ in range(3):
        task.add_log("Independent verification FAILED", event_type="verification_failed", actor="system:x")
    assert _automatic_failures(task) == 3
    task.add_log("re-run", event_type=ra.REQUEUED, actor=ra.ACTOR)
    assert _automatic_failures(task) == 0


def test_control_is_live_high_risk_and_on_by_default():
    from packages.config.control_registry import get_control

    c = get_control("AGENCY_REVIEW_AUTOPILOT")
    assert c.live is True and c.default == "true"
    assert ra.enabled() is True


async def test_schedule_runs_one_pass_at_a_time_in_the_background(monkeypatch):
    import asyncio

    started: list = []
    gate = asyncio.Event()

    async def slow_pass(store=None):
        started.append(1)
        await gate.wait()

    monkeypatch.setattr(ra, "run_review_autopilot", slow_pass)
    monkeypatch.setattr(ra, "_running", None)
    ra.schedule()
    ra.schedule()  # still running: no second pass
    await asyncio.sleep(0)
    assert started == [1]
    gate.set()
    await asyncio.sleep(0)


async def test_a_person_deciding_mid_check_wins(store, monkeypatch):
    # Verifier finding 2026-10-12: the judge call takes minutes; a person who
    # rejected the task meanwhile must not be overwritten by a stale approval.
    from tasks.service import TaskWorkflowService

    task = await store.create(_parked())

    async def judge(t):
        fresh = await store.get(t.task_id)
        TaskWorkflowService(store=store).approve_execution(fresh, actor="priya@x.com", approved=False)
        await store.update(fresh)
        return {"verdict": "APPROVED", "notes": "fine"}

    monkeypatch.setattr(ra, "_judge_plan", judge)
    result = await ra.run_review_autopilot(store)
    saved = await store.get(task.task_id)
    assert saved.status is TaskStatus.WONT_DO and not saved.execution_approved
    assert result.approved == 0


async def test_a_person_acting_during_verification_wins(store, monkeypatch):
    from tasks import independent_verifier as iv

    task = await store.create(_in_review(result=f"Opened {PR}"))

    async def verify(t, r):
        fresh = await store.get(t.task_id)
        fresh.add_log("looked at it", event_type="comment_added", actor="priya@x.com")
        await store.update(fresh)
        return {"judge": {"verdict": "APPROVED"}, "steps": [{"status": "applied", "changed_files": ["a.py"],
                "executed_checks": ["pytest: passed"]}], "ui_evidence": [], "commits": []}

    monkeypatch.setattr(iv, "verify", verify)
    await ra.run_review_autopilot(store)
    assert (await store.get(task.task_id)).status is TaskStatus.IN_REVIEW
