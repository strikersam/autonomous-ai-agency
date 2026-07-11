"""tests/test_brain_config_api.py — admin endpoint contract tests.

Pins the contract from docs/plans/db-brain-switcher.md §3c + §4:

  * GET /admin/api/policy/brain requires auth (401 unauthenticated).
  * GET /admin/api/policy/brain requires admin role (403 non-admin).
  * GET response shape: {config: BrainConfig, providers: [...], safe_default}.
  * PATCH rejects a dead model (probe returns 410) with 422 + a probe report.
  * PATCH accepts a live model and persists.
  * POST /admin/api/policy/brain/test probes without saving.
  * Keys are never leaked in any response (only ``key_present`` flags).

All provider probes are mocked — no live network in CI. Tests use the
TestClient against ``backend.server.app`` and patch the auth dependency
plus the liveness prober.

The ``app_client``, ``non_admin_client``, and ``unauth_client`` fixtures
are defined in ``tests/conftest.py`` so they can be shared with other
brain-config-related test modules (e.g. test_unit5_ui_provider_surface.py).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from services.brain_liveness import ProbeResult


# ── Auth gating ─────────────────────────────────────────────────────────────


def test_get_requires_auth(unauth_client):
    r = unauth_client.get("/admin/api/policy/brain")
    assert r.status_code == 401


def test_get_requires_admin_role(non_admin_client):
    r = non_admin_client.get("/admin/api/policy/brain")
    assert r.status_code == 403


def test_patch_requires_admin_role(non_admin_client):
    r = non_admin_client.patch(
        "/admin/api/policy/brain",
        json={"executor_model": "qwen3-coder:30b"},
    )
    assert r.status_code == 403


def test_test_requires_admin_role(non_admin_client):
    r = non_admin_client.post(
        "/admin/api/policy/brain/test",
        json={"provider": "nvidia", "model": "meta/llama-3.3-70b-instruct"},
    )
    assert r.status_code == 403


# ── GET response shape ──────────────────────────────────────────────────────


def test_get_returns_config_providers_and_safe_default(app_client, monkeypatch):
    """GET response must include the BrainConfig, the provider list, and the safe default."""
    # Make sure provider keys are deterministic for the assertion.
    monkeypatch.setenv("CEREBRAS_API_KEY", "fake-cb")
    monkeypatch.setenv("GROQ_API_KEY", "fake-groq")
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")

    r = app_client.get("/admin/api/policy/brain")
    assert r.status_code == 200
    body = r.json()

    assert "config" in body
    # No saved doc + a Cerebras key present → the recommended free-cloud chain
    # auto-selects Cerebras (Cerebras → Groq → NVIDIA priority). The safe NIM
    # default remains the floor, surfaced separately in `safe_default` below.
    assert body["config"]["primary_provider"] == "cerebras"
    assert body["config"]["planner_model"] == "qwen-3-coder-480b"

    assert "providers" in body
    provider_ids = {p["provider_id"] for p in body["providers"]}
    # UNIT 5: the GET endpoint now returns ALL 14 providers from the
    # BrainProvider Literal (server-driven UI), not just the original 4.
    # The 14 ids must match the catalog (config/models.yaml).
    assert provider_ids == {
        "nvidia", "cerebras", "groq", "ollama", "mistral",
        "deepseek", "zhipu", "zai", "together", "dashscope",
        "moonshot", "openrouter", "anthropic", "aerolink",
    }
    assert len(provider_ids) == 14

    # Each provider entry has key_present + key_env_var + display_name +
    # tier + candidates, but never the key.
    for p in body["providers"]:
        assert "key_present" in p
        assert "key_env_var" in p
        assert "display_name" in p
        assert "tier" in p
        assert p["tier"] in ("free", "paid", "local", "unknown")
        assert "candidates" in p
        assert "api_key" not in p
        assert "key" not in p

    # cerebras/groq/nvidia should be key_present=True (we set the env vars).
    cb = next(p for p in body["providers"] if p["provider_id"] == "cerebras")
    assert cb["key_present"] is True
    assert cb["display_name"] == "Cerebras (fast, free tier)"
    assert cb["tier"] == "free"
    assert cb["candidates"][0] == "qwen-3-coder-480b"
    # ollama is always key_present=True (local).
    ol = next(p for p in body["providers"] if p["provider_id"] == "ollama")
    assert ol["key_present"] is True
    assert ol["tier"] == "local"
    # A paid provider is included (was previously filtered out).
    al = next(p for p in body["providers"] if p["provider_id"] == "aerolink")
    assert al["tier"] == "paid"

    assert body["safe_default"]["model"] == "z-ai/glm-5.2"


def test_get_response_never_leaks_api_keys(app_client):
    """Reiterates the security contract: no key value ever appears in the response."""
    import os
    os.environ["NVIDIA_API_KEY"] = "super-secret-nvapi-key"
    try:
        r = app_client.get("/admin/api/policy/brain")
        body_text = r.text
        assert "super-secret-nvapi-key" not in body_text
    finally:
        del os.environ["NVIDIA_API_KEY"]


# ── PATCH: dead-model rejection ─────────────────────────────────────────────


def test_patch_rejects_dead_model_with_422(app_client, monkeypatch):
    """A model that 410s must be rejected with 422 + a probe report."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")

    async def fake_probe(provider, model, **kw):
        return ProbeResult(
            provider=provider, model=model, live=False,
            status_code=410,
            reason="HTTP 410 Gone — model retired or removed",
            elapsed_ms=42,
        )

    with patch("backend.server.probe_model_liveness", fake_probe):
        r = app_client.patch(
            "/admin/api/policy/brain",
            json={"executor_model": "meta/llama-3.3-70b-instruct"},
        )

    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["message"].startswith("Refusing to persist a dead model")
    assert len(detail["failures"]) == 1
    assert detail["failures"][0]["role"] == "executor"
    assert detail["failures"][0]["status_code"] == 410
    assert "probe_report" in detail


