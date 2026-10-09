"""packages/ai/user_token_quota.py — per-user daily token cap for agent runs.

Adapted from Octop's TokenQuotaMiddleware. ``packages/gateway/token_quota.py``
caps API-key consumers on the proxy surface and ``packages/ai/agent_budget.py``
caps each *agent*; nothing capped the *person* whose dashboard session starts
the agent runs. This module is that missing ceiling.

* ``user_scope(user_id)`` binds the run's owner in a ``ContextVar``. The workflow
  orchestrator binds it for the length of a run, and ``asyncio`` copies the
  context into every task the run creates, so the router sees the owner with no
  change to the OpenAI-shaped payload.
* ``user_quota_refusal(user_id)`` is the pre-run check the orchestrator uses.
* ``ensure_user_within_quota()`` / ``record_user_tokens()`` run inside
  ``ProviderRouter.chat_completion`` around each routed call.

Calls with no bound user (human proxy traffic, background loops) are never
counted or capped. The ``scheduler`` pseudo-user is autonomous work, not a
person, so it is exempt: capping it would silently halt every scheduled job.

The ledger is in-memory, per process and per UTC day, the same scope as
``agent_budget``. A restart clears the day's counts, which a daily cap
tolerates. Tokens are counted after a call returns, so one call can overshoot.
Usage is recorded even while the cap is 0 so the usage endpoints stay useful.
"""
from __future__ import annotations

import contextvars
import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from packages.config.autonomy_limits import user_daily_token_cap

log = logging.getLogger("qwen-proxy")

# Pseudo-users that are autonomous work rather than people.
EXEMPT_USERS = frozenset({"scheduler"})
# Bounds the ledger: past this many users in one day, new ids fold into one
# shared bucket, so a stream of distinct ids cannot grow the dict without limit.
_MAX_USERS_PER_DAY = 5000
_OVERFLOW = "other"
# Generic, client-safe wording (CLAUDE.md rule 27): no counts, no internals.
REFUSAL_MESSAGE = "Daily agent token limit reached. It resets at 00:00 UTC."

_current_user: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_quota_user", default=None
)
_lock = threading.Lock()
_day = ""
_ledger: dict[str, int] = {}


class UserTokenQuotaExceeded(RuntimeError):
    """Raised when a user has used their daily agent token allowance."""


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _roll_day() -> None:
    """Clear the ledger on a new UTC day; caller holds ``_lock``."""
    global _day
    today = _today()
    if today != _day:
        _day = today
        _ledger.clear()


def _counted(user_id: str | None) -> str | None:
    uid = (user_id or "").strip()
    return uid if uid and uid not in EXEMPT_USERS else None


def current_user() -> str | None:
    """The user bound to the running context, or ``None``."""
    return _current_user.get()


@contextmanager
def user_scope(user_id: str | None) -> Iterator[None]:
    """Attribute every routed LLM call inside the block to *user_id*."""
    token = _current_user.set(_counted(user_id))
    try:
        yield
    finally:
        _current_user.reset(token)


def tokens_used_today(user_id: str) -> int:
    """Tokens recorded for *user_id* so far today (UTC)."""
    with _lock:
        _roll_day()
        return _ledger.get(user_id, 0)


def user_quota_refusal(user_id: str | None) -> str | None:
    """Return the generic refusal text when *user_id* is over the cap, else ``None``."""
    cap = user_daily_token_cap()
    uid = _counted(user_id)
    if not cap or uid is None:
        return None
    if tokens_used_today(uid) >= cap:
        log.warning("user token quota reached: user=%s cap=%d", uid, cap)
        return REFUSAL_MESSAGE
    return None


def ensure_user_within_quota() -> None:
    """Raise ``UserTokenQuotaExceeded`` when the bound user is over the cap."""
    refusal = user_quota_refusal(current_user())
    if refusal:
        raise UserTokenQuotaExceeded(refusal)


def record_user_tokens(tokens: int) -> None:
    """Add one call's tokens to the bound user's daily total. Never raises."""
    uid = current_user()
    if uid is None:
        return
    with _lock:
        _roll_day()
        if uid not in _ledger and len(_ledger) >= _MAX_USERS_PER_DAY:
            uid = _OVERFLOW
        _ledger[uid] = _ledger.get(uid, 0) + max(int(tokens or 0), 0)


def usage_snapshot() -> dict[str, int]:
    """Today's per-user token totals, for the admin endpoint and tests."""
    with _lock:
        _roll_day()
        return dict(_ledger)


def reset() -> None:
    """Clear the ledger. Test helper."""
    global _day
    with _lock:
        _ledger.clear()
        _day = ""
