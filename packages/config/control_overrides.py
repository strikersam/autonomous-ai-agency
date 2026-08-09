"""packages/config/control_overrides.py — DB-persisted overrides for platform controls.

Why this exists
---------------
Roughly a hundred feature switches and multi-option settings were only
changeable by editing the Render environment and redeploying. This module lets
an operator make those choices from the dashboard instead: the chosen values are
persisted in the same store as users and companies, applied to the process
environment, and re-applied on every boot.

How it works
------------
The override layer sits *above* the environment, not beside it::

    DB override  →  Render environment  →  code default

Applying an override writes it into ``os.environ`` for the keys in
:mod:`packages.config.control_registry` and nothing else. That is deliberate:
several hundred call sites already read these variables, and rewriting them all
would be a far larger change than the one that was asked for, with far more ways
to alter production behaviour by accident. The allow-list is what makes writing
to the environment safe — a secret is not in the catalogue, so this path can
never set one.

After the environment is updated, two caches are refreshed so ``live`` controls
take effect without a restart:

* the ``settings`` singleton is re-initialised **in place** (every module holds
  the same object, so mutating it updates all of them at once);
* the runtime manager's routing policy is updated through its own
  ``update_policy`` API when a routing key changed.

Values that a module captured at import time cannot be refreshed this way. Those
controls declare ``live=False`` and the dashboard shows a restart badge rather
than claiming the change already landed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from packages.config.control_registry import (
    ControlSpec,
    all_controls,
    coerce,
    get_control,
    is_controllable,
)

log = logging.getLogger("agency-config")

# The single app_settings document holding every override, as {KEY: "value"}.
OVERRIDES_KEY = "platform_control_overrides"

# What the process environment looked like before any override was applied.
# Captured at import so `source` can still distinguish "the operator set this in
# the dashboard" from "Render set this" after overrides land in os.environ.
_BASE_ENV: dict[str, str | None] = {
    spec.key: os.environ.get(spec.key) for spec in all_controls()
}

# Last applied override set, so reads do not need to hit the DB.
_applied: dict[str, str] = {}

# Routing-policy keys that the runtime manager can absorb without a rebuild.
_POLICY_KEYS = frozenset(
    {
        "RUNTIME_DEFAULT",
        "RUNTIME_CODE_GENERATION",
        "RUNTIME_CODE_REVIEW",
        "RUNTIME_REPO_EDITING",
        "RUNTIME_GIT_OPS",
        "RUNTIME_NEVER_PAID",
        "RUNTIME_REQUIRE_APPROVAL",
        "RUNTIME_MAX_PAID_ESCALATIONS",
    }
)

_TASK_TYPE_KEYS = {
    "code_generation": "RUNTIME_CODE_GENERATION",
    "code_review": "RUNTIME_CODE_REVIEW",
    "repo_editing": "RUNTIME_REPO_EDITING",
    "git_operations": "RUNTIME_GIT_OPS",
}


# ── Persistence ───────────────────────────────────────────────────────────────


async def read_overrides() -> dict[str, str]:
    """Read the stored overrides, propagating a storage failure.

    Read-modify-write callers must use this rather than :func:`load_overrides`.
    A failed read that silently becomes ``{}`` would be saved back as ``{}``
    plus the one key being changed — erasing every other override the operator
    had set. A write that cannot first read the current state must not happen
    at all.
    """
    from app_settings import get_setting

    stored = await get_setting(OVERRIDES_KEY, {})
    if not isinstance(stored, dict):
        return {}
    return {k: str(v) for k, v in stored.items() if is_controllable(k)}


async def load_overrides() -> dict[str, str]:
    """Read the stored overrides. Returns ``{}`` on any storage failure.

    The fail-open read, for startup and for rendering the settings screen: a
    platform whose settings store is unreachable must still boot on its
    environment defaults. Never use this to build a value that will be written
    back — see :func:`read_overrides`.
    """
    try:
        return await read_overrides()
    except Exception:  # noqa: BLE001 — config must never break startup
        log.exception("control_overrides: failed to load overrides")
        return {}


async def save_overrides(overrides: dict[str, str], actor: str = "admin") -> None:
    """Persist the full override set."""
    from app_settings import set_setting

    await set_setting(OVERRIDES_KEY, dict(overrides), updated_by=actor)


# ── Application ───────────────────────────────────────────────────────────────


def apply_overrides(overrides: dict[str, str]) -> list[str]:
    """Write *overrides* into ``os.environ`` and refresh dependent caches.

    Keys that were previously overridden but are absent now are reverted to the
    value the environment had at process start, so clearing an override in the
    dashboard really does hand control back to Render.

    Returns the keys whose effective value changed.
    """
    changed: list[str] = []
    for key in set(overrides) | set(_applied):
        if not is_controllable(key):
            continue
        before = os.environ.get(key)
        after = overrides.get(key, _BASE_ENV.get(key))
        if before == after:
            continue
        if after is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = after
        changed.append(key)

    _applied.clear()
    _applied.update({k: v for k, v in overrides.items() if is_controllable(k)})

    if changed:
        _refresh_settings_singleton()
        policy_changes = [k for k in changed if k in _POLICY_KEYS]
        if policy_changes:
            _refresh_runtime_policy(policy_changes)
        log.info("control_overrides: applied %d change(s): %s", len(changed), sorted(changed))
    return changed


def _refresh_settings_singleton() -> None:
    """Re-read every ``settings`` attribute from the updated environment.

    Re-runs ``__init__`` on the existing instance rather than building a new
    one: modules import the object, not the module, so a rebind would leave
    them holding the stale instance.

    ``Settings.__init__`` mints a random ``jwt_secret`` when ``SECRET_KEY`` is
    unset, so the previous one is carried across the refresh. Without that, a
    deployment relying on the generated secret would sign every user out the
    moment an admin saved an unrelated toggle.
    """
    try:
        from packages.config import settings as settings_obj

        previous_secret = getattr(settings_obj, "jwt_secret", "")
        settings_obj.__init__()  # noqa: PLC2801 — deliberate in-place refresh
        if previous_secret and not os.environ.get("SECRET_KEY"):
            settings_obj.jwt_secret = previous_secret
    except Exception:  # noqa: BLE001 — a refresh failure must not break the write
        log.exception("control_overrides: settings refresh failed")


def _refresh_runtime_policy(changed: list[str]) -> None:
    """Push the *changed* routing keys into the live runtime manager.

    Only the keys that actually changed are pushed. A blanket rewrite would
    clobber policy the manager set for itself at build time — notably the
    automatic ``preferred_runtime_id = "e2b"`` promotion when a working E2B
    sandbox is present — turning an unrelated save into a routing change.

    Only touches the manager when one has already been built: constructing it
    here would register adapters and start health polling as a side effect of a
    settings save.
    """
    try:
        import runtimes.manager as runtime_manager

        manager = runtime_manager._runtime_manager  # noqa: SLF001 — no public accessor
        if manager is None:
            return
        updates = _policy_updates(changed, manager.get_policy())
        if updates:
            manager.update_policy(**updates)
    except Exception:  # noqa: BLE001 — never fail a save on this
        log.exception("control_overrides: runtime policy refresh failed")


def _policy_updates(changed: list[str], current: dict[str, Any]) -> dict[str, Any]:
    """Build the ``update_policy`` kwargs for exactly the *changed* keys."""
    updates: dict[str, Any] = {}
    if "RUNTIME_DEFAULT" in changed:
        updates["preferred_runtime_id"] = os.environ.get("RUNTIME_DEFAULT") or "internal_agent"
    if "RUNTIME_NEVER_PAID" in changed:
        updates["never_use_paid_providers"] = _truthy(os.environ.get("RUNTIME_NEVER_PAID"))
    if "RUNTIME_REQUIRE_APPROVAL" in changed:
        updates["require_approval_before_paid_escalation"] = _truthy(
            os.environ.get("RUNTIME_REQUIRE_APPROVAL")
        )
    if "RUNTIME_MAX_PAID_ESCALATIONS" in changed:
        updates["max_paid_escalations_per_day"] = _as_int(
            os.environ.get("RUNTIME_MAX_PAID_ESCALATIONS"), 0
        )

    task_overrides = dict(current.get("task_type_runtime_overrides") or {})
    touched = False
    for task_type, key in _TASK_TYPE_KEYS.items():
        if key not in changed:
            continue
        touched = True
        value = os.environ.get(key)
        if value:
            task_overrides[task_type] = value
        else:
            task_overrides.pop(task_type, None)
    if touched:
        updates["task_type_runtime_overrides"] = task_overrides
    return updates


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in ("1", "true", "yes", "on")


def _as_int(raw: str | None, default: int) -> int:
    try:
        return int((raw or "").strip())
    except (TypeError, ValueError):
        return default


async def apply_from_db() -> list[str]:
    """Load the stored overrides and apply them. Called once at startup."""
    return apply_overrides(await load_overrides())


# ── Mutation ──────────────────────────────────────────────────────────────────


async def set_overrides(updates: dict[str, Any], actor: str = "admin") -> dict[str, Any]:
    """Validate, persist, and apply *updates*.

    A value equal to the environment/code default is stored as an override
    anyway — an operator who deliberately pins a value should not have it move
    when the code default changes underneath them. Use :func:`clear_override` to
    hand a key back to the environment.

    Raises ``ValueError`` when any key or value is invalid; nothing is persisted
    in that case, so a bad field cannot half-apply a batch. A storage failure on
    the read propagates for the same reason — saving on top of an unread state
    would erase the operator's other overrides.

    The read-modify-write is not atomic: two admins saving different controls in
    the same instant can have the earlier write dropped. Left as-is deliberately
    — this is a single-operator admin screen, and the response returns the
    resulting state, so a lost write is visible rather than silent.
    """
    coerced = {key: coerce(key, value) for key, value in updates.items()}
    overrides = await read_overrides()
    overrides.update(coerced)
    await save_overrides(overrides, actor=actor)
    changed = apply_overrides(overrides)
    return {
        "changed": changed,
        "restart_required": sorted(_restart_required(changed)),
        "overrides": overrides,
    }


async def clear_override(key: str, actor: str = "admin") -> dict[str, Any]:
    """Drop the override for *key*, reverting it to the environment default."""
    if not is_controllable(key):
        raise ValueError(f"'{key}' is not an operator-controllable setting")
    overrides = await read_overrides()
    overrides.pop(key, None)
    await save_overrides(overrides, actor=actor)
    changed = apply_overrides(overrides)
    return {
        "changed": changed,
        "restart_required": sorted(_restart_required(changed)),
        "overrides": overrides,
    }


def _restart_required(changed: list[str]) -> set[str]:
    """Of *changed*, the keys whose readers only see the new value after a restart."""
    out = set()
    for key in changed:
        spec = get_control(key)
        if spec is not None and not spec.live:
            out.add(key)
    return out


# ── Read model ────────────────────────────────────────────────────────────────


def effective_value(spec: ControlSpec, overrides: dict[str, str]) -> str:
    """The value *spec* currently resolves to, following override → env → default."""
    if spec.key in overrides:
        return overrides[spec.key]
    base = _BASE_ENV.get(spec.key)
    return spec.default if base is None else base


def value_source(spec: ControlSpec, overrides: dict[str, str]) -> str:
    """Where the effective value came from: ``override``, ``environment``, or ``default``."""
    if spec.key in overrides:
        return "override"
    return "environment" if _BASE_ENV.get(spec.key) is not None else "default"


async def snapshot() -> dict[str, Any]:
    """The full dashboard read model: catalogue + effective state per control."""
    from packages.config.control_registry import GROUPS

    overrides = await load_overrides()
    groups: list[dict[str, Any]] = []
    for group in GROUPS:
        members = [c for c in all_controls() if c.group == group.id]
        if not members:
            continue
        groups.append(
            group.as_dict()
            | {"controls": [_control_state(spec, overrides) for spec in members]}
        )
    return {
        "groups": groups,
        "override_count": len(overrides),
        "control_count": len(all_controls()),
    }


def _control_state(spec: ControlSpec, overrides: dict[str, str]) -> dict[str, Any]:
    """One control's spec plus its current value, source, and dependency state."""
    base = _BASE_ENV.get(spec.key)
    return spec.as_dict() | {
        "value": effective_value(spec, overrides),
        "source": value_source(spec, overrides),
        "env_value": base,
        "override_value": overrides.get(spec.key),
        "missing_requirements": [r for r in spec.requires if not os.environ.get(r)],
    }
