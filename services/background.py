"""services/background.py — shared background-service startup.

Both the FastAPI web lifespan and ``worker_main.py`` call
``start_background_services()`` to start the same set of long-running asyncio
tasks (RuntimeManager, TaskDispatcher, SCHEDULER, self-bootstrap).

``RUN_BACKGROUND_IN_WEB`` (default ``"true"``) controls whether the web process
also runs these services.  Set it to ``"false"`` once a dedicated worker process
is deployed so work is not double-processed.
"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from runtimes.manager import get_runtime_manager
from tasks.automation import TaskAutomationService
from tasks.dispatcher import TaskDispatcher

if TYPE_CHECKING:
    from agent.scheduler import AgentScheduler
    from tasks.store import TaskStore
    from runtimes.manager import RuntimeManager

log = logging.getLogger("llm-wiki")

_DEFAULT_POLL_INTERVAL = 10.0


def run_background_in_web() -> bool:
    """Return True when the web process should also run background services."""
    val = os.environ.get("RUN_BACKGROUND_IN_WEB", "true").strip().lower()
    return val in {"true", "1", "yes"}


@dataclass
class BackgroundServices:
    """Handle returned by ``start_background_services`` — call ``stop()`` on shutdown."""

    runtime_manager: "RuntimeManager"
    dispatcher: "TaskDispatcher"
    dispatcher_task: asyncio.Task  # type: ignore[type-arg]
    _stopped: bool = field(default=False, init=False, repr=False)

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self.dispatcher.stop()
        self.dispatcher_task.cancel()
        try:
            await self.dispatcher_task
        except asyncio.CancelledError:
            pass
        log.info("Task dispatcher stopped")
        await self.runtime_manager.stop()
        log.info("RuntimeManager stopped")


async def start_background_services(
    workspace_root: str | Path,
    task_store: "TaskStore",
    scheduler: "AgentScheduler",
) -> BackgroundServices:
    """Start RuntimeManager, TaskDispatcher, SCHEDULER, and self-bootstrap.

    Returns a :class:`BackgroundServices` handle whose ``stop()`` method should
    be called on process shutdown (or when the FastAPI lifespan context exits).

    Parameters
    ----------
    workspace_root:
        Absolute path used as the working directory for dispatched tasks.
    task_store:
        The active TaskStore instance (SQLite or MongoDB).
    scheduler:
        The AgentScheduler singleton; its ``set_on_fire`` handler is wired here.
    """
    runtime_manager = get_runtime_manager()

    task_automation = TaskAutomationService(store=task_store)
    scheduler.set_on_fire(task_automation.handle_scheduled_job)
    log.info("Scheduler automation wired to task workflow")

    # Durable schedule persistence + boot rehydration (#505): without this, the
    # in-memory scheduler loses every company cadence on redeploy.
    try:
        from agent.schedule_store import ScheduleStore

        n = scheduler.attach_persistence(ScheduleStore())
        log.info("Scheduler durable persistence attached (%d job(s) rehydrated)", n)
    except Exception as exc:
        log.warning("Scheduler durable persistence not attached: %s", exc)

    await runtime_manager.start()
    log.info(
        "RuntimeManager started (%d runtimes registered)",
        len(runtime_manager._registry.ids()),
    )

    dispatcher = TaskDispatcher(
        workspace_root=str(workspace_root),
        poll_interval_s=_DEFAULT_POLL_INTERVAL,
    )
    dispatcher_task = asyncio.create_task(dispatcher.run_forever())
    log.info("Task dispatcher started in background")

    _schedule_self_bootstrap()
    _start_ceo_agency()

    return BackgroundServices(
        runtime_manager=runtime_manager,
        dispatcher=dispatcher,
        dispatcher_task=dispatcher_task,
    )


def _start_ceo_agency() -> None:
    """Start the 24×7 CEO agency loop that *proactively* generates work.

    Without this the dispatcher only ever runs reactively (quick notes, scheduled
    cadences), so specialists sit idle between events — the proactive CEO that is
    supposed to drive continuous improvement was never actually started in
    production. Gated by ``AGENCY_CEO_ENABLED`` (default on); never crashes startup.
    When the CEO LLM is unreachable (e.g. no local Ollama in the cloud) the cycle
    falls back to rule-based directives, so work is still generated.
    """
    if os.environ.get("AGENCY_CEO_ENABLED", "true").strip().lower() in ("0", "false", "no", "off"):
        log.info("CEO agency loop disabled (AGENCY_CEO_ENABLED=false)")
        return
    try:
        from agent.agency import Agency, get_agency, set_agency

        if get_agency() is not None:
            return  # already started
        agency = Agency()
        set_agency(agency)
        agency.start()
        log.info("CEO agency loop started — proactive 24×7 work generation is live")
    except Exception as exc:  # never let the CEO loop break startup
        log.warning("CEO agency loop could not start: %s", exc)


def _schedule_self_bootstrap() -> None:
    """Fire-and-forget self-bootstrap; never blocks or crashes startup."""
    try:
        from services.self_bootstrap import ensure_self_company, self_bootstrap_enabled

        if self_bootstrap_enabled():
            asyncio.create_task(ensure_self_company())
            log.info("Self-bootstrap scheduled (platform onboards itself as a company)")
    except Exception as exc:  # pragma: no cover — defensive
        log.warning("Self-bootstrap could not be scheduled: %s", exc)
