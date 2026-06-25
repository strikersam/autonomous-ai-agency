"""backend/admin_update_task_router.py

Step 1: POST ``/api/workflow/orchestrator/update-task/{run_id}``

Thin admin HTTP surface over ``services.workflow_orchestrator.update_task`` so
that the Telegram ``/redirect`` command can be invoked server-side as well.
Same auth shape as ``backend/admin_digest_router.py``: bearer token from
``ADMIN_SECRET`` (via ``X-Admin-Secret`` header OR ``Authorization: Bearer``).

Wire it up via ``register(app)`` next to the existing
``_register_admin_digest_router(app)`` call.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

log = logging.getLogger("qwen-proxy")


class UpdateTaskRequest(BaseModel):
    """Body for ``POST /api/workflow/orchestrator/update-task/{run_id}``.

    ``extra=\"forbid\"`` because ``ExecutionRequest.metadata`` is a free-form
    dict, and a future round-trip through this endpoint must NEVER silently
    inject extra keys (would clash with ``extra=\"forbid\"`` on the inner
    Pydantic model at the orchestrator). Two explicit fields cover the
    documented use cases; need more → add explicit fields, never relax
    ``extra=\"forbid\"``.
    """

    model_config = ConfigDict(extra="forbid")

    additional_instructions: str = Field(
        ..., min_length=1, max_length=8000,
        description="Operator-scoped instruction injected into the run's metadata.",
    )
    operator: Optional[str] = Field(
        default=None, max_length=128,
        description="Tag stored in metadata.updated_by (defaults to 'admin').",
    )


def _expected_admin_secret() -> str:
    """Resolve the admin secret from env.

    Order matches admin_digest_router.py: ADMIN_SECRET first, then the legacy
    PROXY_ADMIN_SECRET, then the cookie-style fallback. The handlers accept
    BOTH ``X-Admin-Secret`` and ``Authorization: Bearer`` so misconfiguring one
    doesn't lock the operator out.
    """
    return (
        os.environ.get("ADMIN_SECRET")
        or os.environ.get("PROXY_ADMIN_SECRET")
        or os.environ.get("TELEGRAM_PROXY_API_KEY")
        or ""
    ).strip()


def _verify_admin_secret(provided: str) -> bool:
    expected = _expected_admin_secret()
    if not expected or not provided:
        return False
    # Constant-time compare to avoid timing oracles.
    try:
        return hmac.compare_digest(provided, expected)
    except Exception:  # pragma: no cover - defensive
        return False


def _extract_admin_token(
    x_admin_secret: Optional[str],
    authorization: Optional[str],
) -> Optional[str]:
    if x_admin_secret:
        return x_admin_secret.strip()
    if authorization:
        a = authorization.strip()
        if a.lower().startswith("bearer "):
            return a[7:].strip()
        return a
    return None


async def update_workflow_task(
    run_id: str,
    body: UpdateTaskRequest,
    x_admin_secret: Optional[str] = Header(None, alias="X-Admin-Secret"),
    authorization: Optional[str] = Header(None),
):
    """Inject ``additional_instructions`` into a paused or running WorkflowRun.

    Proxies to ``services.workflow_orchestrator.update_task``. Surfaces the
    orchestrator's discriminated errors (``KeyError`` -> 404, ``ValueError``
    -> 409) so the calling Telegram bot can show the operator a clean
    inline-keyboard prompt without parsing the message_id.
    """
    provided = _extract_admin_token(x_admin_secret, authorization)
    if not _verify_admin_secret(provided or ""):
        raise HTTPException(status_code=401, detail="invalid or missing admin secret")

    try:
        from services.workflow_orchestrator import get_workflow_orchestrator
        orchestrator = get_workflow_orchestrator()
    except Exception as exc:
        log.warning("admin_update_task.router.orchestrator_unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=f"WorkflowOrchestrator unavailable: {exc}",
        )

    try:
        run = await orchestrator.update_task(
            run_id,
            additional_instructions=body.additional_instructions,
            operator=body.operator or "admin",
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        log.exception("admin_update_task.update_task_failed run=%s exc=%s", run_id, exc)
        raise HTTPException(status_code=500, detail=f"update_task failed: {exc}")

    meta = dict(run._request.metadata or {}) if run._request is not None else {}
    return {
        "run_id": run_id,
        "status": run.status,
        "current_phase": run.current_phase,
        "updated_by": meta.get("updated_by"),
        "updated_at_utc": meta.get("updated_at_utc"),
        "additional_instructions_length": len(meta.get("additional_instructions", "") or ""),
    }


def register(app) -> None:
    """Mount the update-task endpoint on ``app``.

    Idempotent: skips if a path with the same prefix is already registered
    (defensive against double-load via the in-web lifespan lifecycle).
    """
    target_paths = {"/api/workflow/orchestrator/update-task", "/api/workflow/orchestrator/update-task/"}
    existing_paths = set(getattr(app, "routes_paths_cache", set()) or set())
    if any(p in existing_paths for p in target_paths):
        log.info("admin_update_task_router.register: already mounted, skipping")
        return

    router = APIRouter(prefix="/api/workflow/orchestrator", tags=["workflow-orchestrator"])
    router.add_api_route(
        "/update-task/{run_id}",
        update_workflow_task,
        methods=["POST"],
        response_model=None,
    )
    app.include_router(router)
    log.info("admin_update_task_router.register: mounted POST /api/workflow/orchestrator/update-task/{run_id}")
