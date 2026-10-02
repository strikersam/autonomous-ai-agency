"""packages/gateway/sanitizer.py — outbound prompt sanitiser.

Redacts sensitive values from the prompt before it leaves for an upstream
provider, reusing the patterns in :mod:`packages.security.redact` so there is one
list to maintain. ``GATEWAY_SANITIZER_MODE``:

* ``off`` (default) — the payload passes through untouched;
* ``pii`` — social-security numbers and Luhn-valid card numbers;
* ``secrets_and_pii`` — everything ``redact_secrets`` covers: connection-URI
  credentials, vendor API tokens, bearer headers, ``key=value`` secret
  assignments, plus the PII above.

String content and the text parts of multimodal content are handled; images
and tool payloads are not touched. The mode is read per request, so a
dashboard change applies immediately.
"""

from __future__ import annotations

from typing import Any, Callable

from packages.gateway import config
from packages.gateway.messages import map_texts
from packages.security.redact import _redact_pii, redact_secrets


def _redactor(mode: str) -> Callable[[str], str] | None:
    if mode == "pii":
        return _redact_pii
    if mode == "secrets_and_pii":
        return redact_secrets
    return None


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return *payload* with prompt text redacted per the configured mode."""
    redactor = _redactor(config.sanitizer_mode())
    if redactor is None:
        return payload
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload
    return {**payload, "messages": map_texts(messages, redactor)}
