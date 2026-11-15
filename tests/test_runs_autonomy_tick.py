"""Phase 2 B: /api/autonomy/tick binds its execution to a durable run like the coordinator."""
from __future__ import annotations

import pytest
from starlette.requests import Request

from packages.runs import task_binding
from packages.runs.models import RunState
from tests._runs_task_fixtures import queued_task, reset_process_state, sqlite_pair

_SECRET = "dummy-cron-secret"


@pytest.fixture(autouse=True)
def _fresh(monkeypatch):
    reset_process_state(monkeypatch)
    monkeypatch.setenv("RUNS_LEDGER_ENABLED", "true")
    monkeypatch.setenv("CRON_SECRET", _SECRET)
    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "true")
    monkeypatch.delenv("AGENCY_KILL_SWITCH", raising=False)


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/api/autonomy/tick",
                    "headers": [(b"x-cron-secret", _SECRET.encode())], "query_string": b""})


def _patch_adapter(monkeypatch, execute) -> None:
    from runtimes.adapters import internal_agent

    monkeypatch.setattr(internal_agent.InternalAgentAdapter, "execute", execute)


@pytest.mark.anyio
async def test_the_tick_records_a_run_and_releases_its_lease(tmp_path, monkeypatch):
    import backend.server as server
    from runtimes.base import TaskResult

    seen = {}

    async def execute(self, spec):
        seen["binding"] = task_binding.current_run.get()
        return TaskResult(runtime_id="internal", task_id=spec.task_id, success=False,
                          output="nope"), None

    _patch_adapter(monkeypatch, execute)
    async with sqlite_pair(tmp_path) as (web, other):
        task = await queued_task(web)
        monkeypatch.setattr("tasks.store.get_task_store", lambda: web)
        body = await server.autonomy_tick(_request())
        assert body["dispatch"]["task_id"] == task.task_id and body["dispatch"]["ran"] is True

        binding = seen["binding"]
        assert binding is not None and binding.recording  # the coordinator's binding
        assert task_binding.active_bindings() == []
        stored = await other.get(task.task_id)
        assert stored.current_run_id == binding.run_id
        run = await task_binding.run_store_for(other).get(binding.run_id)
        assert run.task_id == task.task_id and run.state is RunState.FAILED
        lease = await other._run_lease().current(task.task_id)
        assert lease["holder"] == ""


@pytest.mark.anyio
async def test_a_tick_that_lost_its_lease_drops_its_result(tmp_path, monkeypatch):
    import backend.server as server
    from runtimes.base import TaskResult

    async def execute(self, spec):
        binding = task_binding.current_run.get()
        binding.heartbeat.lost.set()  # a newer holder took the lease meanwhile
        return TaskResult(runtime_id="internal", task_id=spec.task_id, success=False,
                          output="late"), None

    _patch_adapter(monkeypatch, execute)
    async with sqlite_pair(tmp_path) as (web, other):
        task = await queued_task(web)
        monkeypatch.setattr("tasks.store.get_task_store", lambda: web)
        await server.autonomy_tick(_request())
        stored = await other.get(task.task_id)
        assert getattr(stored.status, "value", stored.status) == "in_progress"  # not overwritten
