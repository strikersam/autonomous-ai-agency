"""packages/scheduler/cleanup.py — schedule deduplication + stale removal.

Extracted from agent/scheduler.py force_cleanup() logic.
This module provides reusable cleanup functions that can be called
from the scheduler, the cron tick, or the startup lifespan.
"""
from __future__ import annotations

import logging
import inspect
from typing import Any

log = logging.getLogger("scheduler-cleanup")


async def cleanup_stale_jobs(store: Any) -> dict[str, int]:
    """Remove stale run-once + stuck agency jobs from the durable store.

    Args:
        store: The scheduler store (packages/scheduler/store.py SchedulerStore)

    Returns:
        Summary dict with 'deleted', 'deduped', 'total' counts.

    Counters are only incremented after a successful ``store.remove()`` —
    failures are logged via ``log.exception()`` and do NOT silently report
    success.
    """
    summary = {"deleted": 0, "deduped": 0, "total": 0}

    try:
        result = store.load_all()
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

            # Remove stale run-once jobs
            if "run-once" in tags and run_count > 0:
                if await _safe_remove(store, job_id, name, "stale run-once"):
                    summary["deleted"] += 1
                continue

            # Remove stuck agency tasks (10+ retries)
            if run_count > 10 and "agency" in tags:
                if await _safe_remove(store, job_id, name, f"stuck agency (run_count={run_count})"):
                    summary["deleted"] += 1
                    log.info("Cleanup: removed stuck agency task name=%r (run_count=%d)", name, run_count)
                continue

            # Dedup by name
            if name in seen_names:
                if await _safe_remove(store, job_id, name, "duplicate name"):
                    summary["deduped"] += 1
                continue
            seen_names.add(name)

    except Exception as exc:  # noqa: BLE001
        log.warning("Cleanup failed: %s", exc)

    return summary


async def _safe_remove(store: Any, job_id: str, name: str, reason: str) -> bool:
    """Remove a job from the store. Returns True on success, False on failure.

    Logs the exception on failure (never silently swallows).
    """
    try:
        remove_result = store.remove(job_id)
        if inspect.isawaitable(remove_result):
            await remove_result
        return True
    except Exception:  # noqa: BLE001
        log.exception("Failed to remove job %r (name=%r, reason=%s)", job_id, name, reason)
        return False


async def nuclear_cleanup(db: Any) -> dict[str, int]:
    """Directly delete ALL stale jobs from the DB collection.

    More aggressive than cleanup_stale_jobs — uses delete_many for speed.
    Called at startup to clear the 1700+ schedule backlog.

    Uses the SAME stuck-job threshold as ``cleanup_stale_jobs`` (run_count > 10)
    so it doesn't wipe legitimate recurring agency schedules at startup.

    Args:
        db: The database object (get_db() result)

    Returns:
        Summary dict with 'deleted_run_once', 'deleted_stuck', 'total'
    """
    summary = {"deleted_run_once": 0, "deleted_stuck": 0, "total": 0}

    try:
        col = getattr(db, "schedules", None)
        if col is None:
            return summary

        # Delete all run-once jobs
        r1 = await col.delete_many({"tags": {"$in": ["run-once"]}})
        summary["deleted_run_once"] = r1.deleted_count if hasattr(r1, 'deleted_count') else 0

        # Delete stuck agency jobs — same threshold as cleanup_stale_jobs (run_count > 10).
        # The previous `run_count > 0` was too aggressive: it deleted every agency
        # job after the first run, wiping legitimate recurring schedules.
        r2 = await col.delete_many({"tags": {"$in": ["agency"]}, "run_count": {"$gt": 10}})
        summary["deleted_stuck"] = r2.deleted_count if hasattr(r2, 'deleted_count') else 0

        log.info("Nuclear cleanup: deleted %d run-once + %d stuck agency jobs",
                 summary["deleted_run_once"], summary["deleted_stuck"])
    except Exception as exc:  # noqa: BLE001
        log.debug("Nuclear cleanup failed (non-fatal): %s", exc)

    return summary
