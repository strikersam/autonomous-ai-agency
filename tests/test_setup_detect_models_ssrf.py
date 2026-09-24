"""GET /api/setup/detect/models fetched any caller-supplied URL before login."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import setup.api as setup_api


@pytest.fixture()
def calls(monkeypatch) -> list:
    seen: list = []

    async def _fake(url: str) -> list:
        seen.append(url)
        return [{"name": "llama3", "size_gb": 1.0, "modified": ""}]

    monkeypatch.setattr(setup_api, "_detect_ollama_models", _fake)
    return seen


@pytest.fixture()
def anon() -> TestClient:
    from backend.server import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize("url", ["http://169.254.169.254", "http://10.0.0.5:11434", "http://192.168.1.2:11434"])
def test_anonymous_probe_of_private_address_is_refused(anon, calls, url) -> None:
    body = anon.get("/api/setup/detect/models", params={"ollama_url": url}).json()
    assert body["models"] == [] and "admin" in body["error"]
    assert calls == []


@pytest.mark.parametrize("url", ["http://localhost:11434", "http://127.0.0.1:11434"])
def test_default_loopback_ollama_still_works(anon, calls, url) -> None:
    body = anon.get("/api/setup/detect/models", params={"ollama_url": url}).json()
    assert body["total"] == 1 and calls == [url]


def test_admin_may_probe_a_lan_ollama() -> None:
    from types import SimpleNamespace

    admin_request = SimpleNamespace(state=SimpleNamespace(user={"role": "admin"}))
    assert setup_api._ollama_probe_block_reason("http://192.168.1.2:11434", admin_request) is None
