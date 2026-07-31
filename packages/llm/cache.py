"""packages/llm/cache.py — layered caching.

Five independent layers, each with its own TTL and capacity:

    response    full completions, keyed by an exact payload hash
    prompt      system-prompt prefixes, for provider-side prefix cache reuse
    embedding   vectors, keyed by text hash (embeddings never change)
    tool        tool-call results, for idempotent tools
    semantic    near-duplicate prompts matched by cosine similarity

Layers are opt-in through ``cache.yaml``. Only ``response``, ``prompt``, and
``embedding`` are on by default: tool results and semantic matches are safe
only when the caller says they are.

**What is never cached:** streaming requests, requests carrying tools
(the tool result depends on the world, not the prompt), non-zero-temperature
requests above a threshold, and anything the caller marks
``cacheable=False``. Caching a sampled response would silently make a
"creative" agent deterministic — a user-visible behaviour change.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from packages.llm.config import CacheConfig, CacheLayerConfig, get_config

log = logging.getLogger("llm.cache")

T = TypeVar("T")

# Above this temperature the caller wants sampling variety, so a cache hit
# would be a behaviour change rather than an optimisation.
MAX_CACHEABLE_TEMPERATURE = 0.2


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float
    created_at: float
    hits: int = 0


class LRUCache(Generic[T]):
    """Bounded TTL cache with LRU eviction. Thread-safe, dependency-free."""

    def __init__(self, config: CacheLayerConfig, *, name: str = "cache") -> None:
        self._config = config
        self._name = name
        self._entries: OrderedDict[str, _Entry[T]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._config.enabled

    def get(self, key: str) -> T | None:
        if not self._config.enabled:
            return None
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.expires_at <= time.monotonic():
                del self._entries[key]
                self._misses += 1
                return None
            entry.hits += 1
            self._entries.move_to_end(key)
            self._hits += 1
            return entry.value

    def put(self, key: str, value: T, *, ttl_sec: float | None = None) -> None:
        if not self._config.enabled:
            return
        ttl = ttl_sec if ttl_sec is not None else self._config.ttl_sec
        with self._lock:
            self._entries[key] = _Entry(
                value=value,
                expires_at=time.monotonic() + ttl,
                created_at=time.time(),
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self._config.max_entries:
                self._entries.popitem(last=False)
                self._evictions += 1

    def items(self) -> list[tuple[str, T]]:
        """Live (unexpired) entries — used by the semantic layer's scan."""
        now = time.monotonic()
        with self._lock:
            return [(k, e.value) for k, e in self._entries.items() if e.expires_at > now]

    def invalidate(self, key: str) -> bool:
        with self._lock:
            return self._entries.pop(key, None) is not None

    def clear(self) -> int:
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        with self._lock:
            size = len(self._entries)
        return {
            "name": self._name,
            "enabled": self._config.enabled,
            "size": size,
            "max_entries": self._config.max_entries,
            "ttl_sec": self._config.ttl_sec,
            "hits": self._hits,
            "misses": self._misses,
            "evictions": self._evictions,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
        }


def payload_key(payload: dict[str, Any]) -> str:
    """Exact-match cache key over the fields that change the answer.

    Routing constraints are part of the key, not just the prompt. Without
    them a request with ``allow_paid=False`` could be served a cached
    response a paid provider produced earlier, and one with
    ``exclude_providers`` could be served the excluded provider's answer —
    a silent policy breach rather than an optimisation, because the stored
    body reports the provider that the caller rejected.
    """
    material = {
        "model": payload.get("model"),
        "messages": payload.get("messages"),
        "temperature": payload.get("temperature"),
        "max_tokens": payload.get("max_tokens"),
        "response_format": payload.get("response_format"),
        "tools": payload.get("tools"),
        "allow_paid": payload.get("allow_paid"),
        "providers": payload.get("providers"),
        "exclude_providers": payload.get("exclude_providers"),
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def text_key(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Cosine similarity between two vectors, 0.0 when either is degenerate."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class CacheManager:
    """Owns every cache layer and the policy for what may enter them."""

    def __init__(self, config: CacheConfig | None = None) -> None:
        self._config = config or get_config().cache
        self.response: LRUCache[dict[str, Any]] = LRUCache(self._config.response, name="response")
        self.prompt: LRUCache[str] = LRUCache(self._config.prompt, name="prompt")
        self.embedding: LRUCache[list[float]] = LRUCache(self._config.embedding, name="embedding")
        self.tool: LRUCache[Any] = LRUCache(self._config.tool, name="tool")
        self.semantic: LRUCache[tuple[list[float], dict[str, Any]]] = LRUCache(
            self._config.semantic, name="semantic"
        )

    @property
    def config(self) -> CacheConfig:
        return self._config

    def is_cacheable(self, request: Any) -> bool:
        """Whether a response to ``request`` may be stored.

        Deliberately conservative — a wrong cache hit is a correctness bug,
        while a missed hit is only a cost.
        """
        if not getattr(request, "cacheable", True):
            return False
        if getattr(request, "stream", False):
            return False
        if getattr(request, "tools", None):
            return False
        if getattr(request, "temperature", 0.0) > MAX_CACHEABLE_TEMPERATURE:
            return False
        messages = getattr(request, "messages", None) or []
        return bool(messages)

    # ── Response layer ──────────────────────────────────────────────────────

    def get_response(self, key: str) -> dict[str, Any] | None:
        return self.response.get(key)

    def put_response(self, key: str, body: dict[str, Any]) -> None:
        self.response.put(key, body)

    # ── Semantic layer ──────────────────────────────────────────────────────

    def get_semantic(
        self, embedding: list[float], *, threshold: float | None = None
    ) -> dict[str, Any] | None:
        """Nearest cached response above the similarity threshold.

        A linear scan over at most ``max_entries`` vectors. At the default 512
        entries this costs well under a millisecond — far less than the network
        call it avoids, and it keeps a vector database off the dependency list.
        """
        if not self.semantic.enabled or not embedding:
            return None
        limit = threshold if threshold is not None else self._config.semantic_threshold
        best: dict[str, Any] | None = None
        best_score = limit
        for _key, (vector, body) in self.semantic.items():
            score = cosine_similarity(embedding, vector)
            if score >= best_score:
                best_score = score
                best = body
        if best is not None:
            log.debug("llm.cache: semantic hit at similarity %.4f", best_score)
        return best

    def put_semantic(self, key: str, embedding: list[float], body: dict[str, Any]) -> None:
        if embedding:
            self.semantic.put(key, (embedding, body))

    # ── Aggregate ───────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        layers = [
            self.response.stats(), self.prompt.stats(), self.embedding.stats(),
            self.tool.stats(), self.semantic.stats(),
        ]
        hits = sum(int(layer["hits"]) for layer in layers)
        misses = sum(int(layer["misses"]) for layer in layers)
        total = hits + misses
        return {
            "layers": layers,
            "total_hits": hits,
            "total_misses": misses,
            "overall_hit_rate": round(hits / total, 4) if total else 0.0,
        }

    def clear(self) -> dict[str, int]:
        return {
            "response": self.response.clear(),
            "prompt": self.prompt.clear(),
            "embedding": self.embedding.clear(),
            "tool": self.tool.clear(),
            "semantic": self.semantic.clear(),
        }


_manager: CacheManager | None = None
_lock = threading.Lock()


def get_cache() -> CacheManager:
    """The process-wide cache manager."""
    global _manager
    if _manager is None:
        with _lock:
            if _manager is None:
                _manager = CacheManager()
    return _manager


def reset() -> None:
    """Test hook — drop every cache layer."""
    global _manager
    with _lock:
        _manager = None
