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

    # 4. Telegram webhook clear (best-effort)
    try:
        summary["telegram"] = await _heal_telegram()
    except Exception as exc:
        summary["telegram"] = {"error": str(exc)[:200]}
        log.debug("self_heal: telegram failed (non-fatal): %s", exc)

    log.info("self_heal: cycle complete — %s", summary)
    return summary


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

    def _created_ts(x: Any) -> float:
        # Task.created_at is Union[str, float] — coerce so "oldest-created"
        # ordering also holds for stringified timestamps.
        v = x.created_at
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    seen: dict[str, str] = {}  # source_id -> task_id to keep
    for t in sorted(all_tasks, key=lambda x: (
        0 if x.status.value == "in_progress" else 1 if x.status.value == "done" else 2,
        _created_ts(x),
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
        # Handle both epoch float and ISO string
        try:
            started_ts = float(started) if isinstance(started, (int, float)) else float(started)
        except (ValueError, TypeError):
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
