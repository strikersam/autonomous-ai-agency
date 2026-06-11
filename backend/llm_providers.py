"""llm_providers.py — LLM provider adapters and provider selection for the backend."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger("llm-wiki")


@dataclass(frozen=True)
class LlmProviderConfig:
    """Minimal provider config for OpenAI-compatible chat."""

    type: str
    base_url: str
    api_key: str | None = None
    default_model: str | None = None


def normalize_base_url(base_url: str) -> str:
    return (base_url or "").strip().rstrip("/")


def provider_type(provider: LlmProviderConfig) -> str:
    raw = (provider.type or "").strip().lower()
    if raw in {"openai_compat", "openai-compatible", "openai_compat"}:
        host = (urlparse(normalize_base_url(provider.base_url)).hostname or "").lower()
        if host.endswith("anthropic.com"):
            return "anthropic"
        return "openai-compatible"
    return raw or "openai-compatible"


def openai_compat_url(base_url: str, path: str) -> str:
    """Build an OpenAI-compatible URL for a provider base URL.

    Supports base URLs either with or without a trailing /v1. URLs that
    already carry a non-root path (e.g. /v1beta/openai for Google Gemini)
    are used as-is; bare hosts get /v1 appended. Defensively strips
    trailing /v1 from the base before checking to prevent double /v1.
    """
    base = normalize_base_url(base_url)
    if not path.startswith("/"):
        path = "/" + path
    # Prevent double /v1 when base already ends with /v1
    if base.endswith("/v1"):
        return f"{base}{path}"
    parsed = urlparse(base)
    if parsed.path and parsed.path != "/":
        return f"{base}{path}"
    return f"{base}/v1{path}"


def _auth_headers(api_key: str | None) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _anthropic_headers(api_key: str | None) -> dict[str, str]:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _anthropic_payload(
    *, messages: list[dict[str, Any]], model: str, temperature: float
) -> dict[str, Any]:
    system_parts: list[str] = []
    anthropic_messages: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if role == "system":
            system_parts.append(content)
        elif role in {"user", "assistant"}:
            anthropic_messages.append({"role": role, "content": content})
    return {
        "model": model,
        "messages": anthropic_messages or [{"role": "user", "content": ""}],
        "system": "\n\n".join(system_parts) if system_parts else None,
        "max_tokens": 1024,
        "temperature": float(temperature),
    }


def _anthropic_response_text(data: dict[str, Any]) -> str:
    parts: list[str] = []
    for block in data.get("content") or []:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return _strip_think_tags("".join(parts))


def _strip_think_tags(text: str) -> str:
    """Remove <think>…</think> reasoning blocks from model output.

    Some models (DeepSeek R1, QwQ, Qwen3-thinking) emit their chain-of-thought
    inside these tags before the real answer. We strip them so the UI always
    receives clean, actionable text.
    """
    if not text:
        return text
    stripped = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    # Also handle an unclosed <think> block at the end (model cut off mid-think)
    stripped = re.sub(r"<think>[\s\S]*$", "", stripped, flags=re.IGNORECASE)
    return stripped.strip()


async def chat_completion_text(
    provider: LlmProviderConfig,
    *,
    messages: list[dict[str, Any]],
    model: str | None,
    temperature: float,
    timeout_sec: float = 300.0,
    retries: int = 2,
    client: httpx.AsyncClient | None = None,
) -> str:
    use_model = (model or provider.default_model or "").strip()
    if not use_model:
        raise ValueError("Missing model (set provider default_model or pass model)")

    payload: dict[str, Any] = {
        "model": use_model,
        "messages": messages,
        "temperature": float(temperature),
        "stream": False,
    }
    ptype = provider_type(provider)
    url = (
        f"{normalize_base_url(provider.base_url)}/v1/messages"
        if ptype == "anthropic"
        else openai_compat_url(provider.base_url, "/chat/completions")
    )
    headers = _anthropic_headers(provider.api_key) if ptype == "anthropic" else _auth_headers(provider.api_key)

    async def _do(c: httpx.AsyncClient) -> str:
        body = (
            _anthropic_payload(messages=messages, model=use_model, temperature=float(temperature))
            if ptype == "anthropic"
            else payload
        )
        resp = await c.post(url, json=body, headers=headers)
        if resp.status_code == 404 and ptype == "ollama":
            # Older Ollama builds may not expose the OpenAI-compatible surface.
            native_url = f"{normalize_base_url(provider.base_url)}/api/chat"
            native_payload: dict[str, Any] = {
                "model": use_model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": float(temperature)},
            }
            native_headers = {"Content-Type": "application/json"}
            if provider.api_key:
                native_headers["Authorization"] = f"Bearer {provider.api_key}"
            native = await c.post(native_url, json=native_payload, headers=native_headers)
            native.raise_for_status()
            data = native.json()
            msg = data.get("message") if isinstance(data, dict) else None
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return _strip_think_tags(msg["content"])
            if isinstance(data, dict) and isinstance(data.get("response"), str):
                return _strip_think_tags(data["response"])
            raise ValueError("Unexpected Ollama /api/chat response shape")
        resp.raise_for_status()
        data = resp.json()
        if ptype == "anthropic":
            return _anthropic_response_text(data)

        # ── Extract content from OpenAI-compatible response ──────────────────
        choice = data["choices"][0]
        message = choice.get("message") or {}
        content: str | None = message.get("content")

        # Some thinking/reasoning models return content=None and put the answer
        # exclusively in reasoning_content (e.g. deepseek-reasoner via OpenRouter).
        if not content:
            content = message.get("reasoning_content") or ""

        # Strip <think>…</think> blocks emitted by reasoning models.
        return _strip_think_tags(content)

    if client is not None:
        return await _do(client)

    timeout = httpx.Timeout(timeout_sec, connect=min(10.0, timeout_sec))
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                return await _do(c)
        except Exception as exc:
            last_exc = exc
            if attempt >= retries:
                break
            log.warning("LLM chat attempt %s/%s failed: %s", attempt + 1, retries + 1, exc)
    assert last_exc is not None
    raise last_exc


async def list_openai_models(
    provider: LlmProviderConfig,
    *,
    timeout_sec: float = 10.0,
    client: httpx.AsyncClient | None = None,
) -> list[str]:
    ptype = provider_type(provider)
    url = (
        f"{normalize_base_url(provider.base_url)}/v1/models"
        if ptype == "anthropic"
        else openai_compat_url(provider.base_url, "/models")
    )
    headers = _anthropic_headers(provider.api_key) if ptype == "anthropic" else {}
    if provider.api_key and ptype != "anthropic":
        headers["Authorization"] = f"Bearer {provider.api_key}"

    async def _do(c: httpx.AsyncClient) -> list[str]:
        resp = await c.get(url, headers=headers)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            return []
        out: list[str] = []
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                out.append(item["id"])
        return out

    if client is not None:
        return await _do(client)

    timeout = httpx.Timeout(timeout_sec, connect=min(5.0, timeout_sec))
    async with httpx.AsyncClient(timeout=timeout) as c:
        return await _do(c)
