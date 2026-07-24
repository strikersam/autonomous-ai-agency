"""packages/ai/failover_client.py — one dispatcher for the brain-failover chain.

``services/brain_failover`` decides *which* provider to try next; this module is
the single place that actually performs the HTTP call against it, handling the
per-status failover rules and the Anthropic wire format.

Why it exists
-------------
The dispatch loop used to live inline inside ``AgentRunner._chat_text``, which
meant only the agent loop could reach the env-configured provider chain
(nvidia, groq, cerebras, zai, zhipu, deepseek, together, dashscope, moonshot,
mistral, aerolink, openrouter, minimax, google, anthropic, ollama). Everything
routed through ``backend.server.call_llm`` — the CEO strategic assessment above
all — fell back only across the DB-configured ``providers`` records, so when
those were rate-limited the CEO dropped straight to its rule-based path while
the agent loop still had a dozen untried providers available.

Extracting the loop here gives both callers the same breadth from one
implementation, per the repository rule that no logic may be duplicated.

Policy is unchanged: paid providers are admitted to the chain only by
``services.brain_failover._build_registry``, which gates them behind
``ALLOW_PAID_BRAIN`` or the Providers UI toggle. This module never widens that.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("qwen-proxy")

# Models tried per provider before moving on. A provider that 410s its default
# model may still serve an alternate, but past three the next provider is the
# better bet.
_MAX_MODELS_PER_PROVIDER = 3

_DEFAULT_TIMEOUT_SEC = 120.0
_CONNECT_TIMEOUT_SEC = 10.0


class BrainFailoverExhausted(RuntimeError):
    """Every provider in the failover chain failed.

    ``last_error`` carries the most recent provider-level failure so callers can
    surface a specific cause rather than a generic "no brain available".
    """

    def __init__(self, last_error: str, tried: set[str] | None = None) -> None:
        self.last_error = last_error
        self.tried = set(tried or ())
        super().__init__(
            f"All brain providers exhausted. Last error: {last_error}"
            if last_error
            else "All brain providers exhausted."
        )


@dataclass
class FailoverResult:
    """A successful completion plus the accounting its callers need."""

    text: str
    model: str
    provider_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    attempts: list[str] = field(default_factory=list)


def _build_request(provider: Any) -> tuple[str, dict[str, str], bool]:
    """Return ``(url, headers, is_anthropic_native)`` for *provider*.

    Anthropic's native API has no ``/chat/completions`` route and rejects
    ``Authorization: Bearer``, so sending it the OpenAI-compatible shape returns
    a deterministic 400 for every model. OpenAI-compatible Claude gateways
    (OpenRouter, Aerolink) are not Anthropic-native and keep the standard path.
    """
    from packages.ai.router import (
        ProviderConfig,
        _openai_url,
        is_anthropic_base_url,
    )

    if is_anthropic_base_url(provider.base_url):
        cfg = ProviderConfig(
            provider_id=provider.id,
            type="anthropic",
            base_url=provider.base_url,
            api_key=provider.api_key or None,
        )
        return f"{cfg.normalized_base_url}/v1/messages", cfg.auth_headers(), True

    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    return _openai_url(provider.base_url, "/chat/completions"), headers, False


def _is_ollama(provider: Any) -> bool:
    return (
        "ollama" in (getattr(provider, "id", "") or "").lower()
        or ":11434" in (getattr(provider, "base_url", "") or "")
    )


async def failover_chat_completion(
    payload: dict[str, Any],
    *,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
) -> FailoverResult:
    """Run one chat completion across the brain-failover chain.

    Tries each healthy provider in ``services.brain_failover`` order (free, then
    local, then paid), and up to three models per provider. Raises
    :class:`BrainFailoverExhausted` when nothing succeeds — never returns a
    partial or placeholder result.
    """
    from packages.ai.router import ProviderRouter, with_ollama_reasoning_effort
    from services.brain_failover import get_failover_manager

    requested_model = str(payload.get("model") or "")
    fm = get_failover_manager()
    tried: set[str] = set()
    attempts: list[str] = []
    last_error = ""

    for _attempt in range(fm.max_attempts()):
        provider = fm.next_provider(exclude=tried, requested_model=requested_model)
        if provider is None:
            # Every provider is excluded or cooling down. If all of them have
            # tripped their circuit breaker, reset inline and retry rather than
            # waiting for the 5-minute self-heal tick — otherwise the whole
            # system deadlocks with no brain until that tick lands.
            all_providers = fm.get_providers()
            if all_providers and not any(p.is_healthy for p in all_providers):
                log.warning(
                    "brain_failover: all %d providers unhealthy — resetting "
                    "circuit breakers inline (tried=%s)",
                    len(all_providers), tried,
                )
                for p in all_providers:
                    fm.record_success(p.id)
                tried.clear()
                provider = fm.next_provider(exclude=tried, requested_model=requested_model)
            if provider is None:
                log.error("brain_failover: no healthy providers left (tried=%s)", tried)
                break

        tried.add(provider.id)
        chat_url, headers, is_anthropic = _build_request(provider)
        provider_model = fm.resolve_model(provider, requested_model)
        models_to_try = [provider_model] + [
            m for m in provider.models if m != provider_model
        ]

        for try_model in models_to_try[:_MAX_MODELS_PER_PROVIDER]:
            call_payload = {**payload, "model": try_model}
            post_payload = with_ollama_reasoning_effort(
                call_payload, is_ollama=_is_ollama(provider)
            )
            if is_anthropic:
                post_payload = ProviderRouter._anthropic_payload(post_payload)

            attempts.append(f"{provider.id}/{try_model}")
            call_start = time.perf_counter()
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout_sec, connect=_CONNECT_TIMEOUT_SEC)
                ) as client:
                    resp = await client.post(
                        chat_url, json=post_payload, headers=headers
                    )
            except Exception as exc:  # noqa: BLE001 — network errors fail over
                last_error = f"{provider.id} network error: {exc}"
                log.warning("brain_failover: %s network error: %s", provider.id, exc)
                fm.record_failure(provider.id, "network_error")
                break

            call_ms = int((time.perf_counter() - call_start) * 1000)

            if resp.status_code < 400:
                fm.record_success(provider.id, latency_ms=call_ms)
                if is_anthropic:
                    resp = ProviderRouter._anthropic_to_openai_response(
                        resp, try_model
                    )
                data = resp.json()
                usage = data.get("usage") if isinstance(data, dict) else {}
                usage = usage if isinstance(usage, dict) else {}
                return FailoverResult(
                    text=data["choices"][0]["message"]["content"],
                    model=try_model,
                    provider_id=provider.id,
                    prompt_tokens=int(usage.get("prompt_tokens") or 0),
                    completion_tokens=int(usage.get("completion_tokens") or 0),
                    latency_ms=call_ms,
                    attempts=attempts,
                )

            if resp.status_code == 410:
                # Model permanently gone — another model on this provider may
                # still serve.
                log.warning(
                    "brain_failover: %s model %s 410 Gone - trying next model",
                    provider.id, try_model,
                )
                continue

            # The remaining statuses fail identically for every model on this
            # provider, so trying another model here is guaranteed to repeat
            # the error. Move to the next provider instead.
            if resp.status_code in (429, 419):
                last_error = f"{provider.id} {resp.status_code} rate-limited"
                fm.record_failure(provider.id, "rate_limited", resp.status_code)
                break
            if resp.status_code == 413:
                last_error = f"{provider.id} 413 payload too large"
                fm.record_failure(provider.id, "payload_too_large", resp.status_code)
                break
            if resp.status_code in (401, 403):
                last_error = f"{provider.id} {resp.status_code} unauthorized/forbidden"
                fm.record_failure(provider.id, "auth_failed", resp.status_code)
                break
            if resp.status_code >= 500:
                last_error = f"{provider.id} {resp.status_code} server error"
                fm.record_failure(provider.id, "server_error", resp.status_code)
                break

            last_error = f"{provider.id} {resp.status_code}: {resp.text[:200]}"
            log.warning(
                "brain_failover: %s model %s returned %d - trying next model",
                provider.id, try_model, resp.status_code,
            )
            continue
        else:
            fm.record_failure(provider.id, "all_models_failed")
            continue

    raise BrainFailoverExhausted(last_error, tried)
