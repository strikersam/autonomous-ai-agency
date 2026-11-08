"""services/e2b_config.py — Single reader of E2B sandbox environment config.

Constitution §1: this is the ONLY module that calls ``os.environ.get`` for E2B
keys or settings. Every other module must go through ``e2b_enabled()`` /
``resolve_e2b_config()`` so the secret never leaks into logs, DB rows, or
provider configs.

Mirrors the helper style in ``packages/ai/brain.py`` (``allow_paid_brain``,
``resolve_free_nvidia_brain``): a single resolution function returning a frozen
dataclass (or ``None`` when unconfigured), so callers can short-circuit without
ever touching the secret-bearing env.

Activation rule (updated post-data-flow-fix — E2B is EXPERIMENTAL until the
host↔sandbox↔repo data flow is proven on the live deploy):

  * **Explicit opt-in required**: ``E2B_ENABLED=true`` or
    ``RUNTIME_E2B_ENABLED=true`` must be set. A bare ``E2B_API_KEY`` no longer
    auto-enables E2B — the previous auto-on behaviour silently activated a
    broken execution path (host writes bypassed the sandbox, sandbox writes
    were destroyed on close, reads couldn't see the cloned repo). This
    guardrail ensures operators consciously opt in until the data-flow fixes
    are verified end-to-end on the live deploy.
  * ``E2B_ENABLED=false`` is still honoured as an explicit kill-switch.
  * ``AGENT_SANDBOX_MODE=e2b`` is also honoured as an alt activation signal
    (the roadmap ★5 kill-switch), but still requires ``E2B_API_KEY``.
  * Graceful fallback: callers that get ``None`` skip E2B and use today's
    local / MCP path — no behaviour change when E2B is off.

The key is NEVER persisted, NEVER logged, NEVER returned to a frontend. The
returned :class:`E2BConfig` carries it only for in-process SDK calls and is
intentionally not ``repr``-able.
"""
from __future__ import annotations

import importlib
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

# Default E2B sandbox lifetime. It must outlast one task attempt
# (TASK_EXECUTION_TIMEOUT_SEC, 600s by default): at 300s the sandbox died
# mid-run, the task timed out and was re-queued, and the loop repeated for
# hours. The session also refreshes this lifetime on every tool call
# (E2BSandboxSession.call_tool), so it is an idle limit, not a hard cap, and a
# leaked sandbox is still reaped 11 minutes after its last use.
_DEFAULT_TIMEOUT_SEC = 660

# Sandbox providers behind E2BSandboxSession, in auto-mode order: Freestyle
# first because its Free plan never bills, E2B as paid failover. Openers live
# in services/sandbox_providers.py; adding a name here gives it the generic
# env vars <NAME>_API_KEY, <NAME>_SNAPSHOT and <NAME>_API_URL.
PROVIDER_E2B = "e2b"
PROVIDER_FREESTYLE = "freestyle"
SANDBOX_PROVIDERS: tuple[str, ...] = (PROVIDER_FREESTYLE, PROVIDER_E2B)
# Module whose import proves a provider can run here (an SDK, or plain httpx).
_SDK_MODULE = {PROVIDER_E2B: "e2b_code_interpreter", PROVIDER_FREESTYLE: "httpx"}


_warned_unkeyed: set[str] = set()


def _provider_key(provider: str) -> str:
    return (os.environ.get(f"{provider.upper()}_API_KEY") or "").strip()


def sandbox_providers() -> list[str]:
    """The provider chain: ``SANDBOX_PROVIDER`` as an ordered list, keyed ones only.

    ``auto`` (the default) is every known provider with a key, Freestyle first
    (free), then E2B. An install with only ``E2B_API_KEY`` still gets just E2B.
    ``e2b,freestyle`` reverses the order. Unknown names are dropped with a warning.
    """
    raw = os.environ.get("SANDBOX_PROVIDER", "").strip().lower()
    names: list[str] = []
    for part in (raw or "auto").split(","):
        name = part.strip()
        if name == "auto":
            names.extend(SANDBOX_PROVIDERS)
        elif name in SANDBOX_PROVIDERS:
            names.append(name)
        elif name:
            log.warning("SANDBOX_PROVIDER: unknown provider %r ignored (known: %s)",
                        name, ", ".join(SANDBOX_PROVIDERS))
    chain = list(dict.fromkeys(names))  # de-duplicate, keep order
    keyed = [p for p in chain if _provider_key(p)]
    if chain and not keyed and raw not in ("", "auto") and raw not in _warned_unkeyed:
        # Naming only providers without a key turns sandboxing off; say so once.
        _warned_unkeyed.add(raw)
        log.warning("SANDBOX_PROVIDER=%r: none of these providers has an API key; sandboxing is off "
                    "(set %s)", raw, ", ".join(f"{p.upper()}_API_KEY" for p in chain))
    return keyed


def sandbox_provider() -> str:
    """The first provider in the chain (``e2b`` when none has a key)."""
    chain = sandbox_providers()
    return chain[0] if chain else PROVIDER_E2B


