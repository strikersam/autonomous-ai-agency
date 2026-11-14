"""packages/config/runs_settings.py — the operator controls of the durable run layer.

Read from the environment on every call, like ``autonomy_limits``: a Platform
Controls save writes the process environment, so a change applies on the next
read without a restart. Each reader falls back to its default on a missing or
malformed value and clamps numbers to the bounds declared in the catalogue.

* ``RUNS_LEDGER_ENABLED`` (on): record runs, events and side effect operations.
  Recording only; it changes no scheduling or execution decision.
* ``RUNS_RECOVERY_ENABLED`` (off): let a worker take over and resume a run whose
  lease expired. Consumed from phase 2; off keeps today's behaviour.
* ``RUNS_LEASE_TTL_SEC`` (120): how long a run lease lives without a renewal.
* ``RUNS_LEASE_RENEW_SEC`` (30): how often a live run renews its lease.
* ``RUNS_OP_SKEW_SEC`` (30): clock skew margin added to every operation deadline.
"""
from __future__ import annotations

import logging
import os

log = logging.getLogger("qwen-proxy")

_TRUTHY = {"1", "true", "yes", "on"}
_FALSEY = {"0", "false", "no", "off"}


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw in _TRUTHY:
        return True
    if raw in _FALSEY:
        return False
    return default


def _seconds(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        log.warning("%s is not an integer; using %s", name, default)
        value = default
    return min(max(value, minimum), maximum)


def runs_ledger_enabled() -> bool:
    """``RUNS_LEDGER_ENABLED``: record runs and their side effects (default on)."""
    return _flag("RUNS_LEDGER_ENABLED", True)


def runs_recovery_enabled() -> bool:
    """``RUNS_RECOVERY_ENABLED``: resume runs whose lease expired (default off)."""
    return _flag("RUNS_RECOVERY_ENABLED", False)


def lease_ttl_s() -> int:
    """``RUNS_LEASE_TTL_SEC``: run lease lifetime without renewal, 10 to 3600 s."""
    return _seconds("RUNS_LEASE_TTL_SEC", 120, 10, 3600)


def lease_renew_s() -> int:
    """``RUNS_LEASE_RENEW_SEC``: renewal interval, 1 s up to a third of the TTL."""
    ttl = lease_ttl_s()
    return min(_seconds("RUNS_LEASE_RENEW_SEC", 30, 1, 1200), max(ttl // 3, 1))


def op_skew_s() -> int:
    """``RUNS_OP_SKEW_SEC``: clock skew margin on operation deadlines, 0 to 600 s."""
    return _seconds("RUNS_OP_SKEW_SEC", 30, 0, 600)
