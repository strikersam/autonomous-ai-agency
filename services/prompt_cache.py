from __future__ import annotations

"""Prompt Caching — Anthropic-Compatible Prefix Caching (C6 roadmap item).

Implements Anthropic-compatible prefix caching for local models.  Since
local Ollama models lack native cache_control support, this module:

1. Parses cache_control blocks from Anthropic-format content payloads
2. Computes deterministic cache keys from system prompts and stable prefixes
3. Tracks model instances with warm KV caches (system-prompt hashing)
4. Routes requests to the instance most likely to have the prefix cached
5. Exposes cache token metrics (cache_read_input_tokens, cache_creation_input_tokens)

Usage::

    mgr = PromptCacheManager()
    cache_key = mgr.compute_cache_key(system_prompt, messages)
    instance = mgr.get_preferred_instance(cache_key)  # or None
    # ... make LLM call on preferred instance ...
    mgr.record_warm(instance, cache_key)
"""

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("qwen-proxy")


# ── Configuration ──────────────────────────────────────────────────────────────

_CACHE_ENABLED = os.environ.get("PROMPT_CACHE_ENABLED", "true").strip().lower() in ("true", "1", "yes")
_CACHE_MAX_ENTRIES = int(os.environ.get("PROMPT_CACHE_MAX_ENTRIES", "1000"))
_CACHE_TTL_SECONDS = int(os.environ.get("PROMPT_CACHE_TTL", "3600"))  # 1 hour
_INSTANCE_COUNT = int(os.environ.get("PROMPT_CACHE_INSTANCES", "4"))


@dataclass
class CacheEntry:
    """A single cached prefix entry."""

    cache_key: str
    system_hash: str
    model: str
    instance_id: str
    created_at: float
    last_hit_at: float
    hit_count: int = 0
    prefix_tokens: int = 0

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.created_at

    @property
    def is_expired(self) -> bool:
        return self.age_seconds > _CACHE_TTL_SECONDS


@dataclass
class CacheStats:
    """Prompt cache statistics."""

    hits: int = 0
    misses: int = 0
    creations: int = 0
    evictions: int = 0
    total_cache_read_tokens: int = 0
    total_cache_creation_tokens: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def summary(self) -> str:
        return (
            f"PromptCache | hits={self.hits} misses={self.misses} "
            f"hit_rate={self.hit_rate:.1%} "
            f"cache_read_tokens={self.total_cache_read_tokens} "
            f"cache_creation_tokens={self.total_cache_creation_tokens}"
        )


