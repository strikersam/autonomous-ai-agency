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

log = logging.getLogger("qwen-proxy")

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
        """Reconstruct a ScheduledJob from a persisted dict (see as_dict)."""
        return cls(
            job_id=d.get("job_id") or d.get("id") or ("job_" + secrets.token_hex(6)),
            name=d.get("name", ""),
            cron=d.get("cron") or d.get("schedule", ""),
            instruction=d.get("instruction", ""),
            created_at=d.get("created_at") or _now(),
            agent_id=d.get("agent_id"),
            runtime_id=d.get("runtime_id"),
            model=d.get("model"),
            task_type=d.get("task_type", "scheduled"),
            requires_approval=bool(d.get("requires_approval", d.get("approval_gate", False))),
            tags=list(d.get("tags") or []),
            last_run=d.get("last_run"),
            run_count=int(d.get("run_count", 0) or 0),
            enabled=bool(d.get("enabled", True)),
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
        # Durable store (ScheduleStore-like: load_all/upsert/remove). Optional —
        # when None the scheduler behaves exactly as before (in-memory only).
        self._persistence = persistence
        self._aps: Any = None
        if _HAS_APSCHEDULER:
            self._aps = BackgroundScheduler()
            self._aps.start()
            log.info("APScheduler background scheduler started")

    def _persist(self, job: ScheduledJob) -> None:
        if self._persistence is None:
            return
        try:
            self._persistence.upsert(job.as_dict())
        except Exception as exc:  # never let persistence break scheduling
            log.warning("Schedule persist failed for %s: %s", job.job_id, exc)

    def rehydrate(self) -> int:
        """Reload persisted schedules on boot and re-register their cron triggers.

        Returns the number of jobs rehydrated. Does NOT fire jobs or re-persist
        them. Safe to call once at startup after construction. Fixes #505 — the
        12 company cadences + tech-debt burndown now survive a redeploy.
        """
        if self._persistence is None:
            return 0
        count = 0
        try:
            docs = self._persistence.load_all()
        except Exception as exc:
            log.warning("Schedule rehydrate: load_all failed: %s", exc)
            return 0
        for d in docs:
            try:
                job = ScheduledJob.from_dict(d)
                if job.job_id in self._jobs:
                    continue
                self._jobs[job.job_id] = job
                # Register every job with APScheduler — including disabled ones —
                # then pause the disabled ones, so a later toggle(enabled=True)
                # can resume_job() instead of silently failing on a missing job.
                self._register_aps(job)
                if not job.enabled and self._aps:
                    try:
                        self._aps.pause_job(job.job_id)
                    except Exception as exc:
                        log.warning("Could not pause rehydrated job %s: %s", job.job_id, exc)
                count += 1
            except Exception as exc:
                log.warning("Schedule rehydrate: skipping bad record %r: %s", d, exc)
        if count:
            log.info("Rehydrated %d scheduled job(s) from durable store", count)
        return count

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
    ) -> ScheduledJob:
        """Register a new job.  Returns the created :class:`ScheduledJob`."""
        job_id = "job_" + secrets.token_hex(6)
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
            tags=list(tags or []),
        )
        self._jobs[job_id] = job
        self._register_aps(job)
        self._persist(job)
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
        if self._aps:
            try:
                self._aps.remove_job(job_id)
            except Exception:
                pass
        if self._persistence is not None:
            try:
                self._persistence.remove(job_id)
            except Exception as exc:
                log.warning("Schedule remove-persist failed for %s: %s", job_id, exc)
        log.info("Scheduled job deleted: id=%s", job_id)
        return True

    def list(self) -> list[ScheduledJob]:
        return list(self._jobs.values())

    def get(self, job_id: str) -> ScheduledJob | None:
        return self._jobs.get(job_id)

    def shutdown(self) -> None:
        if self._aps and self._aps.running:
            self._aps.shutdown(wait=False)

    def toggle(self, job_id: str, *, enabled: bool) -> ScheduledJob:
        """Enable or disable a job without deleting it."""
        job = self._jobs.get(job_id)
        if not job:
            raise KeyError(f"Job {job_id!r} not found")
        job.enabled = enabled
        if self._aps:
            try:
                if enabled:
                    self._aps.resume_job(job_id)
                else:
                    self._aps.pause_job(job_id)
            except Exception:
                pass
        self._persist(job)
        log.info("Job %s %s", job_id, "enabled" if enabled else "paused")
        return job

    def set_on_fire(self, on_fire: Callable[[ScheduledJob], Any] | None) -> None:
        self._on_fire = on_fire

    def attach_persistence(self, persistence: Any) -> int:
        """Attach a durable store and immediately rehydrate from it (#505).

        Called at startup once the DB is available (the scheduler itself is
        constructed at import time, before Mongo is reachable). Returns the
        number of jobs rehydrated.
        """
        self._persistence = persistence
        return self.rehydrate()

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
        self._persist(job)  # keep last_run/run_count durable
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
