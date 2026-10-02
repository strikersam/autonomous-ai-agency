"""packages/gateway/config.py — the one place gateway settings are read from the environment.

This is a config module in the sense of CLAUDE.md rule 5: it is the only file in
``packages/gateway/`` allowed to call ``os.environ.get()``. Every reader below
looks the variable up at call time (never at import), which is what lets the
dashboard's Platform controls flip them live — an override is written into
``os.environ`` by :mod:`packages.config.control_overrides`.

Every default reproduces the pre-hardening behaviour, except the security
response headers, which default on per CLAUDE.md rule 41.
"""

from __future__ import annotations

import os

_TRUTHY = ("1", "true", "yes", "on")
_SANITIZER_MODES = ("off", "pii", "secrets_and_pii")


def _raw(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _flag(name: str, default: bool) -> bool:
    raw = _raw(name)
    if not raw:
        return default
    return raw.lower() in _TRUTHY


def _non_negative_int(name: str) -> int:
    try:
        return max(0, int(_raw(name, "0") or "0"))
    except ValueError:
        return 0


def max_request_bytes() -> int:
    """``GATEWAY_MAX_REQUEST_BYTES`` — request body ceiling; 0 disables the check."""
    return _non_negative_int("GATEWAY_MAX_REQUEST_BYTES")


def security_headers_enabled() -> bool:
    """``GATEWAY_SECURITY_HEADERS_ENABLED`` — default true (rule 41)."""
    return _flag("GATEWAY_SECURITY_HEADERS_ENABLED", True)


def tokens_per_minute() -> int:
    """``GATEWAY_TOKENS_PER_MINUTE`` — per-consumer token quota; 0 disables."""
    return _non_negative_int("GATEWAY_TOKENS_PER_MINUTE")


def tokens_per_day() -> int:
    """``GATEWAY_TOKENS_PER_DAY`` — per-consumer daily token quota; 0 disables."""
    return _non_negative_int("GATEWAY_TOKENS_PER_DAY")


def prompt_policy_enabled() -> bool:
    """``GATEWAY_PROMPT_POLICY_ENABLED`` — default false."""
    return _flag("GATEWAY_PROMPT_POLICY_ENABLED", False)


def prompt_policy_file() -> str:
    """``GATEWAY_PROMPT_POLICY_FILE`` — deploy wiring (a path), so env-only."""
    return _raw("GATEWAY_PROMPT_POLICY_FILE")


def sanitizer_mode() -> str:
    """``GATEWAY_SANITIZER_MODE`` — ``off`` | ``pii`` | ``secrets_and_pii``."""
    mode = _raw("GATEWAY_SANITIZER_MODE", "off").lower()
    return mode if mode in _SANITIZER_MODES else "off"


def usage_metrics_enabled() -> bool:
    """``GATEWAY_USAGE_METRICS_ENABLED`` — default false."""
    return _flag("GATEWAY_USAGE_METRICS_ENABLED", False)


def upstream_retries() -> int:
    """``GATEWAY_UPSTREAM_RETRIES`` — extra attempts per upstream POST; 0 = none."""
    return min(_non_negative_int("GATEWAY_UPSTREAM_RETRIES"), 10)


def proxy_cache_enabled() -> bool:
    """``GATEWAY_PROXY_CACHE_ENABLED`` — default false."""
    return _flag("GATEWAY_PROXY_CACHE_ENABLED", False)
