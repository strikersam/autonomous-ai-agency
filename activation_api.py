"""activation_api.py — FastAPI routes for instance activation & per-user onboarding control.

Routes:
  GET  /api/activation/status          → public (pre-auth): instance activation state + instanceId
  POST /api/activation/activate         → admin: submit activation token
  GET  /api/activation/users            → admin: list users with onboarding_allowed flag
  PUT  /api/activation/users/{user_id}/onboarding  → admin: toggle onboarding_allowed
  GET  /api/activation/audit-log        → admin: recent activation audit events
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from activation import (
    get_activation,
    instance_id,
    is_activated,
    invalidate_activation_cache,
    save_activation,
)
from rbac import require_admin, audit

log = logging.getLogger("qwen-proxy")

activation_router = APIRouter(prefix="/api/activation", tags=["activation"])

# ── Persistent user-onboarding state (simple JSON file store) ─────────────────
_REPO_ROOT = Path(__file__).resolve().parent
_ONBOARDING_STATE_FILE = _REPO_ROOT / ".onboarding_state.json"
_AUDIT_LOG_FILE = _REPO_ROOT / ".activation_audit.jsonl"

_MAX_AUDIT_LINES = 500


def _load_onboarding_state() -> dict[str, dict[str, Any]]:
    if not _ONBOARDING_STATE_FILE.exists():
        return {}
    try:
        return json.loads(_ONBOARDING_STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_onboarding_state(state: dict[str, dict[str, Any]]) -> None:
    _ONBOARDING_STATE_FILE.write_text(json.dumps(state, indent=2))
    _ONBOARDING_STATE_FILE.chmod(0o600)


def _append_audit(event: dict[str, Any]) -> None:
    event.setdefault("ts", time.time())
    try:
        with _AUDIT_LOG_FILE.open("a") as f:
            f.write(json.dumps(event) + "\n")
        # Trim if too large
        lines = _AUDIT_LOG_FILE.read_text().splitlines()
        if len(lines) > _MAX_AUDIT_LINES:
            _AUDIT_LOG_FILE.write_text("\n".join(lines[-_MAX_AUDIT_LINES:]) + "\n")
    except OSError:
        pass


# ── Per-user onboarding flag helpers ─────────────────────────────────────────

def is_user_onboarding_allowed(user_id: str) -> bool:
    """Return True if the admin has enabled onboarding for this user."""
    state = _load_onboarding_state()
    return state.get(user_id, {}).get("onboarding_allowed", False)


def set_user_onboarding_allowed(user_id: str, allowed: bool, admin_id: str = "admin") -> None:
    state = _load_onboarding_state()
    if user_id not in state:
        state[user_id] = {}
    state[user_id]["onboarding_allowed"] = allowed
    state[user_id]["updated_at"] = time.time()
    state[user_id]["updated_by"] = admin_id
    _save_onboarding_state(state)
    _append_audit({
        "event": "onboarding_toggle",
        "user_id": user_id,
        "allowed": allowed,
        "by": admin_id,
    })


# ── Request / response models ────────────────────────────────────────────────

class ActivationStatusResponse(BaseModel):
    activated: bool
    instance_id: str
    email: str | None = None
    issued_at: float | None = None
    expires_at: float | None = None
    # Registration hint for non-activated instances
    register_email: str = "strikersam@gmail.com"
    register_instructions: str = (
        "Copy your Instance ID above and email it to strikersam@gmail.com with the subject "
        "'LLM Relay Activation Request'. You'll receive a signed activation code by reply. "
        "Paste it in the Activation panel to unlock onboarding."
    )


class ActivateRequest(BaseModel):
    token: str


class ActivateResponse(BaseModel):
    success: bool
    email: str | None = None
    error: str | None = None


class UserOnboardingRecord(BaseModel):
    user_id: str
    onboarding_allowed: bool
    updated_at: float | None = None
    updated_by: str | None = None


class ToggleOnboardingRequest(BaseModel):
    allowed: bool


class AuditLogEntry(BaseModel):
    ts: float
    event: str
    data: dict


# ── Routes ────────────────────────────────────────────────────────────────────

@activation_router.get("/status", response_model=ActivationStatusResponse)
async def activation_status() -> ActivationStatusResponse:
    """Public endpoint — returns instanceId and whether the instance is activated.
    Safe to call before login (needed to show the activation wizard).
    """
    iid = instance_id()
    act = get_activation()
    if act and act.valid:
        return ActivationStatusResponse(
            activated=True,
            instance_id=iid,
            email=act.email,
            issued_at=act.issued_at,
            expires_at=act.expires_at,
        )
    return ActivationStatusResponse(activated=False, instance_id=iid)


@activation_router.post("/activate", response_model=ActivateResponse)
async def activate_instance(body: ActivateRequest, request: Request) -> ActivateResponse:
    """Admin submits a signed activation token received from the repo owner."""
    # Require admin — but allow if instance is not yet activated (bootstrap scenario)
    # so the very first activation can proceed without being blocked by an auth guard
    # that itself depends on activation. After activation, only admin can re-activate.
    if is_activated():
        # Already activated — only admins may replace the activation
        try:
            require_admin(request)
        except HTTPException:
            raise HTTPException(status_code=403, detail="Only admins may re-activate an already-activated instance.")

    result = save_activation(body.token.strip())
    invalidate_activation_cache()

    actor = getattr(request.state, "user_id", "unknown")
    _append_audit({
        "event": "activation_attempt",
        "success": result.valid,
        "email": result.email,
        "error": result.error,
        "by": actor,
    })

    if result.valid:
        log.info("Instance activated for %s", result.email)
        return ActivateResponse(success=True, email=result.email)
    else:
        log.warning("Activation failed: %s", result.error)
        return ActivateResponse(success=False, error=result.error)


@activation_router.get("/users", response_model=list[UserOnboardingRecord])
async def list_users_onboarding(request: Request) -> list[UserOnboardingRecord]:
    """Admin: list all users with their onboarding_allowed status."""
    require_admin(request)
    state = _load_onboarding_state()
    return [
        UserOnboardingRecord(
            user_id=uid,
            onboarding_allowed=data.get("onboarding_allowed", False),
            updated_at=data.get("updated_at"),
            updated_by=data.get("updated_by"),
        )
        for uid, data in state.items()
    ]


@activation_router.put("/users/{user_id}/onboarding", response_model=UserOnboardingRecord)
async def toggle_user_onboarding(
    user_id: str,
    body: ToggleOnboardingRequest,
    request: Request,
) -> UserOnboardingRecord:
    """Admin: enable or disable onboarding for a specific user."""
    require_admin(request)
    if not is_activated():
        raise HTTPException(
            status_code=403,
            detail="Instance is not activated. Activate first, then manage user onboarding.",
        )
    admin_id = getattr(request.state, "user_id", "admin")
    set_user_onboarding_allowed(user_id, body.allowed, admin_id)
    state = _load_onboarding_state()
    data = state.get(user_id, {})
    log.info("Admin %s set onboarding_allowed=%s for user %s", admin_id, body.allowed, user_id)
    audit(
        "toggle_user_onboarding",
        getattr(request.state, "user", {"email": admin_id}),
        resource=user_id,
        detail=f"allowed={body.allowed}",
        request=request,
    )
    return UserOnboardingRecord(
        user_id=user_id,
        onboarding_allowed=body.allowed,
        updated_at=data.get("updated_at"),
        updated_by=data.get("updated_by"),
    )


@activation_router.get("/audit-log", response_model=list[dict])
async def activation_audit_log(request: Request, limit: int = 100) -> list[dict]:
    """Admin: recent activation events."""
    require_admin(request)
    if not _AUDIT_LOG_FILE.exists():
        return []
    lines = _AUDIT_LOG_FILE.read_text().splitlines()
    records = []
    for line in reversed(lines[-limit:]):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records
