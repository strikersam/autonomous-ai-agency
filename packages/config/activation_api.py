"""activation_api.py — FastAPI routes for instance activation & per-user onboarding control.

Routes:
  GET  /api/activation/status          → public (pre-auth): instance activation state + instanceId
  POST /api/activation/activate         → admin: submit activation token
  GET  /api/activation/users            → admin: list users with onboarding_allowed flag
  PUT  /api/activation/users/{user_id}/onboarding  → admin: toggle onboarding_allowed
  GET  /api/activation/audit-log        → admin: recent activation audit events
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from activation import (
    get_activation,
    instance_id,
    is_activated,
    invalidate_activation_cache,
    save_activation,
)
from packages.auth.rbac import require_admin, audit
from db import get_store

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
    """Return True if this user may run the onboarding wizard.

    Resolution order:
      1. If the admin set an explicit per-user record, honour it.
      2. Otherwise fall back to the global default: when the onboarding gate has
         been turned OFF by an admin (``onboarding_gate_enabled = False``), every
         user is allowed by default; when the gate is ON (the shipping default),
         users with no record are blocked until added to the allow-list.

    The global default is read from the in-process settings cache so this stays
    a cheap sync call (the DB remains the source of truth — see app_settings).

    **Fail-open on DB errors:** if the settings cache can't be read (e.g. motor
    event-loop binding failure on Render), we default to ALLOWING onboarding
    rather than blocking. This prevents a silent lockout for every social-login
    user when the DB is temporarily unreachable. The admin's explicit setting
    (gate OFF) takes precedence once the cache is warmed; the fail-open only
    applies during the brief window before the cache self-heals.
    """
    state = _load_onboarding_state()
    rec = state.get(user_id)
    if rec is not None and "onboarding_allowed" in rec:
        return bool(rec["onboarding_allowed"])
    try:
        from packages.config.app_settings import onboarding_gate_enabled_cached
        return not onboarding_gate_enabled_cached()
    except Exception:  # noqa: BLE001 — never block onboarding on a settings read failure
        # Fail OPEN (allow onboarding) instead of fail closed (block).
        # The admin explicitly set the gate to OFF, but the cache read failed
        # (e.g. motor event-loop binding on Render). Blocking every social-login
        # user during a DB outage is worse than temporarily allowing onboarding.
        # The cache self-heals via _maybe_schedule_refresh(), so the next read
        # will honour the admin's actual setting.
        log.warning("onboarding gate-default read failed; failing OPEN (allowing onboarding)")
        return True


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
        "If you own this instance you can activate it yourself — no email needed. "
        "Either set ACTIVATION_REQUIRED=false in the backend environment to disable the "
        "licensing gate, or run `python scripts/activate.py` to mint a signed code with "
        "your own key (set the printed ACTIVATION_PUBLIC_KEY_B64 in the backend env, then "
        "paste the code below). See docs/runbooks/activation.md. "
        "Otherwise, email your Instance ID to strikersam@gmail.com to request a code."
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
    if is_activated():
        act = get_activation()
        if act and act.valid:
            return ActivationStatusResponse(
                activated=True,
                instance_id=iid,
                email=act.email,
                issued_at=act.issued_at,
                expires_at=act.expires_at,
            )
        # Activated via ACTIVATION_REQUIRED=false — no signed token on disk.
        return ActivationStatusResponse(
            activated=True, instance_id=iid, email="activation-not-required"
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


# ── Global onboarding-gate settings (admin) ──────────────────────────────────

class OnboardingSettingsResponse(BaseModel):
    """Effective global onboarding/lifecycle settings."""
    onboarding_gate_enabled: bool = Field(
        description="When True, onboarding requires explicit per-user approval; "
        "when False, every logged-in user may onboard by default.",
    )
    ephemeral_company_ttl_hours: int = Field(
        ge=1,
        description="Hours an ephemeral (non-admin) company survives before the "
        "reaper destroys it.",
    )


class OnboardingSettingsUpdate(BaseModel):
    """Partial update for global onboarding/lifecycle settings."""
    onboarding_gate_enabled: bool | None = Field(
        default=None,
        description="New value for the global onboarding gate, or None to leave it.",
    )
    ephemeral_company_ttl_hours: int | None = Field(
        default=None,
        ge=1,
        description="New ephemeral-company TTL in hours (>= 1), or None to leave it.",
    )


@activation_router.get("/settings", response_model=OnboardingSettingsResponse)
async def get_onboarding_settings(request: Request) -> OnboardingSettingsResponse:
    """Read the global onboarding gate + ephemeral-company settings.

    The gate status (onboarding_gate_enabled) is PUBLIC — non-admin users need
    to read it to know if they can onboard. The ephemeral TTL is admin-only
    but doesn't leak sensitive info (it's just a number). No API keys, no
    user lists, no secrets — safe to expose to any authenticated user.
    """
    from packages.config.app_settings import all_settings, ONBOARDING_GATE_ENABLED_KEY, EPHEMERAL_TTL_HOURS_KEY
    s = await all_settings()
    return OnboardingSettingsResponse(
        onboarding_gate_enabled=bool(s[ONBOARDING_GATE_ENABLED_KEY]),
        ephemeral_company_ttl_hours=int(s[EPHEMERAL_TTL_HOURS_KEY]),
    )


@activation_router.put("/settings", response_model=OnboardingSettingsResponse)
async def update_onboarding_settings(
    body: OnboardingSettingsUpdate,
    request: Request,
) -> OnboardingSettingsResponse:
    """Admin: update the global onboarding gate default and/or ephemeral TTL.

    Turning ``onboarding_gate_enabled`` off lets every logged-in user run the
    setup wizard by default (no per-user allow-list entry required).
    """
    require_admin(request)
    from packages.config.app_settings import (
        set_setting, all_settings,
        ONBOARDING_GATE_ENABLED_KEY, EPHEMERAL_TTL_HOURS_KEY,
    )
    admin_id = getattr(request.state, "user_id", "admin")

    # ``ephemeral_company_ttl_hours`` is constrained ``>= 1`` on the Pydantic
    # model, so an invalid value is rejected with 422 before reaching here.

    if body.onboarding_gate_enabled is not None:
        await set_setting(ONBOARDING_GATE_ENABLED_KEY, body.onboarding_gate_enabled, admin_id)
    if body.ephemeral_company_ttl_hours is not None:
        await set_setting(EPHEMERAL_TTL_HOURS_KEY, int(body.ephemeral_company_ttl_hours), admin_id)

    # The audit append does synchronous file I/O (write + trim); keep it off the
    # event loop so admin traffic never blocks on disk.
    await asyncio.to_thread(_append_audit, {
        "event": "onboarding_settings_update",
        "onboarding_gate_enabled": body.onboarding_gate_enabled,
        "ephemeral_company_ttl_hours": body.ephemeral_company_ttl_hours,
        "by": admin_id,
    })
    audit(
        "update_onboarding_settings",
        getattr(request.state, "user", {"email": admin_id}),
        detail=f"gate_enabled={body.onboarding_gate_enabled} ttl_hours={body.ephemeral_company_ttl_hours}",
        request=request,
    )

    s = await all_settings()
    return OnboardingSettingsResponse(
        onboarding_gate_enabled=bool(s[ONBOARDING_GATE_ENABLED_KEY]),
        ephemeral_company_ttl_hours=int(s[EPHEMERAL_TTL_HOURS_KEY]),
    )


class _RoleUpdateBody(BaseModel):
    """Request body for changing a user's role."""
    role: str


