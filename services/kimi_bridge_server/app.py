"""Kimi web-bridge HTTP service.

Exposes an OpenAI-compatible ``POST /v1/chat/completions`` backed by a Playwright
browser session logged in to kimi.com.  Run as a separate process or container —
never imported by the main backend.

Usage::

    KIMI_BRIDGE_TOKEN=secret uvicorn services.kimi_bridge_server.app:app --port 8011

Environment
-----------
KIMI_BRIDGE_TOKEN          Bearer token required for every request (if unset in
                           production, a warning is emitted and auth is skipped —
                           only acceptable in local dev).
PLAYWRIGHT_USER_DATA_DIR   Path to the persistent Chromium profile directory where
                           the Kimi login cookie is stored (default: ~/.kimi_bridge_profile).
KIMI_BRIDGE_HEADLESS       "false" to run the browser in headed mode (default: true).
KIMI_BRIDGE_MODEL          Override the model name returned in responses (default: kimi-k2.6).
"""
from __future__ import annotations

import hmac
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .browser_driver import KimiBrowserDriver

log = logging.getLogger("kimi-bridge")
logging.basicConfig(level=logging.INFO)

_driver: Optional[KimiBrowserDriver] = None

_BRIDGE_TOKEN = os.environ.get("KIMI_BRIDGE_TOKEN", "").strip()
_DEFAULT_MODEL = os.environ.get("KIMI_BRIDGE_MODEL", "kimi-k2.6").strip() or "kimi-k2.6"


# ─── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _driver
    _driver = KimiBrowserDriver()
    await _driver.start()
    log.info("Kimi bridge service ready on /v1")
    yield
    await _driver.stop()
    log.info("Kimi bridge service shut down")


app = FastAPI(
    title="Kimi Web-Bridge",
    description="OpenAI-compatible chat completions backed by a Kimi browser session",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── Auth middleware ───────────────────────────────────────────────────────────


def _verify_token(request: Request) -> None:
    """Reject requests that don't carry the correct bearer token.

    If KIMI_BRIDGE_TOKEN is not configured we emit a warning and allow the
    request through — this is only acceptable during local development.
    """
    if not _BRIDGE_TOKEN:
        log.warning(
            "KIMI_BRIDGE_TOKEN is not set — bearer auth is disabled. "
            "This is insecure in production."
        )
        return

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    provided = auth_header.removeprefix("Bearer ").strip()
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(provided.encode(), _BRIDGE_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


# ─── Request / response models ────────────────────────────────────────────────


class _ContentPart(BaseModel):
    type: str
    text: Optional[str] = None


class _Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | list[_ContentPart]


class ChatCompletionRequest(BaseModel):
    model: str = Field(default=_DEFAULT_MODEL)
    messages: list[_Message]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    stream: bool = False

    model_config = {"extra": "allow"}


# ─── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/v1/models")
async def list_models(request: Request) -> JSONResponse:
    _verify_token(request)
    return JSONResponse(
        {
            "object": "list",
            "data": [
                {
                    "id": _DEFAULT_MODEL,
                    "object": "model",
                    "owned_by": "kimi-web-bridge",
                    "created": int(time.time()),
                }
            ],
        }
    )


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest) -> JSONResponse:
    _verify_token(request)

    if _driver is None:
        raise HTTPException(status_code=503, detail="Browser driver not initialised")

    if body.stream:
        # Streaming not yet supported — caller should set stream=false
        raise HTTPException(
            status_code=400,
            detail="stream=true is not supported by the Kimi web-bridge; use stream=false",
        )

    # Convert Pydantic messages to plain dicts for the driver
    messages = [
        {"role": m.role, "content": _content_to_str(m.content)}
        for m in body.messages
    ]

    try:
        reply_text = await _driver.ask(messages)
    except Exception as exc:
        log.exception("Browser driver ask() failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Kimi bridge error: {exc}") from exc

    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    # Best-effort token count (rough approximation: 1 token ≈ 4 chars)
    prompt_chars = sum(len(m.get("content", "")) for m in messages)
    completion_chars = len(reply_text)

    return JSONResponse(
        {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": body.model or _DEFAULT_MODEL,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": reply_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": max(1, prompt_chars // 4),
                "completion_tokens": max(1, completion_chars // 4),
                "total_tokens": max(1, (prompt_chars + completion_chars) // 4),
            },
        }
    )


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "driver_ready": _driver is not None})


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _content_to_str(content: str | list[_ContentPart]) -> str:
    if isinstance(content, str):
        return content
    return " ".join(part.text or "" for part in content if part.text)
