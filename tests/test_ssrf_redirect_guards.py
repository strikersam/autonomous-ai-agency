"""SSRF gaps found in the 2026-09-24 QA pass (rule 14).

* Knowledge "ingest from URL" fetched any user-supplied URL with
  ``follow_redirects=True`` and stored + returned the body — a full-read SSRF.
* The company-website scanner and SEO fetcher validated only the starting URL,
  then followed redirects unchecked.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

import backend.server as server
from services import scanner


@pytest.mark.asyncio
async def test_request_hook_blocks_internal_hops() -> None:
    with pytest.raises(httpx.RequestError):
        await scanner.ssrf_request_hook(httpx.Request("GET", "http://169.254.169.254/latest/meta-data"))
    with pytest.raises(httpx.RequestError):
        await scanner.ssrf_request_hook(httpx.Request("GET", "http://127.0.0.1:8001/api/keys"))


@pytest.mark.asyncio
async def test_httpx_redirect_to_internal_address_is_stopped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/"})

    # MockTransport stands in for the public first hop; the hook still sees the
    # redirect target and refuses it before any request is sent there.
    async def allow_first(request: httpx.Request) -> None:
        if request.url.host != "public.example":
            await scanner.ssrf_request_hook(request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=True,
        event_hooks={"request": [allow_first]},
    ) as client:
        with pytest.raises(httpx.RequestError):
            await client.get("http://public.example/")


def test_source_ingest_refuses_internal_urls(monkeypatch) -> None:
    async def _user(request):
        return {"_id": "u1", "email": "qa@example.com", "role": "user"}

    monkeypatch.setattr(server, "get_optional_user", _user)
    client = TestClient(server.app, raise_server_exceptions=False)
    resp = client.post("/api/sources/ingest", data={"url": "http://169.254.169.254/latest/meta-data/"})
    assert resp.status_code == 400
    assert "private or internal" in resp.json()["detail"]
