"""backend/v4_api.py — v4 Dashboard API for the Continuous Improvement Dashboard.

Bridges the v4-dashboard.html frontend (served by Cloudflare Worker at
autonomous-ai-agency.strikersam.workers.dev) to the existing backend services:
ImprovementLoop, SelfHealingAgent, TaskStore, and AgentScheduler.

Previously the dashboard called /v4/* endpoints that didn't exist, causing
the UI to error out silently (404 -> rejected Promise -> empty panels).
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger("llm-wiki")

v4_router = APIRouter(prefix="/v4", tags=["v4 dashboard"])

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATE_FILE = _REPO_ROOT / ".claude" / "state" / "improvement-state.json"

# ── TTL cache for expensive TaskStore queries ────────────────────────────────
# Single-flight TTL cache prevents dashboard refresh bursts from hitting
# MongoDB for every open tab. Default 8s, override via V4_TASKS_CACHE_TTL_SEC.
# Reuses tasks/api.py's _safe_ttl so bounds/guards agree (rejects NaN/inf/zero).

_TASKS_CACHE: dict[str, tuple[float, list[dict]]] = {}
_TASKS_CACHE_LOCK: asyncio.Lock | None = None

try:
    from tasks.api import _safe_ttl
    _TASKS_CACHE_TTL: float = _safe_ttl("V4_TASKS_CACHE_TTL_SEC", 8.0)
except ImportError:
    _TASKS_CACHE_TTL = 8.0


def _get_tasks_cache_lock() -> asyncio.Lock:
    global _TASKS_CACHE_LOCK
    if _TASKS_CACHE_LOCK is None:
        _TASKS_CACHE_LOCK = asyncio.Lock()
    return _TASKS_CACHE_LOCK


async def _get_cached_tasks(limit: int = 50) -> list[dict]:
    """Return cached task dicts; fetches + caches from TaskStore when stale.

    Uses single-flight locking (same pattern as tasks/api.py) so concurrent
    dashboard pollers share one MongoDB query per TTL window.
    """
    cache_key = f"tasks:{limit}"

    # Fast path: serve from cache (no lock needed for read, CPython GIL-safe)
    now = time.monotonic()
    if cache_key in _TASKS_CACHE:
        ts, cached = _TASKS_CACHE[cache_key]
        if now - ts < _TASKS_CACHE_TTL:
            return cached

    try:
        from tasks.store import get_task_store
        store = get_task_store()

        async with _get_tasks_cache_lock():
            # Double-check: another waiter may have already populated the cache
            now2 = time.monotonic()
            if cache_key in _TASKS_CACHE:
                ts, cached = _TASKS_CACHE[cache_key]
                if now2 - ts < _TASKS_CACHE_TTL:
                    return cached

            tasks = await store.list_all(limit=limit)
            result: list[dict] = [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                    "priority": t.priority.value if hasattr(t.priority, "value") else str(t.priority),
                    "agent_id": t.agent_id,
                    "task_type": t.task_type,
                    "tags": t.tags,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                    "source": getattr(t, "source", "manual"),
                }
                for t in tasks
            ]
            _TASKS_CACHE[cache_key] = (time.monotonic(), result)

            # Evict stale entries to prevent unbounded growth
            now3 = time.monotonic()
            stale = [k for k, (ts2, _) in _TASKS_CACHE.items() if now3 - ts2 >= _TASKS_CACHE_TTL]
            for k in stale:
                _TASKS_CACHE.pop(k, None)

            return result
    except Exception as exc:
        log.debug("v4 tasks cache: TaskStore unavailable: %s", exc)
        return []


# ── Helpers ──────────────────────────────────────────────────────────────────

async def _load_improvement_state() -> dict:
    """Load the improvement state from disk (non-blocking)."""
    try:
        return await asyncio.to_thread(lambda: json.loads(_STATE_FILE.read_text()))
    except Exception:
        return {}


async def _save_improvement_state(data: dict) -> None:
    """Save the improvement state to disk (non-blocking)."""
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(lambda: _STATE_FILE.write_text(json.dumps(data, indent=2)))


# ── GET /v4/status ───────────────────────────────────────────────────────────

@v4_router.get("/status")
async def v4_status(request: Request) -> dict[str, Any]:
    """Dashboard KPI strip: improvement loop stats + self-healing events."""
    state = await _load_improvement_state()

    # Self-healing events
    recent_events: list[dict] = []
    try:
        from agent.self_healing import get_self_healing_agent
        healer = get_self_healing_agent()
        if healer:
            recent_events = healer.get_events()[-20:]
    except Exception as exc:
        log.debug("v4/status: self-healing agent unavailable: %s", exc)

    return {
        "improvement_loop": {
            "last_scan": state.get("last_scan"),
            "scan_count": state.get("scan_count", 0),
            "issues_detected": state.get("issues_detected", 0),
            "issues_resolved": state.get("issues_resolved", 0),
            "active_issues": state.get("active_issues", []),
            "last_test_result": state.get("last_test_result"),
            "failing_tests": state.get("failing_tests", []),
        },
        "self_healing": {
            "recent_events": recent_events,
            "event_count": len(recent_events),
        },
    }


# ── GET /v4/improvements ─────────────────────────────────────────────────────

@v4_router.get("/improvements")
async def v4_improvements(request: Request) -> dict[str, Any]:
    """List active and resolved improvement issues."""
    state = await _load_improvement_state()
    return {
        "active": state.get("active_issues", []),
        "resolved": state.get("resolved_issues", []),
    }


# ── POST /v4/improvements/scan ───────────────────────────────────────────────

@v4_router.post("/improvements/scan")
async def v4_improvements_scan(request: Request) -> dict[str, Any]:
    """Trigger an improvement scan as a background task. Returns immediately."""
    try:
        from agent.improvement_loop import get_improvement_loop
        loop = get_improvement_loop()
        if not loop:
            raise HTTPException(status_code=503, detail="ImprovementLoop not running")

        asyncio.create_task(_run_scan_background(loop))
        return {"accepted": True, "detail": "Scan started in background"}
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("v4/improvements/scan failed")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


async def _run_scan_background(loop) -> None:
    """Run the improvement scan in a thread and log results."""
    try:
        new_issues = await asyncio.to_thread(loop.trigger_scan)
        log.info("v4/improvements/scan: background scan found %d issues", len(new_issues))
    except Exception as exc:
        log.error("v4/improvements/scan: background scan failed: %s", exc)


# ── POST /v4/improvements/{issue_id}/resolve ─────────────────────────────────

@v4_router.post("/improvements/{issue_id}/resolve")
async def v4_improvements_resolve(issue_id: str, request: Request) -> dict[str, Any]:
    """Mark an improvement issue as resolved."""
    state = await _load_improvement_state()
    active = state.get("active_issues", [])
    resolved_list = state.get("resolved_issues", [])

    found = False
    for issue in active:
        if issue.get("issue_id") == issue_id:
            issue["resolved"] = True
            resolved_list.append(issue)
            found = True
            break

    if found:
        state["active_issues"] = [i for i in active if i.get("issue_id") != issue_id]
        state["resolved_issues"] = resolved_list
        state["issues_resolved"] = state.get("issues_resolved", 0) + 1
        await _save_improvement_state(state)

        try:
            from agent.improvement_loop import get_improvement_loop
            loop = get_improvement_loop()
            if loop:
                loop.mark_resolved(issue_id)
        except Exception:
            pass

        return {"resolved": True, "issue_id": issue_id}

    return {"resolved": False, "issue_id": issue_id, "detail": "Issue not found"}


# ── GET /v4/quick-notes ──────────────────────────────────────────────────────

@v4_router.get("/quick-notes")
async def v4_quick_notes(request: Request) -> dict[str, Any]:
    """List queued quick notes from the TaskStore.

    Reuses the shared tasks cache so dashboard refresh bursts hit at most
    one MongoDB query per TTL window for all task-related endpoints.
    """
    tasks = await _get_cached_tasks(limit=50)
    notes = []
    pending = 0
    for t in tasks:
        if t.get("task_type") == "quick_note":
            notes.append({
                "note_id": t.get("task_id", ""),
                "content": t.get("title", ""),
                "status": t.get("status", "todo"),
                "added_at": t.get("created_at", ""),
            })
            if t.get("status") in ("todo", "in_progress", "blocked"):
                pending += 1
    return {"notes": notes, "count": len(notes), "pending": pending}


# ── POST /v4/quick-notes ─────────────────────────────────────────────────────

class V4QuickNoteBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    category: str = Field(default="improvement", max_length=64)


@v4_router.post("/quick-notes", status_code=201)
async def v4_quick_notes_submit(body: V4QuickNoteBody, request: Request) -> dict[str, Any]:
    """Submit a quick note instruction. Creates a Task with task_type='quick_note'."""
    note_id = f"qn_{secrets.token_hex(6)}"
    try:
        from tasks.store import get_task_store
        from tasks.models import Task, TaskPriority, TaskStatus
        from tasks.service import TaskWorkflowService

        store = get_task_store()
        workflow = TaskWorkflowService(store=store)
        task = Task(
            owner_id="system",
            title=body.content[:512],
            description=body.content[:10000],
            prompt=body.content[:10000],
            task_type="quick_note",
            tags=["quick-note", body.category],
            status=TaskStatus.TODO,
            priority=TaskPriority.MEDIUM,
            pending_agent_run=True,
        )
        await workflow.create_task(task, actor="system:dashboard")
        # Invalidate cache so the new note appears immediately in the dashboard
        _TASKS_CACHE.clear()
        return {"note_id": task.task_id, "status": "queued", "channel": "task_store"}
    except Exception as exc:
        log.warning("v4/quick-notes: create failed, falling back to file: %s", exc)
        state = await _load_improvement_state()
        state.setdefault("active_issues", []).append({
            "issue_id": note_id,
            "category": "quick_note",
            "severity": "medium",
            "title": body.content[:200],
            "description": body.content[:500],
            "detected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "resolved": False,
        })
        await _save_improvement_state(state)
        return {"note_id": note_id, "status": "queued", "channel": "file"}


# ── POST /v4/report-bug ──────────────────────────────────────────────────────

class V4ReportBugBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field(default="", max_length=5000)
    severity: str = Field(default="medium", max_length=32)


@v4_router.post("/report-bug", status_code=201)
async def v4_report_bug(body: V4ReportBugBody, request: Request) -> dict[str, Any]:
    """Report a bug via the SelfHealingAgent."""
    event_id = f"he_{secrets.token_hex(6)}"
    try:
        from agent.self_healing import get_self_healing_agent
        healer = get_self_healing_agent()
        if healer:
            event = await healer.on_manual_report(
                title=body.title,
                description=body.description,
                severity=body.severity,
            )
            return {"event_id": event.event_id, "status": "dispatched"}

        state = await _load_improvement_state()
        state.setdefault("active_issues", []).append({
            "issue_id": event_id,
            "category": "todo_fixme",
            "severity": body.severity,
            "title": body.title,
            "description": body.description,
            "detected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "resolved": False,
        })
        await _save_improvement_state(state)
        return {"event_id": event_id, "status": "queued_local"}
    except Exception as exc:
        log.exception("v4/report-bug failed")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# ── GET /v4/scheduler/jobs ───────────────────────────────────────────────────

@v4_router.get("/scheduler/jobs")
async def v4_scheduler_jobs(request: Request) -> dict[str, Any]:
    """List scheduled improvement jobs."""
    try:
        from packages.scheduler.scheduler import get_scheduler
        sched = get_scheduler()
        jobs = sched.list()
        return {
            "jobs": [
                {
                    "job_id": getattr(j, "job_id", ""),
                    "name": getattr(j, "name", ""),
                    "cron": getattr(j, "cron", ""),
                    "run_count": getattr(j, "run_count", 0),
                    "enabled": getattr(j, "enabled", True),
                }
                for j in jobs
            ]
        }
    except Exception as exc:
        log.debug("v4/scheduler/jobs: unavailable: %s", exc)
        return {"jobs": []}


# ── POST /v4/scheduler/trigger/{job_id} ──────────────────────────────────────

@v4_router.post("/scheduler/trigger/{job_id}")
async def v4_scheduler_trigger(job_id: str, request: Request) -> dict[str, Any]:
    """Trigger a scheduled job immediately."""
    try:
        from packages.scheduler.scheduler import get_scheduler
        sched = get_scheduler()
        job = sched.trigger(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        return {"triggered": True, "job": job.as_dict()}
    except HTTPException:
        raise
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    except Exception as exc:
        log.exception("v4/scheduler/trigger failed")
        raise HTTPException(status_code=500, detail="Internal server error") from exc


# ── GET /v4/tasks ────────────────────────────────────────────────────────────

@v4_router.get("/tasks")
async def v4_tasks(request: Request, limit: int = 50) -> dict[str, Any]:
    """List tasks from the TaskStore for the dashboard tasks screen.

    Delegates to _get_cached_tasks() which uses a single-flight TTL cache
    (default 8s) to prevent dashboard refresh bursts from hitting MongoDB
    for every open tab.
    """
    tasks = await _get_cached_tasks(limit=limit)
    return {"tasks": tasks}
