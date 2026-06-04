"""
Anthropic Messages API compatibility layer.

Accepts POST /v1/messages in Anthropic format, translates to Ollama OpenAI-compat,
and returns Anthropic-format responses — including full SSE streaming.

This enables Claude Code CLI, the Anthropic Python/TS SDK, and any tool that sets
ANTHROPIC_BASE_URL to use your local Ollama models transparently.

Model routing:
  - Reads MODEL_MAP env var to map Anthropic model names → local Ollama names.
  - Falls back to AGENT_EXECUTOR_MODEL if no mapping found.

Auth:
  - Accepts both x-api-key header (Claude Code default) and Authorization: Bearer.
  - Auth is enforced by proxy.py before this handler is called.

Limitations vs real Anthropic API:
  - Images in content blocks are skipped (Ollama text models don't support vision).
  - Server-side beta tools (advisor_20260301, computer_use, web_search, text_editor,
    bash) are stripped before forwarding — Ollama does not support them.
    For advisor_20260301 specifically: the proxy cannot execute the Anthropic
    server-side Opus sub-inference. Any advisor advice text already present in
    the message history (advisor_tool_result blocks) is preserved as plain-text
    context so the local model still benefits from it on follow-up turns.
    See docs/architecture/advisor-strategy.md for the local equivalent pattern.
  - Caching / prompt caching headers are accepted but not functional.
  - `effort` parameter (Claude Opus 4.8+) is accepted but stripped — Ollama
    has no equivalent; the local model always uses its own defaults.
  - `thinking` parameter (extended / adaptive thinking) is accepted but stripped —
    Ollama has no extended-thinking support. Thinking content blocks in message
    history are also silently removed before forwarding.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, AsyncIterator

import httpx
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from langfuse_obs import emit_chat_observation
from router import get_router, RoutingDecision
from router.health import invalidate_cache as _invalidate_health_cache

log = logging.getLogger("qwen-proxy")


# ─── Fallback-aware HTTP helper ───────────────────────────────────────────────

async def _post_anthropic_with_fallback(
    url: str,
    body: bytes,
    headers: dict[str, str],
    openai_payload: dict[str, Any],
    fallback_models: list[str],
) -> Any:  # returns httpx.Response
    """POST to Ollama; on 5xx retry with each model in *fallback_models*."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
            resp = await client.post(url, content=body, headers=headers)
    except httpx.ConnectError as exc:
        raise HTTPException(status_code=503, detail=f"LLM backend unreachable: {exc}") from exc

    if resp.status_code < 500 or not fallback_models:
        return resp

    for fallback in fallback_models:
        log.warning(
            "Anthropic handler: Ollama returned %d — retrying with fallback model %r",
            resp.status_code, fallback,
        )
        _invalidate_health_cache()
        payload = dict(openai_payload)
        payload["model"] = fallback
        retry_body = json.dumps(payload).encode("utf-8")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
                resp = await client.post(url, content=retry_body, headers=headers)
        except httpx.ConnectError as exc:
            raise HTTPException(status_code=503, detail=f"LLM backend unreachable: {exc}") from exc
        if resp.status_code < 500:
            return resp

    return resp


# ─── Legacy shim (kept for any external callers) ───────────────────────────────

def get_local_model(anthropic_model: str) -> str:
    """Return the local Ollama model name for a given Anthropic model name.

    .. deprecated::
        Prefer ``get_router().route(requested_model=...)`` which returns full
        routing metadata. This shim is kept for backwards compatibility.
    """
    decision = get_router().route(requested_model=anthropic_model)
    return decision.resolved_model


# ─── Request translation: Anthropic → OpenAI ──────────────────────────────────

