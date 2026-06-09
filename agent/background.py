"""agent/background.py — Background Agent

An always-on worker thread that processes tasks submitted from webhooks,
the scheduler, or the resource watchdog — without needing a user to open
a chat window.

Typical use: wire the scheduler's on_fire callback to BackgroundAgent.submit()
so scheduled jobs are automatically dispatched to the agent pipeline.
"""
from __future__ import annotations

import logging
import os
import queue
import secrets
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("qwen-background")

# Retry configuration for heavy task resilience
DEFAULT_MAX_RETRIES = int(os.environ.get("BG_AGENT_MAX_RETRIES", "3"))
DEFAULT_RETRY_DELAY_SEC = float(os.environ.get("BG_AGENT_RETRY_DELAY_SEC", "5.0"))
DEFAULT_HEARTBEAT_INTERVAL_SEC = float(os.environ.get("BG_AGENT_HEARTBEAT_INTERVAL_SEC", "30.0"))


@dataclass
class BackgroundTask:
    task_id: str
    kind: str  # "webhook" | "scheduled" | "watchdog" | "manual"
    payload: dict[str, Any]
    created_at: str
    status: str = "pending"  # pending | running | done | failed
    result: Any = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = DEFAULT_MAX_RETRIES
    last_heartbeat_at: str | None = None
    progress_message: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "payload": self.payload,
            "created_at": self.created_at,
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_heartbeat_at": self.last_heartbeat_at,
            "progress_message": self.progress_message,
        }


