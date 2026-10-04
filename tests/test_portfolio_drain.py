"""tests/test_portfolio_drain.py — portfolio work drains and agents stay busy.

Regressions from the operator's report: SAM did nothing on "pick up portfolio
work"; finished portfolio work came back as duplicate tasks and stayed queued
on the board; agents sat idle while one slow task held the dispatcher.
"""

from __future__ import annotations

import asyncio
import time

import pytest

import tasks.store as task_store_mod
from agents.portfolio import Initiative, InitiativeStatus, PortfolioManager
from tasks import portfolio_intake as pi
from tasks.dispatcher import TaskDispatcher
from tasks.models import Task, TaskStatus
from tasks.store import TaskStore


def _init(title: str, source: str = "roadmap", **kw) -> Initiative:
    return Initiative(initiative_id=title[:8], title=title, business_value=8, time_criticality=5,
                      risk_reduction=3, job_size=kw.pop("job_size", 3), source=source, **kw)


def _portfolio(*inits: Initiative) -> PortfolioManager:
    mgr = PortfolioManager()
    for i in inits:
        mgr.register(i)
    return mgr


def _ptask(title: str, status: TaskStatus, *, created: float, source_id: str) -> Task:
    return Task(owner_id="system", title=f"[portfolio] {title}", source="portfolio",
                source_id=source_id, status=status, created_at=created)


@pytest.fixture
def store(monkeypatch) -> TaskStore:
    fresh = TaskStore()
    monkeypatch.setattr(task_store_mod, "_global_store", fresh)
    return fresh


# ── identity ──────────────────────────────────────────────────────────────────

def test_identity_ignores_which_signal_won():
    """Same work from a bug-log row and a GitHub issue must share one task id."""
    a = _init("Fix: login loop", source="bug")
    b = _init("Fix: Login loop!", source="roadmap")
    assert pi.portfolio_source_id(a) == pi.portfolio_source_id(b)
    assert pi.portfolio_key("[portfolio] Fix: login loop") == pi.portfolio_key(a.title)


# ── no re-creation, board drains ──────────────────────────────────────────────

async def test_done_task_under_legacy_id_is_not_recreated_and_initiative_leaves_queue(store):
    await store.create(_ptask("Implement auth", TaskStatus.DONE, created=1.0,
                              source_id="portfolio:legacyhash0000"))
    auth, ci = _init("Implement auth"), _init("Add CI pipeline")
    portfolio = _portfolio(auth, ci)

    created = await pi.materialize_committed(portfolio, store=store, cap=5)

    assert [t.title for t in created] == ["[portfolio] Add CI pipeline"]
    assert auth.status.value == "done"
    assert auth not in portfolio.prioritized()          # gone from the board queue
    assert ci.status.value == "in_progress"


async def test_second_pass_creates_nothing(store):
    portfolio = _portfolio(_init("Implement auth"))
    assert len(await pi.materialize_committed(portfolio, store=store, cap=5)) == 1
    rebuilt = _portfolio(_init("Implement auth", source="bug"))   # rebuild, new signal
    assert await pi.materialize_committed(rebuilt, store=store, cap=5) == []
    assert len(store._mem) == 1


async def test_board_sync_marks_running_work_in_progress(store):
    await store.create(_ptask("Implement auth", TaskStatus.IN_PROGRESS, created=1.0, source_id="x"))
    portfolio = _portfolio(_init("Implement auth"))
    assert await pi.sync_board_status(portfolio, store=store) == 1
    assert next(iter(portfolio._initiatives.values())).status.value == "in_progress"


# ── duplicates ────────────────────────────────────────────────────────────────

async def test_duplicates_are_cleaned_keeping_the_done_task(store):
    keep = _ptask("Implement auth", TaskStatus.DONE, created=1.0, source_id="a")
    extra_done = _ptask("Implement auth", TaskStatus.DONE, created=2.0, source_id="b")
    open_dup = _ptask("Implement auth", TaskStatus.TODO, created=3.0, source_id="c")
    for t in (keep, extra_done, open_dup):
        await store.create(t)

    index = await pi.portfolio_task_index(store)
    result = await pi.dedupe_portfolio_tasks(index, store)

    assert (result.closed, result.deleted) == (1, 1)
    assert (await store.get(keep.task_id)).status is TaskStatus.DONE
    assert await store.get(extra_done.task_id) is None
    assert (await store.get(open_dup.task_id)).status is TaskStatus.WONT_DO


