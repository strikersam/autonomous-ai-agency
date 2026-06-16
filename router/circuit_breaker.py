"""Per-model circuit breaker for Ollama backend health.

Tracks consecutive failure counts per model name and opens the circuit after
``FAILURE_THRESHOLD`` consecutive errors.  After ``RECOVERY_TIMEOUT`` seconds
the circuit transitions to HALF_OPEN, allowing a single probe request.  A
successful probe closes the circuit; a failed probe re-opens it.

This is the same state machine used by ``services/nim_pool.py`` for NIM
providers, now applied to local Ollama model-level routing.

Configuration (env vars):
    CIRCUIT_BREAKER_FAILURE_THRESHOLD   int   default 3
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT    float default 60.0
    CIRCUIT_BREAKER_ENABLED             bool  default true
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

log = logging.getLogger("qwen-proxy")


def _failure_threshold() -> int:
    try:
        return max(1, int(os.environ.get("CIRCUIT_BREAKER_FAILURE_THRESHOLD") or "3"))
    except ValueError:
        return 3


def _recovery_timeout() -> float:
    try:
        return max(1.0, float(os.environ.get("CIRCUIT_BREAKER_RECOVERY_TIMEOUT") or "60"))
    except ValueError:
        return 60.0


def _enabled() -> bool:
    return os.environ.get("CIRCUIT_BREAKER_ENABLED", "true").strip().lower() in (
        "1", "true", "yes",
    )


_STATE_CLOSED = "CLOSED"
_STATE_OPEN = "OPEN"
_STATE_HALF_OPEN = "HALF_OPEN"


@dataclass
class _Circuit:
    state: str = _STATE_CLOSED
    failures: int = 0
    opened_at: float = field(default_factory=lambda: 0.0)
    probing: bool = False


class OllamaCircuitBreaker:
    """Thread-safe* per-model circuit breaker.

    *Reads/writes to the internal dict are GIL-protected in CPython, which is
    sufficient for our use-case (single-process FastAPI with asyncio).
    """

    def __init__(self) -> None:
        self._circuits: dict[str, _Circuit] = {}

    def _circuit(self, model: str) -> _Circuit:
        if model not in self._circuits:
            self._circuits[model] = _Circuit()
        return self._circuits[model]

    def is_open(self, model: str) -> bool:
        """Return True if the circuit is OPEN and the model should be skipped."""
        if not _enabled():
            return False
        c = self._circuit(model)
        if c.state == _STATE_CLOSED:
            return False
        if c.state == _STATE_OPEN:
            if time.monotonic() - c.opened_at >= _recovery_timeout():
                # Transition to HALF_OPEN and allow the first probe through
                c.state = _STATE_HALF_OPEN
                c.probing = True
                log.info("Circuit HALF_OPEN for model %r — allowing probe request", model)
                return False
            return True
        # HALF_OPEN: allow exactly one probe request at a time
        if c.state == _STATE_HALF_OPEN:
            if c.probing:
                return True  # probe already in flight — block additional requests
            # Edge case: probing was cleared (e.g. by reset) — allow one more probe
            c.probing = True
            return False
        return False

    def record_success(self, model: str) -> None:
        """Record a successful response; close the circuit."""
        if not _enabled():
            return
        c = self._circuit(model)
        if c.state != _STATE_CLOSED:
            log.info("Circuit CLOSED for model %r after successful probe", model)
        c.state = _STATE_CLOSED
        c.failures = 0
        c.probing = False

    def record_failure(self, model: str) -> None:
        """Record a 5xx error; open the circuit after threshold is reached."""
        if not _enabled():
            return
        c = self._circuit(model)
        c.failures += 1
        c.probing = False
        threshold = _failure_threshold()
        if c.state == _STATE_HALF_OPEN or c.failures >= threshold:
            if c.state != _STATE_OPEN:
                log.warning(
                    "Circuit OPEN for model %r after %d failure(s)", model, c.failures
                )
            c.state = _STATE_OPEN
            c.opened_at = time.monotonic()

    def reset(self, model: str | None = None) -> None:
        """Reset circuit state (used in tests and admin operations)."""
        if model is None:
            self._circuits.clear()
        elif model in self._circuits:
            del self._circuits[model]

    def state_for(self, model: str) -> str:
        """Return the current state string (CLOSED/OPEN/HALF_OPEN)."""
        return self._circuit(model).state

    def stats(self) -> dict[str, dict]:
        """Return a snapshot of all circuit states for observability."""
        return {
            m: {"state": c.state, "failures": c.failures, "probing": c.probing}
            for m, c in self._circuits.items()
        }


# Module-level singleton shared by the router and handlers
_breaker: OllamaCircuitBreaker | None = None


def get_circuit_breaker() -> OllamaCircuitBreaker:
    global _breaker
    if _breaker is None:
        _breaker = OllamaCircuitBreaker()
    return _breaker


def reset_circuit_breaker() -> None:
    global _breaker
    _breaker = None
