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
        if self._running_loop() is not None:
            asyncio.create_task(self._remove_persisted(job_id))
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
        try:
            from services.scheduler_store import get_scheduler_store
            self._store = get_scheduler_store()
            return
        except Exception:
            pass
        try:
            from agent.schedule_store import ScheduleStore
            self._store = ScheduleStore()
        except Exception:
            pass

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

        Returns the number of jobs restored from durable storage.
        """
        await self._ensure_store()
        if self._store is None:
            return 0
        try:
            result = self._store.load_all()
            docs = (await result) if inspect.isawaitable(result) else result
            count = 0
            for doc in docs:
                job_id = doc.get("job_id") or doc.get("id")
                if not job_id or job_id in self._jobs:
                    continue
                job = ScheduledJob(
                    job_id=job_id,
                    name=doc.get("name", "restored-job"),
                    cron=doc.get("cron", "0 0 * * *"),
                    instruction=doc.get("instruction", ""),
                    created_at=doc.get("created_at", _now()),
                    agent_id=doc.get("agent_id"),
                    runtime_id=doc.get("runtime_id"),
                    model=doc.get("model"),
                    task_type=doc.get("task_type", "scheduled"),
                    requires_approval=doc.get("requires_approval", False),
                    tags=doc.get("tags", []),
                    last_run=doc.get("last_run"),
                    run_count=doc.get("run_count", 0),
                    enabled=doc.get("enabled", True),
                )
                self._jobs[job_id] = job
                self._register_aps(job)
                count += 1
            if count:
                log.info("Hydrated %d scheduled job(s) from durable store", count)
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
        if self._running_loop() is not None:
            asyncio.create_task(self._persist(job))
        # else: no event loop (sync caller / APScheduler thread) — skip async persist
        log.info("Firing job %s (%s)", job_id, job.name)
        if self._on_fire:
            try:
                result = self._on_fire(job)
                if inspect.isawaitable(result):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        asyncio.run(result)
                    else:
                        loop.create_task(result)
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
