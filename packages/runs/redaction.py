"""packages/runs/redaction.py — scrub secrets from anything a run persists.

Run events, failure reasons and (later) artifacts are stored and served back to
the dashboard, so every string inside them goes through
``packages.security.redact.redact_secrets`` before it is written, plus the run
specific patterns below (shapes the shared redactor does not cover), and every
value stored under a sensitive dict key is replaced outright.
"""
from __future__ import annotations

import re
from typing import Any

from packages.security.redact import redact_secrets

_MAX_DEPTH = 20
_REDACTED = "***"

# A dict key naming a credential: its value is replaced whatever its shape.
_SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key|authorization"
    r"|credential|cookie)"
)

# Shapes the shared redactor misses. Group 1, when present, is the secret part.
_RUN_PATTERNS: tuple[re.Pattern[str], ...] = (
    # PEM private key blocks (RSA, EC, OPENSSH, PKCS#8, encrypted).
    # A block cut off before its END marker is redacted to the end of the text.
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)"),
    # Python repr credential pairs: 'password': 'value'.
    re.compile(
        r"(?i)'[\w. -]*(?:password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key"
        r"|authorization|credential|cookie)[\w. -]*'\s*:\s*'((?:[^'\\]|\\.)+)'"
    ),
    # JSON quoted credential pairs: "api_key": "value" (the key stays readable).
    re.compile(
        r"(?i)\"[\w. -]*(?:password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key"
        r"|authorization|credential|cookie)[\w. -]*\"\s*:\s*\"((?:[^\"\\]|\\.)+)\""
    ),
    # JSON Web Tokens: three base64url segments, the first two starting with eyJ.
    re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]+"),
    # Slack bot, app, user and refresh tokens.
    re.compile(r"(?<![A-Za-z0-9])xox[abeprs]-[A-Za-z0-9-]{10,}"),
)


def redact_text(text: str) -> str:
    """Redact *text* with the run specific patterns, then the shared redactor."""
    if not text:
        return text
    for pattern in _RUN_PATTERNS:
        text = pattern.sub(
            lambda m: m.group(0).replace(m.group(1), _REDACTED) if m.groups() else _REDACTED,
            text,
        )
    return redact_secrets(text)


def is_sensitive_key(key: Any) -> bool:
    """True when a dict key names a credential (case insensitive)."""
    return isinstance(key, str) and _SENSITIVE_KEY_RE.search(key) is not None


def _secret_shaped(value: Any) -> bool:
    # Numbers and booleans under such a key are counters and fencing tokens
    # (``token``, ``lease_token``, ``max_tokens``), not credentials.
    return value not in (None, "") and not isinstance(value, (bool, int, float))


def _redact_key(key: Any) -> Any:
    """A dict key can carry a secret too; ordinary keys come back unchanged."""
    return redact_text(key) if isinstance(key, str) else key


def redact_value(value: Any, _depth: int = 0) -> Any:
    """Return *value* with every string (dict values, list items, nested) redacted.

    Dict keys are redacted like text (ordinary keys are unchanged) and bytes are
    decoded and redacted; a value under a sensitive key (password,
    secret, token, api_key, authorization, credential) is replaced whatever its
    type. Non string scalars elsewhere pass through. Nesting beyond a sane depth
    is replaced rather than walked, so a cyclic or hostile structure cannot
    recurse without bound.
    """
    if _depth > _MAX_DEPTH:
        return "[truncated]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (bytes, bytearray)):  # stored as text, so it is redacted too
        return redact_text(bytes(value).decode("utf-8", errors="replace"))
    if isinstance(value, dict):
        return {_redact_key(k): (_REDACTED if is_sensitive_key(k) and _secret_shaped(v)
                                 else redact_value(v, _depth + 1)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(v, _depth + 1) for v in value]
    return value
