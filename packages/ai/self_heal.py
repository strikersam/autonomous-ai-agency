"""packages/ai/self_heal.py — automatic brain self-healing.

When the active brain provider fails with 410 Gone (model permanently removed)
or sustained 429 Too Many Requests (rate limited), this module:
  1. Detects the failure pattern from the brain watchdog's failure log.
  2. Persists a failover to the next healthy provider (Ollama local first,
     then any other configured provider).
  3. Resets the failure counter so the watchdog starts fresh on the new
     provider.
  4. Unblocks tasks that were BLOCKED due to "No runtime available" /
     "brain_unavailable" so they get re-dispatched on the new provider.

Called from the /api/scheduler/tick handler (every 1 min) so the system
self-heals without operator intervention. Also called from the brain
watchdog after a failover to unblock tasks immediately.

This is the "self-healing mechanism" the operator asked for — no more
permanently blocked tasks from a dead NVIDIA model or a rate-limit storm.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

log = logging.getLogger("self_heal")


async def self_heal_brain_and_unblock_tasks() -> dict[str, Any]:
    """One-shot self-healing pass.

    1. Checks if the active brain provider is in a failure state
       (410 Gone / sustained 429 / cooldown).
    2. If so, persists a failover to the next healthy provider.
    3. Unblocks tasks that were BLOCKED due to runtime/brain unavailability
       so they get re-dispatched on the new provider.

    Returns a summary dict with what was done. Safe to call every tick —
    if the brain is healthy and no tasks are blocked, it's a no-op.
    """
    summary: dict[str, Any] = {
        "brain_checked": False,
        "failover_persisted": None,
        "tasks_unblocked": 0,
        "skipped_reason": None,
    }

    try:
        from packages.ai.brain_config import (
            get_brain_config,
            get_brain_preference,
            RECOMMENDED_PROVIDER_PRIORITY,
            provider_key_present,
            PROVIDER_PRESETS,
            BrainConfigPatch,
            get_brain_config_store,
        )
        from packages.ai.brain import resolve_active_brain
        from packages.ai.watchdog import get_watchdog
    except ImportError as exc:
        summary["skipped_reason"] = f"import failed: {exc}"
        return summary

    # ── Step 1: Check brain health ──────────────────────────────────────
    cfg = await get_brain_config()
    watchdog = get_watchdog()
    preference = get_brain_preference()
    active_provider = cfg.primary_provider if cfg.updated_at else preference

    summary["brain_checked"] = True
    summary["active_provider"] = active_provider
    summary["preference"] = preference

    # PR #963: normalize the provider name before checking failure counts.
    # The watchdog stores failures under the normalized name (e.g. "nvidia"),
    # but active_provider might be "nvidia-nim" (DB provider_id). Without
    # normalization, self_heal never sees the failures → no failover.
    from packages.ai.watchdog import BrainWatchdog as _BW
    normalized_active = _BW._normalize_provider(str(active_provider))
    failure_count = watchdog._failure_counts.get(normalized_active, 0)
    summary["failure_count"] = failure_count
    summary["normalized_active"] = normalized_active

    # PR #1046: if the persisted BrainConfig points at a provider that is NOT
    # in the known-good set (nvidia/cerebras/groq — the ones with API keys on
    # Render), reset it to the safe default (nvidia/z-ai/glm-5.2) immediately.
    # This catches stale configs from UI changes or model catalog refreshes
    # that left a broken provider/model in the DB.
    known_good_providers = {"nvidia", "cerebras", "groq"}
    if cfg.updated_at and normalized_active not in known_good_providers:
        log.warning(
            "self_heal: persisted brain provider %s is not in known-good set %s — resetting to nvidia",
            normalized_active, known_good_providers,
        )
        try:
            store = await get_brain_config_store()
            patch = BrainConfigPatch(
                primary_provider="nvidia",
                planner_model="z-ai/glm-5.2",
                executor_model="z-ai/glm-5.2",
                verifier_model="z-ai/glm-5.2",
                judge_model="z-ai/glm-5.2",
            )
            await store.set_brain_config(patch, actor="self_heal_stale_provider_reset")
            summary["failover_persisted"] = "nvidia"
            summary["reset_reason"] = f"provider {normalized_active} not in known-good set"
        except Exception as exc:
            log.error("self_heal: failed to reset stale brain config: %s", exc)
        # After reset, the next task dispatch will use nvidia. No need to
        # continue the failover search below.
        # Still unblock tasks below.

    # If the active provider has sustained failures, force a failover.
    # threshold=3 matches the watchdog's max_failures default — by this
    # point the watchdog has already triggered a failover, but the
    # persisted config might not have stuck (e.g. BrainConfigStore race).
    # We re-persist to make sure.
    if failure_count < 3 and normalized_active in known_good_providers:
        # Brain is healthy (or failures are transient). Check if there are
        # blocked tasks to unblock anyway (they might have been blocked
        # before a previous failover).
        pass
    else:
        log.warning(
            "self_heal: active provider %s has %d failures — re-persisting failover",
            active_provider, failure_count,
        )

    # ── Step 2: Find the best healthy provider ──────────────────────────
    # Priority: BRAIN_PREFERENCE first, then RECOMMENDED_PROVIDER_PRIORITY.
    # Skip providers that have active failures or are not actually available.
    from packages.ai.watchdog import _is_provider_actually_available, BrainWatchdog
    healthy_provider = None
    candidates = []
    if preference == "ollama":
        candidates = ["ollama"] + [p for p in RECOMMENDED_PROVIDER_PRIORITY if p != "ollama"]
    else:
        candidates = list(RECOMMENDED_PROVIDER_PRIORITY)

    for provider in candidates:
        # Use _is_provider_actually_available instead of provider_key_present
        # so ollama is only picked if OLLAMA_BASE_URL is set (not just because
        # it's always "present"). This prevents false failover to an
        # unreachable ollama on Render free tier.
        if not _is_provider_actually_available(provider):
            continue
        # Skip providers currently in failure state (normalized name)
        normalized = BrainWatchdog._normalize_provider(provider)
        if watchdog._failure_counts.get(normalized, 0) >= 3:
            continue
        healthy_provider = provider
        break

    if healthy_provider is None:
        summary["skipped_reason"] = "no healthy provider available"
        log.warning("self_heal: no healthy provider available — all providers in failure state or unconfigured")
    elif healthy_provider != active_provider or failure_count >= 3:
        # Persist the failover
        try:
            store = await get_brain_config_store()
            preset = PROVIDER_PRESETS.get(healthy_provider, {})
            patch = BrainConfigPatch(
                primary_provider=healthy_provider,  # type: ignore[arg-type]
                planner_model=preset.get("planner"),
                executor_model=preset.get("executor"),
                verifier_model=preset.get("verifier"),
                judge_model=preset.get("judge"),
            )
            await store.set_brain_config(patch, actor="self_heal")
            summary["failover_persisted"] = healthy_provider
            log.info("self_heal: persisted failover %s -> %s", active_provider, healthy_provider)

            # Reset the watchdog failure count for the new provider so it
            # starts fresh
            watchdog._failure_counts[healthy_provider] = 0
        except Exception as exc:
            summary["skipped_reason"] = f"failover persist failed: {exc}"
            log.error("self_heal: failed to persist failover: %s", exc)

    # ── Step 3: Unblock tasks that were BLOCKED due to runtime/brain unavailability ──
    try:
        from tasks.store import get_task_store, TaskStore
        from tasks.models import TaskStatus
        store = get_task_store()
        # Find BLOCKED tasks whose blocked_reason mentions runtime/brain unavailable
        if store._mode == "mongo":
            cursor = store._collection.find(
                {"status": TaskStatus.BLOCKED.value},
                {"_id": 0},
            )
            blocked_docs = await cursor.to_list(length=500)
        else:
            blocked_docs = [
                v for v in store._mem.values()
                if v.get("status") == TaskStatus.BLOCKED.value
            ]

        for doc in blocked_docs:
            blocked_reason = (doc.get("blocked_reason") or "").lower()
            error_message = (doc.get("error_message") or "").lower()
            # Only unblock tasks that were blocked due to runtime/brain issues,
            # NOT tasks blocked for other reasons (e.g. approval gate, code error)
            if not any(kw in blocked_reason + " " + error_message for kw in
                       ("runtime", "brain", "no llm", "unavailable", "no runtime")):
                continue

            task_id = doc.get("task_id") or doc.get("_id")
            if not task_id:
                continue

            # Re-queue the task
            from tasks.models import Task
            task = Task.model_validate(doc)
            task.status = TaskStatus.TODO
            task.pending_agent_run = True
            task.blocked_reason = None
            task.error_message = None
            task.add_log(
                "Task unblocked by self_heal — re-dispatching on new brain provider",
                event_type="self_healed",
                actor="system:self_heal",
                task_status=TaskStatus.TODO,
            )
            await store.update(task)
            summary["tasks_unblocked"] += 1
            log.info("self_heal: unblocked task %s (was: %s)", task_id, blocked_reason[:80])

    except Exception as exc:
        summary["skipped_reason"] = f"task unblock failed: {exc}"
        log.error("self_heal: failed to unblock tasks: %s", exc)

    if summary["failover_persisted"] or summary["tasks_unblocked"]:
        log.info("self_heal: %s", summary)
        # Langfuse trace: self-healing action
        try:
            from langfuse_obs import emit_agency_observation
            emit_agency_observation(
                operation="self_heal",
                actor="system:self_heal",
                status="ok",
                metadata=summary,
            )
        except Exception:
            pass

    return summary


async def _self_heal_tick() -> None:
    """Background tick that runs self_heal_brain_and_unblock_tasks().

    Called from the scheduler tick handler every minute. Catches all
    exceptions so it never breaks the tick.
    """
    try:
        await self_heal_brain_and_unblock_tasks()
    except Exception as exc:
        log.error("self_heal tick failed: %s", exc)
