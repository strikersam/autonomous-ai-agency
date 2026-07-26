"""Ask a provider which models the configured API key may actually use.

``config/models.yaml`` hardcodes a candidate model list per provider. That list
is a snapshot of what the *catalogue* offered when it was written, not of what a
particular account is entitled to, and the two drift apart constantly: providers
archive models, and free tiers expose a different subset than paid ones.

When they drift, every candidate 404s and
:func:`packages.ai.failover_client._try_provider` concludes "no accessible model
(404 model_not_found)" and permanently disables a provider whose key is valid
and whose account is in good standing — it was only ever asked for models it
does not serve.

Every provider in the chain is OpenAI-compatible and answers ``GET /v1/models``
with the list for the presented key, so the truth is one cheap request away.
This module fetches it, caches it, and never raises: discovery is an
*improvement* on the static list, so a provider that does not answer simply
leaves the existing behaviour untouched.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

log = logging.getLogger("qwen-proxy")

# A model list changes on the order of weeks, and a stale entry costs one failed
# attempt that the failover chain already handles. Cache generously.
_TTL_OK_SEC = 6 * 60 * 60
# A provider that did not answer must not be re-asked on every failed call —
# discovery runs on the failure path, which is exactly when the provider is
# least likely to respond.
_TTL_FAIL_SEC = 10 * 60
_TIMEOUT_SEC = 10.0

# provider_id -> (expires_at, models or None)
_CACHE: dict[str, tuple[float, list[str] | None]] = {}


def _models_url(provider: Any) -> tuple[str, dict[str, str]]:
    """Return ``(url, headers)`` for *provider*'s model-listing endpoint.

    Mirrors :func:`packages.ai.failover_client._build_request` so discovery
    authenticates exactly the way the chat call does — a URL or header scheme
    that works for one must work for the other, or the answer is about a
    different account than the one making requests.
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
        return f"{cfg.normalized_base_url}/v1/models", cfg.auth_headers()

    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    return _openai_url(provider.base_url, "/models"), headers


def _parse_ids(body: Any) -> list[str]:
    """Extract model ids from an OpenAI-compatible ``/models`` body.

    Order is preserved: providers list their own preference, and that is a
    better ordering than anything this module could invent.
    """
    if not isinstance(body, dict):
        return []
    entries = body.get("data")
    if not isinstance(entries, list):
        return []
    ids: list[str] = []
    for entry in entries:
        if isinstance(entry, dict):
            model_id = entry.get("id")
            if isinstance(model_id, str) and model_id and model_id not in ids:
                ids.append(model_id)
    return ids


def _fresh_entry(provider_id: str) -> tuple[float, list[str] | None] | None:
    """Return the unexpired cache entry, distinguishing "absent" from "asked and
    got no answer". :func:`cached_models` deliberately collapses the two, so
    discovery needs its own view or a failed lookup is retried on every call."""
    entry = _CACHE.get(provider_id)
    if entry is None or entry[0] <= time.time():
        return None
    return entry


def cached_models(provider_id: str) -> list[str] | None:
    """Return the cached list for *provider_id* without any network call.

    The dispatcher's hot path uses this: a request must never wait on discovery,
    so an unpopulated cache simply means the static catalogue is used.
    """
    entry = _CACHE.get(provider_id)
    if entry is None or entry[0] <= time.time():
        return None
    return entry[1]


def reset_cache() -> None:
    """Drop every cached list. For tests and for an explicit operator refresh."""
    _CACHE.clear()


async def discover_models(provider: Any) -> list[str] | None:
    """Return the model ids *provider*'s key may use, or ``None`` if unknown.

    ``None`` means "could not find out" — never "the account has no models". The
    caller must not treat it as evidence of anything, because a network blip and
    an empty entitlement would otherwise look identical.
    """
    entry = _fresh_entry(provider.id)
    if entry is not None:
        return entry[1]

    try:
        url, headers = _models_url(provider)
        async with httpx.AsyncClient(timeout=_TIMEOUT_SEC) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code >= 400:
            log.warning(
                "model_discovery: %s GET /models returned %d — keeping the "
                "static candidate list",
                provider.id, resp.status_code,
            )
            return _remember(provider.id, None)
        ids = _parse_ids(resp.json())
    except Exception as exc:  # noqa: BLE001 — discovery is best-effort by design
        log.warning("model_discovery: %s listing failed: %s", provider.id, exc)
        return _remember(provider.id, None)

    if not ids:
        return _remember(provider.id, None)
    log.info("model_discovery: %s serves %d models", provider.id, len(ids))
    return _remember(provider.id, ids)


def _remember(provider_id: str, models: list[str] | None) -> list[str] | None:
    ttl = _TTL_OK_SEC if models else _TTL_FAIL_SEC
    _CACHE[provider_id] = (time.time() + ttl, models)
    return models