class _RoleUpdateResponse(BaseModel):
    """Response for a successful role change."""
    user_id: str
    role: str
    updated: bool


@activation_router.post("/users/{user_id}/role")
async def change_user_role(
    user_id: str,
    body: _RoleUpdateBody,
    request: Request,
) -> _RoleUpdateResponse:
    """Change the role of a registered user (admin only).

    Allowed roles: ``user``, ``power_user``, ``admin``.
    """
    require_admin(request)
    admin_id = getattr(request.state, "user_id", "admin")

    allowed_roles = {"user", "power_user", "admin"}
    role = body.role.strip().lower()
    if role not in allowed_roles:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role {body.role!r}. Allowed: {sorted(allowed_roles)}",
        )

    db = get_store()
    try:
        from bson import ObjectId
        try:
            query = {"_id": ObjectId(user_id)}
        except Exception:
            query = {"email": user_id}
        result = await db.users.update_one(query, {"$set": {"role": role}})
    except Exception as exc:
        log.error("change_user_role DB error: %s", exc)
        raise HTTPException(status_code=503, detail="Database error") from exc

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")

    audit(
        "change_user_role",
        getattr(request.state, "user", {"email": admin_id}),
        resource=user_id,
        detail=f"role={role}",
        request=request,
    )
    return _RoleUpdateResponse(user_id=user_id, role=role, updated=True)

