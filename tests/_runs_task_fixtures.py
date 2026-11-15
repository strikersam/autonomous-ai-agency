"""Shared helpers for the phase 2 durable run tests: two "processes" on one SQLite
file, a coordinator with a fake runtime, and a clean binding registry."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from packages.storage.sqlite import SQLiteStore
from runtimes.base import TaskResult
from runtimes.routing import RoutingDecision
from tasks.models import Task
from tasks.service import TaskExecutionCoordinator, TaskWorkflowService
from tasks.store import TaskStore


@asynccontextmanager
async def sqlite_pair(tmp_path: Path) -> AsyncIterator[tuple[TaskStore, TaskStore]]:
    """Two ``TaskStore``s on one SQLite file, one per simulated process."""
    path = str(tmp_path / "agency.db")
    a, b = SQLiteStore(path), SQLiteStore(path)
    await a._get_conn()
    await b._get_conn()
    try:
        yield TaskStore(db=a), TaskStore(db=b)
    finally:
        await a.close()
        await b.close()


def ok_result(task_id: str) -> tuple[TaskResult, RoutingDecision]:
    """A successful runtime result and its routing decision."""
    return (
        TaskResult(runtime_id="internal_agent", task_id=task_id, success=True, output="done"),
        RoutingDecision(task_id=task_id, task_type="general", selected_runtime_id="internal_agent",
                        model_used=None, provider_used="local", reason="test"),
    )


class FakeRuntime:
    """Runs *body* (an async callable taking the spec) as the runtime."""

    def __init__(self, body: Any = None) -> None:
        self.calls = 0
        self._body = body

    async def execute(self, spec: Any) -> Any:
        self.calls += 1
        if self._body is not None:
            return await self._body(spec)
        raise RuntimeError("runtime failed on purpose")


def coordinator(store: TaskStore, runtime: Any) -> TaskExecutionCoordinator:
    """A coordinator over *store* with *runtime* and no real workspace."""
    return TaskExecutionCoordinator(store=store, workflow=TaskWorkflowService(store=store),
                                    runtime_manager=runtime,
                                    workspace_root="/tmp/workspace")  # nosec B108 - fake runtime


async def queued_task(store: TaskStore, title: str = "Routine bugfix") -> Task:
    """A task waiting for the dispatcher."""
    task = Task(owner_id="o@x.com", title=title, requires_approval=False, pending_agent_run=True)
    await store.create(task)
    return task


def reset_process_state(monkeypatch: Any) -> None:
    """Fresh claim and binding registries, a brain, and a fast heartbeat."""
    import tasks.service as svc
    from packages.runs import task_binding
    from tasks import run_lease

    async def _true() -> bool:
        return True

    monkeypatch.setattr(run_lease, "_local_claims", {})
    monkeypatch.setattr(task_binding, "_ACTIVE", {})
    monkeypatch.setattr(svc, "_brain_is_configured", _true)


async def cancel_without_release(binding: Any) -> None:
    """Simulate a dead worker: its heartbeat stops, nothing is released."""
    await binding.heartbeat.stop()
    await asyncio.sleep(0)


async def start_dead_worker(store: TaskStore, task: Task, *, before_death: Any = None
                            ) -> tuple[asyncio.Task, asyncio.Event, Any]:
    """Run *task* until its runtime is entered, then "kill" the worker.

    The heartbeat stops (no renewals, nothing released) and the runtime hangs
    until the returned event is set, after which it raises: the late result of a
    worker that came back after its lease was taken over. *before_death* (async,
    takes the binding) runs first, e.g. to start a side effect.
    """
    from packages.runs import task_binding

    reached, finish, box = asyncio.Event(), asyncio.Event(), {}

    async def body(spec: Any) -> Any:
        binding = task_binding.current_run.get()
        box["binding"] = binding
        if before_death is not None:
            await before_death(binding)
        await binding.heartbeat.stop()
        reached.set()
        await finish.wait()
        raise RuntimeError("late result of the dead worker")

    job = asyncio.create_task(coordinator(store, FakeRuntime(body)).execute(task.task_id))
    await reached.wait()
    return job, finish, box["binding"]
