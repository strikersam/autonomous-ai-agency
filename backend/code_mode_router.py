"""backend/code_mode_router.py — Code Mode phase-2 measurement (admin only).

    GET /api/admin/agent/code-mode/metrics — on vs holdout arm comparison

Backed by :mod:`agent.code_mode_metrics`: per-step tool-selection LLM calls,
estimated prompt tokens, wall time and outcome, split by whether the step had
``run_code`` (arm ``on``) or was held out (``AGENT_CODE_MODE_HOLDOUT_PERCENT``).
Samples hold numbers only, never prompt or tool text.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agent import code_mode_metrics

log = logging.getLogger("qwen-proxy")


class CodeModeMetrics(BaseModel):
    """Arm comparison for the Code Mode experiment."""

    enabled: bool
    holdout_percent: int
    arms: dict[str, dict[str, Any]]
    run_code: dict[str, Any]
    min_samples_per_arm: int
    enough_data: bool
    delta_on_vs_holdout: dict[str, Any] | None = None
    verdict: str | None = None


def build_code_mode_router(get_current_user: Callable) -> APIRouter:
    """Build the router, bound to the app's auth dependency (avoids an import cycle)."""
    router = APIRouter(tags=["agent"])

    @router.get("/api/admin/agent/code-mode/metrics", response_model=CodeModeMetrics)
    async def code_mode_metrics_view(user: dict = Depends(get_current_user)) -> CodeModeMetrics:
        """Compare steps with run_code against the holdout. Admin only."""
        from agent.code_mode import code_mode_enabled, holdout_percent
        from backend.company_api import _is_admin

        if not _is_admin(user):
            raise HTTPException(status_code=403, detail="Admin role required")
        try:
            samples = await code_mode_metrics.get_store().load()
            data = code_mode_metrics.summary(samples)
        except Exception:
            log.exception("code mode metrics summary failed")
            raise HTTPException(status_code=500, detail="Could not compute code mode metrics") from None
        return CodeModeMetrics(enabled=code_mode_enabled(), holdout_percent=holdout_percent(), **data)

    return router
