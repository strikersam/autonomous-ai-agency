"""services/memory_guard.py — keep RSS from creeping to OOM on small dynos.

The backend runs a lot of threads for an async service — motor, httpx, the
APScheduler thread pool, and every ``asyncio.to_thread`` call — against a
constant churn of short-lived buffers (RSS/feed fetches, JSON payloads, health
probes, Langfuse events). glibc keeps freed memory in per-thread arenas and, by
default, only ever returns the *top* of the main heap to the kernel. Freed
blocks stranded in the middle of an arena stay mapped, so RSS climbs
monotonically even while live-object memory is flat — the sawtooth that
OOM-kills the 512 MB free instance (observed: ~450 MB baseline creeping ~10 MB
every 10 min to ~510 MB, then a restart).

This loop periodically runs a ``gc.collect()`` and then a glibc
``malloc_trim(0)``, which walks every arena and hands fully-free pages back to
the OS — the piece the automatic top-of-heap trimming misses. It pairs with
``MALLOC_ARENA_MAX`` (set in the Dockerfile / render.yaml), which caps how many
arenas exist in the first place.

Everything here is best-effort and fail-soft: on a libc without
``malloc_trim`` (e.g. musl/Alpine) the trim is skipped and the gc sweep still
runs. The loop never raises out — a memory guard that crashes the process it is
meant to protect would be worse than none.
"""
from __future__ import annotations

import asyncio
import ctypes
import ctypes.util
import gc
import logging
import os
from typing import Callable

log = logging.getLogger("qwen-proxy")

# How often to sweep. 180s is frequent enough to flatten the sawtooth well below
# the OOM ceiling without adding measurable CPU (a trim is microseconds).
_INTERVAL_SEC = int(os.environ.get("MEMORY_GUARD_INTERVAL_SEC", "180"))


def memory_guard_enabled() -> bool:
    """True unless explicitly disabled. Default on: the whole point is that the
    constrained deployment does not have to remember to turn it on."""
    return os.environ.get("MEMORY_GUARD_ENABLED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _load_malloc_trim() -> "Callable[[int], int] | None":
    """Resolve glibc ``malloc_trim``. Returns None when unavailable (non-glibc)."""
    try:
        libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        trim = libc.malloc_trim
        trim.argtypes = [ctypes.c_size_t]
        trim.restype = ctypes.c_int
        return trim
    except Exception:  # noqa: BLE001 - any failure means "no trim available"
        return None


def trim_now(trim: "Callable[[int], int] | None" = None) -> int:
    """Run one gc sweep + malloc_trim. Returns objects collected. Never raises."""
    collected = 0
    try:
        collected = gc.collect()
        _trim = trim if trim is not None else _load_malloc_trim()
        if _trim is not None:
            _trim(0)
    except Exception as exc:  # noqa: BLE001 - protective, must not propagate
        log.debug("memory_guard: trim failed (ignored): %s", exc)
    return collected


async def memory_guard_loop() -> None:
    """Sweep + trim on a fixed interval until cancelled."""
    trim = _load_malloc_trim()
    log.info(
        "Memory guard started — gc + malloc_trim every %ds (malloc_trim=%s)",
        _INTERVAL_SEC, "available" if trim else "unavailable",
    )
    while True:
        try:
            await asyncio.sleep(_INTERVAL_SEC)
            trim_now(trim)
        except asyncio.CancelledError:
            log.info("Memory guard stopped")
            raise
        except Exception as exc:  # noqa: BLE001 - the loop must outlive its errors
            log.debug("memory_guard tick failed (ignored): %s", exc)
