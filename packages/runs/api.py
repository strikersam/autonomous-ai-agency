"""packages/runs/api.py — the ``/api/runs`` HTTP surface over the durable run store.

Every route is authenticated through the ``get_current_user`` dependency that
``build_runs_router`` is given, and every route that names a run resolves it
through ``_owned_run`` (one tenant check: a run of another owner is a 404, never
a 403; admins see every run, as the workflow orchestrator routes do).

Creating a run never executes it: the underlying task is created through
``TaskWorkflowService.create_task`` (``pending_agent_run`` set), the dispatcher
picks it up, and the request returns at once. The run record is stored first
and linked from ``Task.current_run_id`` before the task exists, so the worker
that claims the task resumes this very run instead of opening another.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from packages.config import runs_settings
from packages.lifecycle.machine import IllegalTransition
from packages.runs.models import RunEvent, RunRecord, RunState
from packages.runs.store import FencedOut, RunStore, get_run_store
from tasks.api import _invalidate_task_caches, _is_admin, _user_id
from tasks.models import Task, TaskStatus
from tasks.service import TaskRuleError, TaskWorkflowService
from tasks.store import get_task_store

log = logging.getLogger("qwen-proxy")

# A run in one of these states has no worker: cancel settles it on the spot.
_CANCEL_NOW = frozenset({RunState.QUEUED, RunState.WAITING_FOR_AGENT, RunState.WAITING_FOR_APPROVAL})
_RETRYABLE = frozenset({RunState.FAILED, RunState.TIMED_OUT, RunState.DEAD_LETTER, RunState.CANCELLED})
_TASK_DONE = frozenset({TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.WONT_DO})
_MAX_DEADLINE_S = 30 * 24 * 3600
_RECOVERY = {"mongo": "cross_host", "sqlite": "same_host", "memory": "none"}


class RunCreateRequest(BaseModel):
    """Body of ``POST /api/runs``."""

    title: str = Field(..., min_length=1, max_length=512)
    description: str = Field(default="", max_length=32_000)
    agent_id: str | None = Field(default=None, max_length=64)
    runtime_id: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=200)
    workflow_id: str | None = Field(default=None, max_length=128)
    parent_run_id: str | None = Field(default=None, max_length=128)
    budget: dict[str, Any] | None = None
    deadline_seconds: int | None = Field(default=None, ge=1, le=_MAX_DEADLINE_S)


class RunCreated(BaseModel):
    """Answer of ``POST /api/runs`` and ``POST /api/runs/{id}/retry``."""

    run_id: str
    task_id: str | None
    state: RunState
    created: bool


class RunView(RunRecord):
    """A run as served to clients: the lease token never leaves the server."""

    lease_token: int | None = Field(default=None, exclude=True)


class RunList(BaseModel):
    """Answer of ``GET /api/runs``."""

    runs: list[RunView]


class RunEventList(BaseModel):
    """Answer of ``GET /api/runs/{id}/events``."""

    run_id: str
    events: list[RunEvent]
    next_after_seq: int


class RunArtifacts(BaseModel):
    """Answer of ``GET /api/runs/{id}/artifacts``."""

    run_id: str
    artifacts: list[str]


class CancelResult(BaseModel):
    """Answer of ``POST /api/runs/{id}/cancel``."""

    run_id: str
    state: RunState
    cancel_requested: bool
    settled: bool


class RunCapabilities(BaseModel):
    """Answer of ``GET /api/runs/capabilities`` (plan decision D5)."""

    backend: str
    durable_lease: bool
    recovery: str
    recovery_enabled: bool
    ledger_enabled: bool
    checkpoint_durable: bool


@dataclass(frozen=True)
class Caller:
    """The authenticated caller, as the tenant check needs it."""

    user_id: str
    is_admin: bool

    @property
    def actor(self) -> str:
        """The actor string written on events."""
        return f"user:{self.user_id}"


def _caller(request: Request) -> Caller:
    user = getattr(request.state, "runs_user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return Caller(user_id=_user_id(user), is_admin=_is_admin(user))


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Run not found")


async def _owned_run(store: RunStore, run_id: str, caller: Caller) -> RunRecord:
    """The one tenant check: the run, or 404 when missing or not the caller's."""
    run = await store.get(run_id)
    if run is None or (not caller.is_admin and run.owner_id != caller.user_id):
        raise _not_found()
    return run


