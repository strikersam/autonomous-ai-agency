"""Tests for the dashboard platform-controls surface.

Covers the three things that would make this feature a liability rather than a
convenience:

1. The catalogue must describe reality — every control's key must be an
   environment variable some code actually reads, or the dashboard is lying
   about what its switches do.
2. The override endpoint must be an allow-list, not a general ``os.environ``
   write primitive. A secret must be unreachable through it.
3. Applying an override must not have side effects beyond the keys it touched —
   in particular it must not re-mint the JWT secret (which would sign every
   user out) or rewrite runtime routing policy the manager set for itself.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from packages.config import control_overrides
from packages.config.control_registry import (
    GROUPS,
    KIND_CHOICE,
    KIND_NUMBER,
    KIND_TOGGLE,
    all_controls,
    coerce,
    controls_by_group,
    get_control,
    is_controllable,
)

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "node_modules", "graphify-out", ".venv", "venv", "__pycache__", "tests"}


def _python_sources() -> str:
    """Every non-test Python file in the repo, concatenated."""
    chunks: list[str] = []
    for path in ROOT.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(chunks)


# ── 1. The catalogue describes reality ────────────────────────────────────────


def test_every_control_key_is_read_somewhere_in_the_source():
    """A control for a variable nothing reads would be a dead switch in the UI."""
    blob = _python_sources()
    orphans = [c.key for c in all_controls() if f'"{c.key}"' not in blob and f"'{c.key}'" not in blob]
    assert orphans == [], f"controls with no reader in the source: {orphans}"


def test_control_keys_are_unique():
    keys = [c.key for c in all_controls()]
    assert len(keys) == len(set(keys))


def test_every_control_belongs_to_a_declared_group():
    group_ids = {g.id for g in GROUPS}
    assert {c.group for c in all_controls()} <= group_ids


def test_every_group_is_non_empty_and_rendered():
    rendered = controls_by_group()
    assert rendered, "the dashboard would render an empty page"
    assert all(g["controls"] for g in rendered)


def test_choice_controls_declare_their_default_as_an_option():
    """Otherwise the dashboard select would render with nothing selected."""
    for control in all_controls():
        if control.kind != KIND_CHOICE:
            continue
        values = {o.value for o in control.options}
        assert control.default in values, f"{control.key} default {control.default!r} not in {values}"


def test_toggle_defaults_are_boolean_strings():
    for control in all_controls():
        if control.kind == KIND_TOGGLE:
            assert control.default in ("true", "false"), control.key


def test_number_defaults_parse_and_sit_inside_their_bounds():
    for control in all_controls():
        if control.kind != KIND_NUMBER:
            continue
        value = int(control.default)
        if control.minimum is not None:
            assert value >= control.minimum, control.key
        if control.maximum is not None:
            assert value <= control.maximum, control.key


def test_no_secret_is_exposed_as_a_control():
    """Secrets stay environment-only per the repository constitution."""
    banned = ("_API_KEY", "_TOKEN", "_SECRET", "PASSWORD", "_KEY_ID")
    leaked = [c.key for c in all_controls() if any(c.key.endswith(b) or b in c.key for b in banned)]
    assert leaked == [], f"secret-shaped keys in the control catalogue: {leaked}"


# ── 2. Validation is an allow-list ────────────────────────────────────────────


def test_unknown_key_is_rejected():
    assert not is_controllable("ANTHROPIC_API_KEY")
    with pytest.raises(ValueError):
        coerce("ANTHROPIC_API_KEY", "sk-leak")


def test_toggle_coercion_normalises_truthy_and_falsey_forms():
    assert coerce("GOVERNANCE_ENABLED", True) == "true"
    assert coerce("GOVERNANCE_ENABLED", "on") == "true"
    assert coerce("GOVERNANCE_ENABLED", "1") == "true"
    assert coerce("GOVERNANCE_ENABLED", False) == "false"
    assert coerce("GOVERNANCE_ENABLED", "off") == "false"
    with pytest.raises(ValueError):
        coerce("GOVERNANCE_ENABLED", "maybe")


def test_choice_coercion_rejects_values_outside_the_option_list():
    assert coerce("BRAIN_PREFERENCE", "ollama") == "ollama"
    with pytest.raises(ValueError):
        coerce("BRAIN_PREFERENCE", "openai")


def test_number_coercion_enforces_declared_bounds():
    assert coerce("AGENT_MAX_STEPS", "12") == "12"
    with pytest.raises(ValueError):
        coerce("AGENT_MAX_STEPS", "0")
    with pytest.raises(ValueError):
        coerce("AGENT_MAX_STEPS", "not-a-number")


def test_runtime_choices_cover_every_registered_adapter_id():
    """A runtime an operator cannot pick from the dropdown is unreachable."""
    spec = get_control("RUNTIME_DEFAULT")
    values = {o.value for o in spec.options}
    assert {"internal_agent", "hermes", "e2b", "docker_agent"} <= values


# ── 3. Applying overrides has no side effects beyond the keys touched ─────────


@pytest.fixture
def clean_overrides():
    """Restore the process environment and the module's applied set."""
    watched = [c.key for c in all_controls()]
    before = {k: os.environ.get(k) for k in watched}
    applied_before = dict(control_overrides._applied)
    yield
    control_overrides._applied.clear()
    control_overrides._applied.update(applied_before)
    for key, value in before.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_apply_overrides_writes_only_catalogued_keys(clean_overrides):
    changed = control_overrides.apply_overrides(
        {"GOVERNANCE_ENABLED": "false", "ANTHROPIC_API_KEY": "sk-leak"}
    )
    assert "GOVERNANCE_ENABLED" in changed
    assert os.environ["GOVERNANCE_ENABLED"] == "false"
    assert "ANTHROPIC_API_KEY" not in changed
    assert os.environ.get("ANTHROPIC_API_KEY") != "sk-leak"


