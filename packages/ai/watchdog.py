"""services/brain_watchdog.py — Brain health watchdog.

Monitors the active brain provider for consecutive failures and auto-fails-
over to the next provider in RECOMMENDED_PROVIDER_PRIORITY when the threshold
is hit. Persists the new provider via the brain config store and pages
Telegram.

Usage (in-process daemon started by the backend)::

    watchdog = BrainWatchdog(max_failures=3)
    watchdog.record_failure("cerebras")   # call on each provider error
    watchdog.record_success("cerebras")   # resets the counter on success

Or as a standalone probe::

    python -m services.brain_watchdog   # one-shot liveness check
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

log = logging.getLogger("brain-watchdog")

_DEFAULT_MAX_FAILURES = int(os.environ.get("BRAIN_WATCHDOG_MAX_FAILURES", "3"))

from packages.ai import brain_config as _bcs  # noqa: E402


class BrainWatchdog:
    """Monitors provider health and triggers failover on consecutive failures."""

    def __init__(self, max_failures: int = _DEFAULT_MAX_FAILURES) -> None:
        self.max_failures = max_failures
        self._failure_counts: dict[str, int] = {}
        self._last_failover: float = 0
        self._failover_log: list[dict[str, Any]] = []

    def record_success(self, provider: str) -> None:
        """Reset failure counter for a provider after a successful call."""
        if self._failure_counts.get(provider, 0) > 0:
            log.info("Brain watchdog: %s recovered (was at %d failures)",
                     provider, self._failure_counts[provider])
        self._failure_counts[provider] = 0

    def record_failure(self, provider: str) -> str | None:
        """Record a provider failure. Returns the new provider if failover triggered."""
        count = self._failure_counts.get(provider, 0) + 1
        self._failure_counts[provider] = count
        log.warning("Brain watchdog: %s failure #%d (threshold=%d)",
                    provider, count, self.max_failures)

        if count >= self.max_failures:
            return self._trigger_failover(provider)
        return None

    def _trigger_failover(self, failed_provider: str) -> str | None:
        """Fail over to the next available provider."""
        candidates = [
            p for p in _bcs.RECOMMENDED_PROVIDER_PRIORITY
            if p != failed_provider and _bcs.provider_key_present(p)
        ]
        if not candidates:
            log.error("Brain watchdog: no failover candidates available "
                      "(all providers down or no keys configured)")
            return None

        new_provider = candidates[0]
        self._failure_counts[failed_provider] = 0
        self._last_failover = time.time()

        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "from_provider": failed_provider,
            "to_provider": new_provider,
            "failure_count": self.max_failures,
        }
        self._failover_log.append(entry)
        log.warning("Brain watchdog: FAILOVER %s -> %s after %d consecutive failures",
                    failed_provider, new_provider, self.max_failures)

        self._persist_failover(new_provider)
        self._notify_failover(failed_provider, new_provider)
        return new_provider

    def _persist_failover(self, new_provider: str) -> None:
        """Persist the new provider in the brain config store (fire-and-forget).

        Uses the proper async BrainConfigStore.set_brain_config() API via the
        process-wide singleton so the in-memory cache is immediately updated.
        Runs in a background task so this method stays synchronous (it's called
        from sync record_failure → _trigger_failover). Errors are logged — the
        failover is best-effort and must never break the request path.
        """
        async def _apply() -> None:
            try:
                from packages.ai.brain_config import (
                    BrainConfigPatch,
                    get_brain_config_store,
                )
                store = await get_brain_config_store()
                preset = _bcs.PROVIDER_PRESETS.get(new_provider)
                if preset:
                    patch = BrainConfigPatch(
                        primary_provider=new_provider,  # type: ignore[arg-type]
                        planner_model=preset.get("planner"),
                        executor_model=preset.get("executor"),
                        verifier_model=preset.get("verifier"),
                        judge_model=preset.get("judge"),
                    )
                    await store.set_brain_config(patch, actor="brain_watchdog")
                    log.info("Brain watchdog: persisted failover to %s", new_provider)
            except Exception as exc:
                log.error("Brain watchdog: failed to persist failover: %s", exc)

        try:
            asyncio.create_task(_apply())
        except RuntimeError:
            # No event loop running (e.g. in a sync script context) — skip persistence
            log.debug("Brain watchdog: no event loop — skipping persistence of failover to %s", new_provider)

    def _notify_failover(self, old: str, new: str) -> None:
        """Send a Telegram notification about the failover."""
        try:
            from telegram_service import NotificationDispatcher
            dispatcher = NotificationDispatcher()
            dispatcher.dispatch(
                f"Brain watchdog: FAILOVER {old} -> {new} "
                f"after {self.max_failures} consecutive failures. "
                f"The agency is now using {new}.",
                channel="telegram",
            )
        except Exception as exc:
            log.debug("Brain watchdog: Telegram notify failed (non-fatal): %s", exc)

    @property
    def failover_log(self) -> list[dict[str, Any]]:
        return list(self._failover_log)

    def status(self) -> dict[str, Any]:
        return {
            "failure_counts": dict(self._failure_counts),
            "max_failures": self.max_failures,
            "last_failover": self._last_failover,
            "failover_count": len(self._failover_log),
        }


_watchdog: BrainWatchdog | None = None


def get_watchdog() -> BrainWatchdog:
    """Return the shared BrainWatchdog singleton."""
    global _watchdog
    if _watchdog is None:
        _watchdog = BrainWatchdog()
    return _watchdog


def reset_watchdog() -> None:
    """Reset the singleton (test helper)."""
    global _watchdog
    _watchdog = None
