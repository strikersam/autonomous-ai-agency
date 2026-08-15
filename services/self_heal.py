"""services/self_heal.py — Autonomous self-healing for the agency.

Runs periodic checks and fixes common failure modes without human intervention:

1. **Task dedup**: every 5 minutes, scans for duplicate tasks (same source_id
   or same title+source) and deletes the duplicates. This prevents the "tons
   of duplicate tasks" buildup from the CEO agency creating tasks on every
   cycle.

2. **Brain failover reset**: when ALL brain providers are unhealthy (all
   circuit breakers open), resets all circuit breakers to CLOSED and clears
   cooldown timers. This prevents the "no healthy providers left" deadlock
   where every provider is in cooldown and the system can't recover.

3. **Telegram webhook clear**: when the Telegram bot gets a 409 conflict,
   automatically calls deleteWebhook to clear the conflict. The bot already
   does this, but this is a backup that runs periodically.

4. **Stuck task cleanup**: moves tasks that have been IN_PROGRESS for more
   than 30 minutes back to TODO (they were likely abandoned by a crashed
   worker).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

log = logging.getLogger("qwen-proxy")

_HEAL_INTERVAL_SEC = int(os.environ.get("SELF_HEAL_INTERVAL_SEC", "300"))  # 5 min
_STUCK_TASK_TIMEOUT_SEC = int(os.environ.get("STUCK_TASK_TIMEOUT_SEC", "1800"))  # 30 min
# Default age a task may sit BLOCKED before the loop retires it to FAILED. A task
# that has already exhausted its dispatch-retry budget and gone BLOCKED almost
# always keeps failing the same way (the dominant live case is
# "planning: TimeoutError" on an auto-generated CEO task that will never plan on
# the free tier). Leaving it BLOCKED lets it be resurrected and re-run five more
# doomed dispatch attempts on every process restart, which is what grew the live
# board past 160 tasks and made it slow. 6h default — long enough that a genuine
# transient outage (brain down, provider cooldown) recovers and the task is
# retried first, short enough that dead tasks don't accumulate for days. Read at
# call time (via BLOCKED_TASK_RETIRE_SEC) so it is tunable without a restart.
_BLOCKED_RETIRE_AGE_DEFAULT = 21600  # 6h


def _blocked_retire_age_sec() -> int:
    try:
        return int(os.environ.get("BLOCKED_TASK_RETIRE_SEC", str(_BLOCKED_RETIRE_AGE_DEFAULT)))
    except (TypeError, ValueError):
        return _BLOCKED_RETIRE_AGE_DEFAULT

_heal_task: asyncio.Task | None = None


async def run_self_heal_cycle() -> dict[str, Any]:
    """Run one self-healing cycle. Returns a summary of what was fixed.

    Called by the background scheduler every 5 minutes and by the
    /api/admin/maintenance/self-heal endpoint for manual triggers.
    """
    summary: dict[str, Any] = {}

    # 1. Task dedup
    try:
        summary["task_dedup"] = await _heal_task_duplicates()
    except Exception as exc:
        summary["task_dedup"] = {"error": str(exc)[:200]}
        log.warning("self_heal: task_dedup failed: %s", exc)

    # 2. Brain failover reset
    try:
        summary["brain_reset"] = await _heal_brain_failover()
    except Exception as exc:
        summary["brain_reset"] = {"error": str(exc)[:200]}
        log.warning("self_heal: brain_reset failed: %s", exc)

    # 3. Stuck task cleanup
    try:
        summary["stuck_tasks"] = await _heal_stuck_tasks()
    except Exception as exc:
        summary["stuck_tasks"] = {"error": str(exc)[:200]}
        log.warning("self_heal: stuck_tasks failed: %s", exc)

    # 3b. Retire chronically-blocked tasks
    try:
        summary["blocked_backlog"] = await _heal_blocked_backlog()
    except Exception as exc:
        summary["blocked_backlog"] = {"error": str(exc)[:200]}
        log.warning("self_heal: blocked_backlog failed: %s", exc)

    # 3c. Purge aged terminal tasks (keeps the board tidy)
    try:
        summary["purge_backlog"] = await _heal_purge_backlog()
    except Exception as exc:
        summary["purge_backlog"] = {"error": str(exc)[:200]}
        log.warning("self_heal: purge_backlog failed: %s", exc)

    # 4. Telegram webhook clear (best-effort)
    try:
        summary["telegram"] = await _heal_telegram()
    except Exception as exc:
        summary["telegram"] = {"error": str(exc)[:200]}
        log.debug("self_heal: telegram failed (non-fatal): %s", exc)

    # 5. Timestamp normalisation (best-effort)
    try:
        summary["ts_normalise"] = await _heal_timestamps()
    except Exception as exc:
        summary["ts_normalise"] = {"error": str(exc)[:200]}
        log.warning("self_heal: ts_normalise failed: %s", exc)

    log.info("self_heal: cycle complete — %s", summary)
    return summary


async def _heal_timestamps() -> dict[str, int]:
    """Normalise ISO 8601 timestamp strings to float epochs in the DB.

    Some code paths write ``updated_at`` / ``created_at`` / ``started_at``
    as ISO 8601 strings instead of float timestamps. This causes crashes
    when other code paths try to do ``float(timestamp)`` or compare
    ``float < str``. This pass scans all tasks and normalises any string
    timestamps to floats so the dispatcher/reconciler don't crash.

    Idempotent — already-float timestamps are skipped.
    """
    from tasks.store import get_task_store, _ts_to_float
    from tasks.models import TaskStatus

    store = get_task_store()
    all_tasks = await store.list_all(limit=10_000)

    normalised = 0
    for t in all_tasks:
        changed = False
        for field in ("created_at", "updated_at", "started_at", "completed_at", "due_date"):
            val = getattr(t, field, None)
            if val is None:
                continue
            if isinstance(val, str):
                # It's a string — try to normalise to float
                normalised_val = _ts_to_float(val)
                if normalised_val:
                    setattr(t, field, normalised_val)
                    changed = True
        if changed:
            try:
                await store.update(t)
                normalised += 1
            except Exception:
                pass

    if normalised > 0:
        log.info("self_heal: normalised ISO 8601 timestamps on %d task(s)", normalised)
    return {"normalised": normalised, "total_scanned": len(all_tasks)}


async def _heal_task_duplicates() -> dict[str, int]:
    """Backfill source_id on legacy ceo_direct tasks, then dedup by source_id.

    Two passes:
    1. BACKFILL: for tasks with source=="ceo_direct" and empty source_id, parse
       the issue number from the title (regex: ``^(issue|quick-note) #(\\d+):``)
       and set source_id = issue_source_id(repo, number).
    2. DEDUP: by source_id only — keep in_progress > done > oldest-created.
       Never delete in_progress tasks.

    Title-based dedup was deliberately removed (commit 312e9ba) — do NOT
    reintroduce it.
    """
    from tasks.store import get_task_store
    store = get_task_store()
    all_tasks = await store.list_all(limit=10_000)

    backfilled = 0
    deleted = 0

    # Pass 1: Backfill source_id on legacy ceo_direct tasks
    import re
    _title_re = re.compile(r"^(?:issue|quick-note) #(\d+):", re.IGNORECASE)
    try:
        import agent.agency as _ag
        repo = _ag._gh_repo()
    except Exception:
        repo = None

    for t in all_tasks:
        if t.source == "ceo_direct" and not t.source_id and repo:
            m = _title_re.match(t.title or "")
            if m:
                number = int(m.group(1))
                sid = f"{repo}#{number}"
                t.source_id = sid
                try:
                    await store.update(t)
                    backfilled += 1
                except Exception:
                    pass

    # Pass 2: Dedup by source_id (keep in_progress > done > oldest-created)
    if backfilled > 0:
        # Re-read after backfill
        all_tasks = await store.list_all(limit=10_000)

    seen: dict[str, str] = {}  # source_id -> task_id to keep
    for t in sorted(all_tasks, key=lambda x: (
        0 if x.status.value == "in_progress" else 1 if x.status.value == "done" else 2,
        x.created_at if isinstance(x.created_at, (int, float)) else 0,
    )):
        if t.status.value == "in_progress":
            # Never delete in_progress tasks — always keep them
            if t.source_id:
                seen[t.source_id] = t.task_id
            continue

        sid = t.source_id or ""
        if not sid:
            continue  # No source_id — can't dedup, leave it

        if sid in seen:
            await store.delete(t.task_id)
            deleted += 1
        else:
            seen[sid] = t.task_id

    if deleted > 0 or backfilled > 0:
        log.info("self_heal: backfilled %d source_ids, deleted %d duplicate tasks (of %d total)",
                 backfilled, deleted, len(all_tasks))
    return {"deleted": deleted, "backfilled": backfilled, "total_scanned": len(all_tasks)}


async def _heal_brain_failover() -> dict[str, Any]:
    """Reset all circuit breakers when ALL providers are unhealthy.

    When every provider is in OPEN state (all in cooldown), the system is
    deadlocked — no LLM call can succeed. This resets all breakers to CLOSED
    so the next call can try again. Without this, the system stays stuck
    until the longest cooldown expires (up to 10 minutes for 410 Gone).
    """
    from services.brain_failover import get_failover_manager
    fm = get_failover_manager()
    providers = fm.get_providers()

    if not providers:
        return {"action": "no_providers", "reset": False}

    healthy = [p for p in providers if p.is_healthy]
    if healthy:
        return {
            "action": "none",
            "reset": False,
            "healthy": len(healthy),
            "total": len(providers),
        }

    # ALL providers unhealthy — reset all circuit breakers
    reset_count = 0
    for p in providers:
        fm.record_success(p.id)  # record_success resets to CLOSED
        reset_count += 1

    log.warning(
        "self_heal: brain failover deadlock detected — reset %d circuit breakers "
        "(all providers were unhealthy)", reset_count
    )
    return {
        "action": "reset_all",
        "reset": True,
        "reset_count": reset_count,
        "healthy": 0,
        "total": len(providers),
    }


async def _heal_stuck_tasks() -> dict[str, int]:
    """Move tasks stuck in IN_PROGRESS for too long back to TODO."""
    from tasks.store import get_task_store
    from tasks.models import TaskStatus
    store = get_task_store()
    all_tasks = await store.list_all(limit=10_000)

    now = time.time()
    moved = 0
    for t in all_tasks:
        if t.status != TaskStatus.IN_PROGRESS:
            continue
        started = t.started_at
        if not started:
            continue
        # Normalise: started_at may be a float OR an ISO 8601 string
        from tasks.store import _ts_to_float
        started_ts = _ts_to_float(started)
        if not started_ts:
            continue
        if now - started_ts > _STUCK_TASK_TIMEOUT_SEC:
            t.status = TaskStatus.TODO
            t.pending_agent_run = True
            t.add_log(
                f"Self-heal: moved from IN_PROGRESS to TODO (stuck for {int(now - started_ts)}s)",
                event_type="self_heal",
                actor="system:self_heal",
            )
            await store.update(t)
            moved += 1

    if moved > 0:
        log.info("self_heal: moved %d stuck tasks from IN_PROGRESS to TODO", moved)
    return {"moved": moved, "total_scanned": len(all_tasks)}


async def _heal_blocked_backlog() -> dict[str, int]:
    """Retire chronically-blocked tasks to FAILED so they stop churning.

    A task lands in BLOCKED only after it has already burned its full
    dispatch-retry budget (``_DISPATCH_RETRY_LIMIT`` attempts). On the free tier
    the dominant reason is a planning timeout on an auto-generated CEO task that
    will never plan — so re-running it wastes the single dispatch worker and the
    task piles up on the board. This pass moves BLOCKED tasks older than
    ``_BLOCKED_RETIRE_AGE_SEC`` to FAILED and pins ``auto_retry_count`` at the
    reconciler's cap, so the FAILED-reconciler pass will NOT resurrect them.

    FAILED is terminal-but-reopenable: a human can still retry or delete the
    task from the board, but the autonomous loop stops spending CPU on work that
    cannot succeed. Never deletes anything — the record is preserved.
    """
    from tasks.store import get_task_store, _ts_to_float
    from tasks.models import TaskStatus

    store = get_task_store()
    # Scan light (no execution_log) — the board-sized fetch stays cheap. The few
    # tasks we actually retire are re-fetched in full below, because store.update
    # does a whole-document replace_one and a log-less Task would wipe the log.
    candidates = await store.list_all(limit=10_000, include_log=False)

    # Match the reconciler's cap so a retired task is above it and never re-queued.
    cap = int(os.environ.get("TASK_AUTO_RETRY_MAX", "5"))
    retire_age = _blocked_retire_age_sec()
    now = time.time()
    retired = 0
    blocked_total = 0
    for c in candidates:
        if c.status != TaskStatus.BLOCKED:
            continue
        blocked_total += 1
        age = now - (_ts_to_float(c.updated_at) or 0.0)
        if age < retire_age:
            continue
        t = await store.get(c.task_id)  # full task — preserves execution_log on replace
        if t is None or t.status != TaskStatus.BLOCKED:
            continue  # raced with another writer — skip
        t.status = TaskStatus.FAILED
        t.pending_agent_run = False
        t.auto_retry_count = max(int(t.auto_retry_count or 0), cap)
        t.error_message = t.blocked_reason or t.error_message
        t.add_log(
            f"Self-heal: retired to FAILED after {int(age)}s BLOCKED "
            f"(exhausted dispatch retries; will not be auto-resurrected)",
            level="warning",
            event_type="self_heal",
            actor="system:self_heal",
            task_status=TaskStatus.FAILED,
        )
        try:
            await store.update(t)
            retired += 1
        except Exception:  # nosec B110 -- best-effort; a failed update just retries next cycle
            pass

    if retired > 0:
        log.info(
            "self_heal: retired %d chronically-blocked task(s) to FAILED (of %d blocked)",
            retired, blocked_total,
        )
    return {"retired": retired, "blocked_total": blocked_total, "total_scanned": len(candidates)}


def _purge_enabled() -> bool:
    return os.environ.get("SELF_HEAL_PURGE_ENABLED", "true").strip().lower() in (
        "true", "1", "yes", "on",
    )


def _purge_days() -> int:
    try:
        return max(1, int(os.environ.get("SELF_HEAL_PURGE_DAYS", "3")))
    except (TypeError, ValueError):
        return 3


async def _heal_purge_backlog() -> dict[str, int]:
    """Delete aged terminal (done/failed) tasks so the board stays tidy.

    The board's load time is already independent of task count (the list
    endpoints project the heavy fields out at the query), so this is about
    hygiene, not latency: an unbounded history of dead autonomous tasks is noise
    a human has to scroll past. Deletes DONE/FAILED tasks whose last update is
    older than ``SELF_HEAL_PURGE_DAYS`` (default 3). Blocked tasks are handled
    first by the retirement pass (BLOCKED -> FAILED at 6h), so they age into this
    purge terminally rather than being deleted while still churning.

    Destructive by design (the operator opted in) but conservative: nothing newer
    than the cutoff is touched, and only terminal statuses are eligible, so no
    in-flight or retryable work can be removed. Off by default-safe via
    ``SELF_HEAL_PURGE_ENABLED=false``.
    """
    if not _purge_enabled():
        return {"deleted": 0, "action": "disabled"}

    from tasks.store import get_task_store, _ts_to_float
    from tasks.models import TaskStatus

    store = get_task_store()
    candidates = await store.list_all(limit=10_000, include_log=False)

    terminal = {TaskStatus.DONE.value, TaskStatus.FAILED.value}
    cutoff = time.time() - _purge_days() * 86400
    deleted = 0
    for t in candidates:
        status = t.status.value if hasattr(t.status, "value") else str(t.status)
        if status not in terminal:
            continue
        ts = _ts_to_float(t.updated_at) or _ts_to_float(t.created_at) or 0.0
        if ts and ts < cutoff:
            try:
                await store.delete(t.task_id)
                deleted += 1
            except Exception:  # nosec B110 -- best-effort; retries next cycle
                pass

    if deleted:
        # Drop cached list pages so the freed board is reflected immediately.
        try:
            from tasks.api import _invalidate_task_caches
            _invalidate_task_caches()
        except Exception:  # nosec B110 -- cache invalidation is best-effort
            pass
        log.info("self_heal: purged %d aged terminal task(s) (>%dd)", deleted, _purge_days())
    return {"deleted": deleted, "cutoff_days": _purge_days(), "total_scanned": len(candidates)}


async def _heal_telegram() -> dict[str, Any]:
    """Clear Telegram webhook if the bot is getting 409 conflicts."""
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return {"action": "no_token", "cleared": False}

    # Check if the bot is running
    if os.environ.get("RUN_TELEGRAM_BOT", "false").strip().lower() not in ("true", "1", "yes", "on"):
        return {"action": "bot_not_running", "cleared": False}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check getUpdates status
            resp = await client.get(
                f"https://api.telegram.org/bot{token}/getWebhookInfo"
            )
            data = resp.json()
            if not data.get("ok"):
                return {"action": "api_error", "cleared": False}

            webhook_url = data.get("result", {}).get("url", "")
            if webhook_url:
                # Webhook is set — clear it so long-polling works
                resp = await client.get(
                    f"https://api.telegram.org/bot{token}/deleteWebhook"
                )
                cleared = resp.json().get("ok", False)
                if cleared:
                    log.info("self_heal: cleared Telegram webhook (was: %s)", webhook_url)
                return {"action": "cleared_webhook", "cleared": cleared, "was": webhook_url}

            return {"action": "no_webhook", "cleared": False}
    except Exception as exc:
        log.debug("self_heal: telegram check failed: %s", exc)
        return {"action": "error", "cleared": False, "error": str(exc)[:100]}


def start_self_heal_scheduler() -> None:
    """Start the background self-heal loop. Called once at startup."""
    global _heal_task
    if _heal_task is not None and not _heal_task.done():
        return
    _heal_task = asyncio.create_task(_self_heal_loop())


async def _self_heal_loop() -> None:
    """Background loop that runs self-heal every _HEAL_INTERVAL_SEC seconds."""
    log.info("self_heal: background loop started (interval=%ds)", _HEAL_INTERVAL_SEC)
    while True:
        try:
            await asyncio.sleep(_HEAL_INTERVAL_SEC)
            await run_self_heal_cycle()
        except asyncio.CancelledError:
            log.info("self_heal: background loop cancelled")
            break
        except Exception as exc:
            log.warning("self_heal: cycle failed: %s", exc)
            await asyncio.sleep(60)  # Wait a minute before retrying


def stop_self_heal_scheduler() -> None:
    """Stop the background self-heal loop."""
    global _heal_task
    if _heal_task is not None:
        _heal_task.cancel()
        _heal_task = None
