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
    Called at startup to clear the 2100+ schedule backlog.

    Uses the SAME stuck-job threshold as ``cleanup_stale_jobs`` (run_count > 10)
    so it doesn't wipe legitimate recurring agency schedules at startup.

    Also deduplicates by name: keeps the newest job for each name, deletes
    all others. This is the nuclear fix for the multiplication bug — even
    if the in-memory dedup missed duplicates, this cleans them on startup.

    Args:
        db: The database object (get_db() result)

    Returns:
        Summary dict with 'deleted_run_once', 'deleted_stuck', 'deduped', 'total'
    """
    summary: dict[str, int] = {"deleted_run_once": 0, "deleted_stuck": 0, "deduped": 0, "total": 0}

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

        # Deduplicate by name: for each name, keep only the newest job.
        # This is the nuclear fix for the 2100+ schedule multiplication bug.
        # Even if the in-memory dedup in cleanup_stale_jobs missed duplicates
        # (e.g. schedule rows persisted from before the dedup logic existed),
        # this cleans them on startup. SQLite-safe: falls back gracefully if
        # $aggregate is not supported.
        try:
            pipeline = [
                {"$sort": {"updated_at": -1}},
                {"$group": {"_id": "$name", "job_ids": {"$push": "$job_id"}, "count": {"$sum": 1}}},
                {"$match": {"count": {"$gt": 1}}},
            ]
            cursor = col.aggregate(pipeline)
            duplicates = await cursor.to_list(length=10000) if hasattr(cursor, 'to_list') else list(cursor)
            for dup in duplicates:
                job_ids = dup.get("job_ids", [])
                # Keep the first (newest), delete the rest
                to_delete = job_ids[1:]
                if to_delete:
                    r3 = await col.delete_many({"job_id": {"$in": to_delete}})
                    summary["deduped"] += r3.deleted_count if hasattr(r3, 'deleted_count') else len(to_delete)
        except Exception as exc:  # noqa: BLE001
            log.debug("Nuclear cleanup dedup failed (non-fatal — SQLite may not support $aggregate): %s", exc)

        # Count total remaining
        try:
            summary["total"] = await col.count_documents({})
        except Exception:  # noqa: BLE001
            pass

        log.info("Nuclear cleanup: deleted %d run-once + %d stuck + %d duplicates (%d remaining)",
                 summary["deleted_run_once"], summary["deleted_stuck"], summary["deduped"], summary["total"])
    except Exception as exc:  # noqa: BLE001
        log.debug("Nuclear cleanup failed (non-fatal): %s", exc)

    return summary
