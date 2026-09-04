"""tests/test_provider_render_env.py — UI → Render env write for provider keys.

Covers the provider→env mapping, the single-var REST helper, and the admin-only
``PUT /api/providers/{id}/render-env`` endpoint that pushes a provider's
key/base_url into the Render service environment (where the runtime brain reads
them). The Render HTTP call is always mocked — no live Render account required.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from packages.integrations import render_env
from packages.integrations.render_env import RenderEnvError, provider_env_names


# ── provider_env_names mapping ────────────────────────────────────────────────


def test_provider_env_names_known():
    assert provider_env_names("nvidia") == ("NVIDIA_API_KEY", "NVIDIA_BASE_URL")
    assert provider_env_names("groq") == ("GROQ_API_KEY", "GROQ_BASE_URL")


def test_provider_env_names_case_insensitive():
    assert provider_env_names("NVIDIA") == ("NVIDIA_API_KEY", "NVIDIA_BASE_URL")


def test_provider_env_names_unknown_is_none():
    assert provider_env_names("not-a-provider") is None


# ── update_service_env_var REST helper ────────────────────────────────────────


class _FakeResp:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeClient:
    """Minimal async-context httpx.AsyncClient stand-in."""
    def __init__(self, status_code: int, capture: dict) -> None:
        self._status = status_code
        self._capture = capture

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def put(self, url, json=None, headers=None):
        self._capture["url"] = url
        self._capture["json"] = json
        self._capture["headers"] = headers
        return _FakeResp(self._status)


@pytest.mark.asyncio
async def test_update_env_var_success(monkeypatch):
    capture: dict = {}
    monkeypatch.setattr(
        render_env.httpx, "AsyncClient", lambda *a, **k: _FakeClient(200, capture)
    )
    await render_env.update_service_env_var(
        "srv-1", "NVIDIA_API_KEY", "nvapi-secret", api_key="rnd_key"
    )
    assert capture["url"].endswith("/services/srv-1/env-vars/NVIDIA_API_KEY")
    assert capture["json"] == {"value": "nvapi-secret"}
    assert capture["headers"]["Authorization"] == "Bearer rnd_key"


@pytest.mark.asyncio
async def test_update_env_var_http_error_raises(monkeypatch):
    monkeypatch.setattr(
        render_env.httpx, "AsyncClient", lambda *a, **k: _FakeClient(422, {})
    )
    with pytest.raises(RenderEnvError):
        await render_env.update_service_env_var(
            "srv-1", "NVIDIA_API_KEY", "x", api_key="rnd_key"
        )


@pytest.mark.asyncio
async def test_update_env_var_unconfigured_raises():
    with pytest.raises(RenderEnvError):
        await render_env.update_service_env_var("", "K", "v", api_key="")


# ── endpoint: auth + gating ───────────────────────────────────────────────────


def test_endpoint_requires_admin(non_admin_client):
    r = non_admin_client.put("/api/providers/nvidia/render-env", json={"api_key": "x"})
    assert r.status_code == 403


def test_endpoint_requires_a_field(app_client):
    r = app_client.put("/api/providers/nvidia/render-env", json={})
    assert r.status_code == 422


def _enable_render(monkeypatch):
    from packages.config import settings
    monkeypatch.setattr(settings, "render_api_key", "rnd_key", raising=False)
    monkeypatch.setattr(settings, "render_service_ids", "srv-1", raising=False)
    monkeypatch.setattr(settings, "render_mcp_allow_writes", "true", raising=False)


def test_endpoint_blocked_when_writes_disabled(app_client, monkeypatch):
    from packages.config import settings
    monkeypatch.setattr(settings, "render_api_key", "rnd_key", raising=False)
    monkeypatch.setattr(settings, "render_service_ids", "srv-1", raising=False)
    monkeypatch.setattr(settings, "render_mcp_allow_writes", "false", raising=False)
    r = app_client.put("/api/providers/nvidia/render-env", json={"api_key": "x"})
    assert r.status_code == 403
    assert "RENDER_MCP_ALLOW_WRITES" in r.json()["detail"]


def test_endpoint_503_when_render_unconfigured(app_client, monkeypatch):
    from packages.config import settings
    monkeypatch.setattr(settings, "render_api_key", "", raising=False)
    monkeypatch.setattr(settings, "render_service_ids", "", raising=False)
    monkeypatch.setattr(settings, "render_mcp_allow_writes", "true", raising=False)
    r = app_client.put("/api/providers/nvidia/render-env", json={"api_key": "x"})
    assert r.status_code == 503


def test_endpoint_unknown_provider_404(app_client, monkeypatch):
    _enable_render(monkeypatch)
    r = app_client.put("/api/providers/not-a-provider/render-env", json={"api_key": "x"})
    assert r.status_code == 404


def test_endpoint_success_writes_key(app_client, monkeypatch):
    _enable_render(monkeypatch)
    mock_write = AsyncMock()
    with patch("packages.integrations.render_env.update_service_env_var", mock_write):
        r = app_client.put("/api/providers/nvidia/render-env", json={"api_key": "nvapi-xyz"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["updated"] == ["NVIDIA_API_KEY"]
    # The helper was called with the target env var + the submitted value.
    args, kwargs = mock_write.call_args
    assert args[0] == "srv-1"
    assert args[1] == "NVIDIA_API_KEY"
    assert args[2] == "nvapi-xyz"
