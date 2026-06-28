"""services/brain_liveness.py — Provider liveness prober for the brain switcher.

The plan's hard constraint #1: "Never land on a dead model. The API must
probe the provider for liveness before saving a model, and refuse to persist
a model that 404/410s."

This module ships a single coroutine, :func:`probe_model_liveness`, that
sends a 5-token chat-completion request to the named provider/model and
reports the HTTP status + a human-readable reason. It is consumed by the
admin endpoints in ``backend/server.py`` (PATCH /admin/api/policy/brain and
POST /admin/api/policy/brain/test) — never by the agent loop, so a slow
probe can never block a task.

Design notes
------------
* All probes use ``httpx.AsyncClient`` with a tight (10s) timeout. A probe
  that times out is reported as ``live=False`` with ``reason="timeout"`` —
  we never raise.
* Anthropic-shaped providers (``api.anthropic.com``) hit ``/v1/messages``
  instead of ``/v1/chat/completions``. We don't ship Anthropic in the
  ``BrainProvider`` Literal today (the plan only allows free tiers), but the
  code is here so adding Anthropic later is a one-line change.
* Ollama is probed via ``GET /api/tags`` (cheap) instead of a real
  chat-completion — this matches the existing ``test_provider`` endpoint
  pattern in ``backend/server.py``.
* The probe returns a :class:`ProbeResult` Pydantic model so the API can
  serialise it directly without manual dict shaping.
* **No keys are persisted.** The probe reads the key from env (via
  :mod:`services.brain_config_store`) at call time and never logs it.
"""
from __future__ import annotations

import logging
import time
from typing import Literal

import httpx
from pydantic import BaseModel

from services.brain_config_store import (
    BrainProvider,
    PROVIDER_DEFAULT_BASE_URL,
    PROVIDER_KEY_ENV,
    provider_api_key,
    provider_base_url,
)

log = logging.getLogger("brain_liveness")

# Probe payload — kept tiny so the probe is fast and cheap on every provider.
# ``max_tokens=5`` is small enough that even strict rate limits won't trip on
# the probe alone, but large enough to confirm the model actually generates.
_PROBE_MESSAGES = [{"role": "user", "content": "Reply with the single word: ok."}]
_PROBE_MAX_TOKENS = 5
_PROBE_TIMEOUT_SECONDS = 10.0


class ProbeResult(BaseModel):
    """Outcome of a single (provider, model) liveness probe."""

    provider: str
    model: str
    live: bool
    status_code: int | None = None
    reason: str = ""
    elapsed_ms: int | None = None


async def probe_model_liveness(
    provider: str,
    model: str,
    *,
    timeout: float = _PROBE_TIMEOUT_SECONDS,
    base_url: str | None = None,
) -> ProbeResult:
    """Probe ``(provider, model)`` for liveness. Never raises.

    Returns a :class:`ProbeResult` with ``live=True`` when the provider
    responded with HTTP 2xx and a parseable body. Any 4xx/5xx, network
    error, or timeout returns ``live=False`` with a human-readable reason
    suitable for surfacing in the UI.

    ``base_url`` overrides the resolved provider base URL. The Brain card uses
    it to **Test a typed-but-not-yet-saved Ollama tunnel URL** before Apply —
    so the operator can verify a new tunnel before persisting it.
    """
    if not model or not model.strip():
        return ProbeResult(
            provider=provider, model=model or "", live=False,
            reason="Empty model id",
        )

    provider_norm = (provider or "").strip().lower()
    if provider_norm not in PROVIDER_DEFAULT_BASE_URL:
        return ProbeResult(
            provider=provider, model=model, live=False,
            reason=f"Unknown provider: {provider!r}",
        )

    override = (base_url or "").strip()
    base_url = override.rstrip("/") if override else provider_base_url(provider_norm)
    api_key = provider_api_key(provider_norm)

    # Ollama is local — no key required. Other providers need a key.
    if provider_norm != "ollama" and not api_key:
        env_var = PROVIDER_KEY_ENV.get(provider_norm) or ""
        return ProbeResult(
            provider=provider, model=model, live=False,
            reason=f"Provider API key not configured (set {env_var})",
        )

    start = time.monotonic()
    try:
        if provider_norm == "ollama":
            return await _probe_ollama(model, base_url, timeout, start)
        return await _probe_openai_compat(provider_norm, model, base_url, api_key, timeout, start)
    except httpx.TimeoutException:
        return ProbeResult(
            provider=provider, model=model, live=False,
            reason=f"Timeout after {timeout:.0f}s",
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )
    except Exception as exc:  # noqa: BLE001 — never raise from a probe
        log.debug("brain_liveness: probe crashed for %s/%s: %s", provider, model, exc)
        return ProbeResult(
            provider=provider, model=model, live=False,
            reason=f"Probe error: {exc}",
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )


