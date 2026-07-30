"""Per-provider API key rotation — the one lever that adds capacity.

Every other rate-limit mechanism in this repo *rations* a fixed budget:
distribution spreads it, pacing meters it, backoff waits for it. None of them
create capacity. When a fleet is genuinely at its ceiling — as ours is, with
four usable free providers carrying all traffic — the only code-level fix that
raises the ceiling is using more than one free-tier account per provider.

Rate limits are commonly enforced **per key**, so where an operator legitimately
holds more than one key for a provider — separate projects, separate
organisations, a paid key alongside a free one — using them in rotation raises
the effective ceiling, and the provider only needs cooling once *all* its keys
are spent rather than the first.

## This is opt-in per provider, deliberately

Rotation is **off unless the operator sets ``<PROVIDER>_KEY_ROTATION=true``**,
even when sibling variables are present. That gate is not ceremony:

> Several providers' acceptable-use policies prohibit registering additional
> accounts in order to exceed published rate limits. Groq's rate-limit
> documentation states limits are per *organisation* and its policy forbids
> orchestrating accounts around them. Automatically discovering
> ``<KEY>_2`` and using it would let this platform commit a terms violation on
> the operator's behalf from nothing more than an env var being present.

So the mechanism exists, and engaging it is a decision someone takes for a
provider whose terms they have read. **Do not enable it to work around a
provider's published limits.** Legitimate uses are keys you are already entitled
to use concurrently.

    ACME_API_KEY=primary
    ACME_API_KEY_2=second-key-you-are-entitled-to-use
    ACME_KEY_ROTATION=true

With a single key — or with rotation not enabled — the pool is a pass-through:
``next_key`` always returns the primary and ``mark_rate_limited`` leaves the
existing provider-level cooldown to do its job exactly as before.

No key material is ever logged or returned by ``snapshot()``. Keys are
identified in diagnostics by a short digest keyed with a per-process random
salt, never by a prefix or suffix of the key itself.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger("qwen-proxy")

# Per-process salt for the diagnostic digests below. Regenerated on every start,
# never persisted, never logged. See `_digest`.
_DIGEST_SALT: bytes = secrets.token_bytes(32)

# A key that returns 429 sits out for this long unless the response carried a
# Retry-After. Deliberately shorter than a provider-level cooldown: the point of
# a pool is that a spent key steps aside for its siblings, not that the whole
# provider stops.
_DEFAULT_KEY_COOLDOWN_SEC: float = 60.0
_MAX_KEY_COOLDOWN_SEC: float = 300.0


def _digest(key: str) -> str:
    """Short label for a key, **stable only within this process**.

    Keyed with a per-process random salt rather than a bare hash. An unsalted
    `sha256(key)[:8]` is a deterministic fingerprint: the same key produces the
    same label in every process and every deployment forever, so a label
    captured from a log can be matched against a candidate key offline, and two
    logs can be correlated as using the same account. Salting per process makes
    the label useful for reading one process's logs — which is all it is for —
    and useless for anything else.

    Never a prefix or suffix of the key itself: a leading fragment of an API key
    is enough to identify an account in a leaked log, and for some providers it
    identifies the key outright.
    """
    return hashlib.blake2b(
        key.encode("utf-8"), key=_DIGEST_SALT, digest_size=4
    ).hexdigest()


def api_keys_for(provider_id: str, base_env: str) -> list[str]:
    """All keys configured for *provider_id*, primary first.

    Thin delegate to ``brain_config.provider_api_keys`` — the environment is
    read there because that module is the only one permitted to read it
    (CLAUDE.md §3), and a secret-discovery path in particular belongs where the
    project's config review looks for it. Sibling keys are only returned when
    the provider has been explicitly opted in; see
    ``provider_key_rotation_enabled``.
    """
    from packages.ai.brain_config import provider_api_keys
    return provider_api_keys(provider_id, base_env)


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
