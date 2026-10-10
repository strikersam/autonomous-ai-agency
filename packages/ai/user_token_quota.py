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

Memory is the hot-path cache, per process and per UTC day. Each recorded call
is also pushed (asynchronously, never blocking the caller) as an atomic ``$inc``
upsert to the ``user_token_usage`` collection, one document per (user, UTC day)
with a TTL, unless ``AGENCY_STATE_PERSISTENCE_ENABLED`` is off or no DB is
reachable. The pre-run check (``user_quota_refusal_async``) reads that
authoritative total so the cap holds across workers and restarts; per-call checks
use the cache plus a throttled background refresh. A DB error leaves the cache
enforcing on its own. Tokens are counted after a call returns, so one call can
overshoot. Usage is recorded even while the cap is 0 so the usage endpoints stay useful.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from packages.config.autonomy_limits import user_daily_token_cap
from packages.storage import state_persistence as _persist

log = logging.getLogger("qwen-proxy")

# Pseudo-users that are autonomous work rather than people.
EXEMPT_USERS = frozenset({"scheduler"})
# Bounds the ledger: past this many users in one day, new ids fold into one
# shared bucket, so a stream of distinct ids cannot grow the dict without limit.
_MAX_USERS_PER_DAY = 5000
# Reserved key that cannot be a user id (ids are stripped text); reported as "other".
_OVERFLOW = "\x00overflow"
_OVERFLOW_LABEL = "other"
# Users folded into the overflow bucket stay refusable: their ids are remembered
# (bounded) so the cap check reads the shared bucket for them and only for them.
_OVERFLOW_IDS_FACTOR = 10
# Generic, client-safe wording (CLAUDE.md rule 27): no counts, no internals.
REFUSAL_MESSAGE = "Daily agent token limit reached. It resets at 00:00 UTC."

USAGE_COLLECTION = "user_token_usage"
_TTL_DAYS = 3  # old days are dropped by a TTL index on expires_at
_REFRESH_S = 15.0  # min gap between background DB refreshes per user
_DB_TIMEOUT_S = 2.0  # the pre-run DB read never stalls a run longer than this

_current_user: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_quota_user", default=None
)
_lock = threading.Lock()
_day = ""
_ledger: dict[str, int] = {}
_overflowed: set[str] = set()
_overflow_logged = False
# DB total per user as of the last refresh. It already includes this worker's
# flushed writes, so the effective figure is max(local, remote), never the sum.
_remote: dict[str, int] = {}
_refreshed: dict[str, float] = {}


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
        _overflowed.clear()
        _remote.clear()
        _refreshed.clear()


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
    """Tokens recorded for *user_id* so far today (UTC).

    A user whose spend was folded into the overflow bucket reads that shared
    bucket, so the cap still applies to them (conservatively).
    """
    with _lock:
        _roll_day()
        remote = _remote.get(user_id, 0)
        if user_id in _ledger:
            return max(_ledger[user_id], remote)
        return max(_ledger.get(_OVERFLOW, 0) if user_id in _overflowed else 0, remote)


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
    uid = current_user()
    _maybe_refresh(uid)
    refusal = user_quota_refusal(uid)
    if refusal:
        raise UserTokenQuotaExceeded(refusal)


def _doc_id(day: str, uid: str) -> str:
    return f"{day}:{uid}"


async def _persist_tokens(day: str, uid: str, count: int) -> None:
    """Atomically add *count* to the (user, day) document. Never raises."""
    col = _persist.collection(USAGE_COLLECTION)
    if col is None:
        return
    try:
        await _persist.ensure_ttl_index(USAGE_COLLECTION, col, "expires_at")
        expires = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=_TTL_DAYS)
        await col.update_one(
            {"_id": _doc_id(day, uid)},
            {"$inc": {"tokens": count},
             "$setOnInsert": {"user_id": uid, "day": day, "expires_at": expires}},
            upsert=True,
        )
    except Exception as exc:  # noqa: BLE001 - the cache keeps enforcing
        log.warning("user token ledger write failed (cache still enforces): %s", exc)


