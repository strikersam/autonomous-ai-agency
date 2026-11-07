"""runtimes/quarantine.py — take a runtime out of rotation after a non-transient refusal.

A runtime whose ``/health`` answers 200 but whose real work is refused (a
mismatched API key, an exhausted billing account) looks healthy to the
router, so every task picks it first, fails, and only then falls back. In
production (2026-11-07) Hermes answered every task with ``HTTP 401: Invalid
Hermes API key`` while its health check stayed green, and E2B answered
``credit_exhausted``; each blocked task burned its dispatch attempts on them.

An adapter that sees such a refusal calls :func:`quarantine`; its
``health_check`` then reports ``available=False`` until the TTL lapses, so the
router skips it. The TTL keeps this self-healing: once the key or the credit
is fixed, the next probe after expiry puts the runtime back.
"""

from __future__ import annotations

import logging
import re
import time

log = logging.getLogger("qwen-proxy")

DEFAULT_TTL_SEC = 900.0

_until: dict[str, float] = {}
_reason: dict[str, str] = {}


def quarantine(runtime_id: str, reason: str, ttl_sec: float = DEFAULT_TTL_SEC) -> None:
    """Mark *runtime_id* unavailable for *ttl_sec* seconds because of *reason*."""
    first = runtime_id not in _until or _until[runtime_id] <= time.monotonic()
    _until[runtime_id] = time.monotonic() + ttl_sec
    _reason[runtime_id] = reason
    if first:
        log.error("Runtime %s quarantined for %ds: %s", runtime_id, int(ttl_sec), reason)


def quarantined(runtime_id: str) -> str | None:
    """Return the quarantine reason while *runtime_id* is quarantined, else None."""
    until = _until.get(runtime_id)
    if until is None:
        return None
    if until <= time.monotonic():
        _until.pop(runtime_id, None)
        _reason.pop(runtime_id, None)
        log.info("Runtime %s quarantine expired; probing again", runtime_id)
        return None
    return _reason.get(runtime_id, "quarantined")


def clear(runtime_id: str | None = None) -> None:
    """Lift the quarantine for one runtime, or all of them (tests, admin reset)."""
    if runtime_id is None:
        _until.clear()
        _reason.clear()
        return
    _until.pop(runtime_id, None)
    _reason.pop(runtime_id, None)


# Markers of an E2B account-level refusal (billing, auth) as opposed to a
# transient sandbox failure. Production 2026-11-07: "403: team is blocked:
# credit_exhausted". Shared by the E2B adapter and services.e2b_sandbox's
# opener so every path that opens a sandbox honours the same quarantine.
E2B_RUNTIME_ID = "e2b"
_E2B_REFUSAL_RE = re.compile(
    r"credit_exhausted|team is blocked|(?<![\w.])40[13](?![\w.])", re.IGNORECASE
)


def is_e2b_account_refusal(exc: BaseException) -> bool:
    """True when *exc* says the E2B account itself cannot create sandboxes."""
    return bool(_E2B_REFUSAL_RE.search(str(exc)))
