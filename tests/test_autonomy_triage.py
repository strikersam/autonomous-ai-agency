"""tests/test_autonomy_triage.py — CEO triage of tasks parked at the approval gate."""

from __future__ import annotations

import pytest

from tasks.autonomy_triage import TRIAGE_ACTOR, triage_gated_tasks
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore


def _parked(title: str, *, task_type: str = "bug_fix", promoted: bool = True,
            created_at: float = 1.0) -> Task:
    task = Task(
        owner_id="o@x.com", title=title, task_type=task_type,
        requires_approval=True, pending_agent_run=False, created_at=created_at,
    )
    if promoted:
        task.add_log("Auto-gated", event_type="approval_gate_promoted", actor="system:dispatcher")
    return task


@pytest.fixture
def store() -> TaskStore:
    return TaskStore()


@pytest.mark.asyncio
async def test_auto_promoted_pr_work_is_approved_and_requeued(store):
    task = _parked("Fix alert: provider timeout")
    await store.create(task)

    result = await triage_gated_tasks(store)

    saved = await store.get(task.task_id)
    assert result.approved == 1
    assert saved.execution_approved is True
    assert saved.pending_agent_run is True
    assert saved.status is TaskStatus.IN_PROGRESS
    assert any(TRIAGE_ACTOR in e.message for e in saved.execution_log)


@pytest.mark.asyncio
async def test_deliberately_gated_task_is_left_for_human(store):
    # Created with requires_approval on purpose (never auto-promoted).
    manual = _parked("Rotate the JWT secret", promoted=False)
    # Auto-promoted, but still outward-facing (a deploy has no merge gate).
    deploy = _parked("Deploy to production", task_type="deploy")
    await store.create(manual)
    await store.create(deploy)

    result = await triage_gated_tasks(store)

    assert result.left_for_human == 2
    for t in (manual, deploy):
        saved = await store.get(t.task_id)
        assert saved.execution_approved is False
        assert saved.status is TaskStatus.TODO


@pytest.mark.asyncio
async def test_duplicate_of_parked_task_is_rejected(store):
    first = _parked("Fix alert: task task_0a0ee0d9a3919559 failed", created_at=1.0)
    second = _parked("Fix alert: task task_1b2cc3d4e5f60718 failed", created_at=2.0)
    await store.create(first)
    await store.create(second)

    result = await triage_gated_tasks(store)

    assert result.approved == 1 and result.rejected == 1
    assert (await store.get(first.task_id)).execution_approved is True
    dup = await store.get(second.task_id)
    assert dup.status is TaskStatus.WONT_DO


@pytest.mark.asyncio
async def test_duplicate_of_queued_task_is_rejected(store):
    queued = Task(owner_id="o@x.com", title="Fix flaky login test", pending_agent_run=True)
    await store.create(queued)
    parked = _parked("Fix flaky login test")
    await store.create(parked)

    result = await triage_gated_tasks(store)

    assert result.rejected == 1
    assert (await store.get(parked.task_id)).status is TaskStatus.WONT_DO


