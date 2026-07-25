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
from typing import TYPE_CHECKING, Any

from runtimes.manager import get_runtime_manager
from tasks.automation import TaskAutomationService
from tasks.dispatcher import TaskDispatcher

if TYPE_CHECKING:
    from packages.scheduler.scheduler import AgentScheduler
    from tasks.store import TaskStore
    from runtimes.manager import RuntimeManager

log = logging.getLogger("llm-wiki")

_DEFAULT_POLL_INTERVAL = 10.0

# Module-level handle to the single trend-watch poller task, so repeated
# _start_autonomy_loops() calls never schedule a duplicate (idempotency).
_trend_watch_task: "asyncio.Task | None" = None
# Module-level handle to the single ephemeral-company reaper task (idempotency).
_ephemeral_reaper_task: "asyncio.Task | None" = None
# Module-level handle to the single CEO supervisor task (idempotency): a second
# sweeper would double every re-drive it decides to make.
_ceo_supervisor_task: "asyncio.Task | None" = None
# Module-level handle to the in-process Hermes sidecar (idempotency + shutdown).
_hermes_server: "Any | None" = None
_hermes_task: "asyncio.Task | None" = None

# Hermes binds here. 127.0.0.1 deliberately, NEVER 0.0.0.0: POST /tasks executes
# arbitrary agent work and its bearer check is optional (HERMES_API_KEY may be
# unset), so exposing it on a public interface would be a remote-execution hole.
# Loopback keeps it reachable by the adapter in this same container and by
# nothing else.
_HERMES_HOST = "127.0.0.1"
_HERMES_PORT = 8100
_HERMES_STARTUP_TIMEOUT_SEC = 20.0