async def test_running_duplicate_is_left_alone(store):
    first = _ptask("Implement auth", TaskStatus.TODO, created=1.0, source_id="a")
    running = _ptask("Implement auth", TaskStatus.IN_PROGRESS, created=2.0, source_id="b")
    for t in (first, running):
        await store.create(t)
    index = await pi.portfolio_task_index(store)
    await pi.dedupe_portfolio_tasks(index, store)
    assert (await store.get(running.task_id)).status is TaskStatus.IN_PROGRESS


# ── failed work is retried, boundedly ────────────────────────────────────────

async def test_failed_portfolio_task_is_retried_up_to_the_limit(store):
    failed = _ptask("Implement auth", TaskStatus.FAILED, created=1.0, source_id="a")
    await store.create(failed)

    assert await pi.retry_failed(await pi.portfolio_task_index(store), store, max_retries=1) == 1
    again = await store.get(failed.task_id)
    assert again.status is TaskStatus.TODO and again.pending_agent_run

    again.status = TaskStatus.FAILED
    await store.update(again)
    assert await pi.retry_failed(await pi.portfolio_task_index(store), store, max_retries=1) == 0


# ── self-heal purge keeps the portfolio record ───────────────────────────────

async def test_purge_keeps_finished_portfolio_tasks(store, monkeypatch):
    monkeypatch.setenv("SELF_HEAL_PURGE_ENABLED", "true")
    from services.self_heal import _heal_purge_backlog

    old = time.time() - 30 * 86400
    portfolio_done = _ptask("Implement auth", TaskStatus.DONE, created=old, source_id="a")
    other_done = Task(owner_id="u", title="old chore", status=TaskStatus.DONE)
    for t in (portfolio_done, other_done):
        t.updated_at = old
        await store.create(t)
        t.updated_at = old
        await store.update(t)
        store._mem[t.task_id]["updated_at"] = old

    await _heal_purge_backlog()
    assert await store.get(portfolio_done.task_id) is not None
    assert await store.get(other_done.task_id) is None


# ── dispatcher keeps every slot busy ─────────────────────────────────────────

class _PendingStore:
    def __init__(self, tasks):
        self.tasks = {t.task_id: t for t in tasks}

    async def list_pending(self, *, limit):
        return [t for t in self.tasks.values() if t.pending_agent_run][:limit]

    async def reconcile_stranded_tasks(self, **_):
        return 0


class _Coordinator:
    def __init__(self, store, slow_id):
        self.store, self.slow_id = store, slow_id
        self.started: list[str] = []
        self.release_slow = asyncio.Event()
        self._active_task_ids: set[str] = set()

    async def execute(self, task_id):
        self.started.append(task_id)
        if task_id == self.slow_id:
            await self.release_slow.wait()
        self.store.tasks[task_id].pending_agent_run = False


def _queued(n):
    return [Task(owner_id="o", task_id=f"t{i}", title=f"T{i}", pending_agent_run=True) for i in range(n)]


async def test_free_slot_is_refilled_while_a_slow_task_runs(monkeypatch):
    """Regression: a batch waited on its slowest task, leaving the other slots idle."""
    from packages.config import settings
    monkeypatch.setattr(settings, "portfolio_auto_materialize_every_polls", 0)
    store = _PendingStore(_queued(3))
    coord = _Coordinator(store, slow_id="t0")
    dispatcher = TaskDispatcher(workspace_root=".", store=store, coordinator=coord, max_concurrency=2)

    await dispatcher._poll_and_execute()          # t0 (slow) + t1 start
    await asyncio.sleep(0)                         # t1 finishes, t0 still running
    await dispatcher._poll_and_execute()          # must not wait for t0
    await asyncio.sleep(0)

    assert coord.started == ["t0", "t1", "t2"]
    assert coord.started.count("t0") == 1          # never picked twice
    coord.release_slow.set()
    await dispatcher.drain()