class BackgroundAgent:
    """Always-on worker that drains a task queue on a daemon thread.

    GATE: Golden Path step #11 (CEO loop) — this agent processes tasks
    submitted from webhooks, schedulers, and watchdogs without user interaction.

    HARDENED (PR #468+):
    - Retry logic with exponential backoff for failure resilience
    - Real-time heartbeat progress reporting to Telegram/notifiers
    - Task progress persisted in task metadata (progress_message, last_heartbeat_at)

    Usage::

        from agent.loop import AgentRunner
        runner = AgentRunner(ollama_base="http://localhost:11434")
        agent = BackgroundAgent(
            on_task_complete=notify_telegram,
            agent_runner=runner,
        )
        agent.start()
        agent.submit(BackgroundTask(
            task_id=secrets.token_hex(8),
            kind="webhook",
            payload={"instruction": "Run tests and report failures"},
            created_at=...,
        ))
    """

    def __init__(
        self,
        *,
        on_task_complete: Callable[[BackgroundTask], None] | None = None,
        agent_runner: Any | None = None,
    ) -> None:
        self._queue: queue.Queue[BackgroundTask] = queue.Queue()
        self._on_task_complete = on_task_complete
        self._agent_runner = agent_runner
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._tasks: dict[str, BackgroundTask] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def submit(self, task: BackgroundTask) -> BackgroundTask:
        """Enqueue *task* for processing. Returns the task (with task_id set)."""
        self._tasks[task.task_id] = task
        self._queue.put(task)
        log.info("Background task submitted: id=%s kind=%s", task.task_id, task.kind)
        return task

    def create_and_submit(
        self,
        kind: str,
        payload: dict[str, Any],
    ) -> BackgroundTask:
        """Convenience: create a task and submit it in one call."""
        task = BackgroundTask(
            task_id="bg_" + secrets.token_hex(6),
            kind=kind,
            payload=payload,
            created_at=_now(),
        )
        return self.submit(task)

    def get_task(self, task_id: str) -> BackgroundTask | None:
        return self._tasks.get(task_id)

    def list_tasks(self, status: str | None = None) -> list[BackgroundTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
            name="background-agent",
        )
        self._thread.start()
        log.info("BackgroundAgent worker started")

    def stop(self, timeout: float = 10.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                task = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue
            try:
                self._handle(task)
            finally:
                self._queue.task_done()

    def _handle(self, task: BackgroundTask) -> None:
        task.status = "running"
        log.info("Processing background task %s (%s)", task.task_id, task.kind)
        try:
            result = self._process(task)
            task.result = result
            task.status = "done"
        except Exception as exc:
            log.error("Background task %s failed: %s", task.task_id, exc)
            task.error = str(exc)
            task.status = "failed"
        finally:
            if self._on_task_complete:
                try:
                    self._on_task_complete(task)
                except Exception as exc:
                    log.warning("on_task_complete callback raised: %s", exc)

    def _process(self, task: BackgroundTask) -> Any:
        """Real handler — dispatches through AgentRunner when available.

        HARDENED (PR #468): This was previously a no-op stub that returned
        a dummy dict. Now it actually runs instructions via the agent pipeline
        with retry logic, heartbeat updates, and real-time progress reporting.

        Falls back to the legacy stub behavior only when no agent_runner
        is injected (for backward compatibility in bare test setups).
        """
        if self._agent_runner is None:
            log.debug(
                "Background task processed (no runner injected): %s", task.kind
            )
            return {
                "dispatched": True,
                "kind": task.kind,
                "payload_keys": list(task.payload),
                "note": "No AgentRunner injected — task not executed. Inject agent_runner for real dispatch.",
            }

        instruction = task.payload.get("instruction", "")
        if not instruction:
            instruction = task.payload.get("request", "")
        if not instruction:
            log.warning(
                "Background task %s has no instruction — nothing to execute",
                task.task_id,
            )
            return {"dispatched": False, "error": "No instruction in payload"}

        # Heartbeat updater — called by the agent job to report progress
        def heartbeat(phase: str = "", message: str = "") -> None:
            task.last_heartbeat_at = _now()
            if message:
                task.progress_message = message
                log.debug("BG task %s heartbeat: %s — %s", task.task_id, phase, message)
            # Refresh notification with progress if callback wired
            if self._on_task_complete:
                try:
                    self._on_task_complete(task)
                except Exception as e:
                    log.exception("on_task_complete callback failed during heartbeat for task %s: %s", task.task_id, e)

        # Retry loop with exponential backoff for failure resilience
        last_error: str | None = None
        max_retries = max(0, min(task.max_retries, DEFAULT_MAX_RETRIES))

        for attempt in range(max_retries + 1):
            task.retry_count = attempt
            if attempt > 0:
                delay = DEFAULT_RETRY_DELAY_SEC * (2 ** (attempt - 1))  # exponential backoff
                log.info(
                    "BG task %s retry %d/%d after %.1fs: %s",
                    task.task_id, attempt, max_retries, delay, last_error or "unknown",
                )
                time.sleep(delay)

            try:
                # Dispatch through the real agent runner (synchronous wrapper)
                import asyncio  # noqa: I001 — imported here for optional dependency
                runner = self._agent_runner

                # Emit initial heartbeat
                heartbeat("starting", f"Task starting (attempt {attempt + 1}/{max_retries + 1})")

                result = asyncio.run(
                    runner.run(
                        instruction=instruction,
                        history=[],
                        requested_model=task.payload.get("model"),
                        auto_commit=task.payload.get("auto_commit", False),
                        max_steps=task.payload.get("max_steps", 5),
                    )
                )

                # Success — record KPIs and return result
                try:
                    from agent.kpi import get_tracker
                    tracker = get_tracker()
                    tracker.record_session()
                    tracker.record_plan()
                    for s in result.get("steps", []):
                        if s.get("status") == "applied":
                            tracker.record_step_applied()
                        elif s.get("status") == "failed":
                            tracker.record_step_failed()
                        elif s.get("status") == "skipped":
                            tracker.record_step_skipped()
                    tracker.record_events()
                except Exception as e:
                    log.error("KPI tracking failed for task %s: %s", task.task_id, e)  # KPI tracking is best-effort

                heartbeat("completed", result.get("summary", "Task completed"))
                return result

            except Exception as exc:
                last_error = str(exc)
                log.error(
                    "BG task %s attempt %d/%d failed: %s",
                    task.task_id, attempt + 1, max_retries + 1, exc,
                )
                # Emit failure heartbeat so watchers know progress
                heartbeat("retry", f"Attempt {attempt + 1} failed: {last_error[:100]}")

                # Don't retry on certain fatal errors
                if "Signal" in str(type(exc).__name__):
                    # asyncio signal handlers (KeyboardInterrupt, SystemExit) — don't retry
                    break

        # All retries exhausted
        log.error(
            "BG task %s FAILED after %d attempts. Last error: %s",
            task.task_id, max_retries + 1, last_error,
        )
        heartbeat("failed", f"Task failed after {max_retries + 1} attempts: {last_error[:200]}")
        return {"dispatched": True, "error": last_error, "attempts": max_retries + 1}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