async def _await_hermes_ready(server: Any, task: "asyncio.Task") -> None:
    """Block until uvicorn is genuinely accepting connections.

    Without this the RuntimeManager's first health probe races the bind and marks
    Hermes down for a whole cooldown despite it coming up milliseconds later —
    which presents as "Hermes is offline" on a deployment where it is running.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + _HERMES_STARTUP_TIMEOUT_SEC
    while not getattr(server, "started", False):
        if task.done() or loop.time() > deadline:
            raise RuntimeError("Hermes server did not start within timeout")
        await asyncio.sleep(0.05)


async def _start_hermes_in_process() -> "asyncio.Task | None":
    """Run the agency's own Hermes server inside this process, on loopback.

    ``RUN_HERMES_IN_PROCESS`` and ``settings.is_hermes_in_process`` existed since
    the flag was introduced, and ``CLAUDE.md`` documents "Hermes in-process :8100"
    as production behaviour — but **nothing ever consumed the flag**. The only way
    to run Hermes was ``Dockerfile.hermes`` as the separate ``agency-hermes``
    Render service. On a single-service deployment the adapter therefore probed
    its default ``http://localhost:8100``, found nothing listening, and reported
    the runtime permanently offline — so ``RUNTIME_CODE_GENERATION=hermes``
    silently fell back to ``internal_agent`` forever.

    This closes that gap: same process, same event loop, no second service, no
    new configuration source. Returns the serving task, or ``None`` when the flag
    is off or startup failed — Hermes is an optimisation, so a failure must
    degrade to the existing fallback rather than break boot.
    """
    global _hermes_server, _hermes_task
    if _hermes_task is not None and not _hermes_task.done():
        return _hermes_task  # idempotent: web + worker may both call in one process

    from packages.config.settings import settings
    if not settings.is_hermes_in_process:
        log.info("Hermes in-process server disabled (RUN_HERMES_IN_PROCESS)")
        return None

    try:
        import uvicorn
        from services.hermes_server import app as hermes_app

        config = uvicorn.Config(
            hermes_app, host=_HERMES_HOST, port=_HERMES_PORT,
            log_level="warning", access_log=False,
        )
        _hermes_server = uvicorn.Server(config)
        _hermes_task = asyncio.create_task(_hermes_server.serve())

        await _await_hermes_ready(_hermes_server, _hermes_task)
    except Exception as exc:  # noqa: BLE001 — never break boot for an optimisation
        log.warning(
            "Hermes in-process server not started (%s) — code tasks will fall "
            "back to internal_agent", exc,
        )
        _hermes_server = None
        _hermes_task = None
        return None

    log.info("Hermes in-process server listening on http://%s:%d",
             _HERMES_HOST, _HERMES_PORT)
    return _hermes_task


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
    autonomy_tasks: list = field(default_factory=list)  # type: ignore[type-arg]
    # In-process Hermes sidecar; None when disabled or it failed to start.
    hermes_task: "asyncio.Task | None" = None  # type: ignore[type-arg]
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
        for t in self.autonomy_tasks:
            t.cancel()
        # Await the cancelled poller task(s) so they fully settle and their
        # exceptions are observed before stop() returns.
        if self.autonomy_tasks:
            results = await asyncio.gather(*self.autonomy_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    log.warning("Autonomy task shutdown error: %s", result)
        global _trend_watch_task, _ephemeral_reaper_task, _ceo_supervisor_task
        _trend_watch_task = None
        _ephemeral_reaper_task = None
        _ceo_supervisor_task = None
        try:
            from services.ceo_supervisor import get_ceo_supervisor
            get_ceo_supervisor().stop()
        except Exception as exc:  # noqa: BLE001 — shutdown is best-effort
            log.warning("Failed to stop CEO supervisor: %s", exc)
        # Stop the threaded autonomy engines (best-effort, but never silent).
        for getter in ("get_self_healing_agent", "get_improvement_loop"):
            try:
                if getter == "get_self_healing_agent":
                    from agent.self_healing import get_self_healing_agent as _g
                else:
                    from agent.improvement_loop import get_improvement_loop as _g
                inst = _g()
                if inst is not None:
                    inst.stop()
            except Exception as exc:  # noqa: BLE001 — shutdown is best-effort
                log.warning("Failed to stop autonomy engine %s: %s", getter, exc)
        await self._stop_hermes()
        await self.runtime_manager.stop()
        log.info("RuntimeManager stopped")

    async def _stop_hermes(self) -> None:
        """Shut the in-process Hermes down so port 8100 is released.

        Uvicorn's own graceful path is used first: setting ``should_exit`` lets
        it close listeners and finish in-flight tasks. Cancelling the task
        outright would leave the socket bound until the process dies, which on a
        reload turns the next boot's bind into an "address already in use" and
        silently costs the runtime.
        """
        global _hermes_server, _hermes_task
        if self.hermes_task is None:
            return
        if _hermes_server is not None:
            _hermes_server.should_exit = True
        try:
            await asyncio.wait_for(self.hermes_task, timeout=10.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            self.hermes_task.cancel()
        except Exception as exc:  # noqa: BLE001 — shutdown is best-effort
            log.warning("Hermes in-process shutdown error: %s", exc)
        _hermes_server = None
        _hermes_task = None
        log.info("Hermes in-process server stopped")


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
    # Capture the FastAPI main event loop so APScheduler's background thread
    # can dispatch on_fire coroutines back onto it via
    # ``asyncio.run_coroutine_threadsafe``. Without this, ``_fire`` would
    # ``asyncio.run()`` a fresh loop in the APScheduler thread — that fresh
    # loop can't reach Motor/aiosqlite clients bound to the main loop, so the
    # on_fire coroutine (which creates a Task in the shared store) crashes
    # with "Future attached to a different loop" and the agency's 24x7
    # cadences silently never produce any work.
    try:
        main_loop = asyncio.get_running_loop()
        scheduler.attach_main_loop(main_loop)
    except RuntimeError:
        log.warning("Scheduler main-loop attach skipped (no running loop)")
    log.info("Scheduler automation wired to task workflow")

    # Durable schedule persistence + boot rehydration (#505): without this, the
    # in-memory scheduler loses every company cadence on redeploy.
    try:
        from agent.schedule_store import ScheduleStore

        # This runs inside the async lifespan, so await hydration directly —
        # the sync attach_persistence() would call asyncio.run() on the live
        # loop, raising (and silently skipping rehydration) instead.
        n = await scheduler.attach_persistence_async(ScheduleStore())
        log.info("Scheduler durable persistence attached (%d job(s) rehydrated)", n)
    except Exception as exc:
        log.warning("Scheduler durable persistence not attached: %s", exc)

    # Must precede runtime_manager.start(): that call runs the first health
    # probe, and a Hermes that is not yet listening is marked down for a whole
    # cooldown even though it comes up milliseconds later.
    hermes_task = await _start_hermes_in_process()

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
    autonomy_tasks = _start_autonomy_loops(scheduler)

    return BackgroundServices(
        runtime_manager=runtime_manager,
        dispatcher=dispatcher,
        dispatcher_task=dispatcher_task,
        autonomy_tasks=autonomy_tasks,
        hermes_task=hermes_task,
    )


def _env_on(name: str, default: str = "true") -> bool:
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "off")


def _start_autonomy_loops(scheduler: "AgentScheduler") -> list:
    """Bootstrap the autonomous loops that turn signals into work (the heart of
    the Autonomy Charter). These engines existed but were **never started** in
    production — their singletons stayed ``None``, so self-heal, log-driven fixes,
    feature generation, and trend application silently never ran. Each is wired
    here, env-gated, idempotent, and fully defensive (never crashes startup):

      • ImprovementLoop  (Loop 2) — continuous TODO/coverage/perf signals → fix jobs.
      • SelfHealingAgent (Loop 1 / G2) — failure signals → verified fixes.
      • LogMonitor       (Loop 1) — runtime ERROR/CRITICAL logs → auto fix tasks.
      • TrendWatcher     (Loop 4 / G4) — periodic trend fetch → per-company scoping.

    The self-heal chain is LogMonitor → SelfHealingAgent → ImprovementLoop →
    ``scheduler.create`` → dispatcher, so ImprovementLoop must be wired first.
    Returns any asyncio tasks created (the trend poller) for shutdown cleanup.
    """
    tasks: list = []

    # 1. ImprovementLoop — must exist before self-heal so _dispatch_fix lands work.
    if _env_on("AGENCY_IMPROVEMENT_ENABLED"):
        try:
            from agent.improvement_loop import (
                ImprovementLoop, get_improvement_loop, set_improvement_loop,
            )
            if get_improvement_loop() is None:
                loop = ImprovementLoop(on_task=scheduler.create)
                set_improvement_loop(loop)
                loop.start()
                log.info("ImprovementLoop started — continuous-improvement signals are live")
        except Exception as exc:  # noqa: BLE001
            log.warning("ImprovementLoop could not start: %s", exc)

    # 2. SelfHealingAgent — verification sweeper + heal ledger (G2).
    if _env_on("AGENCY_SELF_HEAL_ENABLED"):
        try:
            from agent.self_healing import (
                SelfHealingAgent, get_self_healing_agent, set_self_healing_agent,
            )
            if get_self_healing_agent() is None:
                healer = SelfHealingAgent()
                set_self_healing_agent(healer)
                healer.start()
                log.info("SelfHealingAgent started — failures now heal + self-verify (G2)")
        except Exception as exc:  # noqa: BLE001
            log.warning("SelfHealingAgent could not start: %s", exc)

    # 3. LogMonitor — runtime ERROR/CRITICAL → auto fix tasks (needs the healer).
    if _env_on("AGENCY_LOG_MONITOR_ENABLED"):
        try:
            from agent.log_monitor import LogMonitor, get_log_monitor, set_log_monitor
            if get_log_monitor() is None:
                monitor = LogMonitor()
                monitor.attach()
                set_log_monitor(monitor)
                log.info("LogMonitor attached — backend errors auto-create fix tasks (Loop 1)")
        except Exception as exc:  # noqa: BLE001
            log.warning("LogMonitor could not start: %s", exc)

    # 4. TrendWatcher — periodic fetch → per-company scoping (Loop 4 / G4).
    if _env_on("AGENCY_TREND_WATCH_ENABLED"):
        try:
            from agent.trend_watcher import (
                TrendWatcher, get_trend_watcher, set_trend_watcher,
            )
            if get_trend_watcher() is None:
                set_trend_watcher(TrendWatcher())
                log.info("TrendWatcher registered — periodic trend fetch + per-company scoping (G4)")
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            # Idempotent: never schedule a second poller if one is already live
            # (a duplicate would double trend fetches and the per-company fan-out).
            global _trend_watch_task
            if running is not None and (_trend_watch_task is None or _trend_watch_task.done()):
                _trend_watch_task = running.create_task(_trend_watch_loop())
                tasks.append(_trend_watch_task)
            elif running is None:
                log.info("TrendWatcher poller not started (no running event loop)")
        except Exception as exc:  # noqa: BLE001
            log.warning("TrendWatcher could not start: %s", exc)

    # 5. CEO supervisor — the 24x7 babysitter. Sweeps the CEO ledger, closes
    #    finished goals, re-drives stalled ones, and abandons the ones that
    #    spent their budget. Without it a delegation that dies mid-flight (a
    #    recycled process, a sleeping runtime) stays open forever and the
    #    agency silently drops work while looking busy.
    try:
        from services.ceo_supervisor import get_ceo_supervisor, supervisor_enabled
        if supervisor_enabled():
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            global _ceo_supervisor_task
            if running is not None and (
                _ceo_supervisor_task is None or _ceo_supervisor_task.done()
            ):
                supervisor = get_ceo_supervisor()
                _ceo_supervisor_task = running.create_task(supervisor.run_forever())
                tasks.append(_ceo_supervisor_task)
                log.info("CEO supervisor started — stalled goals are re-driven to closure 24x7")
            elif running is None:
                log.info("CEO supervisor not started (no running event loop)")
        else:
            log.info("CEO supervisor disabled (CEO_SUPERVISOR_ENABLED=false)")
    except Exception as exc:  # noqa: BLE001
        log.warning("CEO supervisor could not start: %s", exc)

    # 6. Ephemeral company reaper — destroy expired non-admin agencies (free
    #    Render hosting policy). Persistent (admin) companies are never touched.
    try:
        from services.ephemeral_reaper import reaper_enabled, ephemeral_reaper_loop
        if reaper_enabled():
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            global _ephemeral_reaper_task
            if running is not None and (_ephemeral_reaper_task is None or _ephemeral_reaper_task.done()):
                _ephemeral_reaper_task = running.create_task(ephemeral_reaper_loop())
                tasks.append(_ephemeral_reaper_task)
                log.info("Ephemeral company reaper started — expired non-admin agencies are auto-destroyed")
            elif running is None:
                log.info("Ephemeral reaper not started (no running event loop)")
        else:
            log.info("Ephemeral company reaper disabled (EPHEMERAL_COMPANY_REAPER_ENABLED=false)")
    except Exception as exc:  # noqa: BLE001
        log.warning("Ephemeral reaper could not start: %s", exc)

    return tasks


def _env_float(name: str, default: float) -> float:
    """Parse a float env var, falling back to *default* on a bad value (never raises)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        log.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


async def _trend_watch_loop() -> None:
    """Periodically fetch trends (which fans out per-company scoped tasks, G4).

    Sleeps a short warm-up, then fetches when due and re-checks hourly. Defensive:
    a transient fetch error (or a bad timing env var) never stops the loop.
    """
    from agent.trend_watcher import get_trend_watcher

    await asyncio.sleep(_env_float("TREND_WATCH_WARMUP_SEC", 60.0))
    while True:
        try:
            watcher = get_trend_watcher()
            if watcher is not None and watcher.due_for_fetch():
                await watcher.fetch()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("TrendWatcher fetch cycle error: %s", exc)
        await asyncio.sleep(_env_float("TREND_WATCH_POLL_SEC", 3600.0))


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
        # Capture the FastAPI main loop so the CEO thread can dispatch
        # run_cycle() onto it via run_coroutine_threadsafe — same fix as
        # the scheduler. Without this, asyncio.run() creates a fresh loop
        # that can't see Motor/aiosqlite clients bound to the main loop.
        try:
            main_loop = asyncio.get_running_loop()
            agency.attach_main_loop(main_loop)
        except RuntimeError:
            log.warning("CEO agency main-loop attach skipped (no running loop)")
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
