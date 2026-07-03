"""agent/scheduler.py — Scheduled Agent Jobs

Cron-based job scheduler.  Each job holds an agent instruction that is
dispatched (via the *on_fire* callback) when its cron schedule fires.
External webhooks can also fire jobs immediately via :meth:`trigger`.

Requires ``apscheduler`` (installed as a dependency).  When apscheduler is
not available the scheduler still works — jobs are registered and can be
triggered manually; the background cron execution is simply disabled.
"""
from __future__ import annotations

import logging
import secrets
import time
import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("qwen-scheduler")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    _HAS_APSCHEDULER = True
except ImportError:  # pragma: no cover
    _HAS_APSCHEDULER = False


@dataclass
class ScheduledJob:
    job_id: str
    name: str
    cron: str       # standard 5-field cron expression, e.g. "0 9 * * 1"
    instruction: str
    created_at: str
    description: str | None = None  # BUG-11: human-readable one-liner (max 200 chars)
    agent_id: str | None = None
    runtime_id: str | None = None
    model: str | None = None
    task_type: str = "scheduled"
    requires_approval: bool = False
    tags: list[str] = field(default_factory=list)
    last_run: str | None = None
    run_count: int = 0
    enabled: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.job_id,
            "job_id": self.job_id,
            "name": self.name,
            "description": self.description or "",
            "cron": self.cron,
            "schedule": self.cron,
            "instruction": self.instruction,
            "created_at": self.created_at,
            "agent_id": self.agent_id,
            "runtime_id": self.runtime_id,
            "model": self.model,
            "task_type": self.task_type,
            "requires_approval": self.requires_approval,
            "approval_gate": self.requires_approval,
            "tags": list(self.tags or []),
            "last_run": self.last_run,
            "run_count": self.run_count,
            "enabled": self.enabled,
            "status": "active" if self.enabled else "paused",
            "failures": 0,
            "fail_count": 0,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ScheduledJob":
        """Reconstruct a ScheduledJob from its as_dict() output."""
        return cls(
            job_id=d.get("job_id", d.get("id", "")),
            name=d.get("name", ""),
            description=d.get("description") or None,
            cron=d.get("cron", "0 0 * * *"),
            instruction=d.get("instruction", ""),
            created_at=d.get("created_at", ""),
            agent_id=d.get("agent_id"),
            runtime_id=d.get("runtime_id"),
            model=d.get("model"),
            task_type=d.get("task_type", "scheduled"),
            requires_approval=d.get("requires_approval", False),
            tags=d.get("tags", []),
            last_run=d.get("last_run"),
            run_count=d.get("run_count", 0),
            enabled=d.get("enabled", True),
        )