def _system_field_to_string(system: Any) -> str:
    """Convert Anthropic system field (string or list of content blocks) to plain string."""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        parts: list[str] = []
        for block in system:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def _content_block_to_text(block: dict[str, Any]) -> str:
    """Convert a single Anthropic content block to a plain text string."""
    btype = block.get("type", "")
    if btype == "text":
        return block.get("text", "")
    if btype == "image":
        return "[image — not supported by local model]"
    if btype == "tool_result":
        tool_id = block.get("tool_use_id", "")
        content = block.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                b.get("text", "") for b in content if isinstance(b, dict)
            )
        return f"[Tool result ({tool_id})]: {content}"
    if btype == "tool_use":
        return f"[Called {block.get('name', 'unknown')} with {json.dumps(block.get('input', {}))}]"
    # Thinking blocks — produced by Claude Opus 4.7+ adaptive/extended thinking.
    # Strip silently: the local model has no use for another model's raw reasoning
    # tokens, and including them would only waste context.
    if btype == "thinking":
        return ""
    # Advisor strategy blocks — produced by the real Anthropic API when the
    # advisor_20260301 beta tool is used.  We preserve the advice text so the
    # local model still has that context on follow-up turns.
    if btype == "server_tool_use":
        name = block.get("name", "unknown")
        return f"[{name} consultation requested]"
    if btype == "advisor_tool_result":
        inner = block.get("content") or {}
        if isinstance(inner, dict):
            inner_type = inner.get("type", "")
            if inner_type == "advisor_result":
                return f"[Advisor guidance]: {inner.get('text', '')}"
            if inner_type == "advisor_redacted_result":
                return "[Advisor guidance: redacted by server]"
            if inner_type == "advisor_tool_result_error":
                return f"[Advisor error: {inner.get('error_code', 'unknown')}]"
        return "[Advisor result]"
    return ""


def _messages_to_openai(
    messages: list[dict[str, Any]],
    system: str | None,
) -> list[dict[str, Any]]:
    """Convert Anthropic messages array + system string to OpenAI messages list."""
    out: list[dict[str, Any]] = []

    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if isinstance(content, str):
            out.append({"role": role, "content": content})
        elif isinstance(content, list):
            text = "\n".join(_content_block_to_text(b) for b in content if isinstance(b, dict))
            out.append({"role": role, "content": text})
        else:
            out.append({"role": role, "content": str(content or "")})

    return out


# Anthropic server-side / beta tool types that cannot be forwarded to Ollama.
# These are handled server-side by the real Anthropic API and have no OpenAI equivalent.
_SERVER_TOOL_TYPES: frozenset[str] = frozenset({
    "advisor_20260301",        # Advisor strategy — Opus sub-inference (server-side only)
    "computer_use_20241022",   # Computer use beta
    "computer_use_20250124",
    "computer_use_20260124",   # Computer use — 2026 variant
    "text_editor_20241022",    # Text editor tool (Claude Code)
    "text_editor_20250124",    # Text editor tool (Claude Code — 2025 variant)
    "text_editor_20260101",    # Text editor tool (Claude Code — 2026 variant, v2.1.154+)
    "bash_20241022",           # Bash tool (Claude Code)
    "bash_20250124",           # Bash tool (Claude Code — 2025 variant)
    "bash_20260101",           # Bash tool (Claude Code — 2026 variant, v2.1.154+)
    "web_search_20250305",     # Web search (server-side)
    "web_search_20260101",     # Web search (server-side — 2026 variant)
})


def _tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert Anthropic tool definitions to OpenAI function tool definitions.

    Server-side beta tools (advisor, computer_use, web_search, etc.) are filtered
    out — Ollama does not support them and passing them causes downstream errors.
    """
    out: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        tool_type = tool.get("type", "")
        if tool_type in _SERVER_TOOL_TYPES:
            log.debug("Stripping server-side tool %r (type=%r) — not supported by Ollama", tool.get("name"), tool_type)
            continue
        out.append({
            "type": "function",
            "function": {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return out


# ─── Response translation: OpenAI → Anthropic ─────────────────────────────────

def _finish_reason_to_stop_reason(finish: str | None) -> str:
    mapping = {"tool_calls": "tool_use", "length": "max_tokens", "stop": "end_turn"}
    return mapping.get(finish or "stop", "end_turn")


def _openai_choice_to_anthropic_content(choice: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert an OpenAI response choice to Anthropic content block list."""
    blocks: list[dict[str, Any]] = []
    msg = choice.get("message") or {}

    text = msg.get("content") or ""
    if text:
        blocks.append({"type": "text", "text": text})

    for tc in (msg.get("tool_calls") or []):
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        try:
            inp = json.loads(fn.get("arguments", "{}"))
        except (json.JSONDecodeError, TypeError):
            inp = {}
        blocks.append({
            "type": "tool_use",
            "id": tc.get("id", f"toolu_{uuid.uuid4().hex[:16]}"),
            "name": fn.get("name", ""),
            "input": inp,
        })

    return blocks


