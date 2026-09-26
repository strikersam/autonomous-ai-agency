"""packages/security/canary.py — detect the planted decoy credential leaving via an agent.

Adapted from ai-engineering-from-scratch lesson 15/14 (canary tokens): bait an
agent has no legitimate reason to touch, where touching it is the alarm. The
decoy is planted by ``packages.config.autonomy_limits.plant_canary``. This
module watches the two exits an agent controls:

* an LLM request made on behalf of an agent (a bound agent in
  ``packages/ai/agent_budget.py``), which carries whatever the agent read, e.g.
  the output of ``env``;
* an outbound URL an agent asks ``agent/web_reach.py`` to fetch.

A hit blocks that one action, logs at CRITICAL without the value, and sends
the operator a Telegram notification. It does not engage the kill switch:
that decision stays with a person.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from packages.config.autonomy_limits import CANARY_ENV, canary_value

log = logging.getLogger("qwen-proxy")


class CanaryTripped(RuntimeError):
    """Raised when the decoy credential is about to leave through an agent action."""


def contains_canary(text: str) -> bool:
    """True when *text* contains the planted decoy."""
    value = canary_value()
    return bool(value and text and value in text)


def _notify(message: str) -> None:
    try:
        from telegram_service import NotificationDispatcher

        NotificationDispatcher().send_manual_notification(message)
    except Exception:  # noqa: BLE001 - alerting must never mask the block itself
        log.exception("canary: operator notification failed")


def trip(where: str, actor: str | None) -> CanaryTripped:
    """Alert on a canary hit and return the exception the caller should raise."""
    message = (
        f"CANARY TRIPPED: the decoy credential {CANARY_ENV} reached {where} "
        f"(agent: {actor or 'unknown'}). The action was blocked. Something read "
        "the process environment. Review that agent's recent runs; turn on "
        "AGENCY_KILL_SWITCH if it looks deliberate."
    )
    log.critical(message)
    _notify(message)
    return CanaryTripped(message)


def ensure_payload_clean(payload: dict[str, Any], actor: str) -> None:
    """Raise ``CanaryTripped`` when an agent's LLM request carries the decoy."""
    if canary_value() is None:
        return
    try:
        text = json.dumps(payload.get("messages") or [], default=str)
    except (TypeError, ValueError):
        text = str(payload.get("messages"))
    if contains_canary(text):
        raise trip("an LLM request", actor)
