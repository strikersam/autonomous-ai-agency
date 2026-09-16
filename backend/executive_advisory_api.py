"""backend/executive_advisory_api.py — REST surface for the C-suite advisory.

Exposes the intelligent business-advisory layer (``agent/executive_advisory.py``)
so an operator can actually ask the C-suite a question, rather than the CEO being
the only caller. Mounted on ``backend.server.app`` via
``build_executive_advisory_router(get_current_user)``.

Routes:
  GET  /api/executives          → list the C-suite personas (any authed user)
  POST /api/executives/consult  → ask the C-suite a business question (admin)

``consult`` starts real provider work — research plus one LLM call per executive
plus a synthesis — so it is admin-only, mirroring the budget-spending routes in
``backend/ceo_router.py``. Request and response are Pydantic-validated (rule 11);
the handler never returns raw exception detail to the client (rule 27).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("executive_advisory_api")


# ── Schemas ───────────────────────────────────────────────────────────────────


class AdvisoryConsultRequest(BaseModel):
    """A business question for the C-suite."""

    question: str = Field(..., min_length=1, max_length=4000)
    company_id: str | None = Field(default=None, max_length=128)
    roles: list[str] | None = Field(default=None)
    ground: bool = True
    remember: bool = True


class OpinionModel(BaseModel):
    role: str
    title: str
    text: str = ""
    error: str = ""


class GroundingModel(BaseModel):
    text: str = ""
    sources: list[str] = Field(default_factory=list)


class AdvisoryResponse(BaseModel):
    question: str
    consulted: list[str] = Field(default_factory=list)
    opinions: list[OpinionModel] = Field(default_factory=list)
    answer: str = ""
    grounding: GroundingModel = Field(default_factory=GroundingModel)


class ExecutiveModel(BaseModel):
    role: str
    title: str
    focus: str


class ExecutiveListResponse(BaseModel):
    executives: list[ExecutiveModel] = Field(default_factory=list)


# ── Router ────────────────────────────────────────────────────────────────────


def _require_admin(user: dict) -> None:
    """Reject non-admin callers for the route that spends provider budget.

    Delegates to ``backend.company_api._is_admin`` — the backend app's single
    role-tag authority — so this router cannot drift into a second admin rule.
    """
    from backend.company_api import _is_admin

    if not user or not _is_admin(user):
        raise HTTPException(status_code=403, detail="Admin role required")


def build_executive_advisory_router(
    get_current_user: Callable[..., Any],
) -> APIRouter:
    router = APIRouter(prefix="/api/executives", tags=["executives"])

    @router.get("", response_model=ExecutiveListResponse)
    async def list_executives(
        user: dict = Depends(get_current_user),
    ) -> ExecutiveListResponse:
        """The C-suite personas available to consult."""
        from agent.executive_advisory import default_executives

        return ExecutiveListResponse(
            executives=[
                ExecutiveModel(role=e.role, title=e.title, focus=e.focus)
                for e in default_executives()
            ]
        )

    @router.post("/consult", response_model=AdvisoryResponse)
    async def consult(
        body: AdvisoryConsultRequest,
        user: dict = Depends(get_current_user),
    ) -> AdvisoryResponse:
        """Ask the C-suite a business question and get one recommendation."""
        _require_admin(user)
        from agent.executive_advisory import get_executive_advisory

        company_context = None
        if body.company_id:
            from agent.agency import _company_advisory_context

            company_context = await _company_advisory_context(body.company_id)
        try:
            result = await get_executive_advisory().advise(
                body.question,
                company_context=company_context,
                roles=body.roles,
                ground=body.ground,
                remember=body.remember,
            )
        except Exception:  # noqa: BLE001 — never leak internals (rule 27)
            log.exception("executive consult failed")
            raise HTTPException(status_code=502, detail="Advisory failed")
        return AdvisoryResponse(**result.as_dict())

    return router