def _view(run: RunRecord) -> RunView:
    return RunView.model_validate(run.model_dump())


def _created(run: RunRecord, created: bool) -> RunCreated:
    return RunCreated(run_id=run.run_id, task_id=run.task_id, state=run.state, created=created)


async def _fail_run(store: RunStore, run_id: str, reason: str) -> None:
    try:
        await store.transition(run_id, RunState.FAILED, reason=reason, actor="system:api")
    except Exception:
        log.warning("runs api: could not fail run %s after %s", run_id, reason, exc_info=True)


async def _parent_fields(store: RunStore, body: RunCreateRequest, caller: Caller) -> dict[str, Any]:
    if not body.parent_run_id:
        return {}
    parent = await _owned_run(store, body.parent_run_id, caller)
    return {"parent_run_id": parent.run_id, "root_run_id": parent.root_run_id or parent.run_id,
            "depth": parent.depth + 1}


def _new_task(body: RunCreateRequest, caller: Caller) -> Task:
    return Task(owner_id=caller.user_id, title=body.title, description=body.description,
                agent_id=body.agent_id, runtime_id=body.runtime_id, model_preference=body.model)


def _run_for(task: Task, body: RunCreateRequest, caller: Caller, extra: dict[str, Any]) -> RunRecord:
    deadline = time.time() + body.deadline_seconds if body.deadline_seconds else None
    return RunRecord(
        owner_id=caller.user_id, initiated_by=caller.actor,
        agent_id=body.agent_id, runtime_id=body.runtime_id, requested_model=body.model,
        workflow_id=body.workflow_id, budget=dict(body.budget or {}), deadline_at=deadline,
        state=RunState.QUEUED, **extra,
    )


async def _start_task(store: RunStore, task: Task, run: RunRecord, caller: Caller) -> None:
    """Create the task for a run this request created, then link it (only if unset).

    The run is stored without a ``task_id``; only the request that won the run creates
    a task, so a run never points at a task that does not exist.
    """
    task.current_run_id = run.run_id
    try:
        await TaskWorkflowService(store=get_task_store()).create_task(task, actor=caller.actor)
    except (TaskRuleError, ValueError) as exc:
        await _fail_run(store, run.run_id, "task rejected")
        raise HTTPException(status_code=400, detail="Invalid run request") from exc
    except Exception as exc:
        log.exception("runs api: task creation failed for run %s", run.run_id)
        await _fail_run(store, run.run_id, "task creation failed")
        raise HTTPException(status_code=500, detail="Could not create the run") from exc
    if await store.update(run.run_id, {"task_id": task.task_id}, expect={"task_id": None}):
        run.task_id = task.task_id
    else:
        log.warning("runs api: run %s already linked to a task; task %s left unlinked",
                    run.run_id, task.task_id)
    _invalidate_task_caches(user_id=caller.user_id)
    await store.append_event(run.run_id, "api_created", {
        "title": body_preview(task.title), "request": body_preview(task.description),
    }, actor=caller.actor)


def body_preview(text: str, limit: int = 120) -> str:
    """A short, single line preview of request text (the store redacts it on write)."""
    return " ".join(text.split())[:limit]


async def create_run(
    body: RunCreateRequest, response: Response, caller: Caller = Depends(_caller),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=200),
) -> RunCreated:
    """Queue a run and return at once; a repeated ``Idempotency-Key`` returns the same run."""
    store = get_run_store()
    task = _new_task(body, caller)
    run = _run_for(task, body, caller, await _parent_fields(store, body, caller))
    created = True
    if idempotency_key:
        run, created = await store.get_or_create(f"owner:{caller.user_id}", idempotency_key,
                                                 lambda: run)
    else:
        run = await store.create(run)
    if created:
        await _start_task(store, task, run, caller)
    response.status_code = 201 if created else 200
    return _created(run, created)


