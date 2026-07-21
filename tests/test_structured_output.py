"""Tests for packages/ai/structured_output.py and its integration with the Anthropic router.

Covers:
- system_instruction() for all response_format variants
- _anthropic_payload() with response_format → JSON instruction in system field
- Edge cases: unknown types, missing schema, non-dict inputs
"""
from __future__ import annotations

import pytest

from packages.ai.structured_output import system_instruction
from packages.ai.router import ProviderRouter


# ── system_instruction ────────────────────────────────────────────────────────


class TestSystemInstruction:
    def test_none_returns_none(self):
        assert system_instruction(None) is None

    def test_empty_dict_returns_none(self):
        assert system_instruction({}) is None

    def test_text_type_returns_none(self):
        assert system_instruction({"type": "text"}) is None

    def test_json_object_returns_instruction(self):
        result = system_instruction({"type": "json_object"})
        assert result is not None
        assert "JSON" in result
        assert "valid" in result.lower()

    def test_json_schema_without_schema_body_returns_fallback(self):
        result = system_instruction({"type": "json_schema"})
        assert result is not None
        assert "JSON" in result

    def test_json_schema_with_schema_includes_name_and_schema(self):
        fmt = {
            "type": "json_schema",
            "json_schema": {
                "name": "user_info",
                "schema": {"type": "object", "properties": {"name": {"type": "string"}}},
            },
        }
        result = system_instruction(fmt)
        assert result is not None
        assert "user_info" in result
        assert '"name"' in result  # schema serialized inline

    def test_json_schema_with_empty_json_schema_dict_returns_fallback(self):
        fmt = {"type": "json_schema", "json_schema": {}}
        result = system_instruction(fmt)
        assert result is not None
        assert "JSON" in result

    def test_unknown_type_returns_none(self):
        assert system_instruction({"type": "xml"}) is None

    def test_non_dict_input_returns_none(self):
        assert system_instruction("json_object") is None  # type: ignore[arg-type]
        assert system_instruction(42) is None  # type: ignore[arg-type]
        assert system_instruction([]) is None  # type: ignore[arg-type]

    def test_json_schema_bad_schema_value_returns_fallback(self):
        # A schema value that json.dumps raises on (e.g. a set) triggers the
        # except branch and falls back to the simple json_object instruction.
        fmt = {
            "type": "json_schema",
            "json_schema": {"name": "bad", "schema": {frozenset(): "x"}},
        }
        result = system_instruction(fmt)
        assert result is not None
        assert "JSON" in result

    def test_instruction_says_no_text_around_json(self):
        result = system_instruction({"type": "json_object"})
        assert result is not None
        assert "before or after" in result.lower() or "outside" in result.lower() or "only" in result.lower() or "Do not include" in result


# ── _anthropic_payload integration ───────────────────────────────────────────


def _payload(system: str = "", user: str = "Hello", **extra) -> dict:
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return {"messages": msgs, **extra}


class TestAnthropicPayloadStructuredOutput:
    def test_no_response_format_leaves_system_unchanged(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        p = _payload(system="Be helpful.")
        result = ProviderRouter._anthropic_payload(p)
        assert result["system"] == "Be helpful."

    def test_text_format_leaves_system_unchanged(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        p = _payload(system="Be helpful.", response_format={"type": "text"})
        result = ProviderRouter._anthropic_payload(p)
        assert result["system"] == "Be helpful."

    def test_json_object_appends_instruction_to_system(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        p = _payload(system="Be helpful.", response_format={"type": "json_object"})
        result = ProviderRouter._anthropic_payload(p)
        assert isinstance(result["system"], str)
        assert "Be helpful." in result["system"]
        assert "JSON" in result["system"]

    def test_json_object_no_existing_system_creates_system(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        p = _payload(response_format={"type": "json_object"})
        result = ProviderRouter._anthropic_payload(p)
        assert result["system"] is not None
        assert "JSON" in result["system"]

    def test_json_schema_appends_schema_to_system(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        fmt = {
            "type": "json_schema",
            "json_schema": {
                "name": "order",
                "schema": {"type": "object", "properties": {"id": {"type": "integer"}}},
            },
        }
        p = _payload(system="Process orders.", response_format=fmt)
        result = ProviderRouter._anthropic_payload(p)
        assert isinstance(result["system"], str)
        assert "Process orders." in result["system"]
        assert "order" in result["system"]
        assert '"id"' in result["system"]

    def test_response_format_not_forwarded_to_anthropic_body(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        p = _payload(response_format={"type": "json_object"})
        result = ProviderRouter._anthropic_payload(p)
        # Anthropic's Messages API doesn't accept response_format — must not appear
        assert "response_format" not in result

    def test_json_object_with_caching_on_uses_cache_control_list(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "true")
        p = _payload(system="Be concise.", response_format={"type": "json_object"})
        result = ProviderRouter._anthropic_payload(p)
        # When caching is on and there's system text, the system field is a list
        assert isinstance(result["system"], list)
        combined_text = result["system"][0]["text"]
        assert "Be concise." in combined_text
        assert "JSON" in combined_text

    def test_max_tokens_and_temperature_always_present(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_PROMPT_CACHING", "false")
        p = _payload(response_format={"type": "json_object"})
        result = ProviderRouter._anthropic_payload(p)
        assert "max_tokens" in result
        assert "temperature" in result
