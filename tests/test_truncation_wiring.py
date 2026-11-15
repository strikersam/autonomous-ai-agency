"""A reply cut off at the provider's output limit must not pass as complete.

Before this, the router's Anthropic, Ollama-native and Bedrock translations
hardcoded ``finish_reason: "stop"``, the failover client dropped the reason, and
the agent loop parsed whatever text came back, so a plan truncated at
``max_tokens`` was treated as a whole (malformed) answer.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from agent.loop import AgentRunner
from agent.truncation_guard import TruncatedResponseError
from packages.ai.failover_client import _finish_reason
from packages.ai.router import ProviderRouter, _openai_finish_reason


def _resp(body: dict) -> httpx.Response:
    return httpx.Response(200, content=json.dumps(body).encode(),
                          headers={"content-type": "application/json"})


@pytest.mark.parametrize("native, expected", [
    ("max_tokens", "length"), ("length", "length"), ("MAX_TOKENS", "length"),
    ("end_turn", "stop"), ("tool_use", "stop"), ("stop", "stop"), (None, "stop"),
])
def test_finish_reason_mapping(native, expected) -> None:
    assert _openai_finish_reason(native) == expected


def test_anthropic_translation_reports_truncation() -> None:
    body = {"content": [{"type": "text", "text": "partial"}], "stop_reason": "max_tokens",
            "usage": {"input_tokens": 1, "output_tokens": 1}}
    out = ProviderRouter._anthropic_to_openai_response(_resp(body), "claude-opus-5-5").json()
    assert out["choices"][0]["finish_reason"] == "length"
    body["stop_reason"] = "end_turn"
    out = ProviderRouter._anthropic_to_openai_response(_resp(body), "claude-opus-5-5").json()
    assert out["choices"][0]["finish_reason"] == "stop"


def test_ollama_native_translation_reports_truncation() -> None:
    body = {"message": {"role": "assistant", "content": "partial"}, "done_reason": "length"}
    out = ProviderRouter._ollama_native_to_openai_response(_resp(body), "qwen").json()
    assert out["choices"][0]["finish_reason"] == "length"


def test_bedrock_translation_reports_truncation() -> None:
    data = {"output": {"message": {"content": [{"text": "partial"}]}}, "stopReason": "max_tokens",
            "usage": {"inputTokens": 1, "outputTokens": 1}}
    out = ProviderRouter._bedrock_response_to_openai(data, "anthropic.claude").json()
    assert out["choices"][0]["finish_reason"] == "length"


def test_failover_reads_finish_reason() -> None:
    assert _finish_reason(_resp({"choices": [{"finish_reason": "length"}]})) == "length"
    assert _finish_reason(_resp({"choices": []})) is None


def _runner_with_failover(tmp_path: Path, monkeypatch, finish_reason) -> AgentRunner:
    import packages.ai.failover_client as fc

    async def fake_failover(payload, *, timeout_sec):
        return SimpleNamespace(text='{"steps": [', model=payload["model"],
                               prompt_tokens=1, completion_tokens=1, latency_ms=5,
                               finish_reason=finish_reason)

    monkeypatch.setattr(fc, "failover_chat_completion", fake_failover)
    root = tmp_path / "repo"
    root.mkdir()
    return AgentRunner(ollama_base="https://integrate.api.nvidia.com", workspace_root=root)


def test_agent_loop_rejects_a_truncated_reply(tmp_path: Path, monkeypatch) -> None:
    runner = _runner_with_failover(tmp_path, monkeypatch, "length")
    with pytest.raises(TruncatedResponseError):
        asyncio.run(runner._chat_text("meta/llama-3.3-70b-instruct",
                                      [{"role": "user", "content": "plan"}]))


def test_agent_loop_passes_a_complete_reply(tmp_path: Path, monkeypatch) -> None:
    runner = _runner_with_failover(tmp_path, monkeypatch, "stop")
    out = asyncio.run(runner._chat_text("meta/llama-3.3-70b-instruct",
                                        [{"role": "user", "content": "plan"}]))
    assert out == '{"steps": ['


class _FakeSDK:
    """Stands in for anthropic.AsyncAnthropic / AsyncAnthropicBedrock."""

    def __init__(self, *a, **k) -> None:
        async def create(**kwargs):
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text='{"steps": [')],
                stop_reason="max_tokens",
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            )
        self.messages = SimpleNamespace(create=create)


def _sdk_runner(tmp_path: Path, monkeypatch) -> AgentRunner:
    """A runner whose paid-SDK path returns a truncated reply, and whose failover
    fallback would return a complete one: if the SDK path swallowed the
    truncation and fell back, the call would 'succeed' with the fallback text."""
    import anthropic
    monkeypatch.setenv("ALLOW_PAID_BRAIN", "true")
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _FakeSDK)
    monkeypatch.setattr(anthropic, "AsyncAnthropicBedrock", _FakeSDK)
    return _runner_with_failover(tmp_path, monkeypatch, "stop")


def test_anthropic_sdk_truncation_is_not_swallowed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    runner = _sdk_runner(tmp_path, monkeypatch)
    with pytest.raises(TruncatedResponseError):
        asyncio.run(runner._chat_text("claude-opus-5-5", [{"role": "user", "content": "plan"}]))


def test_bedrock_sdk_truncation_is_not_swallowed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setenv("BEDROCK_DISABLED", "false")  # operator opted into Bedrock
    runner = _sdk_runner(tmp_path, monkeypatch)
    with pytest.raises(TruncatedResponseError):
        asyncio.run(runner._chat_text("claude-opus-5-5", [{"role": "user", "content": "plan"}]))
