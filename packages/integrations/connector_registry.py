"""packages/integrations/connector_registry.py — the connector catalogue.

The agency competes on the same ground as n8n / Make / Zapier: orchestrating
multi-step work across external services. Those products' moat is a large
catalogue of *connectors* — typed, discoverable integrations an operator can
wire into a workflow. This module is the first, deliberately small step toward
that: a registry abstraction plus one real, credential-free connector (an
outbound webhook action).

Design mirrors ``mcp_registry.MCPServerSpec`` — a declarative ``ConnectorSpec``
dataclass with an ``as_dict()`` for the API/UI, and a ``_connectors()``
catalogue factory read live rather than frozen at import. More connectors
(Slack, Google Sheets, …) are added as their own specs + executors in later PRs.

Nothing here reads environment variables directly (see the package docstring);
per-connector configuration requirements are declared in ``requires`` and read
by config modules.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

# The SSRF boundary (CLAUDE.md rule 14). A webhook URL is operator- or
# LLM-supplied — an attacker-influenceable target in the classic SSRF sense —
# so every outbound request must clear this guard before the first hop, and
# redirects must never be auto-followed.
from agent.web_reach import unsafe_target_reason

log = logging.getLogger("qwen-proxy")

# Outbound webhook safety envelope. Kept small and explicit rather than
# configurable, so a connector cannot be turned into an exfiltration or
# amplification primitive by config alone.
_WEBHOOK_TIMEOUT_SECONDS = 10.0
_WEBHOOK_MAX_BYTES = 64 * 1024


@dataclass
class ConnectorSpec:
    """A declared connector, independent of whether it is currently usable.

    ``auth_type`` and ``requires`` tell the UI what an operator must provide
    before the connector can run; ``kind`` distinguishes an *action* (the
    agency calls out) from a future *trigger* (an event calls in).
    """

    connector_id: str
    name: str
    description: str
    category: str
    kind: str                              # "action" | "trigger"
    auth_type: str                         # "none" | "api_key" | "oauth"
    requires: tuple[str, ...] = ()         # env/setting names an operator must set
    available: bool = True                 # False for catalogue-only placeholders

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.connector_id,
            "name": self.name,
            "desc": self.description,
            "category": self.category,
            "kind": self.kind,
            "auth_type": self.auth_type,
            "requires": list(self.requires),
            "available": self.available,
        }


def _connectors() -> list[ConnectorSpec]:
    """Return the connector catalogue. Read live so it can grow at runtime."""
    return [
        ConnectorSpec(
            connector_id="webhook",
            name="Outbound Webhook",
            description=(
                "POST a JSON event to any public HTTPS URL. The Zapier-style "
                "action primitive: notify Slack, trigger a build, or fan out to "
                "another automation. No credentials required."
            ),
            category="messaging",
            kind="action",
            auth_type="none",
            requires=(),
            available=True,
        ),
    ]


def list_connectors() -> list[dict[str, Any]]:
    """Return the catalogue as plain dicts. Cheap; used by the API, UI, tests."""
    return [c.as_dict() for c in _connectors()]


def get_connector(connector_id: str) -> ConnectorSpec | None:
    """Return the spec for *connector_id*, or None if it is not registered."""
    for spec in _connectors():
        if spec.connector_id == connector_id:
            return spec
    return None


async def send_webhook(
    url: str,
    payload: dict[str, Any] | None = None,
    *,
    event: str | None = None,
) -> dict[str, Any]:
    """Execute the ``webhook`` connector: POST *payload* as JSON to *url*.

    Fails soft — always returns a result dict, never raises — so a caller
    (an agent, a workflow step, the API) can read the outcome. The URL clears
    ``unsafe_target_reason`` first (rule 14) and redirects are not followed:
    a redirect to a private address must not become an SSRF bypass.

    Never logs the payload or URL query (either may carry a secret — rule 6);
    only the connector id and the resulting status are logged.
    """
    reason = unsafe_target_reason(url)
    if reason is not None:
        log.warning("connector webhook rejected: unsafe target (%s)", reason)
        return {"ok": False, "error": f"unsafe target: {reason}"}

    body: dict[str, Any] = {"event": event or "webhook", "data": payload or {}}
    try:
        async with httpx.AsyncClient(
            timeout=_WEBHOOK_TIMEOUT_SECONDS, follow_redirects=False
        ) as client:
            resp = await client.post(url, json=body)
    except httpx.HTTPError as exc:
        # Type name only — the message can echo the (secret-bearing) URL.
        log.info("connector webhook failed: %s", type(exc).__name__)
        return {"ok": False, "error": f"request failed: {type(exc).__name__}"}

    # A 3xx is a redirect we deliberately did not follow — surface it, don't chase.
    if 300 <= resp.status_code < 400:
        return {
            "ok": False,
            "status": resp.status_code,
            "error": "target returned a redirect; not followed (SSRF guard)",
        }

    snippet = resp.text[:_WEBHOOK_MAX_BYTES] if resp.text else ""
    ok = 200 <= resp.status_code < 300
    log.info("connector webhook sent: status=%s ok=%s", resp.status_code, ok)
    return {"ok": ok, "status": resp.status_code, "response_snippet": snippet}
