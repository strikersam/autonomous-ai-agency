"""Per-provider API key rotation — the one lever that adds capacity.

Every other rate-limit mechanism in this repo *rations* a fixed budget:
distribution spreads it, pacing meters it, backoff waits for it. None of them
create capacity. When a fleet is genuinely at its ceiling — as ours is, with
four usable free providers carrying all traffic — the only code-level fix that
raises the ceiling is using more than one free-tier account per provider.

Free tiers are rate-limited **per key**, not per provider. Three Groq keys is
three times the requests per minute, and the provider only needs to go into
cooldown once *all* of its keys are spent rather than the first.

Configuration is a numbered suffix on the provider's existing key variable, so
nothing changes for an operator who has one key:

    GROQ_API_KEY=gsk_first
    GROQ_API_KEY_2=gsk_second
    GROQ_API_KEY_3=gsk_third

With a single key the pool is a pass-through: ``next_key`` always returns it and
``mark_rate_limited`` leaves the existing provider-level cooldown to do its job
exactly as before. Rotation only engages once a second key exists.

**Only use extra keys where the provider's terms allow it.** Several free tiers
permit multiple accounts; some do not. This module gives you the mechanism —
whether a given provider permits it is your call, not something code can check.

No key material is ever logged or returned by ``snapshot()``. Keys are
identified in diagnostics by a short salted digest, never by a prefix or suffix
of the key itself.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger("llm-key-pool")

# How many numbered suffixes to probe past the base variable. Ten accounts per
# provider is far beyond any plausible legitimate setup; the loop stops at the
# first gap anyway, so this is only a guard against an unbounded scan.
_MAX_EXTRA_KEYS: int = 10

# A key that returns 429 sits out for this long unless the response carried a
# Retry-After. Deliberately shorter than a provider-level cooldown: the point of
# a pool is that a spent key steps aside for its siblings, not that the whole
# provider stops.
_DEFAULT_KEY_COOLDOWN_SEC: float = 60.0
_MAX_KEY_COOLDOWN_SEC: float = 300.0


def _digest(key: str) -> str:
    """Short, stable, non-reversible label for a key (diagnostics only).

    Never a prefix or suffix of the key itself: a leading fragment of an API key
    is enough to identify an account in a leaked log, and for some providers it
    identifies the key outright.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def api_keys_for(base_env: str) -> list[str]:
    """All configured keys for the variable *base_env*, in priority order.

    Reads ``BASE`` then ``BASE_2``, ``BASE_3`` … stopping at the first gap so a
    typo'd ``_4`` cannot silently promote itself into the ``_2`` slot. Duplicates
    are dropped — the same key twice is not two budgets, and treating it as two
    would double the apparent capacity while halving the real cooldown.
    """
    keys: list[str] = []
    primary = (os.environ.get(base_env) or "").strip()
    if primary:
        keys.append(primary)
    for index in range(2, _MAX_EXTRA_KEYS + 2):
        value = (os.environ.get(f"{base_env}_{index}") or "").strip()
        if not value:
            break
        if value not in keys:
            keys.append(value)
    return keys


@dataclass
class _KeyState:
    cooling_until: float = 0.0
    total_uses: int = 0
    total_rate_limited: int = 0


@dataclass
class _PoolState:
    cursor: int = 0
    keys: dict[str, _KeyState] = field(default_factory=dict)


class KeyPool:
    """Round-robin key selection with per-key rate-limit cooldowns."""

    def __init__(self) -> None:
        self._pools: dict[str, _PoolState] = {}
        self._lock = threading.Lock()

    def _pool(self, provider_id: str) -> _PoolState:
        pool = self._pools.get(provider_id)
        if pool is None:
            pool = _PoolState()
            self._pools[provider_id] = pool
        return pool

    def next_key(self, provider_id: str, keys: list[str]) -> str | None:
        """Return the next usable key, or None when every key is cooling.

        With one key this returns it unconditionally even while cooling: a
        single-key provider has no sibling to fall back to, so withholding it
        would turn a provider-level cooldown (which the caller already handles)
        into a hard outage. Rotation semantics only apply from two keys up.
        """
        if not keys:
            return None
        if len(keys) == 1:
            return keys[0]

        now = time.monotonic()
        with self._lock:
            pool = self._pool(provider_id)
            count = len(keys)
            for offset in range(count):
                index = (pool.cursor + offset) % count
                key = keys[index]
                state = pool.keys.setdefault(key, _KeyState())
                if state.cooling_until > now:
                    continue
                pool.cursor = (index + 1) % count
                state.total_uses += 1
                return key
        return None

    def mark_rate_limited(
        self,
        provider_id: str,
        key: str,
        *,
        retry_after_sec: float | None = None,
    ) -> None:
        """Cool a single key after a 429 from it.

        Honours the provider's own ``Retry-After`` when present, clamped so a
        hostile or malformed value cannot park a key indefinitely.
        """
        wait = _DEFAULT_KEY_COOLDOWN_SEC
        if retry_after_sec is not None and retry_after_sec > 0:
            wait = min(retry_after_sec, _MAX_KEY_COOLDOWN_SEC)
        with self._lock:
            pool = self._pool(provider_id)
            state = pool.keys.setdefault(key, _KeyState())
            state.cooling_until = time.monotonic() + wait
            state.total_rate_limited += 1
        log.info(
            "key_pool: %s key %s rate-limited — resting %.0fs (%d key(s) in pool)",
            provider_id, _digest(key), wait, len(pool.keys),
        )

    def all_cooling(self, provider_id: str, keys: list[str]) -> bool:
        """True when every key in the pool is resting.

        This is the signal that the *provider* should now be cooled: with keys
        still available, a 429 from one of them says nothing about the others.
        """
        if len(keys) <= 1:
            return True
        now = time.monotonic()
        with self._lock:
            pool = self._pool(provider_id)
            return all(
                pool.keys.get(key, _KeyState()).cooling_until > now for key in keys
            )

    def snapshot(self) -> dict[str, object]:
        """Diagnostics. Contains no key material — digests only."""
        now = time.monotonic()
        out: dict[str, object] = {}
        with self._lock:
            for provider_id, pool in self._pools.items():
                out[provider_id] = {
                    "keys": len(pool.keys),
                    "resting": sum(
                        1 for s in pool.keys.values() if s.cooling_until > now
                    ),
                    "detail": [
                        {
                            "id": _digest(key),
                            "resting_for_s": (
                                round(state.cooling_until - now, 1)
                                if state.cooling_until > now
                                else 0.0
                            ),
                            "uses": state.total_uses,
                            "rate_limited": state.total_rate_limited,
                        }
                        for key, state in pool.keys.items()
                    ],
                }
        return out

    def reset(self) -> None:
        """Clear all state (tests only)."""
        with self._lock:
            self._pools.clear()


_POOL = KeyPool()


def get_pool() -> KeyPool:
    """Return the process-singleton KeyPool."""
    return _POOL


def reset() -> None:
    """Clear pool state (tests only)."""
    _POOL.reset()
