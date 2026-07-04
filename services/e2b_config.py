"""services/e2b_config.py — Single reader of E2B sandbox environment config.

Constitution §1: this is the ONLY module that calls ``os.environ.get`` for E2B
keys or settings. Every other module must go through ``e2b_enabled()`` /
``resolve_e2b_config()`` so the secret never leaks into logs, DB rows, or
provider configs.

Mirrors the helper style in ``packages/ai/brain.py`` (``allow_paid_brain``,
``resolve_free_nvidia_brain``): a single resolution function returning a frozen
dataclass (or ``None`` when unconfigured), so callers can short-circuit without
ever touching the secret-bearing env.

Activation rule (matches the user decision in the E2B integration plan):

  * Auto-on whenever ``E2B_API_KEY`` is set AND ``E2B_ENABLED`` is not
    explicitly ``false``.
  * Also auto-on when ``AGENT_SANDBOX_MODE=e2b`` (the roadmap ★5 kill-switch)
    is set together with the key.
  * Graceful fallback: callers that get ``None`` (no key) skip E2B and use
    today's local / MCP path — no behaviour change when E2B is off.

The key is NEVER persisted, NEVER logged, NEVER returned to a frontend. The
returned :class:`E2BConfig` carries it only for in-process SDK calls and is
intentionally not ``repr``-able.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("qwen-proxy")

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}

# Default E2B sandbox template — "base" ships with Python, git, and shell
# utilities. Operators can override via ``E2B_TEMPLATE`` (e.g. a custom
# "python-pytest" template that pre-installs pytest for the in-sandbox
# verifier step).
_DEFAULT_TEMPLATE = "base"

# Default E2B sandbox lifetime. 300s matches the default
# ``TaskSpec.timeout_sec``; long enough for a plan→execute→verify cycle on the
# free NVIDIA brain, short enough that a leaked sandbox is reaped before the
# E2B free-tier quota is exhausted.
_DEFAULT_TIMEOUT_SEC = 300


@dataclass(frozen=True)
class E2BConfig:
    """Resolved E2B sandbox configuration. Never logged in full.

    Attributes:
        api_key: E2B API key (``e2b_...``). Secret — never serialised.
        template: Sandbox template id (default ``base``).
        timeout_sec: Sandbox hard timeout (default 300s).
        metadata: Optional metadata dict passed to ``AsyncSandbox.create``.
    """

    api_key: str
    template: str = _DEFAULT_TEMPLATE
    timeout_sec: int = _DEFAULT_TIMEOUT_SEC
    metadata: dict[str, Any] | None = None

    def __repr__(self) -> str:  # pragma: no cover - defensive
        # Never leak the key in reprs that might end up in logs.
        return f"E2BConfig(template={self.template!r}, timeout_sec={self.timeout_sec}, api_key=***)"

    def __str__(self) -> str:  # pragma: no cover - defensive
        return repr(self)


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in _TRUTHY


def _env_falsy(name: str) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    return raw in _FALSY


def _sandbox_mode_e2b() -> bool:
    """True when ``AGENT_SANDBOX_MODE=e2b`` is set (roadmap ★5 kill-switch)."""
    raw = os.environ.get("AGENT_SANDBOX_MODE", "").strip().lower()
    return raw == "e2b"


def e2b_enabled() -> bool:
    """Return ``True`` when E2B sandboxing should be activated.

    Activation requires:
      1. ``E2B_API_KEY`` present and non-empty (the actual reader is in
         :func:`resolve_e2b_config`, but we mirror the rule here so callers can
         do a cheap bool check without paying for the dataclass allocation).
      2. ``E2B_ENABLED`` not explicitly ``false`` (operator kill-switch).

    When ``E2B_ENABLED=true`` is set but no key is present, returns ``False``
    — the key is the activation signal, the flag is only the opt-out.
    """
    if _env_falsy("E2B_ENABLED"):
        # Explicit opt-out wins over everything (including AGENT_SANDBOX_MODE).
        return False
    key = (os.environ.get("E2B_API_KEY") or "").strip()
    if not key:
        return False
    # Key present and not explicitly disabled → enabled. The optional
    # AGENT_SANDBOX_MODE=e2b is also honoured (it's the canonical roadmap
    # kill-switch), but a bare key already enables E2B per the user decision.
    return True


def resolve_e2b_config() -> E2BConfig | None:
    """Resolve the E2B sandbox config from env, or ``None`` when unconfigured.

    This is the single ``os.environ.get("E2B_API_KEY")`` read in the codebase
    (Constitution §1: no env reads outside config modules). Callers receive a
    frozen :class:`E2BConfig` they can pass to ``AsyncSandbox.create`` — the
    key never escapes this module's dataclass.

    Returns ``None`` when:
      * ``E2B_API_KEY`` is unset / empty.
      * ``E2B_ENABLED=false`` is explicitly set (kill-switch).
    """
    if _env_falsy("E2B_ENABLED"):
        return None
    key = (os.environ.get("E2B_API_KEY") or "").strip()
    if not key:
        return None

    template = (os.environ.get("E2B_TEMPLATE") or "").strip() or _DEFAULT_TEMPLATE

    # Strict int parsing — a malformed env value must not silently fall back to
    # the default and hide a misconfiguration.
    timeout_raw = (os.environ.get("E2B_TIMEOUT_SEC") or "").strip()
    if timeout_raw:
        try:
            timeout_sec = int(timeout_raw)
            if timeout_sec < 30:
                log.warning(
                    "E2B_TIMEOUT_SEC=%s too low; clamping to 30s", timeout_sec
                )
                timeout_sec = 30
            elif timeout_sec > 1800:
                log.warning(
                    "E2B_TIMEOUT_SEC=%s too high; clamping to 1800s", timeout_sec
                )
                timeout_sec = 1800
        except ValueError:
            log.warning("E2B_TIMEOUT_SEC=%r is not an int; using default", timeout_raw)
            timeout_sec = _DEFAULT_TIMEOUT_SEC
    else:
        timeout_sec = _DEFAULT_TIMEOUT_SEC

    metadata: dict[str, Any] | None = None
    metadata_raw = (os.environ.get("E2B_SANDBOX_METADATA") or "").strip()
    if metadata_raw:
        # Metadata is optional and only forwarded if the operator sets it.
        # We accept a simple ``key=value,key=value`` format so it never needs
        # JSON parsing (which would be a fragile env-var pattern).
        metadata = {}
        for pair in metadata_raw.split(","):
            pair = pair.strip()
            if not pair or "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            metadata[k.strip()] = v.strip()
        if not metadata:
            metadata = None

    return E2BConfig(
        api_key=key,
        template=template,
        timeout_sec=timeout_sec,
        metadata=metadata,
    )


def is_e2b_sdk_importable() -> bool:
    """Cheap probe — True when ``e2b_code_interpreter`` is importable.

    Used by :mod:`runtimes.adapters.e2b` and :mod:`services.e2b_sandbox` so a
    deploy without the optional dependency falls back to local tools instead
    of crashing on import.
    """
    try:
        import e2b_code_interpreter  # noqa: F401
        return True
    except ImportError:
        return False
