"""Structured output normalization across LLM providers.

Translates the OpenAI ``response_format`` field to a system-prompt instruction
for providers whose native API does not accept the field (Anthropic, Bedrock).
For OpenAI-compatible providers the field is passed through unchanged.

Supported shapes (per the OpenAI API spec):
  {"type": "text"}                                  — plain text (default, no-op)
  {"type": "json_object"}                           — forces valid JSON
  {"type": "json_schema", "json_schema": {...}}     — enforces a JSON Schema
"""
from __future__ import annotations

import json as _json
from typing import Any


def system_instruction(response_format: dict[str, Any] | None) -> str | None:
    """Return a plain-English JSON instruction for a ``response_format`` dict.

    Returns ``None`` when the format is absent, ``null``, or ``{"type": "text"}``.
    The returned string is suitable for appending to a model's system prompt
    when the provider does not natively support the ``response_format`` field.
    """
    if not response_format or not isinstance(response_format, dict):
        return None
    fmt_type = str(response_format.get("type") or "").strip().lower()
    if fmt_type in ("", "text"):
        return None
    if fmt_type == "json_object":
        return (
            "Always respond with a single, valid JSON object. "
            "Do not include any text before or after the JSON."
        )
    if fmt_type == "json_schema":
        schema_spec = response_format.get("json_schema")
        if schema_spec and isinstance(schema_spec, dict):
            name = schema_spec.get("name") or "response"
            schema = schema_spec.get("schema")
            if schema:
                try:
                    schema_str = _json.dumps(schema, separators=(",", ":"))
                    return (
                        f"Always respond with a single, valid JSON object that conforms "
                        f"to the following schema.\n"
                        f"Schema name: {name}\n"
                        f"Schema: {schema_str}\n"
                        f"Do not include any text before or after the JSON."
                    )
                except (TypeError, ValueError):
                    pass
        return (
            "Always respond with a single, valid JSON object. "
            "Do not include any text before or after the JSON."
        )
    return None
