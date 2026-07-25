"""Structured output normalization across LLM providers.

Translates the OpenAI ``response_format`` field to a system-prompt instruction
for providers whose native API does not accept the field (Anthropic, Bedrock).
For OpenAI-compatible providers the field is passed through unchanged.

Supported shapes (per the OpenAI API spec, mid-2026 edition):
  {"type": "text"}                                  — plain text (default, no-op)
  {"type": "json_object"}                           — forces valid JSON (legacy)
  {"type": "json_schema", "json_schema": {...}}     — enforces a JSON Schema
  {"type": "json_schema", "json_schema": {"strict": true, ...}}
                                                    — strict mode: schema-only or refusal

As of mid-2026, ``json_object`` is classified as legacy. The canonical pattern is
``json_schema`` with ``strict: true``, which guarantees schema compliance but may
return a ``refusal`` field in the response instead of content when the model
cannot comply.  Callers should check ``choices[0].message.refusal`` when strict
mode is requested.
"""
from __future__ import annotations

import json as _json
from typing import Any


def is_strict(response_format: dict[str, Any] | None) -> bool:
    """Return True when the caller has requested strict schema enforcement.

    Strict mode (``json_schema`` + ``strict: true``) means the model MUST
    return schema-conformant JSON or emit a ``refusal`` instead of content.
    Non-strict ``json_schema`` and legacy ``json_object`` are not strict.
    """
    if not response_format or not isinstance(response_format, dict):
        return False
    if str(response_format.get("type") or "").strip().lower() != "json_schema":
        return False
    schema_spec = response_format.get("json_schema")
    if not isinstance(schema_spec, dict):
        return False
    return bool(schema_spec.get("strict"))


def system_instruction(response_format: dict[str, Any] | None) -> str | None:
    """Return a plain-English JSON instruction for a ``response_format`` dict.

    Returns ``None`` when the format is absent, ``null``, or ``{"type": "text"}``.
    The returned string is suitable for appending to a model's system prompt
    when the provider does not natively support the ``response_format`` field.

    When ``strict: true`` is set, the instruction is strengthened: the model is
    told to produce ONLY schema-conformant JSON and to reply with a plain JSON
    object containing ``{"refusal": "<reason>"}`` if it cannot comply, rather
    than returning free-form text or partial JSON.  This mirrors what providers
    with native strict-mode support do via the ``choices[0].message.refusal``
    field.
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
        strict = bool(isinstance(schema_spec, dict) and schema_spec.get("strict"))
        if schema_spec and isinstance(schema_spec, dict):
            name = schema_spec.get("name") or "response"
            schema = schema_spec.get("schema")
            if schema:
                try:
                    schema_str = _json.dumps(schema, separators=(",", ":"))
                    if strict:
                        return (
                            f"You MUST respond with a single, valid JSON object that "
                            f"strictly conforms to the following schema — no additional "
                            f"properties, no missing required fields, no free-form text "
                            f"before or after the JSON.\n"
                            f"Schema name: {name}\n"
                            f"Schema: {schema_str}\n"
                            f"If you cannot produce a fully conformant response, reply "
                            f'with the JSON object {{"refusal": "<brief reason>"}} and '
                            f"nothing else."
                        )
                    return (
                        f"Always respond with a single, valid JSON object that conforms "
                        f"to the following schema.\n"
                        f"Schema name: {name}\n"
                        f"Schema: {schema_str}\n"
                        f"Do not include any text before or after the JSON."
                    )
                except (TypeError, ValueError):
                    pass
        if strict:
            return (
                "You MUST respond with a single, valid JSON object that strictly "
                "conforms to the requested schema. Do not include any text before or "
                "after the JSON. If you cannot comply, reply with "
                '{"refusal": "<brief reason>"} and nothing else.'
            )
        return (
            "Always respond with a single, valid JSON object. "
            "Do not include any text before or after the JSON."
        )
    return None


def extract_refusal(response_body: dict[str, Any]) -> str | None:
    """Extract the ``refusal`` string from an OpenAI-format response body.

    Returns the refusal reason string when the model declined to produce
    schema-conformant output (``choices[0].message.refusal`` is set and
    ``choices[0].message.content`` is ``None``).  Returns ``None`` when
    the response contains normal content.

    This covers both native provider refusals (providers that support strict
    mode natively) and the proxy's own convention of returning
    ``{"refusal": "..."}`` as the JSON body for providers that don't.
    """
    if not isinstance(response_body, dict):
        return None
    choices = response_body.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return None
    msg = choices[0].get("message") or {}
    if not isinstance(msg, dict):
        return None

    # Native provider refusal: message.refusal is set, content is None/null.
    native_refusal = msg.get("refusal")
    if native_refusal and msg.get("content") is None:
        return str(native_refusal)

    # Proxy convention: content is a JSON string {"refusal": "..."}.
    content = msg.get("content")
    if isinstance(content, str):
        stripped = content.strip()
        if stripped.startswith("{"):
            try:
                parsed = _json.loads(stripped)
                if isinstance(parsed, dict) and "refusal" in parsed and len(parsed) == 1:
                    return str(parsed["refusal"])
            except (ValueError, TypeError):
                pass

    return None