async def get_run(run_id: str, caller: Caller = Depends(_caller)) -> RunView:
    """One run (no lease token)."""
    return _view(await _owned_run(get_run_store(), run_id, caller))


async def list_runs(
    state: RunState | None = None, task_id: str | None = Query(default=None, max_length=128),
    parent_run_id: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=50, ge=1, le=500), caller: Caller = Depends(_caller),
) -> RunList:
    """The caller's runs, newest first (admins: every run)."""
    runs = await get_run_store().list(
        owner_id=None if caller.is_admin else caller.user_id, state=state,
        parent_run_id=parent_run_id, task_id=task_id, limit=limit)
    return RunList(runs=[_view(r) for r in runs])


async def run_events(
    run_id: str, after_seq: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=1000),
    caller: Caller = Depends(_caller),
) -> RunEventList:
    """Persisted (already redacted) events with ``seq > after_seq``, oldest first."""
    store = get_run_store()
    await _owned_run(store, run_id, caller)
    events = await store.list_events(run_id, after_seq=after_seq, limit=limit)
    return RunEventList(run_id=run_id, events=events,
                        next_after_seq=events[-1].seq if events else after_seq)


async def run_artifacts(run_id: str, caller: Caller = Depends(_caller)) -> RunArtifacts:
    """The run's ``artifact_refs`` as stored."""
    run = await _owned_run(get_run_store(), run_id, caller)
    return RunArtifacts(run_id=run_id, artifacts=list(run.artifact_refs))


async def _cancel_task(task_id: str | None, caller: Caller) -> None:
    """Move the run's task to ``wont_do`` through the task service (best effort)."""
    if not task_id:
        return
    store = get_task_store()
    task = await store.get(task_id)
    if task is None or task.status in _TASK_DONE:
        return
    try:
        TaskWorkflowService(store=store).transition(
            task, TaskStatus.WONT_DO, actor=caller.actor, message="Run cancelled by request")
        await store.update(task)
    except TaskRuleError:
        log.warning("runs api: task %s could not be cancelled from %s", task_id, task.status.value)
    _invalidate_task_caches()


async def cancel_run(run_id: str, caller: Caller = Depends(_caller)) -> CancelResult:
    """Request cancellation; a run with no worker is cancelled at once."""
    store = get_run_store()
    run = await _owned_run(store, run_id, caller)
    if run.is_terminal:
        raise HTTPException(status_code=409, detail="Run already finished")
    await store.update(run_id, {"cancel_requested": True})
    await store.append_event(run_id, "cancel_requested", {"state": run.state.value}, actor=caller.actor)
    if run.state in _CANCEL_NOW:
        try:
            await store.transition(run_id, RunState.CANCELLED, reason="cancelled by request",
                                   actor=caller.actor)
            await _cancel_task(run.task_id, caller)
        except (FencedOut, IllegalTransition):
            pass  # a worker or another caller moved the run first; report what it is now
    now = await store.get(run_id) or run
    return CancelResult(run_id=run_id, state=now.state, cancel_requested=True,
                        settled=now.is_terminal)


def _retry_run(run: RunRecord) -> RunRecord:
    return RunRecord(
        retry_of=run.run_id, task_id=run.task_id, owner_id=run.owner_id, company_id=run.company_id,
        initiated_by=run.initiated_by, agent_id=run.agent_id, runtime_id=run.runtime_id,
        requested_model=run.requested_model, workflow_id=run.workflow_id,
        parent_run_id=run.parent_run_id, root_run_id=run.root_run_id, depth=run.depth,
        budget=dict(run.budget), state=RunState.QUEUED, attempt=1,
    )


