"""tests/test_brain_ollama_base_url.py

The Ollama base URL is UI-configurable and DB-persisted (Brain card), so a
local/tunnelled Ollama can be the brain without a Render env edit. These tests
pin:

  * resolve_ollama_base_url() precedence: saved DB value > env > localhost.
  * provider_base_url("ollama") routes through that resolver.
  * probe_model_liveness(base_url=...) overrides the resolved URL so the UI can
    Test a typed-but-unsaved tunnel before Apply.
  * BrainConfig / BrainConfigPatch carry ollama_base_url.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

import packages.ai.brain_config as store
from packages.ai.brain_config import (
    BrainConfig,
    BrainConfigPatch,
    BrainConfigStore,
    provider_base_url,
    resolve_ollama_base_url,
)
import services.brain_liveness as bl
from services.brain_liveness import probe_model_liveness


@pytest.fixture(autouse=True)
def _tmp_mirror(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "_store", None)
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "t.db"))
    for v in ("OLLAMA_BASE", "OLLAMA_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    yield


def test_resolve_prefers_saved_db_value(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE", "http://env-host:11434")
    BrainConfigStore()._save_sqlite_mirror(
        BrainConfig(primary_provider="ollama", ollama_base_url="https://tunnel.example.com")
    )
    assert resolve_ollama_base_url() == "https://tunnel.example.com"


def test_resolve_falls_back_to_env_then_default(monkeypatch):
    # No saved doc → env wins.
    monkeypatch.setenv("OLLAMA_BASE", "http://env-host:11434")
    assert resolve_ollama_base_url() == "http://env-host:11434"
    monkeypatch.delenv("OLLAMA_BASE", raising=False)
    assert resolve_ollama_base_url() == "http://localhost:11434"


def test_provider_base_url_ollama_uses_resolver(monkeypatch):
    BrainConfigStore()._save_sqlite_mirror(
        BrainConfig(primary_provider="ollama", ollama_base_url="https://gpu.local")
    )
    assert provider_base_url("ollama") == "https://gpu.local"


def test_config_and_patch_carry_ollama_base_url():
    cfg = BrainConfig(ollama_base_url="https://x.test")
    assert cfg.ollama_base_url == "https://x.test"
    patch = BrainConfigPatch(ollama_base_url="")  # empty clears the override
    assert patch.ollama_base_url == ""


class _FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {"models": [{"name": "qwen3-coder:30b"}]}
        self.text = "ok"

    def json(self):
        return self._payload


def test_probe_base_url_override_hits_the_typed_url(monkeypatch):
    """An Ollama probe with base_url must hit THAT url's /api/tags, not the saved one."""
    seen = {}

    class _Client:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url):
            seen["url"] = url
            return _FakeResp(200)

    monkeypatch.setattr(bl.httpx, "AsyncClient", _Client)
    result = asyncio.run(
        probe_model_liveness("ollama", "qwen3-coder:30b", base_url="https://typed-tunnel.test")
    )
    assert result.live is True
    assert seen["url"].startswith("https://typed-tunnel.test")
    assert seen["url"].endswith("/api/tags")
