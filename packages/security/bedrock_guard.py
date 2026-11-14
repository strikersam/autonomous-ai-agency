"""One check on every outgoing httpx request while the Bedrock kill switch is on.

Per-call-site guards missed paths three review rounds in a row (Providers UI,
OpenClaw, liveness probe, voice worker, ...), because the repo has well over a
hundred ``httpx`` client sites and the provider SDKs it uses sit on httpx too.
This wraps httpx's per-hop send (``_send_single_request``, so redirect hops are
covered) once, so any request to a Bedrock host is refused regardless of which
module built it.

It matches the request *hostname* only (a path or query that merely mentions
"bedrock" is allowed) and reads ``BEDROCK_DISABLED`` on every request, so the
live platform control still works. It does not cover subprocess children
(aider, goose), ``boto3``, ``requests`` or ``aiohttp``; those have their own guards.
"""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

log = logging.getLogger("qwen-proxy")

_INSTALLED = False


def is_bedrock_host(host: str) -> bool:
    """True when a hostname is an Amazon Bedrock endpoint (runtime, mantle, vpce)."""
    return "bedrock" in (host or "").lower()


def _request_host(request: Any) -> str:
    try:
        return request.url.host or ""
    except Exception:  # noqa: BLE001 - never let the guard itself break a request
        return urlsplit(str(getattr(request, "url", ""))).hostname or ""


def _refuse_if_bedrock(request: Any) -> None:
    from packages.ai.brain import bedrock_disabled

    if bedrock_disabled() and is_bedrock_host(_request_host(request)):
        raise RuntimeError("Bedrock is disabled (BEDROCK_DISABLED)")


def install_bedrock_http_guard() -> bool:
    """Wrap httpx's ``send`` once per process. Returns True when newly installed."""
    global _INSTALLED
    if _INSTALLED:
        return False
    try:
        import httpx
    except ImportError:  # pragma: no cover - httpx is a hard dependency
        return False

    # `send` is called once per request, but redirect hops run inside it and call
    # `_send_single_request` directly, so a 302 from an allowed host to a Bedrock host
    # would slip past a `send` wrapper. Wrap the per-hop method when this httpx has it.
    target = "_send_single_request" if hasattr(httpx.Client, "_send_single_request") else "send"
    sync_send = getattr(httpx.Client, target)
    async_send = getattr(httpx.AsyncClient, target)

    def guarded_send(self: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
        _refuse_if_bedrock(request)
        return sync_send(self, request, *args, **kwargs)

    async def guarded_async_send(self: Any, request: Any, *args: Any, **kwargs: Any) -> Any:
        _refuse_if_bedrock(request)
        return await async_send(self, request, *args, **kwargs)

    setattr(httpx.Client, target, guarded_send)
    setattr(httpx.AsyncClient, target, guarded_async_send)
    _INSTALLED = True
    return True
