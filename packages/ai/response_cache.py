"""packages/ai/response_cache.py — LRU+TTL in-memory response cache for the ProviderRouter.

Why this exists:
  Free-tier providers (Cerebras, Groq, NVIDIA NIM) have aggressive per-minute
  rate limits.  The agent loop's plan→execute→verify pattern often sends
  identical prompts within the same minute, burning quota unnecessarily.
  This cache eliminates those duplicate calls while leaving all
  non-deterministic and streaming requests untouched.

Eligibility rules (ALL must hold to cache):
  - RESPONSE_CACHE_ENABLED is not "0/false/no/off"  (default: enabled)
  - payload["stream"] is falsy
  - payload["temperature"] == 0  (non-zero is non-deterministic)

Cache key:
  SHA-256 of (model, messages, temperature, max_tokens, stop) — stable across
  calls regardless of key ordering in the dict.

Backend:
  In-memory OrderedDict (LRU eviction by pop-left) with per-entry monotonic
  expiry.  Single asyncio.Lock guards all mutations.

Configuration (env vars):
  RESPONSE_CACHE_ENABLED        default: true
  RESPONSE_CACHE_TTL_SECONDS    default: 3600  (one hour)
  RESPONSE_CACHE_MAX_SIZE       default: 256   (entries)
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from asyncio import Lock
from collections import OrderedDict
from typing import Any

log = logging.getLogger("llm-response-cache")

_CACHE_ENABLED: bool = os.environ.get("RESPONSE_CACHE_ENABLED", "true").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
_CACHE_TTL_SEC: float = float(os.environ.get("RESPONSE_CACHE_TTL_SECONDS", "3600") or "3600")
_CACHE_MAX_SIZE: int = int(os.environ.get("RESPONSE_CACHE_MAX_SIZE", "256") or "256")

# (key → (expires_at_monotonic, json_body_dict))
_cache: OrderedDict[str, tuple[float, dict[str, Any]]] = OrderedDict()
_lock: Lock = Lock()
_hits: int = 0
_misses: int = 0


def _cache_key(payload: dict[str, Any]) -> str:
    """Return a stable SHA-256 key for the cache-eligible fields in *payload*."""
    fingerprint = {
        "model": payload.get("model"),
        "messages": payload.get("messages"),
        "temperature": payload.get("temperature", 0),
        "max_tokens": payload.get("max_tokens"),
        "stop": payload.get("stop"),
    }
    raw = json.dumps(fingerprint, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def is_cacheable(payload: dict[str, Any]) -> bool:
    """Return True iff this request is eligible for caching."""
    if not _CACHE_ENABLED:
        return False
    if payload.get("stream"):
        return False
    try:
        if float(payload.get("temperature", 0)) > 0.0:
            return False
    except (TypeError, ValueError):
        return False
    return True


async def get_cached(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return a cached JSON body dict, or None if not cached / ineligible.

    Moves the hit entry to the *end* of the OrderedDict (LRU = most-recently
    used at end, eviction from front).
    """
    global _hits, _misses  # noqa: PLW0603
    if not is_cacheable(payload):
        return None
    key = _cache_key(payload)
    async with _lock:
        entry = _cache.get(key)
        if entry is None:
            _misses += 1
            return None
        expires_at, body = entry
        if time.monotonic() > expires_at:
            del _cache[key]
            _misses += 1
            return None
        _cache.move_to_end(key)
        _hits += 1
        log.debug("Cache HIT key=%.8s model=%s", key, payload.get("model"))
        return body


async def put_cached(payload: dict[str, Any], body: dict[str, Any]) -> None:
    """Store *body* under the key derived from *payload* if the request is eligible.

    Evicts the least-recently-used entry when the cache exceeds its max size.
    """
    if not is_cacheable(payload):
        return
    key = _cache_key(payload)
    expires_at = time.monotonic() + _CACHE_TTL_SEC
    async with _lock:
        _cache[key] = (expires_at, body)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX_SIZE:
            evicted_key, _ = _cache.popitem(last=False)
            log.debug("Cache evicted LRU key=%.8s (size limit %d)", evicted_key, _CACHE_MAX_SIZE)
    log.debug("Cache STORE key=%.8s model=%s", key, payload.get("model"))


async def cache_stats() -> dict[str, Any]:
    """Return diagnostic stats for monitoring endpoints."""
    global _hits, _misses  # noqa: PLW0603
    async with _lock:
        now = time.monotonic()
        live = sum(1 for exp, _ in _cache.values() if exp > now)
        total = _hits + _misses
        return {
            "enabled": _CACHE_ENABLED,
            "size": len(_cache),
            "live_entries": live,
            "ttl_seconds": _CACHE_TTL_SEC,
            "max_size": _CACHE_MAX_SIZE,
            "hits": _hits,
            "misses": _misses,
            "hit_rate_pct": round(_hits / total * 100, 1) if total else 0.0,
        }


async def clear_cache() -> int:
    """Clear all cached entries. Returns the number of entries cleared."""
    async with _lock:
        count = len(_cache)
        _cache.clear()
        log.info("Response cache cleared (%d entries removed)", count)
        return count