class PromptCacheManager:
    """Manages prefix cache tracking across model instances.

    Since local Ollama instances can't share KV caches across processes,
    we track which instance (port) most recently processed a given prefix
    and route subsequent requests there.  This gives soft cache affinity
    without requiring kernel-level KV cache sharing.
    """

    def __init__(
        self,
        *,
        enabled: bool = _CACHE_ENABLED,
        max_entries: int = _CACHE_MAX_ENTRIES,
        instance_count: int = _INSTANCE_COUNT,
    ) -> None:
        self.enabled = enabled
        self.max_entries = max_entries
        self.instance_count = instance_count
        self._entries: dict[str, CacheEntry] = {}
        self._stats = CacheStats()

    # ── Public API ──────────────────────────────────────────────────────────

    def compute_cache_key(
        self,
        system_prompt: str,
        messages: list[dict[str, Any]],
        model: str = "",
    ) -> str:
        """Compute a deterministic cache key from the stable prefix.

        The stable prefix is the longest non-mutating sequence of messages
        from the start: system prompt + early turns that haven't changed.
        """
        parts: list[str] = []
        if system_prompt:
            parts.append(system_prompt)
        for m in messages:
            role = m.get("role", "")
            content = str(m.get("content", ""))[:500]  # Truncate for key stability
            parts.append(f"{role}:{content}")
            if role == "user" and len(parts) > 2:
                break  # Only include up to the first user message

        raw = f"{model}|{'|'.join(parts)}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def compute_system_hash(self, system_prompt: str, model: str = "") -> str:
        """Hash a system prompt and model for KV cache fingerprinting."""
        raw = f"{model}|{system_prompt}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def get_preferred_instance(self, cache_key: str) -> str | None:
        """Return the instance ID that has this prefix cached, or None.

        Performs an LRU hit: if the entry exists and is not expired,
        bump the access count and return the instance.
        """
        if not self.enabled:
            return None

        entry = self._entries.get(cache_key)
        if entry is None:
            self._stats.misses += 1
            return None

        if entry.is_expired:
            self._evict(cache_key)
            self._stats.misses += 1
            return None

        entry.last_hit_at = time.monotonic()
        entry.hit_count += 1
        self._stats.hits += 1
        self._stats.total_cache_read_tokens += entry.prefix_tokens
        log.debug("Prompt cache hit: key=%s instance=%s hits=%d", cache_key[:12], entry.instance_id, entry.hit_count)
        return entry.instance_id

    def record_warm(
        self,
        instance_id: str,
        cache_key: str,
        *,
        system_hash: str = "",
        model: str = "",
        prefix_tokens: int = 0,
    ) -> None:
        """Record that an instance now has a warm cache for this prefix."""
        if not self.enabled:
            return

        # Evict if at capacity
        if len(self._entries) >= self.max_entries:
            self._evict_oldest()

        self._entries[cache_key] = CacheEntry(
            cache_key=cache_key,
            system_hash=system_hash,
            model=model,
            instance_id=instance_id,
            created_at=time.monotonic(),
            last_hit_at=time.monotonic(),
            prefix_tokens=prefix_tokens,
        )
        self._stats.creations += 1
        self._stats.total_cache_creation_tokens += prefix_tokens
        log.debug("Prompt cache warm: key=%s instance=%s tokens=%d", cache_key[:12], instance_id, prefix_tokens)

    def invalidate_system(self, system_hash: str) -> int:
        """Invalidate all entries for a given system prompt hash.

        Returns the number of entries removed.
        """
        count = 0
        for key, entry in list(self._entries.items()):
            if entry.system_hash == system_hash:
                self._evict(key)
                count += 1
        return count

    def invalidate_model(self, model: str) -> int:
        """Invalidate all entries for a given model."""
        count = 0
        for key, entry in list(self._entries.items()):
            if entry.model == model:
                self._evict(key)
                count += 1
        return count

    def clear(self) -> int:
        """Clear all cache entries. Returns count cleared."""
        count = len(self._entries)
        self._entries.clear()
        self._stats = CacheStats()
        return count

    def stats(self) -> dict[str, Any]:
        """Return cache statistics."""
        return {
            "enabled": self.enabled,
            "entries": len(self._entries),
            "max_entries": self.max_entries,
            "instance_count": self.instance_count,
            "hits": self._stats.hits,
            "misses": self._stats.misses,
            "creations": self._stats.creations,
            "evictions": self._stats.evictions,
            "hit_rate": round(self._stats.hit_rate, 3),
            "total_cache_read_tokens": self._stats.total_cache_read_tokens,
            "total_cache_creation_tokens": self._stats.total_cache_creation_tokens,
        }

    # ── Anthropic cache_control parsing ─────────────────────────────────────

    @staticmethod
    def parse_cache_control(
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Parse Anthropic cache_control blocks from messages.

        Returns a dict with:
            cache_key: The computed prefix cache key
            system_prompt: Extracted system text
            prefix_tokens: Estimated token count of the stable prefix
            has_ephemeral: True if any content block has ephemeral cache_control
        """
        system_text = ""
        ephemeral_blocks = 0

        for msg in messages:
            if msg.get("role") == "system":
                system_text = str(msg.get("content", ""))
                continue

            content = msg.get("content")
            if not isinstance(content, list):
                continue

            for block in content:
                if not isinstance(block, dict):
                    continue
                cache_ctrl = block.get("cache_control", {})
                if isinstance(cache_ctrl, dict):
                    ctype = cache_ctrl.get("type", "")
                    if ctype == "ephemeral":
                        ephemeral_blocks += 1

        # Estimate prefix tokens: 4 chars ≈ 1 token
        prefix_chars = len(system_text)
        # Include first user message in prefix estimate
        for msg in messages:
            if msg.get("role") == "user":
                prefix_chars += len(str(msg.get("content", "")))
                break

        prefix_tokens = max(1, prefix_chars // 4)

        return {
            "system_prompt": system_text,
            "prefix_tokens": prefix_tokens,
            "has_ephemeral": ephemeral_blocks > 0,
            "ephemeral_blocks": ephemeral_blocks,
        }

    @staticmethod
    def inject_cache_metrics(
        response: dict[str, Any],
        *,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> dict[str, Any]:
        """Inject Anthropic-compatible cache metrics into a response.

        Adds ``cache_read_input_tokens`` and ``cache_creation_input_tokens``
        to the ``usage`` block so clients can track cache efficiency.
        """
        out = dict(response)
        usage = dict(out.get("usage", {}))
        if cache_read_tokens:
            usage["cache_read_input_tokens"] = cache_read_tokens
        if cache_creation_tokens:
            usage["cache_creation_input_tokens"] = cache_creation_tokens
        out["usage"] = usage
        return out

    # ── Internal ────────────────────────────────────────────────────────────

    def _evict(self, cache_key: str) -> None:
        if cache_key in self._entries:
            del self._entries[cache_key]
            self._stats.evictions += 1

    def _evict_oldest(self) -> None:
        if not self._entries:
            return
        oldest_key = min(self._entries.keys(), key=lambda k: self._entries[k].created_at)
        self._evict(oldest_key)


# ── Module-level singleton ─────────────────────────────────────────────────────

_manager: PromptCacheManager | None = None


def get_prompt_cache() -> PromptCacheManager:
    """Return the module-level PromptCacheManager singleton."""
    global _manager
    if _manager is None:
        _manager = PromptCacheManager()
    return _manager
