"""services/sandbox_providers.py — Registry of sandbox providers and failover.

:class:`services.e2b_sandbox.E2BSandboxSession` runs every agent tool call
through six calls on its sandbox object, the E2B ``AsyncSandbox`` surface:

* ``await commands.run(cmd, timeout=..., background=False)`` → object with
  ``stdout``, ``stderr``, ``exit_code`` (a non-zero exit may be returned or
  raised with an ``exit_code`` attribute; the session handles both)
* ``await files.write(path, str | bytes)`` / ``await files.read(path) -> str``
  (a missing file raises ``FileNotFoundError``)
* ``await set_timeout(seconds)`` — keepalive
* ``get_host(port) -> str`` (sync or async) — public host for a preview
* ``await kill()``

A provider is an async *opener* ``(E2BConfig) -> sandbox`` returning an object
with that surface. To add one:

1. write ``services/<name>_sandbox.py`` with the opener,
2. add its name to ``SANDBOX_PROVIDERS`` in :mod:`services.e2b_config`
   (it then reads ``<NAME>_API_KEY``, ``<NAME>_SNAPSHOT``, ``<NAME>_API_URL``),
3. register the opener in ``_BUILTIN`` below.

``SANDBOX_PROVIDER`` takes an ordered list (``freestyle,daytona,instabox,e2b``):
:func:`open_first_available` tries each provider in turn and returns the
first sandbox that opens, so a provider out of quota fails over to the next.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
from typing import Any, Awaitable, Callable

from services.e2b_config import _SDK_MODULE
from services.e2b_config import (
    PROVIDER_DAYTONA,
    PROVIDER_E2B,
    PROVIDER_FREESTYLE,
    PROVIDER_INSTABOX,
    E2BConfig,
)

log = logging.getLogger("qwen-proxy")

Opener = Callable[[E2BConfig], Awaitable[Any]]


async def _open_e2b(config: E2BConfig) -> Any:
    """Create an E2B ``AsyncSandbox`` (needs ``e2b-code-interpreter``)."""
    from e2b_code_interpreter import AsyncSandbox

    return await AsyncSandbox.create(
        api_key=config.api_key,
        timeout=config.timeout_sec,
        **({"template": config.template} if config.template else {}),
        **({"metadata": config.metadata} if config.metadata else {}),
    )


async def _open_freestyle(config: E2BConfig) -> Any:
    from services import freestyle_sandbox

    return await freestyle_sandbox.open_freestyle_sandbox(config)


async def _open_daytona(config: E2BConfig) -> Any:
    from services import daytona_sandbox

    return await daytona_sandbox.open_daytona_sandbox(config)


async def _open_instabox(config: E2BConfig) -> Any:
    from services import instabox_sandbox

    return await instabox_sandbox.open_instabox_sandbox(config)


_BUILTIN: dict[str, Opener] = {
    PROVIDER_E2B: _open_e2b,
    PROVIDER_FREESTYLE: _open_freestyle,
    PROVIDER_DAYTONA: _open_daytona,
    PROVIDER_INSTABOX: _open_instabox,
}
_openers: dict[str, Opener] = dict(_BUILTIN)


def register_sandbox_provider(name: str, opener: Opener) -> None:
    """Register (or replace) the opener for provider *name*."""
    _openers[name.strip().lower()] = opener


def get_opener(name: str) -> Opener | None:
    return _openers.get(name)


async def _warm_sdk(provider: str) -> None:
    """Import *provider*'s SDK in a worker thread, before its opener imports it inline.

    The first import of the Daytona SDK builds hundreds of pydantic models and held the
    event loop for ~10 s on Render's free instance, failing the health check. A missing
    SDK is left for the opener to report.
    """
    try:
        await asyncio.to_thread(importlib.import_module, _SDK_MODULE.get(provider, provider))
    except ImportError:
        pass


async def open_first_available(configs: list[E2BConfig]) -> tuple[Any, E2BConfig]:
    """Open a sandbox with the first provider in *configs* that succeeds.

    Raises ``RuntimeError`` naming every provider's failure when none opens.
    """
    failures: list[str] = []
    for config in configs:
        opener = get_opener(config.provider)
        if opener is None:
            failures.append(f"{config.provider}: no opener registered")
            continue
        try:
            await _warm_sdk(config.provider)
            return await opener(config), config
        except Exception as exc:  # noqa: BLE001 - one provider down must not stop the chain
            log.warning("Sandbox provider %s failed to open; trying the next: %s", config.provider, exc)
            failures.append(f"{config.provider}: {exc}")
    raise RuntimeError("; ".join(failures) or "no sandbox provider configured")
