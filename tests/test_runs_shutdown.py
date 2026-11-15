"""Phase 2 F: graceful shutdown hands every live run to recovery at once."""
from __future__ import annotations

import asyncio

import pytest

from packages.runs import task_binding
from packages.runs.models import RunState
from tasks.models import TaskStatus
from tests._runs_task_fixtures import (FakeRuntime, coordinator, queued_task,
                                       reset_process_state, sqlite_pair)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")


@pytest.mark.anyio
async def test_shutdown_marks_the_run_recovering_and_releases_the_lease(tmp_path):
    async with sqlite_pair(tmp_path) as (worker, other):
        task = await queued_task(worker)
        entered, box = asyncio.Event(), {}

        async def body(spec):
            box["binding"] = task_binding.current_run.get()
            entered.set()
            await asyncio.Event().wait()  # runs until the worker is shut down

        job = asyncio.create_task(coordinator(worker, FakeRuntime(body)).execute(task.task_id))
        await entered.wait()
        binding = box["binding"]
        assert task_binding.active_bindings() == [binding]

        assert await task_binding.shutdown_all() == 1
        assert task_binding.active_bindings() == []
        assert binding.heartbeat.lost.is_set() or binding.fenced
        run = await task_binding.run_store_for(other).get(binding.run_id)
        assert run.state is RunState.RECOVERING
        lease = await other._run_lease().current(task.task_id)
        assert lease["holder"] == ""  # released: another process may claim it now

        # The dispatcher is cancelled after the shutdown write: the cancelled
        # execution must not overwrite the task with its own outcome.
        job.cancel()
        with pytest.raises(BaseException):
            await job
        stored = await other.get(task.task_id)
        assert stored.status is TaskStatus.IN_PROGRESS
        assert (await task_binding.run_store_for(other).get(binding.run_id)).state \
            is RunState.RECOVERING


@pytest.mark.anyio
async def test_background_stop_releases_runs_before_cancelling_the_dispatcher(monkeypatch):
    from services import background

    order: list[str] = []

    async def fake_shutdown_all(reason="shutdown"):
        order.append(f"runs:{reason}")
        return 0

    class _Dispatcher:
        def stop(self):
            order.append("dispatcher")

    class _Runtime:
        async def stop(self):
            order.append("runtime")

    monkeypatch.setattr(task_binding, "shutdown_all", fake_shutdown_all)
    idle = asyncio.create_task(asyncio.Event().wait())
    bg = background.BackgroundServices(runtime_manager=_Runtime(), dispatcher=_Dispatcher(),
                                       dispatcher_task=idle)
    await bg.stop()
    assert order[:2] == ["runs:shutdown", "dispatcher"] and order[-1] == "runtime"
