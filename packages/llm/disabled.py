"""packages/llm/disabled.py — bridge to the durable provider on/off switch.

The set of disabled providers already has one owner: ``services/brain_failover.py``
persists it to MongoDB, so it survives a Render deploy, and the Providers screen
renders it. Two things write to it — an operator flipping a provider off in the
UI, and the legacy failover path auto-disabling a provider whose failure only a
human can fix (a revoked key, an account with no credit).

``LLMRouter`` has to observe the same switch. Its circuit breaker is a different
instrument: the breaker is in-memory, recovers on its own, and resets on
restart, which is right for "this provider is having a bad minute" and wrong for
"this key was revoked in March". Without this bridge, enabling
``LLM_ROUTER_ENABLED`` silently means a disabled provider is routed to anyway
and a dead key is retried forever.

Both functions import ``services.brain_failover`` lazily and never raise:
``packages/llm`` must not take a hard dependency on ``services`` (that direction
is a circular import), and a storage hiccup must never take the brain offline.
"""
from __future__ import annotations

import logging

log = logging.getLogger("llm.disabled")

# Statuses whose only cure is a human: a new key, or money on the account.
# Retrying them costs latency on every request and never succeeds, which is why
# the legacy path persists the provider as disabled instead of relying on a
# breaker that reopens on a timer.
UNFIXABLE_STATUSES = frozenset({401, 402, 403})


def disabled_provider_ids() -> frozenset[str]:
    """Provider ids currently switched off. Empty when the store is unreachable."""
    try:
        from services.brain_failover import disabled_providers
        return frozenset(disabled_providers())
    except Exception as exc:  # pragma: no cover - storage/import is best-effort
        log.debug("llm.disabled: could not read the disabled set (%s)", exc)
        return frozenset()


def auto_disable(provider_id: str, reason: str) -> None:
    """Persist a provider as disabled, through the store that already owns it."""
    if not provider_id:
        return
    try:
        from services.brain_failover import auto_disable_provider
        auto_disable_provider(provider_id, reason)
        log.warning("llm.router: auto-disabled %s — %s", provider_id, reason)
    except Exception as exc:  # pragma: no cover - storage is best-effort
        log.debug("llm.disabled: could not disable %s (%s)", provider_id, exc)


def _billing_signals() -> tuple[str, ...]:
    """The one list of "you have no money" phrases, borrowed not copied.

    Lazy because ``packages.ai.failover_client`` imports the router: taking this
    at module scope would close the cycle.
    """
    try:
        from packages.ai.failover_client import _BILLING_SIGNALS
        return _BILLING_SIGNALS
    except Exception:  # pragma: no cover - defensive
        return ()


def is_unfixable(status: int | None, body: str = "") -> bool:
    """Whether this failure needs a human rather than a retry.

    Two shapes qualify. A 401/402/403 says so in the status line. A billing
    refusal says so only in the body: providers disagree on the code for "your
    account is empty" — DeepSeek answers 402, Anthropic answers 400 with
    "credit balance is too low" — and both mean every model on that provider
    will refuse identically.
    """
    if status in UNFIXABLE_STATUSES:
        return True
    if status is None or not 400 <= status < 500:
        return False
    haystack = body[:600].lower()
    return any(signal in haystack for signal in _billing_signals())


def describe(status: int | None, error: str = "") -> str:
    """The operator-facing reason string for an unfixable status."""
    if status == 402:
        return "402 out of credit"
    if status in (401, 403):
        return f"{status} invalid or expired API key"
    if status is not None:
        return f"{status} out of credit/quota"
    return f"error {error}".strip()
