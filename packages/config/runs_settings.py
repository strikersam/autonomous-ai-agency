"""packages/config/runs_settings.py — the operator controls of the durable run layer.

Read from the environment on every call, like ``autonomy_limits``: a Platform
Controls save writes the process environment, so a change applies on the next
read without a restart. Each reader falls back to its default on a missing or
malformed value and clamps numbers to the bounds declared in the catalogue.

* ``RUNS_LEDGER_ENABLED`` (on): record runs, events and side effect operations.
  Recording only; it changes no scheduling or execution decision.
* ``RUNS_RECOVERY_ENABLED`` (off): let a worker take over and resume a run whose
  lease expired. Consumed from phase 2; off keeps today's behaviour.
* ``RUNS_LEASE_TTL_SEC`` (600): how long a run lease lives without a renewal.
* ``RUNS_LEASE_RENEW_SEC`` (60): how often a live run renews its lease.
* ``RUNS_OP_SKEW_SEC`` (30): clock skew margin added to every operation deadline.
* ``RUNS_MAX_ATTEMPTS`` (3): attempts a recovered run gets before it is dead lettered.
* ``RUNS_RETRY_BACKOFF_BASE_SEC`` (10): base of the exponential backoff (with
  jitter) before a recovered run is queued again.
* ``RUNS_RECOVERY_TICK_SEC`` (30): how often the dispatcher runs the recovery tick.
* ``RUNS_DURABLE_APPROVALS`` (on): run approvals are stored in ``run_approvals``
  and bound to an action hash; off, the release gate and ``check`` refuse everything.
* ``RUNS_ARTIFACT_MAX_BYTES`` (1048576): largest artifact a run may store.
* ``RUNS_MAX_CHILDREN`` (16): child runs one parent may spawn (composer).
* ``RUNS_MAX_DEPTH`` (4): deepest child run level below a root run (composer).
* ``RUNS_MAX_PARALLEL`` (4): children of one fan out that execute at the same time.
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
    return _seconds("RUNS_LEASE_TTL_SEC", 600, 10, 3600)


def lease_renew_s() -> int:
    """``RUNS_LEASE_RENEW_SEC``: renewal interval, 1 s up to a third of the TTL."""
    ttl = lease_ttl_s()
    return min(_seconds("RUNS_LEASE_RENEW_SEC", 60, 1, 1200), max(ttl // 3, 1))


def op_skew_s() -> int:
    """``RUNS_OP_SKEW_SEC``: clock skew margin on operation deadlines, 0 to 600 s."""
    return _seconds("RUNS_OP_SKEW_SEC", 30, 0, 600)


def max_attempts() -> int:
    """``RUNS_MAX_ATTEMPTS``: attempts before a recovered run is dead lettered, 1 to 20."""
    return _seconds("RUNS_MAX_ATTEMPTS", 3, 1, 20)


def retry_backoff_base_s() -> int:
    """``RUNS_RETRY_BACKOFF_BASE_SEC``: backoff base for recovered runs, 0 to 3600 s."""
    return _seconds("RUNS_RETRY_BACKOFF_BASE_SEC", 10, 0, 3600)


def recovery_tick_s() -> int:
    """``RUNS_RECOVERY_TICK_SEC``: recovery tick cadence in the dispatcher, 5 to 3600 s."""
    return _seconds("RUNS_RECOVERY_TICK_SEC", 30, 5, 3600)


def max_children() -> int:
    """``RUNS_MAX_CHILDREN``: child runs one parent may spawn, 1 to 500."""
    return _seconds("RUNS_MAX_CHILDREN", 16, 1, 500)


def max_depth() -> int:
    """``RUNS_MAX_DEPTH``: deepest child run level below a root run, 1 to 10."""
    return _seconds("RUNS_MAX_DEPTH", 4, 1, 10)


def max_parallel() -> int:
    """``RUNS_MAX_PARALLEL``: children of one fan out running at once, 1 to 64."""
    return _seconds("RUNS_MAX_PARALLEL", 4, 1, 64)


def task_auto_retry_cap() -> int:
    """``TASK_AUTO_RETRY_MAX`` (read by the task reconciler too): auto retries per task."""
    return _seconds("TASK_AUTO_RETRY_MAX", 5, 0, 1000)


def durable_approvals_enabled() -> bool:
    """``RUNS_DURABLE_APPROVALS``: durable, action bound run approvals (default on)."""
    return _flag("RUNS_DURABLE_APPROVALS", True)


def artifact_max_bytes() -> int:
    """``RUNS_ARTIFACT_MAX_BYTES``: largest stored artifact, 1 KiB to 8 MiB."""
    return _seconds("RUNS_ARTIFACT_MAX_BYTES", 1_048_576, 1024, 8 * 1024 * 1024)
