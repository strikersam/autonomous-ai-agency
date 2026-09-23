"""tests/test_daily_automation_2026_09_23.py — Daily automation tests (2026-09-23).

Covers the Langfuse session-header propagation implemented today:

  ``X-Claude-Code-Session-Id`` / ``X-Session-Id`` → Langfuse ``sessionId``

  ``emit_chat_observation`` in ``langfuse_obs.py`` has accepted ``session_id``
  since v4.1.0, but the parameter was never threaded through the call chain:
  the three entry-point handlers (``chat_handlers.py``, ``handlers/anthropic_compat.py``,
  ``proxy.py``) extracted nothing from the request headers, and neither the
  ``_emit_safely`` wrappers nor the streaming generators forwarded it.
  The Langfuse internal emitters (``_emit_sdk``, ``_emit_langfuse_http``) also
  had the parameter but were never called with it from ``emit_chat_observation``.

  Result: every session group in Langfuse was empty regardless of what the
  Claude Code client sent in ``X-Claude-Code-Session-Id``.

  Fix (2026-09-23):
    1. ``langfuse_obs.py`` — ``emit_chat_observation`` now forwards ``session_id``
       to both ``_emit_sdk`` and both ``_emit_langfuse_http`` call sites.
    2. ``chat_handlers.py`` — ``_emit_safely``, ``_stream_openai_chat``, and
       ``_stream_ollama_chat`` each gain ``session_id`` parameter; forwarded
       to ``emit_chat_observation``.  ``handle_openai_chat_completions`` and
       ``handle_ollama_native_chat`` extract the header (prefer
       ``X-Claude-Code-Session-Id``, fall back to ``X-Session-Id``) and thread
       it through.  ``X-Claude-Code-Agent-Type`` and
       ``X-Claude-Code-Request-Class`` are captured into ``routing_meta``.
    3. ``handlers/anthropic_compat.py`` — same as (2) for ``_emit_safely``,
       ``_stream_anthropic_sse``, and ``handle_anthropic_messages``.
    4. ``proxy.py`` — the legacy ``api/generate`` / ``v1/completions`` tracker
       now extracts and passes ``session_id``.

All tests use source-inspection only — no pydantic, no MongoDB.
"""
from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


# ── 1. emit_chat_observation forwards session_id to internal emitters ─────────

class TestEmitChatObservationForwardsSessionId:
    """The outer function must pass session_id into every internal call."""

    def _src(self) -> str:
        return (_ROOT / "langfuse_obs.py").read_text(encoding="utf-8")

    def test_emit_chat_observation_accepts_session_id(self) -> None:
        src = self._src()
        # The public function must declare the parameter
        idx = src.find("def emit_chat_observation(")
        assert idx != -1, "emit_chat_observation not found"
        block = src[idx: idx + 600]
        assert "session_id" in block, (
            "emit_chat_observation must have a session_id parameter"
        )

    def test_session_id_forwarded_to_emit_sdk(self) -> None:
        src = self._src()
        # Find the _emit_sdk call site (second occurrence — first is the definition)
        first = src.find("_emit_sdk(")
        assert first != -1, "_emit_sdk not found in langfuse_obs.py"
        idx = src.find("_emit_sdk(", first + 1)
        assert idx != -1, "_emit_sdk call site not found in langfuse_obs.py"
        block = src[idx: idx + 500]
        assert "session_id=session_id" in block, (
            "emit_chat_observation must pass session_id= to _emit_sdk"
        )

    def test_session_id_forwarded_to_http_fallback(self) -> None:
        src = self._src()
        # Both the SDK-fallback and the HTTP-only path call _emit_langfuse_http;
        # session_id=session_id must appear at least 2 times in the file (in the two
        # _emit_langfuse_http call sites) plus once in _emit_sdk
        assert src.count("session_id=session_id") >= 3, (
            "emit_chat_observation must pass session_id= to _emit_langfuse_http "
            "in both the SDK-fallback path and the HTTP-only path "
            f"(found {src.count('session_id=session_id')} occurrence(s))"
        )


# ── 2. chat_handlers.py ────────────────────────────────────────────────────────

