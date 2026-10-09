"""backend/usage_router.py — read-only agent token usage per user (UTC day).

    GET /api/usage/agent-tokens          — the caller's own usage today
    GET /api/admin/usage/agent-tokens    — every user's usage today (admin only)

Backed by :mod:`packages.ai.user_token_quota`, so counts are per process and reset
on restart and at 00:00 UTC. The cap is the ``AGENT_USER_TOKENS_PER_DAY`` control.
"""

from __future__ import annotations

import logging
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packages.ai import user_token_quota
from packages.config.autonomy_limits import user_daily_token_cap

log = logging.getLogger("qwen-proxy")


class UserTokenUsage(BaseModel):
    """One user's agent token usage for the current UTC day."""

    user_id: str
    tokens_used: int
    daily_cap: int
    remaining: int | None
    exceeded: bool


class UserTokenUsageList(BaseModel):
    """All users' usage for the current UTC day, highest first."""

    daily_cap: int
    users: list[UserTokenUsage]


def _usage(user_id: str, used: int, cap: int) -> UserTokenUsage:
    return UserTokenUsage(
        user_id=user_id,
        tokens_used=used,
        daily_cap=cap,
        remaining=max(cap - used, 0) if cap else None,
        exceeded=bool(cap) and used >= cap,
    )


def build_usage_router(get_current_user: Callable) -> APIRouter:
    """Build the router, bound to the app's auth dependency (avoids an import cycle)."""
    router = APIRouter(tags=["usage"])

    @router.get("/api/usage/agent-tokens", response_model=UserTokenUsage)
    async def my_agent_token_usage(user: dict = Depends(get_current_user)) -> UserTokenUsage:
        """The authenticated caller's agent token usage today."""
        from backend.company_api import _resolve_user_id

        uid = _resolve_user_id(user)  # raises 401 when the session has no identity
        return _usage(uid, user_token_quota.tokens_used_today(uid), user_daily_token_cap())

    @router.get("/api/admin/usage/agent-tokens", response_model=UserTokenUsageList)
    async def all_agent_token_usage(user: dict = Depends(get_current_user)) -> UserTokenUsageList:
        """Every user's agent token usage today. Admin only."""
        from backend.company_api import _is_admin

        if not _is_admin(user):
            raise HTTPException(status_code=403, detail="Admin role required")
        cap = user_daily_token_cap()
        rows = sorted(user_token_quota.usage_snapshot().items(), key=lambda kv: -kv[1])
        return UserTokenUsageList(daily_cap=cap, users=[_usage(u, n, cap) for u, n in rows])

    return router
