from __future__ import annotations

"""backend/admin_digest_router.py — admin/service-only router.

Triggers the daily Telegram review digest. Authenticated via a
service-to-service header (X-Admin-Secret) shared with the GitHub
Actions cron `.github/workflows/daily-digest.yml`. Not user-facing.

Endpoints:
  POST /api/admin/digest/send     — build + dispatch to Telegram
  GET  /api/admin/digest/preview  — dry-run; returns the markdown body only

Auth: X-Admin-Secret header compared (constant-time) against the env var
DIGEST_SECRET (preferred) with ADMIN_SECRET as a fallback. If neither is
configured the endpoint refuses with 503 so we never accept a no-secret
default.

Self-registration:
  Importing this module is a no-op. Call `register(app)` (e.g. from
  backend/server.py near the SPA mount) to mount the router.
"""
import hmac
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/digest", tags=["admin-digest"])

# Lazy module-level import: kept inside a try/except so test environments
# without a working telegram_service (or missing httpx) can still exercise
# the auth + aggregator paths via patch.object(adm, "NotificationDispatcher").
try:
    from packages.notifications.service import NotificationDispatcher
except Exception as _exc:  # pragma: no cover - import path requires live tw
    log.warning("admin_digest.notification_dispatcher_import_failed exc=%s", _exc)
    NotificationDispatcher = None  # type: ignore[assignment]  # noqa: N806


def _expected_secret() -> str:
    return (
        os.environ.get("DIGEST_SECRET", "").strip()
        or os.environ.get("ADMIN_SECRET", "").strip()
    )


def _check_secret(provided: Optional[str]) -> bool:
    expected = _expected_secret()
    if not expected:
        log.warning("admin_digest.no_secret_configured")
        return False
    if not provided:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _build_payload_or_500():
    """Returns a DigestPayload (or raises HTTPException(503/500))."""
    try:
        from services.daily_digest import build_daily_digest
        from services.decisions_store import get_decisions_store
        from services.workflow_orchestrator import get_workflow_orchestrator
    except ImportError as exc:
        log.exception("admin_digest.import_failed exc=%s", exc)
        raise HTTPException(status_code=503, detail=f"digest dependencies not importable: {exc}")
    try:
        return build_daily_digest(
            decisions_store=get_decisions_store(),
            workflow_orchestrator=get_workflow_orchestrator,
            cutoff_utc=None,
        )
    except Exception as exc:
        log.exception("admin_digest.build_failed exc=%s", exc)
        raise HTTPException(status_code=500, detail=f"digest build failed: {exc}")


@router.post("/send")
async def send_daily_digest_endpoint(
    x_admin_secret: Optional[str] = Header(default=None, alias="X-Admin-Secret"),
    x_idempotency_key: Optional[str] = Header(default=None, alias="X-Idempotency-Key"),
) -> dict[str, Any]:
    """Build the digest payload and dispatch to Telegram.

    Returns a JSON envelope describing what was sent; idempotent on
    X-Idempotency-Key (today: logged, not enforced — accepted for future).
    """
    if not _check_secret(x_admin_secret):
        raise HTTPException(status_code=401, detail="digest authentication failed")

    payload = _build_payload_or_500()

    if NotificationDispatcher is None:
        raise HTTPException(status_code=503, detail="telegram dispatcher not available")
    try:
        dispatcher = NotificationDispatcher()
        await dispatcher.send_daily_digest(payload)
    except Exception as exc:
        log.exception("admin_digest.dispatch_failed exc=%s", exc)
        raise HTTPException(status_code=502, detail=f"telegram dispatch failed: {exc}")

    return {
        "ok": True,
        "cutoff_utc": payload.cutoff_utc,
        "generated_utc": payload.generated_utc,
        "counts": payload.summary.counts,
        "truncated_path": payload.truncated_path,
        "markdown_chars": len(payload.markdown_body),
        "idempotency_key": x_idempotency_key,
    }


@router.get("/preview")
async def preview_digest_endpoint(
    x_admin_secret: Optional[str] = Header(default=None, alias="X-Admin-Secret"),
) -> dict[str, Any]:
    """Dry-run: same auth, returns the would-be markdown body but does NOT
    dispatch to Telegram. Useful for the cron workflow's `dry_run` path."""
    if not _check_secret(x_admin_secret):
        raise HTTPException(status_code=401, detail="digest authentication failed")
    payload = _build_payload_or_500()
    return {
        "ok": True,
        "cutoff_utc": payload.cutoff_utc,
        "markdown_body": payload.markdown_body,
        "counts": payload.summary.counts,
        "truncated_path": payload.truncated_path,
    }


def register(app: Any) -> None:
    """Mount this router on a FastAPI app. Idempotent."""
    if app is None:
        return
    try:
        app.include_router(router)
        log.info("admin_digest_router.registered prefix=/api/admin/digest")
    except Exception as exc:  # pragma: no cover
        log.warning("admin_digest_router.register_failed exc=%s", exc)