def _build_anthropic_response(
    data: dict[str, Any],
    anthropic_model: str,
    msg_id: str,
) -> dict[str, Any]:
    choices = data.get("choices") or []
    usage = data.get("usage") or {}

    content_blocks: list[dict[str, Any]] = []
    stop_reason = "end_turn"

    if choices:
        choice = choices[0]
        stop_reason = _finish_reason_to_stop_reason(choice.get("finish_reason"))
        content_blocks = _openai_choice_to_anthropic_content(choice)

    return {
        "id": msg_id,
        "type": "message",
        "role": "assistant",
        "content": content_blocks,
        "model": anthropic_model,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": int(usage.get("prompt_tokens") or 0),
            "output_tokens": int(usage.get("completion_tokens") or 0),
        },
    }


# ─── Anthropic SSE streaming ───────────────────────────────────────────────────

def _sse_event(event_type: str, data: dict[str, Any]) -> bytes:
    return (
        f"event: {event_type}\n"
        f"data: {json.dumps(data, separators=(',', ':'))}\n\n"
    ).encode("utf-8")


async def _stream_anthropic_sse(
    target_url: str,
    forward_headers: dict[str, str],
    forward_body: bytes,
    anthropic_model: str,
    local_model: str,
    msg_id: str,
    email: str,
    department: str,
    key_id: str | None,
    openai_messages: list[dict[str, Any]],
    start_time: float,
    routing_meta: dict[str, Any] | None = None,
) -> AsyncIterator[bytes]:
    """Translate Ollama OpenAI SSE stream → Anthropic SSE stream."""

    # ── Preamble events ────────────────────────────────────────────────────────
    yield _sse_event("message_start", {
        "type": "message_start",
        "message": {
            "id": msg_id,
            "type": "message",
            "role": "assistant",
            "content": [],
            "model": anthropic_model,
            "stop_reason": None,
            "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 1},
        },
    })
    yield _sse_event("content_block_start", {
        "type": "content_block_start",
        "index": 0,
        "content_block": {"type": "text", "text": ""},
    })
    yield _sse_event("ping", {"type": "ping"})

    # ── Stream from Ollama ─────────────────────────────────────────────────────
    text_parts: list[str] = []
    input_tokens = 0
    output_tokens = 0
    ttft_ms: int | None = None
    line_buf = bytearray()

    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        async with client.stream("POST", target_url, content=forward_body, headers=forward_headers) as resp:
            if resp.status_code >= 400:
                error_body = await resp.aread()
                log.error("Ollama returned %d: %s", resp.status_code, error_body[:500])
                yield _sse_event("error", {
                    "type": "error",
                    "error": {"type": "api_error", "message": f"Upstream error {resp.status_code}"},
                })
                return

            async for chunk in resp.aiter_bytes(chunk_size=512):
                line_buf.extend(chunk)
                # Parse complete SSE lines from the buffer
                while True:
                    nl = bytes(line_buf).find(b"\n")
                    if nl == -1:
                        break
                    raw_line = bytes(line_buf[:nl])
                    del line_buf[:nl + 1]

                    if not raw_line.startswith(b"data:"):
                        continue
                    payload_bytes = raw_line[5:].strip()
                    if payload_bytes == b"[DONE]":
                        continue

                    try:
                        obj = json.loads(payload_bytes)
                    except json.JSONDecodeError:
                        continue

                    # Extract usage from final chunk
                    u = obj.get("usage")
                    if isinstance(u, dict):
                        input_tokens = int(u.get("prompt_tokens") or 0)
                        output_tokens = int(u.get("completion_tokens") or 0)

                    # Extract text deltas and emit as Anthropic content_block_delta
                    for ch in (obj.get("choices") or []):
                        delta = ch.get("delta") or {}
                        text = delta.get("content")
                        if isinstance(text, str) and text:
                            if ttft_ms is None:
                                ttft_ms = int((time.perf_counter() - start_time) * 1000)
                            text_parts.append(text)
                            yield _sse_event("content_block_delta", {
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {"type": "text_delta", "text": text},
                            })

    # ── Epilogue events ────────────────────────────────────────────────────────
    full_text = "".join(text_parts)
    if not output_tokens and full_text:
        output_tokens = max(len(full_text) // 4, 1)

    yield _sse_event("content_block_stop", {"type": "content_block_stop", "index": 0})
    yield _sse_event("message_delta", {
        "type": "message_delta",
        "delta": {"stop_reason": "end_turn", "stop_sequence": None},
        "usage": {"output_tokens": output_tokens},
    })
    yield _sse_event("message_stop", {"type": "message_stop"})

    # ── Langfuse observation ───────────────────────────────────────────────────
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    await _emit_safely(
        email, department, key_id, local_model, openai_messages, full_text,
        input_tokens, output_tokens,
        latency_ms=latency_ms,
        ttft_ms=ttft_ms or 0,
        routing_meta=routing_meta,
    )


# ─── Langfuse emission ─────────────────────────────────────────────────────────

async def _emit_safely(
    email: str,
    department: str,
    key_id: str | None,
    model: str,
    messages: list[dict[str, Any]],
    out_text: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int = 0,
    ttft_ms: int = 0,
    routing_meta: dict[str, Any] | None = None,
) -> None:
    try:
        await asyncio.to_thread(
            emit_chat_observation,
            email=email,
            department=department,
            key_id=key_id,
            model=model,
            messages=messages,
            output_text=out_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            ttft_ms=ttft_ms,
            routing_meta=routing_meta,
        )
    except Exception as exc:
        log.warning("Anthropic compat Langfuse emit error: %s", exc)


# ─── Main handler ──────────────────────────────────────────────────────────────

async def handle_anthropic_messages(
    *,
    request: Request,
    ollama_base: str,
    email: str,
    department: str,
    key_id: str | None,
) -> JSONResponse | StreamingResponse:
    """Handle POST /v1/messages — Anthropic Messages API format."""
    start_time = time.perf_counter()
    body_bytes = await request.body()

    try:
        payload: dict[str, Any] = json.loads(body_bytes) if body_bytes else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")

    # ── Field extraction ───────────────────────────────────────────────────────
    anthropic_model = str(payload.get("model") or "claude-3-5-sonnet-20241022")

    system_raw = payload.get("system")
    system_text = _system_field_to_string(system_raw) if system_raw else None

    anthropic_messages: list[dict[str, Any]] = payload.get("messages") or []
    stream = bool(payload.get("stream", False))
    max_tokens = payload.get("max_tokens")
    tools: list[dict[str, Any]] = payload.get("tools") or []

    # ── Route: decide which local model to use ─────────────────────────────────
    # Manual override: client sends X-Model-Override header (works from any IDE).
    override_model = request.headers.get("x-model-override") or None
    openai_messages_for_routing = _messages_to_openai(anthropic_messages, system_text)
    routing = get_router().route(
        requested_model=anthropic_model,
        messages=openai_messages_for_routing,
        system=system_text,
        has_tools=bool(tools),
        stream=stream,
        override_model=override_model,
        endpoint_type="chat",
    )
    local_model = routing.resolved_model
    routing_meta = routing.to_meta()

    # ── Build OpenAI payload ───────────────────────────────────────────────────
    openai_messages = openai_messages_for_routing

    openai_payload: dict[str, Any] = {
        "model": local_model,
        "messages": openai_messages,
        "stream": stream,
    }

    if max_tokens:
        openai_payload["max_tokens"] = max_tokens

    if stream:
        openai_payload["stream_options"] = {"include_usage": True}

    if tools:
        openai_payload["tools"] = _tools_to_openai(tools)

    # Pass through sampling params if present
    for param in ("temperature", "top_p"):
        val = payload.get(param)
        if val is not None:
            openai_payload[param] = val

    # Strip Anthropic-specific parameters that Ollama does not understand.
    # `effort` is new in Claude Opus 4.8 (Claude Code v2.1.154+); Ollama would
    # return a 400 if we forwarded it.
    effort = payload.get("effort")
    if effort is not None:
        log.debug("Stripping effort=%r — not supported by Ollama backend", effort)

    # `thinking` (extended / adaptive) is an Anthropic-only capability.
    # Ollama has no equivalent; forwarding it causes a 400 error.
    thinking = payload.get("thinking")
    if thinking is not None:
        thinking_type = thinking.get("type") if isinstance(thinking, dict) else thinking
        log.debug("Stripping thinking param (type=%r) — not supported by Ollama backend", thinking_type)

    forward_body = json.dumps(openai_payload).encode("utf-8")
    target_url = f"{ollama_base}/v1/chat/completions"
    forward_headers = {"Content-Type": "application/json"}
    msg_id = f"msg_{uuid.uuid4().hex[:24]}"

    log.info(
        "→ /v1/messages model=%s → %s [%s/%s] stream=%s tools=%d",
        anthropic_model, local_model,
        routing.mode, routing.selection_source,
        stream, len(tools),
    )

    # ── Streaming response ─────────────────────────────────────────────────────
    if stream:
        return StreamingResponse(
            _stream_anthropic_sse(
                target_url, forward_headers, forward_body,
                anthropic_model, local_model, msg_id,
                email, department, key_id, openai_messages, start_time,
                routing_meta=routing_meta,
            ),
            media_type="text/event-stream",
            headers={
                "X-Accel-Buffering": "no",
                "Cache-Control": "no-cache",
                "anthropic-version": "2023-06-01",
                "X-Routing-Mode": routing.mode,
                "X-Routing-Model": local_model,
            },
        )

    # ── Non-streaming response (with fallback retry on 5xx) ───────────────────
    resp = await _post_anthropic_with_fallback(
        target_url, forward_body, forward_headers,
        openai_payload, routing.fallback_chain,
    )

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    if not resp.headers.get("content-type", "").startswith("application/json"):
        raise HTTPException(status_code=resp.status_code, detail=resp.text[:500])

    data = resp.json()
    anthropic_resp = _build_anthropic_response(data, anthropic_model, msg_id)

    pt = anthropic_resp["usage"]["input_tokens"]
    ct = anthropic_resp["usage"]["output_tokens"]
    out_text = next(
        (b.get("text", "") for b in anthropic_resp["content"] if b.get("type") == "text"),
        "",
    )

    await _emit_safely(
        email, department, key_id, local_model, openai_messages, out_text,
        pt, ct, latency_ms=latency_ms,
        routing_meta=routing_meta,
    )

    return JSONResponse(
        content=anthropic_resp,
        status_code=resp.status_code,
        headers={
            "anthropic-version": "2023-06-01",
            "X-Routing-Mode": routing.mode,
            "X-Routing-Model": local_model,
        },
    )


# ---------------------------------------------------------------------------
# Token estimation helper (lightweight, no model call required)
# ---------------------------------------------------------------------------

def _estimate_tokens_for_messages(
    messages: list[dict],
    system: str | None,
    tools: list[dict] | None = None,
) -> int:
    """Estimate input token count for an Anthropic-format message list.

    Uses a simple character-count heuristic (4 chars ≈ 1 token) plus fixed
    overhead for images and tool definitions.  Accurate enough for quota
    preflight checks; not a substitute for real tokenisation.
    """
    total_chars = 0

    if system:
        total_chars += len(system)

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            for block in content:
                btype = block.get("type", "")
                if btype == "text":
                    total_chars += len(block.get("text", ""))
                elif btype in ("image", "image_url"):
                    # Fixed 1000-token cost per image regardless of size
                    total_chars += 4000
                elif btype == "tool_use":
                    total_chars += len(str(block.get("input", "")))
                elif btype == "tool_result":
                    inner = block.get("content", "")
                    if isinstance(inner, str):
                        total_chars += len(inner)
                    elif isinstance(inner, list):
                        for ib in inner:
                            total_chars += len(str(ib.get("text", "")))

    # Per-message structural overhead (role, turn markers)
    total_chars += len(messages) * 16

    # Tool definitions add per-tool overhead
    for tool in tools or []:
        total_chars += len(tool.get("name", "")) + len(tool.get("description", "")) + 64
        schema = tool.get("input_schema", {})
        total_chars += len(str(schema))

    # 4 chars ≈ 1 token; minimum 1
    return max(1, total_chars // 4)


# ---------------------------------------------------------------------------
# output_format normalisation helper (Anthropic structured-output extension)
# ---------------------------------------------------------------------------

def _normalize_anthropic_output_format(
    payload: dict,
    openai_payload: dict,
) -> bool:
    """Translate Anthropic ``output_format`` into an Ollama ``format`` field.

    Modifies *openai_payload* in place and returns ``True`` when a format was
    applied (caller should set ``anthropic-beta: structured-outputs-…``).

    Supported types:
    - ``json_schema``  → ``openai_payload["format"]`` = the schema dict
    - ``json_object``  → ``openai_payload["format"]`` = ``"json"``
    - anything else   → no change, returns ``False``
    """
    output_format = payload.get("output_format")
    if not isinstance(output_format, dict):
        return False

    fmt_type = output_format.get("type")

    if fmt_type == "json_schema":
        js = output_format.get("json_schema")
        if isinstance(js, dict) and "schema" in js:
            openai_payload["format"] = js["schema"]
        else:
            # Malformed json_schema — fall back to plain JSON mode
            openai_payload["format"] = "json"
        return True

    if fmt_type == "json_object":
        openai_payload["format"] = "json"
        return True

    return False