async def test_idle_dispatcher_pulls_in_portfolio_work(monkeypatch):
    from packages.config import settings
    import tasks.autonomy_triage as triage
    import tasks.dispatcher as disp

    calls = []

    async def _materialize():
        calls.append(1)
        return 0

    monkeypatch.setattr(triage, "materialize_portfolio", _materialize)
    monkeypatch.setattr(settings, "portfolio_auto_materialize_every_polls", 10_000)
    monkeypatch.setattr(disp, "_IDLE_PORTFOLIO_EVERY", 1)
    store = _PendingStore([])
    dispatcher = TaskDispatcher(workspace_root=".", store=store,
                                coordinator=_Coordinator(store, slow_id=""), max_concurrency=2)
    await dispatcher._poll_and_execute()
    assert calls == [1]


# ── SAM picks up portfolio work ──────────────────────────────────────────────

async def test_sam_picks_up_portfolio_work(store, monkeypatch):
    import importlib

    import tasks.autonomy_triage as triage
    from agent.sam import SamAgent

    # test_portfolio_api.py reloads these modules; patch the live sys.modules copy.
    papi = importlib.import_module("agents.portfolio_api")

    async def _materialize():
        return 2

    svc = papi.PortfolioService()
    svc.portfolio = _portfolio(_init("A", status=InitiativeStatus.IN_PROGRESS),
                               _init("B", status=InitiativeStatus.DONE), _init("C"))
    monkeypatch.setattr(triage, "materialize_portfolio", _materialize)
    monkeypatch.setattr(papi, "_SERVICE", svc)

    reply = await SamAgent().process_command("pick up portfolio work", is_admin=True)
    assert "Picked up 2 portfolio initiatives" in reply
    assert "1 initiatives queued, 1 in flight, 1 done" in reply

    refused = await SamAgent().process_command("pick up portfolio work", is_admin=False)
    assert "needs an admin" in refused


# ── learning loop actually runs ──────────────────────────────────────────────

async def test_dispatcher_runs_session_retro(monkeypatch):
    """Regression: run_retro_cycle was registered as a loop but never called."""
    import services.session_retro as retro
    import tasks.dispatcher as disp
    from packages.config import settings

    calls = []

    async def _retro():
        calls.append(1)
        return {"routed": 1}

    monkeypatch.setattr(retro, "run_retro_cycle", _retro)
    monkeypatch.setattr(disp, "_RETRO_EVERY", 1)
    monkeypatch.setattr(settings, "portfolio_auto_materialize_every_polls", 0)
    store = _PendingStore([])
    dispatcher = TaskDispatcher(workspace_root=".", store=store,
                                coordinator=_Coordinator(store, slow_id=""), max_concurrency=1)
    await dispatcher._poll_and_execute()
    assert calls == [1]


def test_session_retro_is_on_by_default(monkeypatch):
    from services.session_retro import retro_enabled

    monkeypatch.delenv("SESSION_RETRO_ENABLED", raising=False)
    assert retro_enabled() is True
    monkeypatch.setenv("SESSION_RETRO_ENABLED", "false")
    assert retro_enabled() is False


def test_portfolio_controls_are_live_and_override(monkeypatch):
    import os

    from packages.config import control_overrides, settings
    from packages.config.control_registry import get_control

    assert get_control("PORTFOLIO_AUTO_MATERIALIZE_EVERY_POLLS").default == "60"
    retry = get_control("PORTFOLIO_RETRY_MAX")
    assert retry.live and retry.default == "2"
    before = {k: os.environ.get(k) for k in ("PORTFOLIO_RETRY_MAX",)}
    applied = dict(control_overrides._applied)
    try:
        control_overrides.apply_overrides({"PORTFOLIO_RETRY_MAX": "5"})
        assert settings.portfolio_retry_max == 5
    finally:
        for k, v in before.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        control_overrides._applied.clear()
        control_overrides._applied.update(applied)
        control_overrides.apply_overrides({})
        control_overrides._applied.clear()
        control_overrides._applied.update(applied)


def test_portfolio_prompt_keeps_definition_of_done_for_long_descriptions():
    """A long initiative description must not truncate away the definition of done."""
    from types import SimpleNamespace

    from tasks.portfolio_intake import _DEFINITION_OF_DONE, map_initiative_to_task

    initiative = SimpleNamespace(
        title="Big initiative", description="x" * 10_000, horizon=None, source="manual",
    )
    assert map_initiative_to_task(initiative).prompt.endswith(_DEFINITION_OF_DONE)
