"""packages/integrations/render_env.py — write a single Render env var over REST.

The admin Providers UI edits a provider's key/base_url, but the runtime brain
(``services/brain_failover``) reads those from **environment variables**, not
from the Mongo ``providers`` collection. So a UI edit never reached the running
process. This module closes that gap: it pushes one provider's key/base_url into
the Render service's environment, where the runtime actually reads it.

Why REST and not the Render MCP: the MCP's ``update_environment_variables`` tool
**replaces the service's entire env-var list** — a partial list silently drops
every other secret. Render's REST API has a single-variable endpoint
(``PUT /v1/services/{id}/env-vars/{key}``) that updates one variable and leaves
the rest untouched, which is the only safe shape for "edit one provider's key".

Secret handling (rule 6): the value is taken from the request, sent straight to
Render over TLS, and never written to disk or logged — not even partially.
Callers pass credentials in; this module reads no environment itself.
"""
from __future__ import annotations

import logging

import httpx

log = logging.getLogger("qwen-proxy")

_RENDER_API_BASE = "https://api.render.com/v1"


class RenderEnvError(RuntimeError):
    """Raised when Render rejects or cannot serve an env-var write."""


def provider_env_names(provider_id: str) -> tuple[str, str] | None:
    """Return ``(key_env, base_url_env)`` for a provider id, or ``None``.

    Sourced from ``services.brain_failover._PROVIDER_REGISTRY`` so the UI cannot
    write an arbitrary environment variable — only the ones a known provider
    actually reads. ``base_url_env`` may be an empty string for providers that
    have no configurable base URL.
    """
    from services.brain_failover import _PROVIDER_REGISTRY

    pid = (provider_id or "").strip().lower()
    for entry in _PROVIDER_REGISTRY:
        if str(entry.get("id", "")).lower() == pid:
            return str(entry.get("key_env") or ""), str(entry.get("base_url_env") or "")
    return None


async def update_service_env_var(
    service_id: str,
    key: str,
    value: str,
    *,
    api_key: str,
    timeout: float = 20.0,
) -> None:
    """Set one environment variable on a Render service via the REST API.

    Updates a single variable in place — the service's other env vars are left
    untouched. Render applies the change and, for a service with auto-deploy on,
    rolls it out on the next deploy. Raises ``RenderEnvError`` on any failure;
    the caller maps that onto a generic HTTP error (the exception text may quote
    Render's response, which does not belong in a client body).

    The value is never logged.
    """
    if not (service_id and key and api_key):
        raise RenderEnvError("Render env write is not configured")

    url = f"{_RENDER_API_BASE}/services/{service_id}/env-vars/{key}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.put(
                url,
                json={"value": value},
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
    except httpx.HTTPError as exc:  # transport failure — never includes the value
        log.warning("Render env write transport error for %s: %s", key, exc)
        raise RenderEnvError("Render unreachable") from exc

    if resp.status_code >= 400:
        # Log the status and key name only — never the body (it can echo the
        # value) and never the value itself.
        log.warning("Render env write for %s failed: HTTP %s", key, resp.status_code)
        raise RenderEnvError(f"Render returned HTTP {resp.status_code}")

    log.info("Render env var %s updated on service %s", key, service_id)


__all__ = ["RenderEnvError", "provider_env_names", "update_service_env_var"]
