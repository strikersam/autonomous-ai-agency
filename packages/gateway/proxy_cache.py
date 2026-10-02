"""packages/gateway/proxy_cache.py — exact-match response cache for the proxy path.

A thin gate over :mod:`packages.ai.response_cache`, reusing its eligibility rules
(non-streaming, ``temperature`` explicitly 0, no ``tools``), LRU and TTL. Two
things are added here:

* it is off unless ``GATEWAY_PROXY_CACHE_ENABLED`` is set — ``RESPONSE_CACHE_ENABLED``
  (which defaults on and gates the ProviderRouter) is deliberately not consulted
  for the opt-in, although ``response_cache`` still honours it as a global
  kill-switch, so setting it to ``false`` disables this cache too;
* entries are keyed by consumer, so one API key can never be served another
  key's completion. The consumer is folded into the ``model`` field of the
  fingerprint the shared cache hashes.
"""

from __future__ import annotations

from typing import Any

from packages.ai import response_cache
from packages.gateway import config, usage_metrics

HIT = "HIT"
MISS = "MISS"


def _keyed(consumer: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {**payload, "model": f"{consumer}|{payload.get('model')}"}


async def lookup(consumer: str, payload: dict[str, Any]) -> tuple[str | None, dict[str, Any] | None]:
    """Return ``(X-Cache value, cached body)``; ``(None, None)`` when not applicable."""
    if not config.proxy_cache_enabled() or not response_cache.is_cacheable(payload):
        return None, None
    body = await response_cache.get_cached(_keyed(consumer, payload))
    usage_metrics.record_cache(body is not None)
    return (HIT, body) if body is not None else (MISS, None)


async def store(consumer: str, payload: dict[str, Any], body: Any, status_code: int) -> None:
    """Cache a successful JSON completion for *consumer*."""
    if status_code != 200 or not isinstance(body, dict) or not config.proxy_cache_enabled():
        return
    await response_cache.put_cached(_keyed(consumer, payload), body)
