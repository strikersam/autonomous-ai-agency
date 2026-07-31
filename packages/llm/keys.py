"""packages/llm/keys.py — multi-key rotation with per-key health.

A provider may hold several API keys. When one key is rate-limited or its
quota is exhausted, the ring hands out the next healthy key instead of
failing the request — the narrowest failure scope in ADR-008 §4.

Key material is read from the environment at call time and never stored in a
config object, never logged, and never persisted. Statistics are keyed by a
short digest so the dashboard can show "key 2 of 3 is cooling" without ever
exposing the secret.

Values may hold several keys separated by commas or whitespace, matching the
convention already used by ``packages/ai/key_pool.py``.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger("llm.keys")

_SPLIT = re.compile(r"[,\s]+")

# Cooldown applied when a key reports a rate limit without a Retry-After.
DEFAULT_COOLDOWN_SEC = 30.0
# Quota exhaustion is a much longer condition than a burst limit.
QUOTA_COOLDOWN_SEC = 1800.0
MAX_COOLDOWN_SEC = 3600.0


def _digest(key: str) -> str:
    """Stable, non-reversible 8-char identifier for a key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def resolve_keys(env_names: list[str]) -> list[str]:
    """Read the environment variables named in ``env_names`` into a key list.

    Order is preserved and duplicates are dropped so a key listed twice
    doesn't get double weight in the rotation.
    """
    keys: list[str] = []
    for name in env_names:
        raw = os.environ.get(name, "").strip()
        if not raw:
            continue
        for part in _SPLIT.split(raw):
            candidate = part.strip()
            if candidate and candidate not in keys:
                keys.append(candidate)
    return keys


@dataclass
class KeyState:
    """Rolling health for one key."""

    digest: str
    index: int
    env_name: str = ""
    requests: int = 0
    successes: int = 0
    failures: int = 0
    rate_limits: int = 0
    cooling_until: float = 0.0
    consecutive_limits: int = 0
    last_error: str = ""
    last_used: float = 0.0

    @property
    def healthy(self) -> bool:
        return time.monotonic() >= self.cooling_until

    @property
    def success_rate(self) -> float:
        return self.successes / self.requests if self.requests else 1.0

    def as_dict(self) -> dict[str, object]:
        remaining = max(0.0, self.cooling_until - time.monotonic())
        return {
            "digest": self.digest,
            "index": self.index,
            "env": self.env_name,
            "requests": self.requests,
            "successes": self.successes,
            "failures": self.failures,
            "rate_limits": self.rate_limits,
            "success_rate": round(self.success_rate, 4),
            "healthy": self.healthy,
            "cooling_for_sec": round(remaining, 1),
            "last_error": self.last_error,
        }


@dataclass
class _Ring:
    provider_id: str
    cursor: int = 0
    states: dict[str, KeyState] = field(default_factory=dict)


class KeyRing:
    """Per-provider round-robin key selection with cooldowns."""

    def __init__(self) -> None:
        self._rings: dict[str, _Ring] = {}
        self._lock = threading.Lock()

    def _ring(self, provider_id: str) -> _Ring:
        ring = self._rings.get(provider_id)
        if ring is None:
            ring = _Ring(provider_id=provider_id)
            self._rings[provider_id] = ring
        return ring

    def _state(self, ring: _Ring, key: str, index: int, env_name: str) -> KeyState:
        digest = _digest(key)
        state = ring.states.get(digest)
        if state is None:
            state = KeyState(digest=digest, index=index, env_name=env_name)
            ring.states[digest] = state
        else:
            state.index = index
        return state

    def acquire(
        self, provider_id: str, keys: list[str], *, env_names: list[str] | None = None
    ) -> tuple[str | None, int]:
        """Return the next healthy key and its index.

        Returns ``(None, -1)`` when every key is cooling — the caller should
        treat the provider as temporarily unavailable and move on rather than
        burning an attempt on a key that is guaranteed to 429.

        A provider with no keys at all (a local Ollama, say) yields
        ``("", 0)``: an empty string means "no auth needed", distinct from
        ``None`` which means "all keys exhausted".
        """
        if not keys:
            return "", 0
        names = env_names or []
        with self._lock:
            ring = self._ring(provider_id)
            count = len(keys)
            start = ring.cursor % count
            for offset in range(count):
                index = (start + offset) % count
                env_name = names[index] if index < len(names) else ""
                state = self._state(ring, keys[index], index, env_name)
                if state.healthy:
                    ring.cursor = (index + 1) % count
                    state.requests += 1
                    state.last_used = time.time()
                    return keys[index], index
            return None, -1

    def record_success(self, provider_id: str, key: str) -> None:
        if not key:
            return
        with self._lock:
            state = self._rings.get(provider_id, _Ring(provider_id)).states.get(_digest(key))
            if state is None:
                return
            state.successes += 1
            state.consecutive_limits = 0
            state.cooling_until = 0.0
            state.last_error = ""

    def record_failure(self, provider_id: str, key: str, error: str = "") -> None:
        if not key:
            return
        with self._lock:
            state = self._rings.get(provider_id, _Ring(provider_id)).states.get(_digest(key))
            if state is None:
                return
            state.failures += 1
            state.last_error = error[:200]

    def record_rate_limit(
        self,
        provider_id: str,
        key: str,
        *,
        retry_after: float | None = None,
        quota_exhausted: bool = False,
        error: str = "",
    ) -> float:
        """Cool a key down and return the cooldown length in seconds.

        Consecutive limits on the same key double the cooldown — a key that
        keeps 429ing is probably out of quota for the window, not merely
        bursty.
        """
        if not key:
            return 0.0
        with self._lock:
            ring = self._ring(provider_id)
            state = ring.states.get(_digest(key))
            if state is None:
                state = self._state(ring, key, 0, "")
            state.rate_limits += 1
            state.failures += 1
            state.consecutive_limits += 1
            state.last_error = error[:200] or "rate limited"

            if retry_after and retry_after > 0:
                cooldown = float(retry_after)
            elif quota_exhausted:
                cooldown = QUOTA_COOLDOWN_SEC
            else:
                cooldown = DEFAULT_COOLDOWN_SEC * (2 ** (state.consecutive_limits - 1))
            cooldown = min(cooldown, MAX_COOLDOWN_SEC)
            state.cooling_until = time.monotonic() + cooldown

        log.info(
            "llm.keys: %s key #%d cooling for %.0fs (%s)",
            provider_id, state.index, cooldown, state.last_error,
        )
        return cooldown

    def all_cooling(self, provider_id: str, keys: list[str]) -> bool:
        """True when every key for the provider is in cooldown."""
        if not keys:
            return False
        with self._lock:
            ring = self._rings.get(provider_id)
            if ring is None:
                return False
            for key in keys:
                state = ring.states.get(_digest(key))
                if state is None or state.healthy:
                    return False
            return True

    def snapshot(self) -> dict[str, list[dict[str, object]]]:
        """Per-provider key health, safe to render in the dashboard."""
        with self._lock:
            return {
                pid: sorted(
                    (s.as_dict() for s in ring.states.values()),
                    key=lambda d: d["index"],  # type: ignore[index,return-value]
                )
                for pid, ring in self._rings.items()
            }

    def reset(self) -> None:
        with self._lock:
            self._rings.clear()


_ring = KeyRing()


def get_ring() -> KeyRing:
    """The process-wide key ring."""
    return _ring


def reset() -> None:
    """Test hook — clear all key statistics."""
    _ring.reset()
