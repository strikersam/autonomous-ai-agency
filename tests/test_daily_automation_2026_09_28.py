"""tests/test_daily_automation_2026_09_28.py — Daily automation tests (2026-09-28).

Covers the ``X-Claude-Code-Prompt-Id`` → Langfuse ``prompt:<id>`` tag forwarding,
the finer-grained sibling of the ``X-Claude-Code-Session-Id`` propagation shipped
2026-09-23 (``tests/test_daily_automation_2026_09_23.py``). Claude Code 2.1.283
added ``x-claude-code-prompt-id`` to its gateway hint headers so a downstream
gateway can group every tool-call round trip that serves one user prompt — today
those round trips land in Langfuse as separate, ungrouped traces.

Fix (2026-09-28):
  1. ``langfuse_obs.py`` — ``_emit_langfuse_http_sync`` gains a ``prompt_id``
     parameter and adds a ``prompt:<id>`` trace tag when present (mirroring the
     ``session:<id>`` tag). ``emit_chat_observation`` forwards ``prompt_id`` to
     both ``_emit_langfuse_http`` call sites. Unlike ``session_id``, there is no
     first-class Langfuse ``promptId`` trace field, so this is tag-only.
  2. ``chat_handlers.py`` — ``_emit_safely``, ``_stream_openai_chat``, and
     ``_stream_ollama_chat`` each gain a ``prompt_id`` parameter, forwarded to
     ``emit_chat_observation``. ``handle_openai_chat_completions`` and
     ``handle_ollama_native_chat`` extract ``X-Claude-Code-Prompt-Id`` and
     thread it through every call site alongside ``session_id``.
  3. ``handlers/anthropic_compat.py`` — same as (2) for ``_emit_safely``,
     ``_stream_anthropic_sse``, and ``handle_anthropic_messages``.
  4. ``proxy.py`` — the legacy ``api/generate`` / ``v1/completions`` tracker
     now also extracts and passes ``prompt_id``.

Absent header is a no-op: no exception, no ``prompt:None`` tag, and the trace
is byte-identical to today's output — fully backward compatible.

All tests use source-inspection plus one functional tag-emission test — no
pydantic, no MongoDB, no live Langfuse.
"""
from __future__ import annotations

import inspect
import unittest.mock as mock
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


# ── 1. langfuse_obs.py forwards prompt_id ──────────────────────────────────────

class TestEmitChatObservationForwardsPromptId:
    """The outer function and the HTTP emitter must carry prompt_id end to end."""

    def _src(self) -> str:
        return (_ROOT / "langfuse_obs.py").read_text(encoding="utf-8")

    def test_emit_chat_observation_accepts_prompt_id(self) -> None:
        src = self._src()
        idx = src.find("def emit_chat_observation(")
        assert idx != -1, "emit_chat_observation not found"
        sig_end = src.find(") -> None:", idx)
        block = src[idx: sig_end + 10]
        assert "prompt_id: str | None = None" in block, (
            "emit_chat_observation must accept prompt_id and default it to None"
        )

    def test_emit_langfuse_http_sync_accepts_prompt_id(self) -> None:
        from langfuse_obs import _emit_langfuse_http_sync
        sig = inspect.signature(_emit_langfuse_http_sync)
        assert "prompt_id" in sig.parameters
        assert sig.parameters["prompt_id"].default is None

    def test_prompt_id_forwarded_to_http_call_sites(self) -> None:
        src = self._src()
        # Both the SDK-fallback and the HTTP-only path call _emit_langfuse_http.
        assert src.count("prompt_id=prompt_id") >= 2, (
            "emit_chat_observation must pass prompt_id= to _emit_langfuse_http "
            "in both the SDK-fallback path and the HTTP-only path "
            f"(found {src.count('prompt_id=prompt_id')} occurrence(s))"
        )

    def test_http_trace_includes_prompt_tag_when_present(self) -> None:
        """When prompt_id is provided, trace tags must include prompt:<id>."""
        from langfuse_obs import _emit_langfuse_http_sync

        captured_tags: list[str] = []

        def fake_post(url, json=None, auth=None):
            nonlocal captured_tags
            if "traces" in url and json:
                captured_tags = json.get("tags", [])
            resp = mock.MagicMock()
            resp.status_code = 200
            return resp

        with mock.patch(
            "langfuse_obs._env_val",
            side_effect=lambda k: "testkey" if "KEY" in k else "https://cloud.langfuse.com",
        ):
            with mock.patch("httpx.Client") as mock_client_cls:
                mock_client = mock.MagicMock()
                mock_client.__enter__ = lambda s: s
                mock_client.__exit__ = mock.MagicMock(return_value=False)
                mock_client.post = fake_post
                mock_client_cls.return_value = mock_client

                _emit_langfuse_http_sync(
                    email="user@test.com",
                    department="eng",
                    key_id=None,
                    model="gemma4:27b",
                    messages=[],
                    output_text="hi",
                    prompt_tokens=1,
                    completion_tokens=1,
                    meta={},
                    task_name="test",
                    session_id="my-session-xyz",
                    prompt_id="my-prompt-abc",
                )

        assert "prompt:my-prompt-abc" in captured_tags
        assert "session:my-session-xyz" in captured_tags

    def test_http_trace_has_no_prompt_tag_when_absent(self) -> None:
        """Absent prompt_id must not add a prompt: tag — no-op, backward compatible."""
        from langfuse_obs import _emit_langfuse_http_sync

        captured_tags: list[str] = []

        def fake_post(url, json=None, auth=None):
            nonlocal captured_tags
            if "traces" in url and json:
                captured_tags = json.get("tags", [])
            resp = mock.MagicMock()
            resp.status_code = 200
            return resp

        with mock.patch(
            "langfuse_obs._env_val",
            side_effect=lambda k: "testkey" if "KEY" in k else "https://cloud.langfuse.com",
        ):
            with mock.patch("httpx.Client") as mock_client_cls:
                mock_client = mock.MagicMock()
                mock_client.__enter__ = lambda s: s
                mock_client.__exit__ = mock.MagicMock(return_value=False)
                mock_client.post = fake_post
                mock_client_cls.return_value = mock_client

                _emit_langfuse_http_sync(
                    email="user@test.com",
                    department="eng",
                    key_id=None,
                    model="gemma4:27b",
                    messages=[],
                    output_text="hi",
                    prompt_tokens=1,
                    completion_tokens=1,
                    meta={},
                    task_name="test",
                )

        assert not any(t.startswith("prompt:") for t in captured_tags)

    def test_no_first_class_prompt_id_trace_field(self) -> None:
        """Langfuse has no promptId trace field — this must stay tag-only."""
        src = self._src()
        assert 'trace_body["promptId"]' not in src