def test_clearing_an_override_restores_the_startup_environment(clean_overrides):
    key = "GOVERNANCE_ENABLED"
    baseline = control_overrides._BASE_ENV.get(key)

    control_overrides.apply_overrides({key: "false"})
    assert os.environ[key] == "false"

    control_overrides.apply_overrides({})
    assert os.environ.get(key) == baseline


def test_apply_overrides_refreshes_the_settings_singleton(clean_overrides):
    from packages.config import settings

    control_overrides.apply_overrides({"GOVERNANCE_ENABLED": "false"})
    assert settings.governance_enabled is False

    control_overrides.apply_overrides({"GOVERNANCE_ENABLED": "true"})
    assert settings.governance_enabled is True


def test_settings_refresh_preserves_a_generated_jwt_secret(clean_overrides, monkeypatch):
    """Re-running Settings.__init__ mints a new random secret when SECRET_KEY is
    unset. Carrying the old one across is what stops an unrelated toggle save
    from invalidating every session."""
    from packages.config import settings

    monkeypatch.delenv("SECRET_KEY", raising=False)
    original = settings.jwt_secret
    assert original

    control_overrides.apply_overrides({"GOVERNANCE_ENABLED": "false"})
    assert settings.jwt_secret == original


def test_effective_value_follows_override_then_env_then_default(clean_overrides):
    spec = get_control("GOVERNANCE_ENABLED")

    assert control_overrides.effective_value(spec, {"GOVERNANCE_ENABLED": "false"}) == "false"
    assert control_overrides.value_source(spec, {"GOVERNANCE_ENABLED": "false"}) == "override"

    base = control_overrides._BASE_ENV.get(spec.key)
    expected = spec.default if base is None else base
    assert control_overrides.effective_value(spec, {}) == expected
    assert control_overrides.value_source(spec, {}) == ("default" if base is None else "environment")


def test_policy_updates_only_carry_the_keys_that_changed(clean_overrides):
    """A blanket policy rewrite would clobber the manager's own E2B promotion."""
    current = {
        "preferred_runtime_id": "e2b",
        "task_type_runtime_overrides": {"code_generation": "e2b"},
    }
    os.environ["RUNTIME_NEVER_PAID"] = "true"

    updates = control_overrides._policy_updates(["RUNTIME_NEVER_PAID"], current)

    assert updates == {"never_use_paid_providers": True}
    assert "preferred_runtime_id" not in updates
    assert "task_type_runtime_overrides" not in updates


def test_policy_updates_merge_task_type_overrides(clean_overrides):
    current = {"task_type_runtime_overrides": {"code_generation": "e2b"}}
    os.environ["RUNTIME_CODE_REVIEW"] = "hermes"

    updates = control_overrides._policy_updates(["RUNTIME_CODE_REVIEW"], current)

    assert updates["task_type_runtime_overrides"] == {
        "code_generation": "e2b",
        "code_review": "hermes",
    }


def test_clearing_a_task_type_route_drops_it_from_the_policy(clean_overrides):
    current = {"task_type_runtime_overrides": {"code_review": "hermes"}}
    os.environ.pop("RUNTIME_CODE_REVIEW", None)

    updates = control_overrides._policy_updates(["RUNTIME_CODE_REVIEW"], current)

    assert updates["task_type_runtime_overrides"] == {}