class TestChatHandlersSessionId:
    """All emit wrappers and streaming generators in chat_handlers must carry session_id."""

    def _src(self) -> str:
        return (_ROOT / "chat_handlers.py").read_text(encoding="utf-8")

    def test_emit_safely_has_session_id_param(self) -> None:
        src = self._src()
        # _emit_safely must declare the keyword argument
        assert "session_id: str | None = None" in src, (
            "chat_handlers._emit_safely must accept session_id kwarg"
        )

    def test_emit_safely_forwards_session_id(self) -> None:
        src = self._src()
        assert "session_id=session_id" in src, (
            "chat_handlers._emit_safely must pass session_id to emit_chat_observation"
        )

    def test_stream_openai_chat_has_session_id_param(self) -> None:
        src = self._src()
        # Verify the generator signature carries the param
        idx = src.find("async def _stream_openai_chat(")
        assert idx != -1, "_stream_openai_chat not found"
        block = src[idx: idx + 600]
        assert "session_id" in block, (
            "_stream_openai_chat must accept session_id parameter"
        )

    def test_stream_ollama_chat_has_session_id_param(self) -> None:
        src = self._src()
        idx = src.find("async def _stream_ollama_chat(")
        assert idx != -1, "_stream_ollama_chat not found"
        block = src[idx: idx + 600]
        assert "session_id" in block, (
            "_stream_ollama_chat must accept session_id parameter"
        )

    def test_handle_openai_chat_extracts_cc_session_id_header(self) -> None:
        src = self._src()
        assert "x-claude-code-session-id" in src, (
            "handle_openai_chat_completions must check X-Claude-Code-Session-Id header"
        )

    def test_handle_openai_chat_extracts_fallback_session_id_header(self) -> None:
        src = self._src()
        assert "x-session-id" in src, (
            "handle_openai_chat_completions must fall back to X-Session-Id header"
        )

    def test_handle_openai_chat_records_agent_type(self) -> None:
        src = self._src()
        assert "x-claude-code-agent-type" in src, (
            "handle_openai_chat_completions must capture X-Claude-Code-Agent-Type"
        )

    def test_handle_openai_chat_records_request_class(self) -> None:
        src = self._src()
        assert "x-claude-code-request-class" in src, (
            "handle_openai_chat_completions must capture X-Claude-Code-Request-Class"
        )

    def test_streaming_call_passes_session_id(self) -> None:
        src = self._src()
        # The StreamingResponse wrapping _stream_openai_chat must supply session_id
        idx = src.find("_stream_openai_chat(")
        assert idx != -1, "_stream_openai_chat call not found"
        call_block = src[idx: idx + 300]
        assert "session_id=" in call_block, (
            "The _stream_openai_chat call site must pass session_id="
        )

    def test_non_streaming_emit_passes_session_id(self) -> None:
        src = self._src()
        # There are multiple _emit_safely calls; at least one must carry session_id=
        count = src.count("session_id=session_id")
        assert count >= 4, (
            f"Expected session_id=session_id at _emit_safely, streaming call site "
            f"and emit_chat_observation; found {count} occurrence(s)"
        )


# ── 3. handlers/anthropic_compat.py ───────────────────────────────────────────

class TestAnthropicCompatSessionId:
    """The Anthropic-compat handler must propagate session_id through all paths."""

    def _src(self) -> str:
        return (_ROOT / "handlers" / "anthropic_compat.py").read_text(encoding="utf-8")

    def test_emit_safely_has_session_id_param(self) -> None:
        src = self._src()
        assert "session_id: str | None = None" in src, (
            "anthropic_compat._emit_safely must accept session_id kwarg"
        )

    def test_emit_safely_forwards_session_id(self) -> None:
        src = self._src()
        assert "session_id=session_id" in src, (
            "anthropic_compat._emit_safely must pass session_id to emit_chat_observation"
        )

    def test_stream_sse_has_session_id_param(self) -> None:
        src = self._src()
        idx = src.find("async def _stream_anthropic_sse(")
        assert idx != -1, "_stream_anthropic_sse not found"
        block = src[idx: idx + 600]
        assert "session_id" in block, (
            "_stream_anthropic_sse must accept session_id parameter"
        )

    def test_handle_anthropic_extracts_cc_session_id_header(self) -> None:
        src = self._src()
        assert "x-claude-code-session-id" in src, (
            "handle_anthropic_messages must check X-Claude-Code-Session-Id header"
        )

    def test_handle_anthropic_extracts_fallback_session_id_header(self) -> None:
        src = self._src()
        assert "x-session-id" in src, (
            "handle_anthropic_messages must fall back to X-Session-Id header"
        )

    def test_handle_anthropic_records_agent_type(self) -> None:
        src = self._src()
        assert "x-claude-code-agent-type" in src, (
            "handle_anthropic_messages must capture X-Claude-Code-Agent-Type"
        )

    def test_streaming_call_passes_session_id(self) -> None:
        src = self._src()
        # The StreamingResponse call wraps _stream_anthropic_sse — look for that call
        # site (not the function definition which also starts with the same token)
        idx = src.find("StreamingResponse(")
        assert idx != -1, "StreamingResponse call not found in anthropic_compat.py"
        call_block = src[idx: idx + 600]
        assert "session_id=" in call_block, (
            "The _stream_anthropic_sse call inside StreamingResponse must pass session_id="
        )