@pytest.mark.asyncio
async def test_store_failure_is_swallowed(store, monkeypatch):
    async def _boom(**_kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(store, "list_awaiting_approval", _boom)
    result = await triage_gated_tasks(store)

    assert (result.approved, result.rejected) == (0, 0)


@pytest.mark.asyncio
async def test_dispatcher_runs_triage_on_cadence(store, monkeypatch, tmp_path):
    from packages.config import settings
    from tasks import autonomy_triage
    from tasks.dispatcher import TaskDispatcher

    calls = []

    async def _fake(s=None):
        calls.append(s)
        return autonomy_triage.TriageResult()

    async def _no_alerts(owner_id):
        return ""

    monkeypatch.setattr(autonomy_triage, "triage_gated_tasks", _fake)
    monkeypatch.setattr("agent.sam_actions.fix_alerts", _no_alerts)
    monkeypatch.setattr(settings, "agency_auto_triage", "true")
    monkeypatch.setattr(settings, "agency_auto_triage_every_polls", 2)
    dispatcher = TaskDispatcher(workspace_root=str(tmp_path), store=store)

    await dispatcher._poll_and_execute()
    assert calls == []
    await dispatcher._poll_and_execute()
    assert calls == [store]

    monkeypatch.setattr(settings, "agency_auto_triage", "false")
    await dispatcher._poll_and_execute()
    await dispatcher._poll_and_execute()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_numbered_titles_are_not_duplicates(store):
    a = _parked("Fix issue #41", created_at=1.0)
    b = _parked("Fix issue #42", created_at=2.0)
    await store.create(a)
    await store.create(b)

    result = await triage_gated_tasks(store)

    assert (result.approved, result.rejected) == (2, 0)


@pytest.mark.asyncio
async def test_deliberately_gated_duplicate_is_not_rejected(store):
    queued = Task(owner_id="o@x.com", title="Rotate the JWT secret", pending_agent_run=True)
    await store.create(queued)
    manual = _parked("Rotate the JWT secret", promoted=False)
    await store.create(manual)

    result = await triage_gated_tasks(store)

    assert (result.rejected, result.left_for_human) == (0, 1)
    assert (await store.get(manual.task_id)).status is TaskStatus.TODO


@pytest.mark.asyncio
async def test_portfolio_intake_builds_board_off_loop_and_materializes(monkeypatch):
    # Regression: portfolio initiatives only became tasks when someone pressed
    # refresh on the board — nothing ran the materializer on its own.
    import importlib
    import threading

    from tasks.autonomy_triage import materialize_portfolio

    # Patch the module object the code under test will import (other tests
    # swap agents.portfolio_api in sys.modules).
    portfolio_api = importlib.import_module("agents.portfolio_api")

    loop_thread = threading.get_ident()
    seen = {}

    class _Svc:
        def ensure_fresh(self):
            seen["thread"] = threading.get_ident()

    async def _materialize(svc):
        return ["task_a", "task_b"]

    monkeypatch.setattr(portfolio_api, "get_service", lambda: _Svc())
    monkeypatch.setattr(portfolio_api, "_materialize_and_log", _materialize)

    assert await materialize_portfolio() == 2
    assert seen["thread"] != loop_thread  # sync board build kept off the event loop


@pytest.mark.asyncio
async def test_portfolio_intake_failure_is_swallowed(monkeypatch):
    import importlib

    from tasks.autonomy_triage import materialize_portfolio

    portfolio_api = importlib.import_module("agents.portfolio_api")

    def _boom():
        raise RuntimeError("github down")

    monkeypatch.setattr(portfolio_api, "get_service", _boom)
    assert await materialize_portfolio() == 0


@pytest.mark.asyncio
async def test_dispatcher_runs_portfolio_intake_on_its_own_cadence(store, monkeypatch, tmp_path):
    from packages.config import settings
    from tasks import autonomy_triage
    from tasks.dispatcher import TaskDispatcher

    calls = []

    async def _fake():
        calls.append(1)
        return 0

    monkeypatch.setattr(autonomy_triage, "materialize_portfolio", _fake)
    monkeypatch.setattr(settings, "agency_auto_triage", "false")
    monkeypatch.setattr(settings, "portfolio_auto_materialize_every_polls", 3)
    dispatcher = TaskDispatcher(workspace_root=str(tmp_path), store=store)

    for _ in range(6):
        await dispatcher._poll_and_execute()
    assert len(calls) == 2

    monkeypatch.setattr(settings, "portfolio_auto_materialize_every_polls", 0)
    for _ in range(6):
        await dispatcher._poll_and_execute()
    assert len(calls) == 2


def _trend(title: str, *, owner: str = "system:trend-scoping", created_at: float = 1.0) -> Task:
    return Task(
        owner_id=owner, title=title, task_type="trend_scoping",
        tags=["trend-scoping", "gate:telegram"], requires_approval=True,
        pending_agent_run=False, created_at=created_at,
    )


@pytest.mark.asyncio
async def test_trend_code_change_is_approved_when_enabled(store, monkeypatch):
    # Regression: trend code-change tasks are created gated, so triage never
    # touched them and they piled up in "To be approved".
    from packages.config import settings

    monkeypatch.setattr(settings, "agency_triage_approve_trends", "true")
    task = _trend("[trend] Upgrade to FastAPI 0.120")
    await store.create(task)

    result = await triage_gated_tasks(store)

    saved = await store.get(task.task_id)
    assert result.approved == 1
    assert saved.execution_approved is True and saved.pending_agent_run is True


@pytest.mark.asyncio
async def test_trend_code_change_left_for_human_when_disabled(store, monkeypatch):
    from packages.config import settings

    monkeypatch.setattr(settings, "agency_triage_approve_trends", "false")
    task = _trend("[trend] Upgrade to FastAPI 0.120")
    await store.create(task)

    result = await triage_gated_tasks(store)

    assert (result.approved, result.left_for_human) == (0, 1)
    assert (await store.get(task.task_id)).status is TaskStatus.TODO


@pytest.mark.asyncio
async def test_trend_type_from_a_person_is_left_for_human(store, monkeypatch):
    from packages.config import settings

    monkeypatch.setattr(settings, "agency_triage_approve_trends", "true")
    task = _trend("[trend] something", owner="boss@x.com")
    await store.create(task)

    result = await triage_gated_tasks(store)

    assert result.left_for_human == 1


@pytest.mark.asyncio
async def test_duplicate_trend_is_rejected(store, monkeypatch):
    from packages.config import settings

    monkeypatch.setattr(settings, "agency_triage_approve_trends", "true")
    first = _trend("[trend] Adopt uv for installs", created_at=1.0)
    second = _trend("[trend] Adopt uv for installs!", created_at=2.0)
    await store.create(first)
    await store.create(second)

    result = await triage_gated_tasks(store)

    assert (result.approved, result.rejected) == (1, 1)
    assert (await store.get(second.task_id)).status is TaskStatus.WONT_DO
