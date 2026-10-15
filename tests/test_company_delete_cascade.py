"""Deleting a company must remove everything scheduled for it.

Regression for "I still see stuff running for a company I deleted 2 months ago":
the delete removed the company rows and the in-memory schedules but left the
durable schedule rows (rehydrated on every boot) and every task the schedules and
CEO directives had spawned, and nothing guarded the scheduler or the dispatcher
against work for a company that no longer exists.
"""
from __future__ import annotations

import asyncio
import logging

import pytest

from models.company_graph import Company
from packages.scheduler import scheduler as scheduler_module
from packages.scheduler.scheduler import AgentScheduler
from services import company_cleanup
from services.company_graph import CompanyGraphService
from services.company_graph_store import SQLiteStore
from tasks.automation import TaskAutomationService
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore


class _ActivityLog:
    """Stand-in for the activity_log collection the deletion record goes to."""

    def __init__(self) -> None:
        self.docs: list[dict] = []

    async def insert_one(self, doc: dict) -> None:
        self.docs.append(dict(doc))

    async def find_one(self, query: dict) -> dict | None:
        return next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolated company store, durable schedule store, scheduler and task store."""
    import agent.schedule_store as schedule_store_module
    from agents import store as agent_store_module
    from agents.store import AgentStore
    from services import company_agency

    companies = SQLiteStore()
    companies._db_path = str(tmp_path / "companies.db")
    monkeypatch.setattr("services.company_graph_store.get_company_graph_store", lambda: companies)

    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setattr(schedule_store_module, "_SQLITE_DB_PATH", str(tmp_path / "sched.db"))
    durable = schedule_store_module.ScheduleStore()
    assert durable.mode == "sqlite"

    sched = AgentScheduler(persistence=durable)
    fired: list[str] = []
    sched.set_on_fire(lambda job: fired.append(job.job_id))
    monkeypatch.setattr(scheduler_module, "_scheduler_instance", sched)
    monkeypatch.setattr(company_agency, "_company_agency_service", None)

    tasks = TaskStore()
    monkeypatch.setattr("tasks.store._global_store", tasks)
    activity = _ActivityLog()
    monkeypatch.setattr(company_cleanup, "_activity_log", lambda: activity)
    monkeypatch.setattr(agent_store_module, "_store", AgentStore())

    class Env:
        pass

    e = Env()
    e.companies, e.durable, e.sched, e.tasks, e.fired = companies, durable, sched, tasks, fired
    e.activity = activity
    e.service = CompanyGraphService(store=companies)
    yield e
    sched.shutdown()


async def _company(env, name):
    return await env.companies.create_company(Company(name=name, domain=f"{name.lower()}.com"))


async def _schedule(env, company_id, suffix):
    job = env.sched.create(
        name=f"company:{company_id}:{suffix}", cron="0 3 * * *", instruction="scan",
        tags=["company-agency", f"company:{company_id}", suffix],
    )
    await asyncio.sleep(0.05)  # let the fire-and-forget persist task land
    return job


async def _task(env, company_id, status=TaskStatus.TODO, *, via_field=False):
    task = Task(
        owner_id="system", title=f"work for {company_id}", status=status, pending_agent_run=True,
        tags=[] if via_field else [f"company:{company_id}"],
        company_id=company_id if via_field else None,
    )
    return await env.tasks.create(task)


def _durable_ids(env, company_id):
    tag = f"company:{company_id}"
    return {d["job_id"] for d in env.durable.load_all() if tag in (d.get("tags") or [])}


def _memory_ids(env, company_id):
    tag = f"company:{company_id}"
    return {j.job_id for j in env.sched.list() if tag in (j.tags or [])}


@pytest.mark.asyncio
async def test_delete_company_removes_schedules_tasks_and_never_fires(env):
    doomed, keeper = await _company(env, "Kyndryl"), await _company(env, "Keeper")
    job = await _schedule(env, doomed.id, "security-audit")
    await _schedule(env, doomed.id, "health-scan")
    keeper_job = await _schedule(env, keeper.id, "health-scan")
    todo = await _task(env, doomed.id)
    running = await _task(env, doomed.id, TaskStatus.IN_PROGRESS)
    by_field = await _task(env, doomed.id, via_field=True)
    done = await _task(env, doomed.id, TaskStatus.DONE)
    keeper_task = await _task(env, keeper.id)
    assert len(_durable_ids(env, doomed.id)) == 2  # precondition: rows really persisted

    assert await env.service.delete_company(doomed.id) is True

    assert _memory_ids(env, doomed.id) == set()
    assert _durable_ids(env, doomed.id) == set()
    env.sched._fire(job.job_id)
    assert env.fired == []  # the deleted job cannot fire
    for t in (todo, running, by_field):
        got = await env.tasks.get(t.task_id)
        assert got.status is TaskStatus.WONT_DO and got.pending_agent_run is False
    assert (await env.tasks.get(done.task_id)).status is TaskStatus.DONE  # history kept
    pending = {t.task_id for t in await env.tasks.list_pending()}
    assert pending == {keeper_task.task_id}
    # Another company is untouched.
    assert _memory_ids(env, keeper.id) == {keeper_job.job_id}
    assert _durable_ids(env, keeper.id) == {keeper_job.job_id}


@pytest.mark.asyncio
async def test_durable_row_not_loaded_in_memory_is_removed_and_not_rehydrated(env):
    """The root cause for old deletes: the row lives only in the durable store."""
    doomed, _ = await _company(env, "Kyndryl"), await _company(env, "Keeper")
    job = await _schedule(env, doomed.id, "health-scan")
    env.sched._jobs.pop(job.job_id)  # process restarted: nothing loaded yet

    await env.service.delete_company(doomed.id)

    assert _durable_ids(env, doomed.id) == set()
    fresh = AgentScheduler(persistence=env.durable)
    try:
        await fresh.hydrate()
        assert fresh.list() == []
    finally:
        fresh.shutdown()


@pytest.mark.asyncio
async def test_sweep_reaps_orphans_of_a_company_deleted_long_ago(env):
    live = await _company(env, "Live")
    ghost = "co_kyndryl_deleted_2_months_ago"  # never existed in this store
    ghost_job = await _schedule(env, ghost, "health-scan")
    env.sched._jobs.pop(ghost_job.job_id)  # persisted only
    in_memory_ghost = await _schedule(env, ghost, "security-audit")
    live_job = await _schedule(env, live.id, "health-scan")
    ghost_task = await _task(env, ghost, TaskStatus.FAILED)
    live_task = await _task(env, live.id)

    result = await company_cleanup.reap_orphaned_company_state()

    assert result == {"schedules": 2, "tasks": 1}
    assert _durable_ids(env, ghost) == set() and _memory_ids(env, ghost) == set()
    assert in_memory_ghost.job_id not in {j.job_id for j in env.sched.list()}
    assert (await env.tasks.get(ghost_task.task_id)).status is TaskStatus.WONT_DO
    assert (await env.tasks.get(live_task.task_id)).status is TaskStatus.TODO
    assert _memory_ids(env, live.id) == {live_job.job_id}
    # Idempotent: a second sweep finds nothing.
    assert await company_cleanup.reap_orphaned_company_state() == {"schedules": 0, "tasks": 0}


@pytest.mark.asyncio
async def test_scheduler_hook_skips_and_reaps_job_of_deleted_company(env):
    await _company(env, "Live")
    ghost_job = await _schedule(env, "co_ghost", "health-scan")
    sibling = await _schedule(env, "co_ghost", "security-audit")
    automation = TaskAutomationService(store=env.tasks)

    assert await automation.handle_scheduled_job(ghost_job) is None

    assert await env.tasks.list_all() == []  # no task was created
    assert _memory_ids(env, "co_ghost") == set() and _durable_ids(env, "co_ghost") == set()
    assert sibling.job_id not in {j.job_id for j in env.sched.list()}


@pytest.mark.asyncio
async def test_scheduler_hook_still_creates_tasks_for_live_company(env):
    live = await _company(env, "Live")
    job = await _schedule(env, live.id, "health-scan")
    task = await TaskAutomationService(store=env.tasks).handle_scheduled_job(job)
    assert task is not None and f"company:{live.id}" in task.tags
    assert _memory_ids(env, live.id) == {job.job_id}


@pytest.mark.asyncio
async def test_dispatcher_filter_cancels_orphans_and_keeps_live_work(env):
    live = await _company(env, "Live")
    orphan = await _task(env, "co_ghost")
    kept = await _task(env, live.id)
    plain = await env.tasks.create(Task(owner_id="u", title="no company", pending_agent_run=True))

    runnable = await company_cleanup.filter_orphaned_tasks(env.tasks, [orphan, kept, plain])

    assert [t.task_id for t in runnable] == [kept.task_id, plain.task_id]
    assert (await env.tasks.get(orphan.task_id)).status is TaskStatus.WONT_DO


@pytest.mark.asyncio
async def test_unknown_company_state_is_never_treated_as_deleted(env, monkeypatch):
    """A lookup error, or an empty company store, must not delete anything."""
    job = await _schedule(env, "co_x", "health-scan")
    task = await _task(env, "co_x")

    # 1. Empty store: it cannot tell us co_x was deleted.
    assert await company_cleanup.reap_orphaned_company_state() == {"schedules": 0, "tasks": 0}

    # 2. Store raises.
    await _company(env, "Live")

    async def boom(_id):
        raise RuntimeError("db down")

    monkeypatch.setattr(env.companies, "get_company", boom)
    assert await company_cleanup.reap_orphaned_company_state() == {"schedules": 0, "tasks": 0}
    assert _memory_ids(env, "co_x") == {job.job_id}
    assert (await env.tasks.get(task.task_id)).status is TaskStatus.TODO


@pytest.mark.asyncio
async def test_failed_teardown_step_is_logged_and_sweep_finishes_the_job(env, monkeypatch, caplog):
    doomed, _ = await _company(env, "Kyndryl"), await _company(env, "Keeper")
    await _schedule(env, doomed.id, "health-scan")
    task = await _task(env, doomed.id)

    async def boom(_company_id):
        raise RuntimeError("store unavailable")

    real_cancel = company_cleanup.cancel_company_tasks
    monkeypatch.setattr(company_cleanup, "cancel_company_tasks", boom)
    with caplog.at_level(logging.ERROR, logger="qwen-proxy"):
        assert await env.service.delete_company(doomed.id) is True

    assert any("teardown incomplete" in r.getMessage() and "cancel tasks" in r.getMessage()
               for r in caplog.records)
    assert _durable_ids(env, doomed.id) == set()  # the other steps still ran
    assert (await env.tasks.get(task.task_id)).status is TaskStatus.TODO  # this one failed
    monkeypatch.setattr(company_cleanup, "cancel_company_tasks", real_cancel)
    await company_cleanup.reap_orphaned_company_state()
    assert (await env.tasks.get(task.task_id)).status is TaskStatus.WONT_DO


def test_company_id_from_tags_ignores_the_agency_marker_tag():
    assert company_cleanup.company_id_from_tags(["company-agency", "company:abc", "x"]) == "abc"
    assert company_cleanup.company_id_from_tags(["company-agency", "company:"]) is None
    assert company_cleanup.company_id_from_tags(None) is None


# ── Review findings on #1764 ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_last_company_with_failed_teardown_is_still_reaped(env, monkeypatch):
    """Codex P1: deleting the only company left its orphans live forever."""
    only = await _company(env, "Kyndryl")
    await _schedule(env, only.id, "health-scan")
    task = await _task(env, only.id)

    async def boom(_company_id):
        raise RuntimeError("store unavailable")

    real_cancel = company_cleanup.cancel_company_tasks
    monkeypatch.setattr(company_cleanup, "cancel_company_tasks", boom)
    assert await env.service.delete_company(only.id) is True
    monkeypatch.setattr(company_cleanup, "cancel_company_tasks", real_cancel)
    assert await env.companies.list_companies(limit=1) == []  # no company left

    await company_cleanup.reap_orphaned_company_state()

    assert (await env.tasks.get(task.task_id)).status is TaskStatus.WONT_DO


@pytest.mark.asyncio
async def test_stale_worker_save_after_delete_is_cancelled_before_it_runs(env):
    """CodeRabbit: a worker holding a stale model re-saves the task as runnable."""
    only = await _company(env, "Kyndryl")
    task = await _task(env, only.id, TaskStatus.IN_PROGRESS)
    stale = await env.tasks.get(task.task_id)  # the worker loaded it before the delete

    await env.service.delete_company(only.id)
    stale.status, stale.pending_agent_run = TaskStatus.TODO, True  # transient failure path
    await env.tasks.update(stale)

    pending = await env.tasks.list_pending()
    assert await company_cleanup.filter_orphaned_tasks(env.tasks, pending) == []
    assert (await env.tasks.get(task.task_id)).status is TaskStatus.WONT_DO


@pytest.mark.asyncio
async def test_store_that_swallows_a_remove_error_is_reported_as_failed(env, monkeypatch):
    """Codex P2: ScheduleStore.remove() caught the error, so the purge claimed success."""
    doomed = await _company(env, "Kyndryl")
    job = await _schedule(env, doomed.id, "health-scan")

    real_remove = type(env.durable).remove

    def remove(self, job_id):  # the real method, against a backend that raises
        good, self._sqlite = self._sqlite, _Broken()
        try:
            return real_remove(self, job_id)
        finally:
            self._sqlite = good

    monkeypatch.setattr(type(env.durable), "remove", remove)
    result = await company_cleanup.purge_company_schedules(doomed.id)

    assert result == {"removed": 0, "failed": 1}
    assert _memory_ids(env, doomed.id) == {job.job_id}  # not forgotten while the row lives
    assert _durable_ids(env, doomed.id) == {job.job_id}


class _Broken:
    def execute(self, *_a, **_k):
        raise RuntimeError("sqlite locked")


@pytest.mark.asyncio
async def test_durable_read_failure_still_removes_in_memory_jobs(env, monkeypatch):
    """CodeRabbit: a load_all() error skipped even the jobs already in memory."""
    doomed = await _company(env, "Kyndryl")
    job = await _schedule(env, doomed.id, "health-scan")

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(env.durable, "load_all", boom)
    result = await env.sched.delete_by_tag(f"company:{doomed.id}")

    assert result == {"removed": 1, "failed": 1}  # failed: the store could not be read
    assert job.job_id not in {j.job_id for j in env.sched.list()}


@pytest.mark.asyncio
async def test_api_process_without_the_worker_store_still_purges_durable_rows(env, monkeypatch):
    """Codex P2: with RUN_BACKGROUND_IN_WEB=false the API scheduler read the wrong store."""
    doomed, _ = await _company(env, "Kyndryl"), await _company(env, "Keeper")
    await _schedule(env, doomed.id, "health-scan")  # persisted by the worker's scheduler
    api_sched = AgentScheduler(persistence=None)

    class OtherCollection:  # what _ensure_store() picks in the API process
        def load_all(self):
            return []

        def remove(self, _job_id):
            return None

    api_sched._store = OtherCollection()
    monkeypatch.setattr(scheduler_module, "_scheduler_instance", api_sched)
    try:
        assert await env.service.delete_company(doomed.id) is True
    finally:
        api_sched.shutdown()

    assert _durable_ids(env, doomed.id) == set()


@pytest.mark.asyncio
async def test_deletion_record_uses_the_real_store_without_booting_the_web_app(tmp_path, monkeypatch):
    """The record must work in the worker: no backend.server import, scheduler untouched."""
    import sys

    import db

    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    import packages.storage.sqlite as sqlite_module

    monkeypatch.setattr(sqlite_module, "_SQLITE_DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(db, "_store", None)
    worker_sched = AgentScheduler()
    monkeypatch.setattr(scheduler_module, "_scheduler_instance", worker_sched)
    monkeypatch.delitem(sys.modules, "backend.server", raising=False)
    try:
        assert await company_cleanup.record_company_deleted("co_gone") is True
        assert await company_cleanup._was_deleted("co_gone") is True
        assert await company_cleanup._was_deleted("co_alive") is False
        assert "backend.server" not in sys.modules
        assert scheduler_module.get_scheduler() is worker_sched
    finally:
        worker_sched.shutdown()
        monkeypatch.setattr(db, "_store", None)