async def _retry_target(store: RunStore, run: RunRecord) -> Task:
    """The run's task, provided nothing else is already running it."""
    if run.state not in _RETRYABLE or not run.task_id:
        raise HTTPException(status_code=409, detail="Run cannot be retried")
    task = await get_task_store().get(run.task_id)
    if task is None:
        raise HTTPException(status_code=409, detail="Run cannot be retried")
    current = await store.get(task.current_run_id) if task.current_run_id else None
    if current is not None and current.run_id != run.run_id and not current.is_terminal:
        raise HTTPException(status_code=409, detail="Task already has an active run")
    return task


async def retry_run(run_id: str, caller: Caller = Depends(_caller)) -> RunCreated:
    """Retry a finished run as a NEW run (``retry_of`` set) and re-queue its task."""
    store = get_run_store()
    run = await _owned_run(store, run_id, caller)
    task = await _retry_target(store, run)
    new_run = _retry_run(run)
    if not await store.update(run_id, {"retried_by": new_run.run_id}, expect={"retried_by": None}):
        raise HTTPException(status_code=409, detail="Run already retried")
    new_run = await store.create(new_run)
    task.current_run_id = new_run.run_id
    try:
        TaskWorkflowService(store=get_task_store()).retry(task, actor=caller.actor)
    except (TaskRuleError, ValueError) as exc:
        await _fail_run(store, new_run.run_id, "task could not be re-queued")
        await store.update(run_id, {"retried_by": None}, expect={"retried_by": new_run.run_id})
        raise HTTPException(status_code=409, detail="Run cannot be retried") from exc
    await get_task_store().update(task)
    _invalidate_task_caches(user_id=task.owner_id)
    await store.append_event(run_id, "retried", {"new_run_id": new_run.run_id}, actor=caller.actor)
    return _created(new_run, True)


async def _checkpoint_durable() -> bool:
    try:
        from services.orchestrator_checkpoint import get_orchestrator_checkpoint_store

        return bool(await get_orchestrator_checkpoint_store().is_durable())
    except Exception:
        return False


async def capabilities(caller: Caller = Depends(_caller)) -> RunCapabilities:
    """What this deployment guarantees for runs, by storage backend."""
    from packages.runs.task_binding import has_durable_lease

    backend = get_run_store().backend
    return RunCapabilities(
        backend=backend, durable_lease=has_durable_lease(get_task_store()),
        recovery=_RECOVERY.get(backend, "none"),
        recovery_enabled=runs_settings.runs_recovery_enabled(),
        ledger_enabled=runs_settings.runs_ledger_enabled(),
        checkpoint_durable=await _checkpoint_durable(),
    )


def build_runs_router(get_current_user: Callable[..., Any]) -> APIRouter:
    """The ``/api/runs`` router, every route behind *get_current_user*."""

    async def authenticate(request: Request, user: Any = Depends(get_current_user)) -> None:
        request.state.runs_user = user

    router = APIRouter(prefix="/api/runs", tags=["runs"], dependencies=[Depends(authenticate)])
    # /capabilities is declared before /{run_id} so the path parameter does not capture it.
    router.add_api_route("/capabilities", capabilities, methods=["GET"], response_model=RunCapabilities)
    router.add_api_route("", create_run, methods=["POST"], response_model=RunCreated, status_code=201)
    router.add_api_route("", list_runs, methods=["GET"], response_model=RunList)
    router.add_api_route("/{run_id}", get_run, methods=["GET"], response_model=RunView)
    router.add_api_route("/{run_id}/events", run_events, methods=["GET"], response_model=RunEventList)
    router.add_api_route("/{run_id}/artifacts", run_artifacts, methods=["GET"],
                         response_model=RunArtifacts)
    router.add_api_route("/{run_id}/cancel", cancel_run, methods=["POST"], response_model=CancelResult)
    router.add_api_route("/{run_id}/retry", retry_run, methods=["POST"], response_model=RunCreated,
                         status_code=201)
    return router