# ── 2. chat_handlers.py ────────────────────────────────────────────────────────

class TestChatHandlersPromptId:
    """All emit wrappers and streaming generators in chat_handlers must carry prompt_id."""

    def _src(self) -> str:
        return (_ROOT / "chat_handlers.py").read_text(encoding="utf-8")

    def test_emit_safely_has_prompt_id_param(self) -> None:
        src = self._src()
        assert "prompt_id: str | None = None" in src, (
            "chat_handlers._emit_safely must accept prompt_id kwarg"
        )

    def test_emit_safely_forwards_prompt_id(self) -> None:
        src = self._src()
        assert "prompt_id=prompt_id" in src, (
            "chat_handlers._emit_safely must pass prompt_id to emit_chat_observation"
        )

    def test_stream_openai_chat_has_prompt_id_param(self) -> None:
        src = self._src()
        idx = src.find("async def _stream_openai_chat(")
        assert idx != -1, "_stream_openai_chat not found"
        block = src[idx: idx + 600]
        assert "prompt_id" in block, (
            "_stream_openai_chat must accept prompt_id parameter"
        )

    def test_stream_ollama_chat_has_prompt_id_param(self) -> None:
        src = self._src()
        idx = src.find("async def _stream_ollama_chat(")
        assert idx != -1, "_stream_ollama_chat not found"
        block = src[idx: idx + 600]
        assert "prompt_id" in block, (
            "_stream_ollama_chat must accept prompt_id parameter"
        )

    def test_handle_openai_chat_extracts_prompt_id_header(self) -> None:
        src = self._src()
        assert "x-claude-code-prompt-id" in src, (
            "handle_openai_chat_completions must check X-Claude-Code-Prompt-Id header"
        )

    def test_handle_ollama_chat_extracts_prompt_id_header(self) -> None:
        src = self._src()
        assert src.count("x-claude-code-prompt-id") >= 2, (
            "both handle_openai_chat_completions and handle_ollama_native_chat "
            "must check X-Claude-Code-Prompt-Id header"
        )

    def test_streaming_call_passes_prompt_id(self) -> None:
        src = self._src()
        idx = src.find("_stream_openai_chat(")
        assert idx != -1, "_stream_openai_chat call not found"
        call_block = src[idx: idx + 300]
        assert "prompt_id=" in call_block, (
            "The _stream_openai_chat call site must pass prompt_id="
        )

    def test_non_streaming_emit_passes_prompt_id(self) -> None:
        src = self._src()
        count = src.count("prompt_id=prompt_id")
        assert count >= 6, (
            f"Expected prompt_id=prompt_id at every _emit_safely / streaming call "
            f"site across both handlers; found {count} occurrence(s)"
        )


