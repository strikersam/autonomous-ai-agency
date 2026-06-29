"""runtimes/health.py — RuntimeHealthService.

Periodically polls all registered runtimes for health and caches the
results.  Exposes get_health(runtime_id) for instant access without
blocking.  Also implements circuit-breaker logic: a runtime that fails
N consecutive checks is marked OPEN (unhealthy) and skipped by the
routing engine until it recovers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from runtimes.base import RuntimeHealth

if TYPE_CHECKING:
    from runtimes.registry import RuntimeCapabilityRegistry

log = logging.getLogger("qwen-proxy")

# ── Circuit-breaker constants ─────────────────────────────────────────────────
CB_FAILURE_THRESHOLD = 3    # consecutive failures → OPEN
CB_RECOVERY_SEC      = 30   # seconds before re-probing after OPEN
SLOW_PROBE_SEC       = 300  # probe interval for runtimes that have never been healthy


@dataclass
class CircuitState:
    runtime_id: str
    consecutive_failures: int = 0
    open_since: float | None = None   # monotonic time when circuit opened
    ever_healthy: bool = False        # True once a probe has succeeded
    total_failures: int = 0           # lifetime failure count
    last_probe_at: float = 0.0        # monotonic time of last attempted probe

    @property
    def is_open(self) -> bool:
        if self.open_since is None:
            return False
        return (time.monotonic() - self.open_since) < CB_RECOVERY_SEC

    @property
    def slow_probe_mode(self) -> bool:
        """Reduce probe frequency for runtimes that have never come online."""
        return not self.ever_healthy and self.total_failures >= 6

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.open_since = None
        self.ever_healthy = True

    def record_failure(self) -> None:
        self.total_failures += 1
        self.consecutive_failures += 1
        if self.consecutive_failures >= CB_FAILURE_THRESHOLD:
            if self.open_since is None:
                self.open_since = time.monotonic()
                log.warning("Circuit OPEN for runtime %s after %d failures",
                            self.runtime_id, self.consecutive_failures)


class RuntimeHealthService:
    """Async health polling service for all registered runtimes."""

    def __init__(
        self,
        registry: "RuntimeCapabilityRegistry",
        poll_interval_sec: int = 30,
    ) -> None:
        self._registry = registry
        self._poll_interval = poll_interval_sec
        self._cache: dict[str, RuntimeHealth] = {}
        self._circuits: dict[str, CircuitState] = {}
        self._task: asyncio.Task | None = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background polling loop with an immediate initial check."""
        if self._task is None or self._task.done():
            asyncio.create_task(self._poll_all())
            self._task = asyncio.create_task(self._poll_loop())
            log.info("RuntimeHealthService started (interval=%ds)", self._poll_interval)

    async def stop(self) -> None:
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, RuntimeError):
            pass
        finally:
            self._task = None

    # ── Public API ────────────────────────────────────────────────────────────

    def get_health(self, runtime_id: str) -> RuntimeHealth | None:
        """Return the last-known health for *runtime_id* (may be stale)."""
        return self._cache.get(runtime_id)

    def is_available(self, runtime_id: str) -> bool:
        """Return True if the runtime is available (not circuit-open)."""
        circuit = self._circuits.get(runtime_id)
        if circuit and circuit.is_open:
            return False
        h = self._cache.get(runtime_id)
        return h.available if h else True  # optimistic until first check

    def all_health(self) -> list[dict]:
        """Return health snapshots for all known runtimes."""
        return [
            {
                **h.as_dict(),
                "circuit_open": self._circuits.get(h.runtime_id, CircuitState(h.runtime_id)).is_open,
            }
            for h in self._cache.values()
        ]

    async def verify_all(self) -> list[dict]:
        """Force an immediate health check of all runtimes and return results."""
        await self._poll_all()
        return self.all_health()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _poll_loop(self) -> None:
        while True:
            await self._poll_all()
            await asyncio.sleep(self._poll_interval)

    async def _poll_all(self) -> None:
        adapters = self._registry.all()
        tasks = [self._poll_one(a.RUNTIME_ID) for a in adapters]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _poll_one(self, runtime_id: str) -> None:
        adapter = self._registry.get(runtime_id)
        if adapter is None:
            return
        circuit = self._circuits.setdefault(runtime_id, CircuitState(runtime_id))
        now = time.monotonic()

        # Slow-probe mode: runtimes that have never been healthy get probed
        # much less aggressively to avoid constant log spam and CPU waste.
        if circuit.slow_probe_mode and (now - circuit.last_probe_at) < SLOW_PROBE_SEC:
            return

        # Normal circuit breaker: skip during the recovery window.
        if circuit.is_open:
            return

        # Recovery window just expired — reset open_since so that a fresh
        # failure after the probe re-opens the circuit from scratch.
        if circuit.open_since is not None:
            circuit.open_since = None
            log.info("Circuit probe for runtime %s (was OPEN, attempting recovery)", runtime_id)
            # Try to bring the runtime back before probing.
            await self._try_auto_start(runtime_id)

        circuit.last_probe_at = now
        try:
            health = await asyncio.wait_for(adapter.health_check(), timeout=30.0)
            self._cache[runtime_id] = health
            if health.available:
                circuit.record_success()
                log.info("Runtime %s is healthy (latency=%.0fms)",
                         runtime_id, health.latency_ms or 0)
            else:
                circuit.record_failure()
        except Exception as exc:
            # After the circuit opens (3 failures), these fire every 30s during
            # recovery probes — demote to DEBUG to avoid log spam. The circuit-
            # open state itself is already logged at WARNING in record_failure().
            if circuit.is_open:
                log.debug("Health check still failing for %s (circuit OPEN): %s", runtime_id, exc)
            else:
                log.warning("Health check failed for %s: %s (circuit failures: %d)",
                          runtime_id, exc, circuit.consecutive_failures + 1)
            circuit.record_failure()
            self._cache[runtime_id] = RuntimeHealth(
                runtime_id=runtime_id,
                available=False,
                error=f"{type(exc).__name__}: {exc}",
            )

    async def _try_auto_start(self, runtime_id: str) -> None:
        """Attempt to start a dead runtime subprocess before re-probing.

        Uses the local subprocess fallback in runtimes/control.py which spawns
        docker/agent_runtime.py as a lightweight HTTP wrapper on a fixed port.
        Imported lazily to avoid the control→manager→health circular import.
        """
        try:
            from runtimes.control import RUNTIME_LOCAL_PORTS, _start_local_runtime  # noqa: PLC0415
            if runtime_id not in RUNTIME_LOCAL_PORTS:
                return
            result = await _start_local_runtime(runtime_id)
            status = result.get("status", "")
            if status in ("started", "already_running"):
                log.info("Auto-started runtime %s (status=%s, pid=%s)",
                         runtime_id, status, result.get("pid", "?"))
                # Brief pause for the subprocess to finish initialising.
                await asyncio.sleep(1.0)
            elif status == "error":
                log.debug("Auto-start failed for %s: %s", runtime_id, result.get("error"))
        except Exception as exc:
            log.debug("Auto-start skipped for %s: %s", runtime_id, exc)
