"""FastAPI routes for the task workflow system."""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from typing import Any
from collections.abc import Mapping
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from tasks.models import (
    ApprovalRequest,
    ClarifyRequest,
    CommentAddRequest,
    ExecutionApprovalRequest,
    FollowUpRequest,
    Task,
    TaskCreateRequest,
    TaskPriority,
    TaskStatus,
    TaskUpdateRequest,
)
from tasks.service import TaskWorkflowService
from tasks.service import TaskExecutionCoordinator
from tasks.store import TaskStore, get_task_store
log = logging.getLogger("qwen-proxy")


# Single-flight TTL upper bound (AGENTS.md: all config from env vars).
# Override via TASKS_MAX_CACHE_TTL_SEC; default 3600s (1 hour cap).
try:
    _MAX_CACHE_TTL_SEC: float = float(os.environ.get("TASKS_MAX_CACHE_TTL_SEC", "3600"))
    if not (0 < _MAX_CACHE_TTL_SEC < float("inf")):
        raise ValueError("out of range")
except (TypeError, ValueError):
    log.warning("TASKS_MAX_CACHE_TTL_SEC invalid; defaulting to 3600s")
    _MAX_CACHE_TTL_SEC = 3600.0


def _safe_ttl(name: str, default: float) -> float:
    """Tolerant TTL env-var parser.

    Returns the env-var value when it parses to a positive float ≤ the env-tunable
    cap (``_MAX_CACHE_TTL_SEC``); otherwise logs a warning and returns *default*.
    Avoids operator-mistake footguns: ``float("abc")`` raising at module import
    (= 5xx on every endpoint), zero disabling the cache (MongoDB stampede),
    negative numbers inverting the comparison (cache never hits), ``nan`` silently
    disabling caching, ``inf`` letting the cache dict grow unbounded, and operators
    typing huge values (e.g. 99999) by accident.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        log.warning("Env var %s=%r is not numeric; using default %s", name, raw, default)
        return default
    if not math.isfinite(value) or value <= 0 or value > _MAX_CACHE_TTL_SEC:
        log.warning(
            "Env var %s=%s must be a finite positive number ≤ %s; using default %s",
            name, value, _MAX_CACHE_TTL_SEC, default,
        )
        return default
    return value


# Default 8s; override via TASKS_LIST_ALL_CACHE_TTL_SEC. Single-flight TTL absorbs
# dashboard refresh bursts (N concurrent admin tabs hit one MongoDB query).
_LIST_ALL_CACHE: dict = {}
_LIST_ALL_CACHE_TTL: float = _safe_ttl("TASKS_LIST_ALL_CACHE_TTL_SEC", 8.0)
_LIST_ALL_CACHE_LOCK: asyncio.Lock | None = None


def _get_list_all_lock() -> asyncio.Lock:
    global _LIST_ALL_CACHE_LOCK
    if _LIST_ALL_CACHE_LOCK is None:
        _LIST_ALL_CACHE_LOCK = asyncio.Lock()
    return _LIST_ALL_CACHE_LOCK


task_router = APIRouter(prefix="/api/tasks", tags=["tasks"])


async def _current_user(request: Request) -> Any:
    # Fast path: JWTAuthMiddleware has already validated the token and stored
    # the user dict in request.state.user.
    user = getattr(request.state, "user", None)
    if user is not None:
        return user
    # Slow path: re-verify the Bearer token directly using the same V3_JWT_SECRET
    # that JWTAuthMiddleware uses.  The old approach (importing backend.server.
    # get_current_user) used a different JWT_SECRET and always raised 401.
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth[:7].lower() == "bearer " else request.headers.get("x-api-key", "").strip()
    if token:
        try:
            from tokens import verify_token
            payload = verify_token(token, token_type="access")
            if payload:
                return {
                    "email": payload.get("email"),
                    "_id": payload.get("sub"),
                    "name": payload.get("name"),
                    "role": payload.get("role", "user"),
                }
        except Exception as exc:
            log.warning("Token verification error: %s", exc)
    raise HTTPException(status_code=401, detail="Not authenticated")


def _get_store(_: Request) -> TaskStore:
    return get_task_store()


def _get_workflow(request: Request) -> TaskWorkflowService:
    return TaskWorkflowService(store=_get_store(request))


def _queue_task_execution(background_tasks: BackgroundTasks, request: Request, task_id: str) -> None:
    background_tasks.add_task(
        TaskExecutionCoordinator(
            store=_get_store(request),
            workflow=_get_workflow(request),
            workspace_root=str(Path(__file__).resolve().parent.parent),
        ).execute,
        task_id,
    )


def _is_admin(user: Any) -> bool:
    if isinstance(user, Mapping):
        return user.get("role", "user") == "admin"
    return getattr(user, "role", getattr(user, "get", lambda k, d=None: d)("role", "user")) == "admin"


def _user_id(user: Any) -> str:
    if isinstance(user, Mapping):
        return str(user.get("_id") or user.get("id") or user.get("email") or "unknown")
    return str(getattr(user, "_id", None) or getattr(user, "id", None) or getattr(user, "email", "unknown"))


async def _load_task(request: Request, task_id: str, user: Any) -> tuple[Task, TaskStore, str]:
    store = _get_store(request)
    owner_id = None if _is_admin(user) else _user_id(user)
    task = await store.get(task_id, owner_id=owner_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task, store, _user_id(user)


@task_router.post("/", status_code=201)
async def create_task(body: TaskCreateRequest, request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    workflow = _get_workflow(request)
    task = Task(
        owner_id=_user_id(user),
        title=body.title,
        description=body.description,
        prompt=body.prompt,
        agent_id=body.agent_id,
        runtime_id=body.runtime_id,
        model_preference=body.model_preference,
        priority=body.priority,
        task_type=body.task_type,
        tags=body.tags,
        due_date=body.due_date,
        requires_approval=body.requires_approval,
        status=body.status,
        story_points=body.story_points,
        sprint_id=body.sprint_id,
        review_reason="Created in review lane" if body.status is TaskStatus.IN_REVIEW else None,
    )
    try:
        await workflow.create_task(task, actor=_user_id(user))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"task": task.as_dict()}


@task_router.get("/")
async def list_tasks(
    request: Request,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    agent_id: str | None = None,
    tag: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: Any = Depends(_current_user),
) -> dict[str, Any]:
    store = _get_store(request)
    owner_id = _user_id(user)

    if _is_admin(user):
        cache_key = f"list_all:{status}:{limit}:{offset}"
        cached = _LIST_ALL_CACHE.get(cache_key)
        if cached and time.monotonic() - cached["ts"] < _LIST_ALL_CACHE_TTL:
            tasks = cached["tasks"]
        else:
            async with _get_list_all_lock():
                cached = _LIST_ALL_CACHE.get(cache_key)
                if cached and time.monotonic() - cached["ts"] < _LIST_ALL_CACHE_TTL:
                    tasks = cached["tasks"]
                else:
                    tasks = await store.list_all(status=status, limit=limit, offset=offset)
                    _LIST_ALL_CACHE[cache_key] = {"tasks": tasks, "ts": time.monotonic()}
                    # Evict expired entries to prevent unbounded growth.
                    now = time.monotonic()
                    stale = [k for k, v in _LIST_ALL_CACHE.items() if now - v["ts"] >= _LIST_ALL_CACHE_TTL]
                    for k in stale:
                        _LIST_ALL_CACHE.pop(k, None)
    else:
        tasks = await store.list_for_user(
            owner_id,
            status=status,
            priority=priority,
            agent_id=agent_id,
            tag=tag,
            limit=limit,
            offset=offset,
        )
    # Exclude execution_log from list view — it can be 10k+ entries per task
    # (7 MB+ response, 27s load time). Full log is available on GET /{task_id}.
    return {"tasks": [
        {k: v for k, v in task.as_dict().items() if k != "execution_log"}
        for task in tasks
    ]}


@task_router.get("/counts")
async def task_counts(request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    counts = await _get_store(request).count_for_user(_user_id(user))
    return {"counts": counts}


@task_router.get("/due-soon")
async def tasks_due_soon(request: Request, within_hours: int = 24, user: Any = Depends(_current_user)) -> dict[str, Any]:
    tasks = await _get_store(request).get_due_soon(within_hours)
    if not _is_admin(user):
        uid = _user_id(user)
        tasks = [task for task in tasks if task.owner_id == uid]
    # Exclude execution_log from list view — it can be 10k+ entries per task
    # (7 MB+ response, 27s load time). Full log is available on GET /{task_id}.
    return {"tasks": [
        {k: v for k, v in task.as_dict().items() if k != "execution_log"}
        for task in tasks
    ]}


@task_router.get("/{task_id}")
async def get_task(task_id: str, request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    task, _, _ = await _load_task(request, task_id, user)
    return {"task": task.as_dict()}


@task_router.patch("/{task_id}")
async def update_task(task_id: str, body: TaskUpdateRequest, request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    task, store, actor = await _load_task(request, task_id, user)
    workflow = _get_workflow(request)
    updates = body.model_dump(exclude_none=True)

    if "title" in updates:
        task.title = updates["title"]
    if "description" in updates:
        task.description = updates["description"]
    if "prompt" in updates:
        task.prompt = updates["prompt"]
    if "runtime_id" in updates:
        task.runtime_id = updates["runtime_id"]
    if "model_preference" in updates:
        task.model_preference = updates["model_preference"]
    if "priority" in updates:
        task.priority = updates["priority"]
    if "task_type" in updates:
        task.task_type = updates["task_type"]
    if "tags" in updates:
        task.tags = updates["tags"]
    if "due_date" in updates:
        task.due_date = updates["due_date"]
    if "requires_approval" in updates:
        task.requires_approval = updates["requires_approval"]
    if "story_points" in updates:
        task.story_points = updates["story_points"]
    if "sprint_id" in updates:
        task.sprint_id = updates["sprint_id"]
    if "agent_id" in updates:
        workflow.assign_agent(task, updates["agent_id"], actor=actor)

    if body.status is not None:
        try:
            workflow.transition(
                task,
                body.status,
                actor=actor,
                blocked_reason=task.blocked_reason or "Manually blocked" if body.status is TaskStatus.BLOCKED else None,
                review_reason=task.review_reason or "Awaiting review" if body.status is TaskStatus.IN_REVIEW else None,
                pending_agent_run=True if body.status is TaskStatus.IN_PROGRESS else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    await store.update(task)
    return {"task": task.as_dict()}



@task_router.post("/purge", summary="Bulk-delete terminal tasks older than N days")
async def purge_old_tasks(
    request: Request,
    days: int = Query(default=7, ge=1, le=365, description="Delete tasks completed/failed more than N days ago"),
    statuses: str = Query(default="done,failed,cancelled", description="Comma-separated statuses to purge"),
    user: Any = Depends(_current_user),
) -> dict:
    """Delete terminal (done/failed/cancelled) tasks older than ``days`` days.

    Keeps the last 24 h of any status untouched so in-flight work is safe.
    Returns the count of deleted tasks.
    """
    import time as _time
    store = _get_store(request)
    cutoff = _time.time() - days * 86400
    target_statuses = {s.strip().lower() for s in statuses.split(",")}

    all_tasks = await store.list_all(limit=10_000)
    deleted = 0
    for task in all_tasks:
        ts = task.updated_at or task.created_at or 0
        if (
            task.status.lower() in target_statuses
            and isinstance(ts, (int, float))
            and ts < cutoff
        ):
            await store.delete(task.task_id, owner_id=None)  # admin purge — no owner check
            deleted += 1

    log.info("Purged %d terminal tasks older than %d days", deleted, days)
    return {"deleted": deleted, "days": days, "statuses": list(target_statuses)}

@task_router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, request: Request, user: Any = Depends(_current_user)) -> None:
    owner_id = None if _is_admin(user) else _user_id(user)
    deleted = await _get_store(request).delete(task_id, owner_id=owner_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")


@task_router.post("/{task_id}/comments", status_code=201)
async def add_comment(task_id: str, body: CommentAddRequest, request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    task, store, actor = await _load_task(request, task_id, user)
    workflow = _get_workflow(request)
    try:
        comment = workflow.add_comment(task, author=actor, body=body.body, reply_to=body.reply_to)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await store.update(task)
    return {"comment": comment.model_dump(), "task": task.as_dict()}


@task_router.post("/{task_id}/approve")
async def approve_checkpoint(task_id: str, body: ApprovalRequest, request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    task, store, actor = await _load_task(request, task_id, user)
    workflow = _get_workflow(request)
    try:
        workflow.record_approval(
            task,
            checkpoint_id=body.checkpoint_id,
            approved=body.approve,
            actor=actor,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await store.update(task)
    return {"task": task.as_dict()}


@task_router.post("/{task_id}/approve-execution")
async def approve_execution(
    task_id: str,
    body: ExecutionApprovalRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: Any = Depends(_current_user),
) -> dict[str, Any]:
    """Decide a task's **pre-execution** approval gate (Autonomy Charter Gate Matrix).

    ``requires_approval`` tasks are parked by the dispatcher before they run.
    Approving here re-queues the task for execution; rejecting blocks it.
    """
    task, store, actor = await _load_task(request, task_id, user)
    workflow = _get_workflow(request)
    try:
        workflow.approve_execution(task, actor=actor, approved=body.approve, reason=body.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await store.update(task)
    if body.approve:
        _queue_task_execution(background_tasks, request, task_id)
    return {"task": task.as_dict()}


@task_router.post("/{task_id}/retry")
async def retry_task(task_id: str, request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    task, store, actor = await _load_task(request, task_id, user)
    workflow = _get_workflow(request)
    try:
        workflow.retry(task, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await store.update(task)
    return {"task": task.as_dict()}


@task_router.post("/{task_id}/follow-up")
async def follow_up_task(
    task_id: str,
    body: FollowUpRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: Any = Depends(_current_user),
) -> dict[str, Any]:
    """Give a task new guidance and re-run it, carrying the conversation forward.

    This is the missing 'rerun / give follow-up command' capability: the message is
    appended to the task thread and the task is re-opened and re-queued (the
    dispatcher picks it up; we also kick an immediate background run).
    """
    task, store, actor = await _load_task(request, task_id, user)
    workflow = _get_workflow(request)
    try:
        workflow.follow_up(
            task,
            actor=actor,
            message=body.message,
            model_preference=body.model_preference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await store.update(task)
    _queue_task_execution(background_tasks, request, task.task_id)
    return {"task": task.as_dict(), "queued": True}


@task_router.post("/{task_id}/escalate")
async def escalate_task(task_id: str, request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    task, store, actor = await _load_task(request, task_id, user)
    workflow = _get_workflow(request)
    workflow.escalate(task, actor=actor)
    await store.update(task)
    return {"task": task.as_dict()}


@task_router.patch("/{task_id}/clarify")
async def clarify_task(task_id: str, body: ClarifyRequest, request: Request, user: Any = Depends(_current_user)) -> dict[str, Any]:
    task, store, actor = await _load_task(request, task_id, user)
    task.status = TaskStatus.NEEDS_CLARIFICATION
    task.blocked_reason = body.reason
    task.add_log(
        f"Clarification requested: {body.reason}",
        event_type="clarification_requested",
        actor=actor,
        task_status=task.status,
    )
    task.touch()
    await store.update(task)
    return {"task": task.as_dict()}


@task_router.post("/{task_id}/run", status_code=202)
async def run_task(
    task_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    user: Any = Depends(_current_user),
) -> dict[str, Any]:
    task, store, actor = await _load_task(request, task_id, user)

    if task.status in {TaskStatus.BLOCKED, TaskStatus.IN_REVIEW, TaskStatus.DONE}:
        raise HTTPException(
            status_code=400,
            detail=f"Task in status '{task.status.value}' cannot be run directly. Move it back to todo/in_progress or use retry.",
        )

    task.pending_agent_run = True
    if task.status is TaskStatus.TODO:
        task.add_log(
            "Task queued for immediate execution",
            event_type="execution_requested",
            actor=actor,
            task_status=task.status,
        )
    await store.update(task)
    _queue_task_execution(background_tasks, request, task.task_id)
    return {"task": task.as_dict(), "queued": True}