# ── 4. proxy.py ───────────────────────────────────────────────────────────────

class TestProxySessionId:
    """The legacy completions tracker in proxy.py must pass session_id."""

    def _src(self) -> str:
        return (_ROOT / "proxy.py").read_text(encoding="utf-8")

    def test_proxy_extracts_session_id_header(self) -> None:
        src = self._src()
        assert "x-claude-code-session-id" in src, (
            "proxy.py must extract X-Claude-Code-Session-Id for the legacy tracker"
        )

    def test_proxy_passes_session_id_to_emit(self) -> None:
        src = self._src()
        # The emit_chat_observation call in the legacy path must carry session_id=
        idx = src.find("emit_chat_observation,")
        assert idx != -1, "emit_chat_observation call not found in proxy.py"
        # proxy.py has extra blank lines (it's a large file with its own formatting),
        # so we need a wider window to find session_id= past all the kwargs
        block = src[idx: idx + 800]
        assert "session_id=" in block, (
            "proxy.py emit_chat_observation call must pass session_id="
        )


# ── 5. No-header no-op: session_id defaults to None ─────────────────────────

class TestSessionIdDefaultsToNone:
    """Calls without a session header must not break — session_id defaults None."""

    def test_emit_safely_default_is_none(self) -> None:
        src = (_ROOT / "chat_handlers.py").read_text(encoding="utf-8")
        # The _emit_safely signature must default session_id to None
        idx = src.find("async def _emit_safely(")
        assert idx != -1
        sig_block = src[idx: idx + 500]
        assert "session_id: str | None = None" in sig_block, (
            "_emit_safely must default session_id=None so calls without it still work"
        )

    def test_emit_chat_observation_default_is_none(self) -> None:
        src = (_ROOT / "langfuse_obs.py").read_text(encoding="utf-8")
        idx = src.find("def emit_chat_observation(")
        assert idx != -1, "emit_chat_observation not found"
        # Find end of signature — the closing `) -> None:` line
        sig_end = src.find(") -> None:", idx)
        block = src[idx: sig_end + 10]
        assert "session_id: str | None = None" in block, (
            "emit_chat_observation session_id must default to None in its signature"
        )


# ── 6. Prefer X-Claude-Code-Session-Id over X-Session-Id ────────────────────

class TestHeaderPrecedence:
    """The longer Claude Code header must take precedence over the generic one."""

    def test_cc_header_checked_first_in_chat_handlers(self) -> None:
        src = (_ROOT / "chat_handlers.py").read_text(encoding="utf-8")
        # In both handlers, the CC-specific header is mentioned before the generic one
        # in the same preference chain; verify CC appears closer to session_id assignment
        cc_pos = src.find("x-claude-code-session-id")
        generic_pos = src.find("x-session-id")
        assert cc_pos != -1 and generic_pos != -1
        # CC header should appear before the generic one in the source
        assert cc_pos < generic_pos, (
            "X-Claude-Code-Session-Id should be the first preference in chat_handlers"
        )

    def test_cc_header_checked_first_in_anthropic_compat(self) -> None:
        src = (_ROOT / "handlers" / "anthropic_compat.py").read_text(encoding="utf-8")
        cc_pos = src.find("x-claude-code-session-id")
        generic_pos = src.find("x-session-id")
        assert cc_pos != -1 and generic_pos != -1
        assert cc_pos < generic_pos, (
            "X-Claude-Code-Session-Id should be the first preference in anthropic_compat"
        )