def test_restart_required_lists_only_non_live_controls():
    required = control_overrides._restart_required(
        ["GOVERNANCE_ENABLED", "AGENCY_CEO_ENABLED", "NOT_A_CONTROL"]
    )
    # GOVERNANCE_ENABLED is read through the settings singleton (live);
    # AGENCY_CEO_ENABLED is consumed when background services start (not live).
    assert required == {"AGENCY_CEO_ENABLED"}


# ── 4. The HTTP surface ───────────────────────────────────────────────────────
#
# Exercised against a standalone app rather than the full backend so the tests
# stay hermetic: the router only needs an auth dependency and a settings store,
# and both are supplied here.


@pytest.fixture
def controls_app(monkeypatch, clean_overrides):
    """A minimal app mounting the controls router over an in-memory store."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.platform_controls_router import build_platform_controls_router

    stored: dict[str, str] = {}

    async def fake_load() -> dict[str, str]:
        return dict(stored)

    async def fake_save(overrides, actor="admin"):
        stored.clear()
        stored.update(overrides)

    monkeypatch.setattr(control_overrides, "load_overrides", fake_load)
    monkeypatch.setattr(control_overrides, "save_overrides", fake_save)

    role = {"value": "admin"}

    async def fake_user():
        return {"email": "ops@example.com", "role": role["value"]}

    app = FastAPI()
    app.include_router(build_platform_controls_router(fake_user))
    with TestClient(app) as test_client:
        yield test_client, role, stored


def test_get_returns_the_grouped_catalogue_with_values(controls_app):
    test_client, _role, _stored = controls_app

    response = test_client.get("/api/admin/platform-controls")

    assert response.status_code == 200
    body = response.json()
    assert body["control_count"] == len(all_controls())
    assert body["groups"], "no groups rendered"
    first = body["groups"][0]["controls"][0]
    assert {"key", "label", "kind", "value", "source", "live"} <= set(first)


def test_non_admin_is_refused(controls_app):
    test_client, role, _stored = controls_app
    role["value"] = "user"

    assert test_client.get("/api/admin/platform-controls").status_code == 403
    assert (
        test_client.put(
            "/api/admin/platform-controls", json={"updates": {"GOVERNANCE_ENABLED": False}}
        ).status_code
        == 403
    )


def test_put_persists_applies_and_reports_the_change(controls_app):
    test_client, _role, stored = controls_app

    response = test_client.put(
        "/api/admin/platform-controls",
        json={"updates": {"GOVERNANCE_ENABLED": False, "AGENT_MAX_STEPS": 15}},
    )

    assert response.status_code == 200
    body = response.json()
    assert stored["GOVERNANCE_ENABLED"] == "false"
    assert stored["AGENT_MAX_STEPS"] == "15"
    assert os.environ["GOVERNANCE_ENABLED"] == "false"
    assert "GOVERNANCE_ENABLED" in body["changed"]
    # The response carries a fresh snapshot so the UI re-renders from the truth.
    assert body["groups"]


def test_put_rejects_the_whole_batch_when_one_field_is_invalid(controls_app):
    test_client, _role, stored = controls_app

    response = test_client.put(
        "/api/admin/platform-controls",
        json={"updates": {"GOVERNANCE_ENABLED": False, "BRAIN_PREFERENCE": "openai"}},
    )

    assert response.status_code == 400
    assert stored == {}, "a rejected batch must not half-apply"


def test_put_refuses_a_key_outside_the_catalogue(controls_app):
    test_client, _role, stored = controls_app

    response = test_client.put(
        "/api/admin/platform-controls", json={"updates": {"ANTHROPIC_API_KEY": "sk-leak"}}
    )

    assert response.status_code == 400
    assert stored == {}


def test_put_with_no_updates_is_a_bad_request(controls_app):
    test_client, _role, _stored = controls_app
    assert test_client.put("/api/admin/platform-controls", json={"updates": {}}).status_code == 400


def test_delete_reverts_a_control_to_the_environment(controls_app):
    test_client, _role, stored = controls_app
    test_client.put(
        "/api/admin/platform-controls", json={"updates": {"GOVERNANCE_ENABLED": False}}
    )
    assert stored["GOVERNANCE_ENABLED"] == "false"

    response = test_client.delete("/api/admin/platform-controls/GOVERNANCE_ENABLED")

    assert response.status_code == 200
    assert "GOVERNANCE_ENABLED" not in stored
    assert os.environ.get("GOVERNANCE_ENABLED") == control_overrides._BASE_ENV.get(
        "GOVERNANCE_ENABLED"
    )


def test_delete_of_an_unknown_key_is_a_404(controls_app):
    test_client, _role, _stored = controls_app
    assert test_client.delete("/api/admin/platform-controls/ANTHROPIC_API_KEY").status_code == 404
