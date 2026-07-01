"""worker_main.py — always-on background worker entrypoint.

Runs the RuntimeManager, TaskDispatcher, CEO Agency loop, and SCHEDULER
**without** the FastAPI HTTP server.  Deploy as a separate Render worker
service (``type: worker``) so task execution and the CEO loop continue 24×7
even when the web process is sleeping due to inactivity on the free tier.

Usage::

    python worker_main.py

Environment
-----------
STORAGE_BACKEND    "sqlite" or "mongodb" (default: mongodb)
MONGO_URL          MongoDB connection string (required if STORAGE_BACKEND=mongodb)
RUN_BACKGROUND_IN_WEB
                   Set to "false" on the web service once this worker is
                   deployed, so background work is not double-processed.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

# Ensure the repo root is on sys.path so all internal imports resolve.
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(worker)s %(message)s",
    defaults={"worker": "[worker]"},
)
log = logging.getLogger("worker")


async def _main() -> None:
    """Bootstrap services and run until SIGTERM / SIGINT."""
    from packages.scheduler.scheduler import AgentScheduler, set_scheduler
    from tasks.store import get_task_store, set_task_store
    from db import get_store
    from services.background import start_background_services

    # Initialise the scheduler singleton (same pattern as backend/server.py)
    scheduler = AgentScheduler()
    set_scheduler(scheduler)

    # Initialise the task store (mirrors backend bootstrap)
    store = get_store()
    task_store = get_task_store()
    # Ensure the task store is wired (set_task_store idempotent when same instance)
    set_task_store(task_store)

    log.info("Worker starting — STORAGE_BACKEND=%s", os.environ.get("STORAGE_BACKEND", "mongodb"))

    # Optional DB bootstrap (non-fatal; same logic as web lifespan)
    try:
        from db import ensure_bootstrap

        await ensure_bootstrap()
        log.info("DB bootstrap complete")
    except Exception as exc:
        log.warning("DB bootstrap deferred: %s — continuing in limited mode", exc)

    bg = await start_background_services(
        workspace_root=ROOT_DIR,
        task_store=task_store,
        scheduler=scheduler,
    )
    log.info("All background services started — worker is running")

    # Start the Telegram bot on the worker service (the web service has
    # TELEGRAM_POLLER_DISABLED=true so only ONE process polls getUpdates).
    # The bot runs as a background task alongside the other services.
    from packages.notifications.bot import run_bot

    async def _bot_supervisor():
        """Run the Telegram bot, restarting on crash."""
        while True:
            try:
                await run_bot()
                log.warning("Telegram bot exited; retrying in 30s.")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("Telegram bot crashed: %s — restarting in 30s", exc)
            await asyncio.sleep(30)

    bot_task = asyncio.create_task(_bot_supervisor())
    log.info("Telegram bot supervisor started on worker")

    # Block forever, respond to SIGTERM / SIGINT with graceful shutdown.
    stop_event = asyncio.Event()

    def _handle_signal() -> None:
        log.info("Shutdown signal received — stopping background services …")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    await stop_event.wait()

    await bg.stop()
    log.info("Worker shut down cleanly")


if __name__ == "__main__":
    asyncio.run(_main())