# ── 3. handlers/anthropic_compat.py ───────────────────────────────────────────

class TestAnthropicCompatPromptId:
    """The Anthropic-compat handler must propagate prompt_id through all paths."""

    def _src(self) -> str:
        return (_ROOT / "handlers" / "anthropic_compat.py").read_text(encoding="utf-8")

    def test_emit_safely_has_prompt_id_param(self) -> None:
        src = self._src()
        assert "prompt_id: str | None = None" in src, (
            "anthropic_compat._emit_safely must accept prompt_id kwarg"
        )

    def test_emit_safely_forwards_prompt_id(self) -> None:
        src = self._src()
        assert "prompt_id=prompt_id" in src, (
            "anthropic_compat._emit_safely must pass prompt_id to emit_chat_observation"
        )

    def test_stream_sse_has_prompt_id_param(self) -> None:
        src = self._src()
        idx = src.find("async def _stream_anthropic_sse(")
        assert idx != -1, "_stream_anthropic_sse not found"
        block = src[idx: idx + 600]
        assert "prompt_id" in block, (
            "_stream_anthropic_sse must accept prompt_id parameter"
        )

    def test_handle_anthropic_extracts_prompt_id_header(self) -> None:
        src = self._src()
        assert "x-claude-code-prompt-id" in src, (
            "handle_anthropic_messages must check X-Claude-Code-Prompt-Id header"
        )

    def test_streaming_call_passes_prompt_id(self) -> None:
        src = self._src()
        idx = src.find("StreamingResponse(")
        assert idx != -1, "StreamingResponse call not found in anthropic_compat.py"
        call_block = src[idx: idx + 600]
        assert "prompt_id=" in call_block, (
            "The _stream_anthropic_sse call inside StreamingResponse must pass prompt_id="
        )


# ── 4. proxy.py ───────────────────────────────────────────────────────────────

class TestProxyPromptId:
    """The legacy completions tracker in proxy.py must pass prompt_id."""

    def _src(self) -> str:
        return (_ROOT / "proxy.py").read_text(encoding="utf-8")

    def test_proxy_extracts_prompt_id_header(self) -> None:
        src = self._src()
        assert "x-claude-code-prompt-id" in src, (
            "proxy.py must extract X-Claude-Code-Prompt-Id for the legacy tracker"
        )

    def test_proxy_passes_prompt_id_to_emit(self) -> None:
        src = self._src()
        idx = src.find("emit_chat_observation,")
        assert idx != -1, "emit_chat_observation call not found in proxy.py"
        # proxy.py has extra blank lines (large file, its own formatting), so a
        # wider window is needed to find prompt_id= past all the kwargs.
        block = src[idx: idx + 900]
        assert "prompt_id=" in block, (
            "proxy.py emit_chat_observation call must pass prompt_id="
        )


# ── 5. No-header no-op: prompt_id defaults to None everywhere ─────────────────

class TestPromptIdDefaultsToNone:
    """Calls without a prompt-id header must not break — prompt_id defaults None."""

    def test_emit_safely_default_is_none(self) -> None:
        src = (_ROOT / "chat_handlers.py").read_text(encoding="utf-8")
        idx = src.find("async def _emit_safely(")
        assert idx != -1
        sig_block = src[idx: idx + 500]
        assert "prompt_id: str | None = None" in sig_block, (
            "_emit_safely must default prompt_id=None so calls without it still work"
        )

    def test_emit_chat_observation_default_is_none(self) -> None:
        from langfuse_obs import emit_chat_observation
        sig = inspect.signature(emit_chat_observation)
        assert sig.parameters["prompt_id"].default is None

    def test_emit_chat_observation_runs_without_prompt_id(self) -> None:
        """Legacy callers that never pass prompt_id keep working unchanged."""
        from langfuse_obs import emit_chat_observation

        with mock.patch("langfuse_obs._langfuse_enabled", return_value=False):
            # With Langfuse disabled, the function returns early — this only
            # asserts the call succeeds without a TypeError on missing kwarg.
            emit_chat_observation(
                email="test@example.com",
                department="eng",
                key_id=None,
                model="qwen3-coder:30b",
                messages=[{"role": "user", "content": "hi"}],
                output_text="hello",
                prompt_tokens=5,
                completion_tokens=3,
                session_id="claude-code-session-abc123",
            )
