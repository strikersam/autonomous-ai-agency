"""packages/llm/quarantine.py — take providers that need money out of the loop.

Three refusals look alike on the wire and need opposite responses:

* a **rate limit** (429 "slow down") clears within the minute — cool the key;
* a **daily free quota** (Gemini's 429 "You exceeded your current quota", Groq's
  429 "quota exhausted") resets on its own — cool the key until the window ends;
* a **funds refusal** (HTTP 402, or a body naming credit, billing or payment)
  never clears by waiting. Retrying it every cycle spends an attempt of every
  request on a provider that cannot answer.

This module owns the third case. A funds refusal quarantines the provider for
``PROVIDER_FUNDS_QUARANTINE_HOURS`` (live control, default 24 h) through the
same durable on/off store the Providers screen and the doctor already read, so
the state survives a deploy and is visible. When the quarantine expires the
provider is routed to again — one real call re-probes it. ``0`` keeps the
previous behaviour: switched off until a human switches it back on.

Nothing here raises: classification is pure, and storage is best-effort, as in
``packages.llm.disabled``.
"""
from __future__ import annotations

import logging
import re

log = logging.getLogger("llm.quarantine")

# Phrases that mean "this account has no money / no paid plan for this".
_FUNDS_SIGNALS: tuple[str, ...] = (
    "insufficient_quota",           # OpenAI's code for "no credit"
    "insufficient balance", "insufficient_balance", "credit balance",
    "out of credit", "credits", "credit",
    "billing", "payment required", "payment", "card on file",
    "top up", "top-up", "upgrade your account", "upgrade your plan",
    "free plan",
)
# Phrases that mean a quota window that resets by itself. Checked first for
# 429s: Gemini's free-tier 429 says "exceeded your current quota, please check
# your plan and billing details" — it names billing and still resets daily.
_RESETTING_SIGNALS: tuple[str, ...] = (
    "exceeded your current quota", "quota exceeded for metric",
    "resource_exhausted", "per day", "per minute", "per hour",
    "requests per", "tokens per", "rate limit", "rate_limit", "rpm", "rpd", "tpm",
    "try again in", "retry in", "please retry",
)
_FUNDS_STATUSES = frozenset({400, 403, 429})
# Whole words only: "discredited" and "accreditation" are not funds refusals.
_FUNDS_RE = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(sig) for sig in _FUNDS_SIGNALS) + r")(?![a-z0-9])"
)
_STRONG_FUNDS_RE = re.compile(
    r"(?<![a-z0-9])(?:insufficient[ _]balance|credit balance|out of credits?"
    r"|payment required|card on file)(?![a-z0-9])"
)


def is_funds_refusal(status: int | None, body: str = "") -> bool:
    """True when *status*/*body* say the account needs credits, payment or a plan.

    402 always qualifies. A 400/403/429 qualifies only when its body names
    funds — and, for any of them, not when the body describes a quota window
    that resets on its own (unless it carries OpenAI's ``insufficient_quota``,
    which is the no-credit code despite its name).
    """
    if status == 402:
        return True
    if status not in _FUNDS_STATUSES:
        return False
    text = (body or "")[:800].lower()
    if "insufficient_quota" in text:
        return True
    if any(signal in text for signal in _RESETTING_SIGNALS):
        return False
    # A 400 is usually a bad request whose body may quote user content (a prompt
    # about "credit card payment"), so only unambiguous phrases count there.
    pattern = _STRONG_FUNDS_RE if status == 400 else _FUNDS_RE
    return bool(pattern.search(text))


def quarantine_seconds() -> float:
    """The live ``PROVIDER_FUNDS_QUARANTINE_HOURS`` control, in seconds (0 = manual)."""
    try:
        from packages.config import settings
        return float(settings.provider_funds_quarantine_sec)
    except Exception:  # noqa: BLE001 - an unreadable control keeps the default
        return 24 * 3600.0


def quarantine_provider(provider_id: str, reason: str) -> None:
    """Take *provider_id* out of the brain chain for the configured window.

    With the control at 0 this is the old permanent auto-disable. Idempotent:
    a provider already switched off keeps its first, most specific reason.
    """
    if not provider_id:
        return
    ttl = quarantine_seconds()
    try:
        from services import brain_failover
        if ttl <= 0:
            brain_failover.auto_disable_provider(provider_id, reason)
        else:
            brain_failover.quarantine_provider(provider_id, reason, ttl)
        log.warning(
            "llm.quarantine: %s out of the loop (%s) for %s",
            provider_id, reason, f"{ttl / 3600:.0f}h" if ttl > 0 else "until re-enabled",
        )
    except Exception as exc:  # pragma: no cover - storage is best-effort
        log.debug("llm.quarantine: could not quarantine %s (%s)", provider_id, exc)