def test_patch_accepts_live_model_and_persists(app_client, monkeypatch):
    """A model that probes 200 OK must be persisted."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")

    async def fake_probe(provider, model, **kw):
        return ProbeResult(
            provider=provider, model=model, live=True,
            status_code=200, reason="OK — provider responded with a valid chat completion",
            elapsed_ms=120,
        )

    with patch("backend.server.probe_model_liveness", fake_probe):
        r = app_client.patch(
            "/admin/api/policy/brain",
            json={
                "primary_provider": "nvidia",
                "planner_model":  "meta/llama-3.3-70b-instruct",
                "executor_model": "meta/llama-3.3-70b-instruct",
                "verifier_model": "meta/llama-3.3-70b-instruct",
                "judge_model":    "meta/llama-3.3-70b-instruct",
            },
        )

    assert r.status_code == 200
    body = r.json()
    assert body["config"]["primary_provider"] == "nvidia"
    assert body["config"]["planner_model"] == "meta/llama-3.3-70b-instruct"
    assert body["config"]["updated_by"] == "admin@example.com"
    assert body["config"]["updated_at"]  # ISO timestamp set
    assert len(body["probe_report"]) == 4
    assert all(p["live"] for p in body["probe_report"])

    # Follow-up GET must reflect the persisted config.
    r2 = app_client.get("/admin/api/policy/brain")
    assert r2.status_code == 200
    assert r2.json()["config"]["updated_by"] == "admin@example.com"


def test_patch_rejects_when_provider_key_missing(app_client, monkeypatch):
    """If the chosen provider's key is missing, the probe short-circuits → 422."""
    monkeypatch.delenv("CEREBRAS_API_KEY", raising=False)

    async def fake_probe(provider, model, **kw):
        # The real prober returns this when the key is missing — we mock the
        # same shape so the test exercises the API layer, not the prober.
        return ProbeResult(
            provider=provider, model=model, live=False,
            reason="Provider API key not configured (set CEREBRAS_API_KEY)",
        )

    with patch("backend.server.probe_model_liveness", fake_probe):
        r = app_client.patch(
            "/admin/api/policy/brain",
            json={"primary_provider": "cerebras", "executor_model": "qwen-3-coder-480b"},
        )

    assert r.status_code == 422


def test_patch_only_probes_changed_fields(app_client, monkeypatch):
    """A partial PATCH only probes the changed role — not every role."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")

    probed: list[tuple[str, str]] = []

    async def fake_probe(provider, model, **kw):
        probed.append((provider, model))
        return ProbeResult(provider=provider, model=model, live=True, status_code=200, reason="OK")

    with patch("backend.server.probe_model_liveness", fake_probe):
        r = app_client.patch(
            "/admin/api/policy/brain",
            json={"executor_model": "nvidia/some-other-model"},
        )

    assert r.status_code == 200
    # Only executor was patched → only one probe.
    assert len(probed) == 1
    assert probed[0][1] == "nvidia/some-other-model"


# ── POST /test ──────────────────────────────────────────────────────────────


def test_test_endpoint_probes_without_persisting(app_client, monkeypatch):
    """POST /admin/api/policy/brain/test fires a probe but does NOT save."""
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-nv")

    async def fake_probe(provider, model, **kw):
        return ProbeResult(
            provider=provider, model=model, live=True,
            status_code=200, reason="OK", elapsed_ms=88,
        )

    with patch("backend.server.probe_model_liveness", fake_probe):
        r = app_client.post(
            "/admin/api/policy/brain/test",
            json={"provider": "nvidia", "model": "meta/llama-3.3-70b-instruct"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["live"] is True
    assert body["status_code"] == 200
    assert body["elapsed_ms"] == 88

    # Confirm the config was NOT changed.
    r2 = app_client.get("/admin/api/policy/brain")
    assert r2.json()["config"]["updated_at"] == ""  # still the boot default


# ── Validation ──────────────────────────────────────────────────────────────


def test_patch_rejects_invalid_provider(app_client):
    """Pydantic Literal rejects an unknown provider before any probe fires."""
    r = app_client.patch(
        "/admin/api/policy/brain",
        json={"primary_provider": "not-a-real-provider"},  # not in the BrainProvider Literal
    )
    assert r.status_code == 422
    # Pydantic validation error, not our probe-failure 422.
    detail = r.json()["detail"]
    # Pydantic returns a list of validation errors.
    assert isinstance(detail, list)
    assert any("primary_provider" in str(e.get("loc", [])) for e in detail)


def test_patch_rejects_empty_model_string(app_client):
    """Empty model strings are rejected by Pydantic min_length=1."""
    r = app_client.patch(
        "/admin/api/policy/brain",
        json={"executor_model": ""},
    )
    assert r.status_code == 422
