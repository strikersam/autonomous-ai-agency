"""Request hygiene: request ids, body-size limit, security headers."""

from __future__ import annotations

import re

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.testclient import TestClient

from packages.gateway.hygiene import GatewayHygieneMiddleware, get_request_id, sanitize_request_id
from tests.gateway_support import (  # noqa: F401
    chat_body,
    clear_dependency_overrides,
    gateway_env,
    make_client,
)


@pytest.fixture
def app_client(gateway_env) -> TestClient:
    app = FastAPI()
    app.add_middleware(GatewayHygieneMiddleware)

    @app.get("/v1/ping")
    async def ping() -> dict[str, str]:
        return {"request_id": get_request_id()}

    @app.get("/outside")
    async def outside() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/api/cached")
    async def cached() -> JSONResponse:
        return JSONResponse({"ok": True}, headers={"Cache-Control": "max-age=60"})

    @app.get("/v1/stream")
    async def stream() -> StreamingResponse:
        async def gen():
            yield b"data: x\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.post("/v1/echo")
    async def echo(request: Request) -> dict[str, int]:
        return {"bytes": len(await request.body())}

    return TestClient(app)


def test_valid_request_id_is_echoed_and_visible_to_handlers(app_client):
    resp = app_client.get("/v1/ping", headers={"X-Request-Id": "abc.DEF_123-x"})
    assert resp.headers["X-Request-Id"] == "abc.DEF_123-x"
    assert resp.json() == {"request_id": "abc.DEF_123-x"}


@pytest.mark.parametrize("bad", ["has space", "semi;colon", "a" * 129, "new\tline", "<script>"])
def test_unsafe_request_id_is_replaced_by_uuid_hex(app_client, bad):
    resp = app_client.get("/v1/ping", headers={"X-Request-Id": bad})
    echoed = resp.headers["X-Request-Id"]
    assert echoed != bad
    assert re.fullmatch(r"[0-9a-f]{32}", echoed)
    assert resp.json()["request_id"] == echoed


def test_missing_request_id_is_generated_and_boundary_length_is_accepted(app_client):
    assert re.fullmatch(r"[0-9a-f]{32}", app_client.get("/outside").headers["X-Request-Id"])
    assert sanitize_request_id("a" * 128) == "a" * 128
    assert sanitize_request_id("a" * 129) != "a" * 129
    assert re.fullmatch(r"[0-9a-f]{32}", sanitize_request_id(""))
    assert re.fullmatch(r"[0-9a-f]{32}", sanitize_request_id("é-accent"))
    assert get_request_id() == ""


def test_security_headers_only_on_api_prefixes(app_client):
    secured = app_client.get("/v1/ping")
    assert secured.headers["X-Content-Type-Options"] == "nosniff"
    assert secured.headers["X-Frame-Options"] == "DENY"
    assert secured.headers["Cache-Control"] == "no-store"
    plain = app_client.get("/outside")
    for name in ("X-Content-Type-Options", "X-Frame-Options", "Cache-Control"):
        assert name not in plain.headers


def test_existing_cache_control_is_not_clobbered(app_client):
    assert app_client.get("/api/cached").headers["Cache-Control"] == "max-age=60"
    streamed = app_client.get("/v1/stream")
    assert streamed.headers["Cache-Control"] == "no-cache"
    assert streamed.headers["X-Content-Type-Options"] == "nosniff"


def test_security_headers_can_be_switched_off_live(app_client, gateway_env):
    gateway_env.setenv("GATEWAY_SECURITY_HEADERS_ENABLED", "false")
    resp = app_client.get("/v1/ping")
    assert "X-Frame-Options" not in resp.headers
    assert "X-Request-Id" in resp.headers


def test_body_limit_is_off_by_default(app_client):
    resp = app_client.post("/v1/echo", content=b"x" * 100_000)
    assert resp.status_code == 200 and resp.json() == {"bytes": 100_000}


def test_declared_content_length_over_limit_is_413(app_client, gateway_env):
    gateway_env.setenv("GATEWAY_MAX_REQUEST_BYTES", "1000")
    resp = app_client.post("/v1/echo", content=b"x" * 1001)
    assert resp.status_code == 413
    assert resp.json() == {"detail": "Request body too large"}
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert "X-Request-Id" in resp.headers
    assert app_client.post("/v1/echo", content=b"x" * 1000).status_code == 200


def test_streamed_body_without_content_length_is_counted(app_client, gateway_env):
    gateway_env.setenv("GATEWAY_MAX_REQUEST_BYTES", "1000")

    def chunks():
        for _ in range(5):
            yield b"y" * 300

    resp = app_client.post("/v1/echo", content=chunks())
    assert resp.status_code == 413
    assert resp.json() == {"detail": "Request body too large"}


def test_proxy_app_preserves_request_id_echo(gateway_env):
    import proxy

    client = TestClient(proxy.app)
    resp = client.get("/health", headers={"X-Request-Id": "trace-42"})
    assert resp.headers["X-Request-Id"] == "trace-42"
    assert re.fullmatch(r"[0-9a-f]{32}", client.get("/health").headers["X-Request-Id"])
    assert "X-Frame-Options" not in resp.headers  # /health is outside the secured prefixes


def test_proxy_chat_response_carries_headers_and_forwards_request_id(gateway_env):
    client, upstream, observations = make_client(gateway_env)
    resp = client.post("/v1/chat/completions", json=chat_body(), headers={"X-Request-Id": "req-1"})

    assert resp.status_code == 200
    assert resp.headers["X-Request-Id"] == "req-1"
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert upstream.requests[0].headers["X-Request-Id"] == "req-1"
    assert observations[0]["routing_meta"]["request_id"] == "req-1"


def test_proxy_stream_keeps_its_no_cache_and_forwards_request_id(gateway_env):
    sse = b'data: {"choices":[{"delta":{"content":"a"}}],"usage":{"prompt_tokens":1,"completion_tokens":1}}\n\ndata: [DONE]\n\n'
    client, upstream, _obs = make_client(
        gateway_env, lambda _r: httpx.Response(200, content=sse, headers={"content-type": "text/event-stream"})
    )
    resp = client.post("/v1/chat/completions", json=chat_body(stream=True), headers={"X-Request-Id": "s-1"})

    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "no-cache"
    assert resp.headers["X-Request-Id"] == "s-1"
    assert upstream.requests[0].headers["X-Request-Id"] == "s-1"