class AgentScheduler:
    """Register, list, trigger, and delete cron-scheduled agent jobs.

    Usage::

        sched = AgentScheduler(on_fire=lambda job: print(job.instruction))
        job = sched.create(name="daily-lint", cron="0 9 * * *",
                           instruction="Run wiki lint and report")
        sched.trigger(job.job_id)   # fire immediately (webhook-style)
    """

    def __init__(
        self,
        on_fire: Callable[[ScheduledJob], None] | None = None,
        persistence: Any | None = None,
    ) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._on_fire = on_fire
        self._aps: Any = None
        # Durable store (ScheduleStore-like: load_all/upsert/remove). Optional —
        # when None the scheduler behaves exactly as before (in-memory only).
        self._persistence = persistence
        self._store = persistence  # #505: durable store (lazy-init if None)
        # Main event loop reference — set by ``attach_main_loop()`` from the
        # FastAPI lifespan so APScheduler's background thread can schedule
        # coroutines on it via ``asyncio.run_coroutine_threadsafe`` instead of
        # ``asyncio.run`` (which would create a *new* loop that can't reach
        # Motor/aiosqlite resources bound to the main loop).
        self._main_loop: Any = None
        if _HAS_APSCHEDULER:
            self._aps = BackgroundScheduler()
            self._aps.start()
            log.info("APScheduler background scheduler started")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        *,
        name: str,
        cron: str,
        instruction: str,
        description: str | None = None,  # BUG-11
        agent_id: str | None = None,
        runtime_id: str | None = None,
        model: str | None = None,
        task_type: str = "scheduled",
        requires_approval: bool = False,
        tags: list[str] | None = None,
        run_once: bool = False,
    ) -> ScheduledJob:
        """Register a new job.  Returns the created :class:`ScheduledJob`.

        ``run_once=True`` fires the job once then auto-deletes it, preventing
        accumulation of stale one-shot agency/fix schedules.

        Dedup guard: if a job with the same ``name`` already exists the existing
        job is returned unchanged (idempotent creation).
        """
        # Dedup: return existing job with same name instead of creating a duplicate.
        for existing in self._jobs.values():
            if existing.name == name:
                log.debug("Scheduler dedup — %r already exists (id=%s)", name, existing.job_id)
                return existing
        job_id = "job_" + secrets.token_hex(6)
        _tags = list(tags or [])
        if run_once and "run-once" not in _tags:
            _tags.append("run-once")
        job = ScheduledJob(
            job_id=job_id,
            name=name,
            description=description,
            cron=cron,
            instruction=instruction,
            created_at=_now(),
            agent_id=agent_id,
            runtime_id=runtime_id,
            model=model,
            task_type=task_type,
            requires_approval=requires_approval,
            tags=_tags,
        )
        self._jobs[job_id] = job
        self._register_aps(job)
        if self._running_loop() is not None:
            asyncio.create_task(self._persist(job))
        elif self._store is not None:
            # No event loop (sync caller, test fixture) — persist synchronously.
            try:
                self._store.upsert(job.as_dict())
            except Exception:
                pass
        log.info("Scheduled job created: id=%s name=%r cron=%r", job_id, name, cron)
        return job

    def trigger(self, job_id: str) -> ScheduledJob:
        """Fire a job immediately (webhook / manual trigger)."""
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Job {job_id!r} not found")
        self._fire(job_id)
        return self._jobs[job_id]

    def delete(self, job_id: str) -> bool:
        """Remove a job. Returns *True* if it existed."""
        if job_id not in self._jobs:
            return False
        del self._jobs[job_id]
        running = self._running_loop()
        if running is not None:
            asyncio.create_task(self._remove_persisted(job_id))
        elif self._main_loop is not None:
            # APScheduler thread: dispatch persistence delete onto the FastAPI
            # main loop so it can safely reach Motor/aiosqlite clients.
            try:
                asyncio.run_coroutine_threadsafe(
                    self._remove_persisted(job_id), self._main_loop,
                )
            except Exception:
                pass
        elif self._store is not None:
            # No event loop — delete synchronously.
            try:
                self._store.remove(job_id)
            except Exception:
                pass
        if self._aps:
            try:
                self._aps.remove_job(job_id)
            except Exception:
                pass
        log.info("Scheduled job deleted: id=%s", job_id)
        return True

    def list(self) -> list[ScheduledJob]:
        return list(self._jobs.values())

    def get(self, job_id: str) -> ScheduledJob | None:
        return self._jobs.get(job_id)

    def shutdown(self) -> None:
        if self._aps and self._aps.running:
            self._aps.shutdown(wait=False)

    def rename(self, job_id: str, *, name: str) -> ScheduledJob:
        """Update the display name of a job."""
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Job {job_id!r} not found")
        job.name = name
        if self._running_loop() is not None:
            asyncio.create_task(self._persist(job))
        elif self._store is not None:
            try:
                self._store.upsert(job.as_dict())
            except Exception:
                pass
        log.info("Job %s renamed to %r", job_id, name)
        return job

    def toggle(self, job_id: str, *, enabled: bool) -> ScheduledJob:
        """Enable or disable a job without deleting it."""
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Job {job_id!r} not found")
        job.enabled = enabled
        if self._running_loop() is not None:
            asyncio.create_task(self._persist(job))
        elif self._store is not None:
            # No event loop — persist synchronously.
            try:
                self._store.upsert(job.as_dict())
            except Exception:
                pass
        if self._aps:
            try:
                if enabled:
                    self._aps.resume_job(job_id)
                else:
                    self._aps.pause_job(job_id)
            except Exception:
                pass
        log.info("Job %s %s", job_id, "enabled" if enabled else "paused")
        return job

    def set_on_fire(self, on_fire: Callable[[ScheduledJob], Any] | None) -> None:
        self._on_fire = on_fire

    def attach_main_loop(self, loop: Any) -> None:
        """Capture the FastAPI main event loop so APScheduler's background
        thread can dispatch coroutines back onto it.

        Without this, ``_fire`` would fall back to ``asyncio.run(coro)`` which
        spins up a *fresh* event loop in the APScheduler thread. That fresh
        loop can't see Motor/aiosqlite clients bound to the main loop, so the
        on_fire coroutine (which creates a Task in the shared store) crashes
        with ``RuntimeError: Future attached to a different loop`` — and the
        agency's 24x7 cadences silently never produce any work.
        """
        self._main_loop = loop
        log.info("Scheduler main loop attached (loop=%r)", loop)

    # ------------------------------------------------------------------
    # Async scheduling helper
    # ------------------------------------------------------------------

    @staticmethod
    def _running_loop() -> "asyncio.AbstractEventLoop | None":
        """Return the running event loop, or ``None`` when called synchronously.

        Used so persistence coroutines are only *constructed* when there is a
        loop to await them on. Constructing a coroutine and then failing to
        schedule it (the old ``try create_task / except RuntimeError`` pattern)
        leaks an un-awaited coroutine and emits a RuntimeWarning.
        """
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return None

    # ── #505: Durable scheduler store ─────────────────────────────────────

    def attach_persistence(self, persistence: Any) -> int:
        """Attach a durable store and immediately rehydrate from it (#505).

        Called at startup once the DB is available (the scheduler itself is
        constructed at import time, before Mongo is reachable). Returns the
        number of jobs rehydrated.
        """
        self._persistence = persistence
        self._store = persistence
        return self.rehydrate()

    async def attach_persistence_async(self, persistence: Any) -> int:
        """Async variant of :meth:`attach_persistence` for callers already on
        an event loop (e.g. the FastAPI lifespan startup).

        The sync path delegates to ``asyncio.run()``, which raises and leaks a
        coroutine if invoked from a running loop. Async callers should use this
        method so hydration is awaited directly and the real count is returned.
        """
        self._persistence = persistence
        self._store = persistence
        return await self.hydrate()

    async def _ensure_store(self) -> None:
        if self._store is not None:
            return
        # Prefer the services.scheduler_store singleton (backward compat for
        # tests that inject via mod._store) and fall back to the agent-level
        # ScheduleStore when it isn't available.
        # Always use the migrated singleton path. If the singleton import or
        # init fails, log + return (caller checks self._store is None).
        # The previous try/except fallback to ScheduleStore() created a second
        # store instance, causing hydration/persistence drift.
        try:
            from packages.scheduler.store import get_scheduler_store
            self._store = get_scheduler_store()
        except Exception:  # noqa: BLE001
            log.exception("Scheduler store initialisation failed")

    def rehydrate(self) -> int:
        """Sync entry-point for attach_persistence(); delegates to hydrate().

        With no running loop (sync startup, tests) hydration runs to completion
        and the count is returned. If a loop is already running we cannot block
        on it, so hydration is scheduled as a background task and ``0`` is
        returned — constructing a coroutine for ``asyncio.run()`` here would
        raise and leak it. Async callers should use ``attach_persistence_async``
        for an awaited, accurate count.
        """
        loop = self._running_loop()
        if loop is not None:
            loop.create_task(self.hydrate())
            return 0
        return asyncio.run(self.hydrate())

    async def hydrate(self) -> int:
        """#505: Rehydrate persisted schedules on boot.

        Skips stale run-once jobs (already fired) and deletes them from the
        durable store so they don't accumulate across restarts (#844).

        Deduplicates by name: if multiple persisted jobs share the same name
        (caused by a previous bug where hydrate() loaded everything blindly),
        only the first is rehydrated; subsequent duplicates are deleted from
        the durable store. This self-heals the 1115-schedule multiplication bug
        on next restart.

        Returns the number of jobs restored from durable storage.
        """
        await self._ensure_store()
        if self._store is None:
            return 0
        try:
            result = self._store.load_all()
            docs = (await result) if inspect.isawaitable(result) else result
            count = 0
            cleaned = 0
            seen_names: set[str] = set()  # name dedup — prevents schedule multiplication
            for doc in docs:
                job_id = doc.get("job_id") or doc.get("id")
                if not job_id or job_id in self._jobs:
                    continue
                name = doc.get("name", "restored-job")
                tags = doc.get("tags") or []
                run_count = doc.get("run_count", 0)
                # Skip stale run-once jobs that already fired — they lived
                # their one life and should not be rehydrated. Also delete
                # them from the durable store so they don't pile up forever.
                if "run-once" in tags and run_count > 0:
                    try:
                        remove_result = self._store.remove(job_id)
                        if inspect.isawaitable(remove_result):
                            await remove_result
                        cleaned += 1
                    except Exception:
                        pass
                    continue
                # Name dedup: if we already hydrated a job with this name,
                # delete this duplicate from the durable store and skip it.
                if name in seen_names:
                    try:
                        remove_result = self._store.remove(job_id)
                        if inspect.isawaitable(remove_result):
                            await remove_result
                        cleaned += 1
                    except Exception:
                        pass
                    log.info("Hydrate: deduplicated schedule name=%r (job_id=%s)", name, job_id)
                    continue
                seen_names.add(name)
                job = ScheduledJob(
                    job_id=job_id,
                    name=name,
                    description=doc.get("description") or None,
                    cron=doc.get("cron", "0 0 * * *"),
                    instruction=doc.get("instruction", ""),
                    created_at=doc.get("created_at", _now()),
                    agent_id=doc.get("agent_id"),
                    runtime_id=doc.get("runtime_id"),
                    model=doc.get("model"),
                    task_type=doc.get("task_type", "scheduled"),
                    requires_approval=doc.get("requires_approval", False),
                    tags=tags,
                    last_run=doc.get("last_run"),
                    run_count=run_count,
                    enabled=doc.get("enabled", True),
                )
                self._jobs[job_id] = job
                self._register_aps(job)
                count += 1
            if count:
                log.info("Hydrated %d scheduled job(s) from durable store", count)
            if cleaned:
                log.info("Cleaned %d stale/duplicate job(s) from durable store", cleaned)
            return count
        except Exception as exc:
            log.warning("Scheduler hydration failed: %s", exc)
            return 0

    async def _persist(self, job: ScheduledJob) -> None:
        """#505: Persist a job to durable storage."""
        await self._ensure_store()
        if self._store is None:
            return
        try:
            result = self._store.upsert(job.as_dict())
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            log.warning("Scheduler persist failed for %s: %s", job.job_id, exc)

    async def force_cleanup(self) -> dict[str, int]:
        """Force-dedup and clean stale schedules from both the durable store
        and in-memory state.

        Can be called at any time (e.g. via an admin API endpoint) to clean up
        schedule multiplication without waiting for a restart. Reads all
        documents from the store, deduplicates by name, removes stale
        run-once jobs that have already fired, and prunes corresponding
        in-memory jobs from ``self._jobs`` so ``list()`` immediately reflects
        the cleanup.

        Does NOT remove in-memory jobs that have no corresponding store
        document (e.g. freshly-created jobs that haven't been persisted yet).

        Returns a summary dict with ``deleted``, ``deduped``, and ``total`` counts.
        """
        await self._ensure_store()
        summary = {"deleted": 0, "deduped": 0, "total": 0}
        if self._store is None:
            return summary
        try:
            result = self._store.load_all()
            docs = (await result) if inspect.isawaitable(result) else result
            summary["total"] = len(docs)
            seen_names: set[str] = set()
            for doc in docs:
                job_id = doc.get("job_id") or doc.get("id")
                if not job_id:
                    continue
                name = doc.get("name", "restored-job")
                tags = doc.get("tags") or []
                run_count = doc.get("run_count", 0)
                # Remove stale run-once jobs that already fired — from
                # both the durable store and in-memory state.
                if "run-once" in tags and run_count > 0:
                    try:
                        remove_result = self._store.remove(job_id)
                        if inspect.isawaitable(remove_result):
                            await remove_result
                    except Exception:
                        pass
                    self._jobs.pop(job_id, None)
                    summary["deleted"] += 1
                    continue
                # Also remove agency tasks that have retried 10+ times — these
                # are stuck tasks (e.g. NVIDIA 410 Gone) that keep re-queuing
                # and multiplying the schedule count. After 10 retries, the
                # task is permanently stuck and should be removed.
                if run_count > 10 and "agency" in tags:
                    try:
                        remove_result = self._store.remove(job_id)
                        if inspect.isawaitable(remove_result):
                            await remove_result
                    except Exception:
                        pass
                    self._jobs.pop(job_id, None)
                    summary["deleted"] += 1
                    log.info("Force-cleanup: removed stuck agency task name=%r (run_count=%d)", name, run_count)
                    continue
                # Name dedup — delete duplicates from store and memory.
                # The first-seen job stays; subsequent duplicates are removed.
                if name in seen_names:
                    try:
                        remove_result = self._store.remove(job_id)
                        if inspect.isawaitable(remove_result):
                            await remove_result
                    except Exception:
                        pass
                    self._jobs.pop(job_id, None)
                    summary["deduped"] += 1
                    log.info("Force-cleanup: deduplicated schedule name=%r (job_id=%s)", name, job_id)
                    continue
                seen_names.add(name)
            log.info("Force-cleanup: total=%d deleted=%d deduped=%d",
                     summary["total"], summary["deleted"], summary["deduped"])
        except Exception as exc:
            log.warning("Force-cleanup failed: %s", exc)
        return summary

    async def purge_all(self) -> dict[str, int]:
        """Delete EVERY schedule from the durable store and in-memory state.

        Operator maintenance escape hatch for schedule-backlog poisoning:
        force_cleanup() only removes fired run-once jobs, >10-retry agency
        tasks, and name-duplicates — a backlog of uniquely-named rows (2,859
        in the 2026-07-03 incident) passes all three filters and keeps
        OOM-cycling the free-tier instance on every boot. Platform loops
        recreate their own schedules on demand, so a full wipe is safe;
        company cadences are re-established by their owning services.

        Returns ``{"total": <rows seen>, "deleted": <rows removed>}``.
        """
        await self._ensure_store()
        summary = {"total": 0, "deleted": 0}
        if self._store is not None:
            try:
                result = self._store.load_all()
                docs = (await result) if inspect.isawaitable(result) else result
                summary["total"] = len(docs)
                for doc in docs:
                    job_id = doc.get("job_id") or doc.get("id")
                    if not job_id:
                        continue
                    await self._remove_persisted(job_id)
                    summary["deleted"] += 1
            except Exception as exc:
                log.warning("Purge-all failed while draining the store: %s", exc)
        # In-memory jobs (incl. any not yet persisted) — APScheduler entries
        # are unregistered via the normal delete() path where possible.
        for job_id in list(self._jobs):
            try:
                self.delete(job_id)
            except Exception:
                self._jobs.pop(job_id, None)
        log.info("Purge-all: total=%d deleted=%d (schedule store wiped by operator)",
                 summary["total"], summary["deleted"])
        return summary

    async def _remove_persisted(self, job_id: str) -> None:
        """#505: Remove a job from durable storage."""
        if self._store is None:
            await self._ensure_store()
        if self._store is None:
            return
        try:
            result = self._store.remove(job_id)
            if inspect.isawaitable(result):
                await result
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register_aps(self, job: ScheduledJob) -> None:
        if not self._aps:
            return
        try:
            parts = job.cron.strip().split()
            if len(parts) != 5:
                log.warning("Invalid cron expression %r for job %s", job.cron, job.job_id)
                return
            trigger = CronTrigger(
                minute=parts[0],
                hour=parts[1],
                day=parts[2],
                month=parts[3],
                day_of_week=parts[4],
            )
            self._aps.add_job(
                self._fire,
                trigger=trigger,
                args=[job.job_id],
                id=job.job_id,
            )
        except Exception as exc:
            log.warning("Could not register APScheduler job %s: %s", job.job_id, exc)

    def _fire(self, job_id: str) -> None:
        job = self._jobs.get(job_id)
        if not job or not job.enabled:
            return
        job.last_run = _now()
        job.run_count += 1
        # run-once: self-destruct after first fire so one-shot tasks don't accumulate.
        if "run-once" in (job.tags or []):
            self.delete(job_id)
            log.info("run-once job %s fired and self-deleted", job_id)
        # Persist the updated last_run/run_count. When called from the
        # APScheduler thread (no running loop) prefer the captured main loop
        # so the coroutine can safely touch Motor/aiosqlite clients bound to
        # it. ``asyncio.run`` would create a fresh loop that can't reach
        # those clients and crashes with "Future attached to a different loop".
        running = self._running_loop()
        if running is not None:
            asyncio.create_task(self._persist(job))
        elif self._main_loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._persist(job), self._main_loop)
            except Exception as exc:  # pragma: no cover - defensive
                log.debug("Scheduler persist thread-safe dispatch failed: %s", exc)
        # else: no loop at all — skip async persist (same as before)
        log.info("Firing job %s (%s)", job_id, job.name)
        if self._on_fire:
            try:
                result = self._on_fire(job)
                if inspect.isawaitable(result):
                    running = self._running_loop()
                    if running is not None:
                        # Called from an async context (e.g. scheduler.trigger()
                        # invoked from a request handler) — schedule on this loop.
                        running.create_task(result)
                    elif self._main_loop is not None:
                        # Called from APScheduler's background thread — dispatch
                        # onto the FastAPI main loop so the coroutine can safely
                        # use Motor/aiosqlite clients bound to it.
                        asyncio.run_coroutine_threadsafe(result, self._main_loop)
                    else:
                        # Last-resort fallback: only used before the lifespan
                        # wires ``attach_main_loop`` (e.g. tests). Creates a
                        # fresh loop — fine for pure-Python coroutines but will
                        # fail if the coroutine touches main-loop-bound resources.
                        asyncio.run(result)
            except Exception as exc:
                log.error("on_fire callback for job %s raised: %s", job_id, exc)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Singleton accessor ────────────────────────────────────────────────────────
# proxy.py owns the authoritative SCHEDULER instance and calls set_scheduler()
# during startup so other modules can retrieve it without a circular import.

_scheduler_instance: "AgentScheduler | None" = None


def set_scheduler(instance: "AgentScheduler") -> None:
    global _scheduler_instance
    _scheduler_instance = instance


def get_scheduler() -> "AgentScheduler":
    if _scheduler_instance is None:
        raise RuntimeError("Scheduler not initialised — call set_scheduler() at startup")
    return _scheduler_instance