async def _probe_openai_compat(
    provider: str,
    model: str,
    base_url: str,
    api_key: str | None,
    timeout: float,
    start: float,
) -> ProbeResult:
    """Probe an OpenAI-compatible provider (Cerebras / Groq / NIM)."""
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    url = f"{url}/chat/completions"

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": _PROBE_MESSAGES,
        "max_tokens": _PROBE_MAX_TOKENS,
        "temperature": 0,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload, headers=headers)

    elapsed_ms = int((time.monotonic() - start) * 1000)
    live = 200 <= resp.status_code < 300
    reason = _describe_http_status(resp.status_code, resp.text, provider)
    return ProbeResult(
        provider=provider, model=model, live=live,
        status_code=resp.status_code, reason=reason, elapsed_ms=elapsed_ms,
    )


async def _probe_ollama(
    model: str, base_url: str, timeout: float, start: float
) -> ProbeResult:
    """Probe local Ollama via GET /api/tags (cheap) then a 5-token completion."""
    base = base_url.rstrip("/")
    tags_url = f"{base}/api/tags"

    async with httpx.AsyncClient(timeout=timeout) as client:
        # Step 1: confirm Ollama is up.
        try:
            r = await client.get(tags_url)
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                provider="ollama", model=model, live=False,
                reason=f"Ollama unreachable: {exc}",
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
        if r.status_code != 200:
            return ProbeResult(
                provider="ollama", model=model, live=False,
                status_code=r.status_code,
                reason=f"Ollama /api/tags returned {r.status_code}",
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
        # Step 2: confirm the model is actually pulled.
        try:
            data = r.json()
        except Exception:  # noqa: BLE001
            data = {}
        available = {
            str(m.get("name", "")).strip()
            for m in data.get("models", [])
            if isinstance(m, dict)
        }
        # Ollama tags include the :tag suffix. Match on the model name with
        # or without the suffix so users can type either "qwen3-coder:30b"
        # or "qwen3-coder".
        normalised_target = model.split(":", 1)[0].strip()
        normalised_available = {n.split(":", 1)[0].strip() for n in available}
        if normalised_target and normalised_target not in normalised_available:
            return ProbeResult(
                provider="ollama", model=model, live=False,
                status_code=200,
                reason=f"Model {model!r} not pulled locally. Available: {', '.join(sorted(available))[:200]}",
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )
        # Model present → live.
        return ProbeResult(
            provider="ollama", model=model, live=True,
            status_code=200, reason="Model available locally",
            elapsed_ms=int((time.monotonic() - start) * 1000),
        )


def _describe_http_status(status_code: int, body: str, provider: str) -> str:
    """Turn an HTTP status into a short, human-readable reason.

    The plan specifically calls out 410 Gone (the symptom of the retired
    ``meta/llama-3.3-70b-instruct``) and 404 — those get explicit
    "dead model" wording so the UI shows the operator what happened.
    """
    body_excerpt = (body or "")[:200].replace("\n", " ").strip()
    if status_code == 410:
        return f"HTTP 410 Gone — model retired or removed ({body_excerpt})"
    if status_code == 404:
        return f"HTTP 404 Not Found — model id not recognised ({body_excerpt})"
    if status_code == 401 or status_code == 403:
        return f"HTTP {status_code} — auth failed (check {provider.upper()}_API_KEY)"
    if status_code == 429:
        return f"HTTP 429 — rate-limited (provider is up, but quota hit)"
    if 200 <= status_code < 300:
        return "OK — provider responded with a valid chat completion"
    if 500 <= status_code < 600:
        return f"HTTP {status_code} — provider server error ({body_excerpt})"
    return f"HTTP {status_code} ({body_excerpt})"
