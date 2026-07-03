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

    Works on BOTH MongoDB (via $aggregate) and SQLite (via Python-side dedup
    fallback). The SQLite fallback loads all docs, groups by name in Python,
    and deletes duplicates — slower than $aggregate but correct.

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
        # Try MongoDB $aggregate first; fall back to Python-side dedup for
        # SQLite (which doesn't support $aggregate).
        deduped = await _dedup_by_name(col)
        summary["deduped"] = deduped

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


async def _dedup_by_name(col: Any) -> int:
    """Deduplicate schedule rows by name, keeping the newest.

    Tries MongoDB $aggregate first (fast, single round-trip). Falls back to
    Python-side dedup (load all, group, delete) for SQLite or any store that
    doesn't support $aggregate. Returns the number of duplicate rows deleted.
    """
    # ── Attempt 1: MongoDB $aggregate pipeline ──────────────────────────
    try:
        pipeline = [
            {"$sort": {"updated_at": -1}},
            {"$group": {"_id": "$name", "job_ids": {"$push": "$job_id"}, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ]
        cursor = col.aggregate(pipeline)
        duplicates = await cursor.to_list(length=10000) if hasattr(cursor, 'to_list') else list(cursor)
        deleted = 0
        for dup in duplicates:
            job_ids = dup.get("job_ids", [])
            to_delete = job_ids[1:]  # keep newest (first after $sort)
            if to_delete:
                r = await col.delete_many({"job_id": {"$in": to_delete}})
                deleted += r.deleted_count if hasattr(r, 'deleted_count') else len(to_delete)
        if deleted > 0:
            return deleted
        # If $aggregate returned results but nothing was deleted, still return 0
        # (don't fall through to Python-side — $aggregate worked, just no dupes)
        return 0
    except Exception as exc:  # noqa: BLE001
        log.debug("nuclear_cleanup $aggregate dedup failed, trying Python-side: %s", exc)

    # ── Attempt 2: Python-side dedup (SQLite-safe) ──────────────────────
    # Load all docs, group by name, keep newest, delete the rest.
    # This is O(n) in memory but correct for any storage backend.
    try:
        result = col.find({})
        docs = await result.to_list(length=50000) if hasattr(result, 'to_list') else list(result)
        if not docs:
            return 0

        # Group by name, track newest per name
        newest_by_name: dict[str, dict] = {}
        duplicates_by_name: dict[str, list[str]] = {}
        for doc in docs:
            name = doc.get("name", "")
            updated = doc.get("updated_at", "")
            job_id = doc.get("job_id") or doc.get("_id")
            if not job_id:
                continue
            if name not in newest_by_name:
                newest_by_name[name] = doc
            else:
                existing_updated = newest_by_name[name].get("updated_at", "")
                if updated > existing_updated:
                    # Current doc is newer — demote the existing one to duplicates
                    existing_job_id = newest_by_name[name].get("job_id") or newest_by_name[name].get("_id")
                    duplicates_by_name.setdefault(name, []).append(existing_job_id)
                    newest_by_name[name] = doc
                else:
                    duplicates_by_name.setdefault(name, []).append(job_id)

        # Collect all job_ids to delete
        to_delete: list[str] = []
        for job_ids in duplicates_by_name.values():
            to_delete.extend(job_ids)

        if not to_delete:
            return 0

        r = await col.delete_many({"job_id": {"$in": to_delete}})
        deleted = r.deleted_count if hasattr(r, 'deleted_count') else len(to_delete)
        log.info("Python-side dedup: deleted %d duplicate schedules (of %d total)", deleted, len(docs))
        return deleted
    except Exception as exc:  # noqa: BLE001
        log.debug("nuclear_cleanup Python-side dedup failed (non-fatal): %s", exc)
        return 0
