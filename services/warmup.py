"""services/warmup.py — bounded startup warm-up steps.

Extracted from backend/server.py's lifespan() so any startup-path module can
bound a slow step against a budget instead of awaiting it unconditionally.
Uvicorn does not open its listening socket until lifespan startup returns, so
an unbounded await here delays every health check and can crash-loop the
deploy: Render times the health check out, restarts the container, and the
restart repeats the same slow step from scratch. See backend/server.py's
lifespan() docstring for the full incident history.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Coroutine

log = logging.getLogger("startup-warmup")

# Overflowed warm-up steps are kept referenced here: the event loop only
# holds a weak reference to a running task, so a dropped one can be
# garbage-collected mid-flight and silently never finish.
_warmup_overflow: list[asyncio.Task] = []


def defer_to_background(task: "asyncio.Task[Any]", label: str) -> None:
    """Let an overrunning step finish out of band without leaking or warning twice."""
    _warmup_overflow.append(task)

    def _settled(done: "asyncio.Task[Any]") -> None:
        if done in _warmup_overflow:
            _warmup_overflow.remove(done)
        if not done.cancelled() and done.exception() is not None:
            log.warning("startup: deferred %s failed (non-fatal): %s",
                        label, done.exception())

    task.add_done_callback(_settled)


async def warmup_step(
    coro: "Coroutine[Any, Any, Any]", label: str, deadline: float, budget_sec: float,
) -> Any:
    """Await ``coro`` until ``deadline`` (a loop timestamp); defer it past that.

    ``deadline`` lets several steps share one budget spent across all of them
    (pass the same value to each call). ``budget_sec`` is only used for the
    log message so the operator sees the configured budget rather than
    whatever slice happened to be left.
    """
    task = asyncio.ensure_future(coro)
    remaining = max(0.0, deadline - asyncio.get_running_loop().time())
    try:
        return await asyncio.wait_for(asyncio.shield(task), timeout=remaining)
    except (asyncio.TimeoutError, TimeoutError):
        defer_to_background(task, label)
        log.warning(
            "startup: %s exceeded the %.1fs warm-up budget — continuing in the "
            "background so the port opens and health checks can be answered",
            label, budget_sec,
        )
        return None
