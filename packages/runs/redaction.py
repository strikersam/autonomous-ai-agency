"""packages/runs/redaction.py — scrub secrets from anything a run persists.

Run events, failure reasons and (later) artifacts are stored and served back to
the dashboard, so every string inside them goes through
``packages.security.redact.redact_secrets`` before it is written.
"""
from __future__ import annotations

from typing import Any

from packages.security.redact import redact_secrets

_MAX_DEPTH = 20


def redact_value(value: Any, _depth: int = 0) -> Any:
    """Return *value* with every string (dict values, list items, nested) redacted.

    Dict keys are kept as they are; non string scalars pass through. Nesting
    beyond a sane depth is replaced rather than walked, so a cyclic or hostile
    structure cannot recurse without bound.
    """
    if _depth > _MAX_DEPTH:
        return "[truncated]"
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {k: redact_value(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_value(v, _depth + 1) for v in value]
    return value
