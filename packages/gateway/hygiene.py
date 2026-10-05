"""packages/gateway/hygiene.py — request-hygiene middleware for the proxy.

A pure-ASGI middleware (not ``BaseHTTPMiddleware``, which would buffer or
re-task streaming responses) that does four things:

* sanitises ``X-Request-Id`` and exposes it through :func:`get_request_id`;
* rejects oversized bodies with 413 (declared and streamed length);
* adds the rule-41 security headers on the API prefixes, never overriding a
  header the route already set (streaming routes set their own ``no-cache``);
* echoes the request id on every response.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from packages.gateway import config

log = logging.getLogger("qwen-proxy")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_SECURED_PREFIXES = ("/v1/", "/api/", "/agent/")
_SECURITY_HEADERS = (
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Cache-Control", "no-store"),
)

_request_id_var: ContextVar[str] = ContextVar("gateway_request_id", default="")


def get_request_id() -> str:
    """The sanitised id of the request being served, or ``""`` outside one."""
    return _request_id_var.get()


def sanitize_request_id(raw: str | None) -> str:
    """Return *raw* when it is a safe token, else a fresh uuid4 hex."""
    if raw and _REQUEST_ID_RE.fullmatch(raw):
        return raw
    return uuid.uuid4().hex


class _BodyTooLarge(Exception):
    """Raised from the wrapped ``receive`` when the streamed body passes the limit."""


class _State:
    """Per-request flags shared between the receive and send wrappers."""

    def __init__(self) -> None:
        self.too_large = False
        self.response_started = False


class GatewayHygieneMiddleware:
    """See the module docstring."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = sanitize_request_id(Headers(scope=scope).get("x-request-id"))
        token = _request_id_var.set(request_id)
        try:
            await self._handle(scope, receive, send, request_id)
        finally:
            _request_id_var.reset(token)

    async def _handle(self, scope: Scope, receive: Receive, send: Send, request_id: str) -> None:
        state = _State()
        path = scope.get("path", "")
        secured = config.security_headers_enabled() and path.startswith(_SECURED_PREFIXES)
        limit = config.max_request_bytes()

        async def send_wrapper(message: Message) -> None:
            if state.too_large:
                # The app is unwinding from an aborted body read; only our 413 goes out.
                await self._send_413(send, request_id, secured, state)
                return
            if message["type"] == "http.response.start":
                state.response_started = True
                self._decorate(message, request_id, secured)
            await send(message)

        if limit > 0 and _declared_length(scope) > limit:
            state.too_large = True
            await self._send_413(send, request_id, secured, state)
            return
        wrapped_receive = _limit_receive(receive, limit, state) if limit > 0 else receive
        try:
            await self.app(scope, wrapped_receive, send_wrapper)
        except _BodyTooLarge:
            await self._send_413(send, request_id, secured, state)

    @staticmethod
    def _decorate(message: Message, request_id: str, secured: bool) -> None:
        message.setdefault("headers", [])
        headers = MutableHeaders(scope=message)
        headers["X-Request-Id"] = request_id
        if secured:
            for name, value in _SECURITY_HEADERS:
                if name not in headers:
                    headers[name] = value

    async def _send_413(self, send: Send, request_id: str, secured: bool, state: _State) -> None:
        if state.response_started:
            return
        state.response_started = True
        body = json.dumps({"detail": "Request body too large"}).encode("utf-8")
        start: dict[str, Any] = {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
        self._decorate(start, request_id, secured)
        await send(start)
        await send({"type": "http.response.body", "body": body})


def _declared_length(scope: Scope) -> int:
    raw = Headers(scope=scope).get("content-length", "")
    return int(raw) if raw.isdigit() else 0


def _limit_receive(receive: Receive, limit: int, state: _State) -> Receive:
    """Wrap *receive* so a streamed body larger than *limit* aborts the request."""
    seen = 0

    async def limited() -> Message:
        nonlocal seen
        message = await receive()
        if message["type"] == "http.request":
            seen += len(message.get("body", b""))
            if seen > limit:
                state.too_large = True
                log.warning("Rejected request body over the %d byte gateway limit", limit)
                raise _BodyTooLarge()
        return message

    return limited
