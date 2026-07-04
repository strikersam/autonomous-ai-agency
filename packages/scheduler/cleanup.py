"""packages/scheduler/cleanup.py — schedule deduplication + stale removal.

Extracted from agent/scheduler.py force_cleanup() logic.
This module provides reusable cleanup functions that can be called
from the scheduler, the cron tick, or the startup lifespan.

2026-07-03 incident fix: stale UNFIRED run-once jobs (run_count==0, old
created_at) are now deleted after SCHEDULE_RUN_ONCE_TTL_DAYS (default 7).
This exact class survived every existing filter and became the 2,873-row
pile that OOM'd the 512MB Render instance.
"""
from __future__ import annotations

import logging
import inspect
import os
import time
from typing import Any

log = logging.getLogger("scheduler-cleanup")

# Stale unfired run-once jobs older than this (in days) are deleted.
# This is the fix for the 2026-07-03 incident: run-once jobs with
# run_count==0 survived every existing filter and piled up to 2,873 rows.
_SCHEDULE_RUN_ONCE_TTL_DAYS = int(os.environ.get("SCHEDULE_RUN_ONCE_TTL_DAYS", "7"))


def _is_stale(created_at: str, ttl_seconds: int, now_epoch: float) -> bool:
    """Check if a created_at timestamp is older than ttl_seconds.

    Handles multiple timestamp formats:
    - ISO 8601: "2026-06-20T12:00:00Z"
    - Epoch string: "1718889600"
    - strftime: "2026-06-20T12:00:00Z"
    """
    if not created_at:
        return False  # Don't delete if we can't determine age
    # Try parsing as epoch
    try:
        ts = float(created_at)
        return (now_epoch - ts) > ttl_seconds
    except (ValueError, TypeError):
        pass
    # Try ISO 8601
    try:
        from datetime import datetime, timezone
        ts_str = created_at.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (now_epoch - dt.timestamp()) > ttl_seconds
    except Exception:  # nosec B110 — timestamp parsing, best-effort
        pass
    # Try strftime format (the scheduler uses this)
    try:
        from datetime import datetime, timezone
        dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return (now_epoch - dt.timestamp()) > ttl_seconds
    except Exception:
        return False  # Don't delete if we can't parse


async def cleanup_stale_jobs(store: Any) -> dict[str, int]:
    """Remove stale run-once + stuck agency jobs from the durable store.

    Args:
        store: The scheduler store (packages/scheduler/store.py SchedulerStore)

    Returns:
        Summary dict with 'deleted', 'deduped', and 'total' counts.

    Counters are only incremented after a successful ``store.remove()`` —
    failures are logged via ``log.exception()`` and do NOT silently report
    success.
    """
    summary = {"deleted": 0, "deduped": 0, "total": 0}

    try:
        result = store.load_all()
        docs = (await result) if inspect.isawaitable(result) else result
        summary["total"] = len(docs)

        # Compute the staleness cutoff
        ttl_seconds = _SCHEDULE_RUN_ONCE_TTL_DAYS * 24 * 3600
        now_epoch = time.time()

        seen_names: set[str] = set()
        for doc in docs:
            job_id = doc.get("job_id") or doc.get("id")
            if not job_id:
                continue
            name = doc.get("name", "restored-job")
            tags = doc.get("tags") or []
            run_count = doc.get("run_count", 0)

            # Remove stale run-once jobs (already fired)
            if "run-once" in tags and run_count > 0:
                if await _safe_remove(store, job_id, name, "stale run-once (fired)"):
                    summary["deleted"] += 1
                continue

            # Remove stale UNFIRED run-once jobs older than TTL
            # This is the fix for the 2,873-row pile: run-once jobs with
            # run_count==0 that were created but never fired, surviving
            # every existing filter.
            if "run-once" in tags and run_count == 0:
                created_at = doc.get("created_at", "")
                if _is_stale(created_at, ttl_seconds, now_epoch):
                    if await _safe_remove(store, job_id, name, f"stale unfired run-once (age > {_SCHEDULE_RUN_ONCE_TTL_DAYS}d)"):
                        summary["deleted"] += 1
                        log.info("Cleanup: removed stale unfired run-once name=%r (created=%s)", name, created_at)
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
    Called at startup to clear the 2,873-row pile from the 2026-07-03 incident.

    Also removes stale unfired run-once jobs (run_count==0, old created_at)
    that survived previous cleanup filters.
    """
    from datetime import datetime, timezone, timedelta

    summary = {"deleted": 0, "deduped": 0, "deleted_run_once": 0, "deleted_stuck": 0, "total": 0}

    try:
        # Access the collection — handle attribute-style (db.schedules),
        # dict-style (db["scheduled_jobs"]), and fallback (db.scheduled_jobs)
        collection = getattr(db, "schedules", None)
        if collection is None:
            if hasattr(db, "__getitem__"):
                try:
                    collection = db["scheduled_jobs"]
                except (KeyError, TypeError):
                    pass
        if collection is None:
            collection = getattr(db, "scheduled_jobs", None)
        if collection is None:
            raise AttributeError("DB has no schedules/scheduled_jobs collection")
        summary["total"] = await collection.count_documents({})

        # 1. Delete fired run-once jobs (run_count > 0)
        result = await collection.delete_many({"tags": {"$in": ["run-once"]}, "run_count": {"$gt": 0}})
        summary["deleted_run_once"] = result.deleted_count

        # 2. Delete stale unfired run-once jobs (run_count == 0, old created_at)
        ttl_seconds = _SCHEDULE_RUN_ONCE_TTL_DAYS * 24 * 3600
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl_seconds)
        # Try ISO format cutoff (scheduler uses strftime "%Y-%m-%dT%H:%M:%SZ")
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        result = await collection.delete_many({
            "tags": {"$in": ["run-once"]},
            "run_count": 0,
            "created_at": {"$lt": cutoff_str},
        })
        summary["deleted_run_once"] += result.deleted_count

        # 3. Delete stuck agency tasks (run_count > 10)
        result = await collection.delete_many({"run_count": {"$gt": 10}, "tags": {"$in": ["agency"]}})
        summary["deleted_stuck"] = result.deleted_count

        # 4. Dedup by name: keep newest, delete rest
        pipeline = [
            {"$sort": {"created_at": -1}},
            {"$group": {"_id": "$name", "docs": {"$push": "$$ROOT"}, "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
        ]
        try:
            cursor = collection.aggregate(pipeline)
            async for group in cursor:
                docs = group.get("docs", [])
                # Keep the first (newest), delete the rest
                for doc in docs[1:]:
                    await collection.delete_one({"job_id": doc.get("job_id")})
                    summary["deduped"] += 1
        except Exception as exc:  # noqa: BLE001 — $aggregate may not be available
            log.warning("Nuclear cleanup dedup pipeline failed: %s", exc)

        summary["deleted"] = summary["deleted_run_once"] + summary["deleted_stuck"] + summary["deduped"]
        summary["total"] = await collection.count_documents({})

    except Exception as exc:  # noqa: BLE001
        log.warning("Nuclear cleanup failed: %s", exc)

    return summary