async def refresh_user_total(user_id: str) -> int | None:
    """Pull today's authoritative DB total for *user_id* into the cache.

    Returns the DB total, or ``None`` when persistence is off or the read
    failed (the cache is then left as it was).
    """
    col = _persist.collection(USAGE_COLLECTION)
    if col is None:
        return None
    with _lock:
        _roll_day()
        day = _day
    try:
        doc = await asyncio.wait_for(col.find_one({"_id": _doc_id(day, user_id)}), _DB_TIMEOUT_S)
        total = _safe_count((doc or {}).get("tokens"))
    except Exception as exc:  # noqa: BLE001 - fall back to the cache
        log.warning("user token ledger read failed (using cache): %s", exc)
        return None
    with _lock:
        if _day == day:
            _remote[user_id] = total
            _refreshed[user_id] = time.monotonic()
    return total


def _maybe_refresh(user_id: str | None) -> None:
    """Kick a throttled background refresh for the per-call (sync) check."""
    uid = _counted(user_id)
    if uid is None or not user_daily_token_cap() or not _persist.persistence_enabled():
        return
    now = time.monotonic()
    with _lock:
        _roll_day()  # a day change clears the throttle, so roll before stamping it
        if now - _refreshed.get(uid, -_REFRESH_S) < _REFRESH_S:
            return
        _refreshed[uid] = now
    _persist.fire_and_forget(refresh_user_total(uid))


async def user_quota_refusal_async(user_id: str | None) -> str | None:
    """Pre-run check that consults the authoritative DB total first.

    Same contract as :func:`user_quota_refusal`; the DB read only tightens it.
    """
    uid = _counted(user_id)
    if uid is not None and user_daily_token_cap():
        await refresh_user_total(uid)
    return user_quota_refusal(user_id)


def _safe_count(tokens: object) -> int:
    """Coerce *tokens* to a non-negative int; anything unusable counts as 0."""
    try:
        return max(int(tokens or 0), 0)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        return 0


def record_user_tokens(tokens: int) -> None:
    """Add one call's tokens to the bound user's daily total. Never raises."""
    global _overflow_logged
    uid = current_user()
    if uid is None:
        return
    count = _safe_count(tokens)
    with _lock:
        _roll_day()
        if uid not in _ledger and len(_ledger) >= _MAX_USERS_PER_DAY:
            if len(_overflowed) < _MAX_USERS_PER_DAY * _OVERFLOW_IDS_FACTOR:
                _overflowed.add(uid)
            if not _overflow_logged:
                _overflow_logged = True
                log.warning("user token ledger full (%d users); folding new users into a shared bucket",
                            _MAX_USERS_PER_DAY)
            uid = _OVERFLOW
        _ledger[uid] = _ledger.get(uid, 0) + count
        day = _day
    if count:
        _persist.fire_and_forget(_persist_tokens(day, current_user() or uid, count))


def anthropic_usage_total(resp: object) -> int:
    """Input + output tokens from an Anthropic SDK response; 0 when absent."""
    usage = getattr(resp, "usage", None)
    return _safe_count(getattr(usage, "input_tokens", 0)) + _safe_count(
        getattr(usage, "output_tokens", 0)
    )


def usage_snapshot() -> dict[str, int]:
    """Today's per-user token totals, for the admin endpoint and tests."""
    with _lock:
        _roll_day()
        return {(_OVERFLOW_LABEL if k == _OVERFLOW else k): v for k, v in _ledger.items()}


def reset() -> None:
    """Clear the ledger. Test helper."""
    global _day, _overflow_logged
    with _lock:
        _ledger.clear()
        _overflowed.clear()
        _overflow_logged = False
        _remote.clear()
        _refreshed.clear()
        _day = ""