@dataclass(frozen=True)
class E2BConfig:
    """Resolved E2B sandbox configuration. Never logged in full.

    Attributes:
        api_key: E2B API key (``e2b_...``). Secret — never serialised.
        template: Sandbox template id (default ``base``).
        timeout_sec: Sandbox idle lifetime (default 660s).
        metadata: Optional metadata dict passed to ``AsyncSandbox.create``.
    """

    api_key: str
    template: str = _DEFAULT_TEMPLATE
    timeout_sec: int = _DEFAULT_TIMEOUT_SEC
    metadata: dict[str, Any] | None = None
    provider: str = PROVIDER_E2B
    api_url: str | None = None

    def __repr__(self) -> str:  # pragma: no cover - defensive
        # Never leak the key in reprs that might end up in logs.
        return (
            f"E2BConfig(provider={self.provider!r}, template={self.template!r}, "
            f"timeout_sec={self.timeout_sec}, api_key=***)"
        )

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

    **EXPERIMENTAL guardrail** (post-data-flow-fix): E2B requires explicit
    opt-in via ``E2B_ENABLED=true`` or ``RUNTIME_E2B_ENABLED=true``. A bare
    ``E2B_API_KEY`` no longer auto-enables — the previous auto-on behaviour
    silently activated a broken execution path. Operators must consciously
    opt in until the host↔sandbox↔repo data flow is verified on the live
    deploy.

    Activation requires ALL of:
      1. ``E2B_ENABLED`` is not explicitly ``false`` (kill-switch).
      2. ``E2B_ENABLED=true`` OR ``RUNTIME_E2B_ENABLED=true`` OR
         ``AGENT_SANDBOX_MODE=e2b`` (explicit opt-in).
      3. ``E2B_API_KEY`` is present and non-empty (checked in
         :func:`resolve_e2b_config`; ``e2b_enabled`` only gates the
         behavioural switch, the key gates the actual config resolution).
    """
    if _env_falsy("E2B_ENABLED"):
        # Explicit opt-out wins over everything (including AGENT_SANDBOX_MODE).
        return False
    # Require explicit opt-in: E2B_ENABLED=true, RUNTIME_E2B_ENABLED=true,
    # or AGENT_SANDBOX_MODE=e2b. A bare key is NOT enough.
    explicit_opt_in = (
        _env_truthy("E2B_ENABLED")
        or _env_truthy("RUNTIME_E2B_ENABLED")
        or _sandbox_mode_e2b()
    )
    if not explicit_opt_in:
        return False
    # Key presence is checked by resolve_e2b_config(); here we only return
    # True so callers know they should attempt E2B. The actual key read
    # happens in resolve_e2b_config() (the single env reader).
    return bool(sandbox_providers())


def resolve_e2b_config() -> E2BConfig | None:
    """Resolve the E2B sandbox config from env, or ``None`` when unconfigured.

    This is the single ``os.environ.get("E2B_API_KEY")`` read in the codebase
    (Constitution §1: no env reads outside config modules). Callers receive a
    frozen :class:`E2BConfig` they can pass to ``AsyncSandbox.create`` — the
    key never escapes this module's dataclass.

    Returns ``None`` when:
      * E2B is not explicitly enabled (see :func:`e2b_enabled`).
      * ``E2B_API_KEY`` is unset / empty.
      * ``E2B_ENABLED=false`` is explicitly set (kill-switch).
    """
    configs = resolve_sandbox_configs()
    return configs[0] if configs else None


def resolve_sandbox_configs() -> list[E2BConfig]:
    """One config per provider in the chain, in failover order ([] when off)."""
    if not e2b_enabled():
        return []
    timeout_sec, metadata = _shared_settings()
    return [_provider_config(p, timeout_sec, metadata) for p in sandbox_providers()]


def _provider_config(provider: str, timeout_sec: int, metadata: dict[str, Any] | None) -> E2BConfig:
    name = provider.upper()
    if provider == PROVIDER_E2B:
        template = (os.environ.get("E2B_TEMPLATE") or "").strip() or _DEFAULT_TEMPLATE
    else:
        # Empty = the provider's default image.
        template = (os.environ.get(f"{name}_SNAPSHOT") or "").strip()
    return E2BConfig(
        api_key=_provider_key(provider),
        template=template,
        timeout_sec=timeout_sec,
        metadata=metadata,
        provider=provider,
        api_url=(os.environ.get(f"{name}_API_URL") or "").strip() or None,
    )


def _shared_settings() -> tuple[int, dict[str, Any] | None]:
    """Lifetime and metadata, shared by every provider."""
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

    return timeout_sec, metadata


def is_e2b_sdk_importable() -> bool:
    """Cheap probe — True when any provider in the chain can run here.

    E2B needs ``e2b_code_interpreter``; Freestyle needs only ``httpx``. With no
    provider keyed, this reports on E2B as before.

    Used by :mod:`runtimes.adapters.e2b` and :mod:`services.e2b_sandbox` so a
    deploy without the optional dependency falls back to local tools instead
    of crashing on import.
    """
    for provider in sandbox_providers() or [PROVIDER_E2B]:
        try:
            importlib.import_module(_SDK_MODULE.get(provider, provider))
            return True
        except ImportError:
            continue
    return False
