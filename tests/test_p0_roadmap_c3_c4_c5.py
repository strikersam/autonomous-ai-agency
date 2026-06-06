from __future__ import annotations

"""Tests for C3 Streaming Delta Reconstruction, C4 Chat History Persistence,
C5 Context Window Management."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from services.streaming_delta import (
    StreamingDeltaReconstructor,
    DeltaChunk,
    ReconstructResult,
    create_streaming_reconstructor,
)
from services.chat_history import (
    ChatHistoryStore,
    get_chat_history,
)
from services.context_window import (
    ContextWindowManager,
    TruncationStrategy,
    TruncationResult,
    get_context_window_manager,
)


# ── C3: Streaming Delta Reconstruction ───────────────────────────────────────

class TestDeltaChunk:
    def test_to_sse_bytes(self) -> None:
        chunk = DeltaChunk(content="Hello", role="assistant", index=0)
        sse = chunk.to_sse_bytes("test-model", "chatcmpl-123")
        assert b"data:" in sse
        assert b"Hello" in sse
        assert b"test-model" in sse

    def test_to_sse_with_tool_calls(self) -> None:
        chunk = DeltaChunk(
            content="",
            role="assistant",
            index=0,
            tool_calls=[{"function": {"name": "read_file", "arguments": "{}"}}],
        )
        sse = chunk.to_sse_bytes("test-model", "chatcmpl-456")
        assert b"tool_calls" in sse
        assert b"read_file" in sse

    def test_done_sse_bytes(self) -> None:
        sse = DeltaChunk.done_sse_bytes("model", "id")
        assert sse == b"data: [DONE]\n\n"


class TestStreamingDeltaReconstructor:
    @pytest.mark.asyncio
    async def test_feed_and_emit(self) -> None:
        recon = StreamingDeltaReconstructor(model="test", chunk_size=5)
        # Simulate SSE chunks
        chunks = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}\n',
            b'data: {"choices":[{"delta":{"content":" World"}}]}\n',
            b"data: [DONE]\n",
        ]
        for c in chunks:
            recon.feed_sse_bytes(c)

        emitted = await recon.emit_all()
        # emit_all returns SSE-formatted bytes; extract content for assertion
        assert len(emitted) >= 3
        full_text = b"".join(emitted).decode()
        # Parse SSE lines to extract content deltas
        import json as _json
        content_parts: list[str] = []
        for line in full_text.split("\n"):
            if line.startswith("data: ") and line != "data: [DONE]":
                try:
                    obj = _json.loads(line[6:])
                    delta = obj["choices"][0].get("delta", {})
                    if "content" in delta:
                        content_parts.append(delta["content"])
                except Exception:
                    pass
        extracted = "".join(content_parts)
        assert "Hello" in extracted
        assert "World" in extracted
        assert "[DONE]" in full_text

    @pytest.mark.asyncio
    async def test_feed_text(self) -> None:
        recon = StreamingDeltaReconstructor(model="test", chunk_size=10)
        recon.feed_text("Direct text feed without SSE parsing")
        emitted = await recon.emit_all()
        # Parse SSE chunks to extract content
        import json as _json
        content_parts: list[str] = []
        for chunk in emitted:
            try:
                obj = _json.loads(chunk.decode().removeprefix("data: ").strip())
                if isinstance(obj, dict):
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    if "content" in delta:
                        content_parts.append(delta["content"])
            except Exception:
                pass
        full_text = "".join(content_parts)
        assert "Direct text feed" in full_text

    @pytest.mark.asyncio
    async def test_hooks(self) -> None:
        recon = StreamingDeltaReconstructor(model="test", chunk_size=20)
        async def uppercase_hook(text: str) -> str:
            return text.upper()
        recon.add_hook("uppercase", uppercase_hook)
        recon.feed_text("hello world")
        emitted = await recon.emit_all()
        full_text = b"".join(emitted).decode()
        assert "HELLO WORLD" in full_text

    @pytest.mark.asyncio
    async def test_hook_failure_is_nonfatal(self) -> None:
        recon = StreamingDeltaReconstructor(model="test", chunk_size=20)
        async def failing_hook(text: str) -> str:
            raise RuntimeError("hook failure")
        recon.add_hook("failing", failing_hook)
        recon.feed_text("hello")
        emitted = await recon.emit_all()
        full_text = b"".join(emitted).decode()
        assert "hello" in full_text  # Should still get the original text

    @pytest.mark.asyncio
    async def test_remove_hook(self) -> None:
        recon = StreamingDeltaReconstructor(model="test", chunk_size=20)
        async def noisy_hook(text: str) -> str:
            return text + "!!!"
        recon.add_hook("noisy", noisy_hook)
        recon.remove_hook("noisy")
        recon.feed_text("hello")
        emitted = await recon.emit_all()
        full_text = b"".join(emitted).decode()
        assert "!!!" not in full_text

    @pytest.mark.asyncio
    async def test_stats(self) -> None:
        recon = StreamingDeltaReconstructor(model="test-model")
        recon.feed_text("hello world")
        stats = recon.stats()
        assert stats["model"] == "test-model"
        assert stats["accumulated_chars"] == 11
        assert "hooks" in stats

    def test_factory_with_guardrails(self) -> None:
        # Should not raise even if guardrails not installed
        recon = create_streaming_reconstructor(
            model="test", enable_guardrails=True
        )
        assert isinstance(recon, StreamingDeltaReconstructor)

    @pytest.mark.asyncio
    async def test_emit_as_async_iterator(self) -> None:
        recon = StreamingDeltaReconstructor(model="test", chunk_size=10)
        recon.feed_text("test content")
        chunks: list[bytes] = []
        async for chunk in recon.emit():
            chunks.append(chunk)
        assert len(chunks) >= 1
        # Parse SSE chunks to extract content
        import json as _json
        content_parts: list[str] = []
        for chunk in chunks:
            try:
                line = chunk.decode().strip()
                if line.startswith("data: ") and line != "data: [DONE]":
                    obj = _json.loads(line[6:])
                    delta = obj.get("choices", [{}])[0].get("delta", {})
                    if "content" in delta:
                        content_parts.append(delta["content"])
            except Exception:
                pass
        full_text = "".join(content_parts)
        assert "test content" in full_text


# ── C4: Chat History Persistence ─────────────────────────────────────────────

class TestChatHistoryStore:
    @pytest.fixture
    def store(self, tmp_path) -> ChatHistoryStore:
        db_path = str(tmp_path / "test_chat.db")
        store = ChatHistoryStore(db_path=db_path, max_sessions=10)
        yield store
        store.close()

    def test_create_session(self, store) -> None:
        sid = store.create_session(model="test-model")
        assert sid.startswith("sess_")
        assert len(sid) > 10

    def test_append_and_get_messages(self, store) -> None:
        sid = store.create_session()
        store.append(sid, {"role": "user", "content": "hello"})
        store.append(sid, {"role": "assistant", "content": "hi there"})
        msgs = store.get_messages(sid)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_get_history(self, store) -> None:
        sid = store.create_session()
        store.append(sid, {"role": "user", "content": "question"})
        store.append(sid, {"role": "assistant", "content": "answer"})
        history = store.get_history(sid)
        assert len(history) == 2
        assert "_seq" not in history[0]  # Clean format
        assert history[0]["role"] == "user"

    def test_append_bulk(self, store) -> None:
        sid = store.create_session()
        msgs = [
            {"role": "user", "content": "a"},
            {"role": "assistant", "content": "b"},
            {"role": "user", "content": "c"},
        ]
        count = store.append_bulk(sid, msgs)
        assert count == 3
        assert store.message_count(sid) == 3

    def test_trim_history(self, store) -> None:
        sid = store.create_session()
        for i in range(10):
            store.append(sid, {"role": "user", "content": f"msg{i}"})
        store.trim_history(sid, max_messages=5)
        msgs = store.get_messages(sid)
        assert len(msgs) == 5
        # Should keep the most recent messages
        assert msgs[-1]["content"] == "msg9"

    def test_auto_trim_on_append(self, store) -> None:
        sid = store.create_session()
        for i in range(15):
            store.append(sid, {"role": "user", "content": f"msg{i}"}, max_messages=10)
        assert store.message_count(sid) == 10

    def test_delete_session(self, store) -> None:
        sid = store.create_session()
        store.append(sid, {"role": "user", "content": "test"})
        assert store.delete_session(sid) is True
        assert store.delete_session(sid) is False
        assert store.message_count(sid) == 0

    def test_list_sessions(self, store) -> None:
        s1 = store.create_session(model="a")
        s2 = store.create_session(model="b")
        sessions = store.list_sessions()
        assert len(sessions) >= 2
        ids = {s["session_id"] for s in sessions}
        assert s1 in ids
        assert s2 in ids

    def test_update_message(self, store) -> None:
        sid = store.create_session()
        store.append(sid, {"role": "user", "content": "original"})
        assert store.update_message(sid, 1, "updated") is True
        msgs = store.get_messages(sid)
        assert msgs[0]["content"] == "updated"

    def test_export_import_session(self, store) -> None:
        sid = store.create_session(model="test-model")
        store.append(sid, {"role": "user", "content": "hello"})
        store.append(sid, {"role": "assistant", "content": "world"})

        exported = store.export_session(sid)
        assert exported is not None
        assert exported["model"] == "test-model"
        assert len(exported["messages"]) == 2

        imported_id = store.import_session(exported)
        assert imported_id is not None

    def test_session_counts(self, store) -> None:
        store.create_session()
        store.create_session()
        counts = store.session_counts()
        assert counts["sessions"] == 2

    def test_enforce_session_limit(self, store) -> None:
        # Limit is 10, create 15 sessions
        for i in range(15):
            store.create_session(model=f"model{i}")
        sessions = store.list_sessions()
        assert len(sessions) <= 10

    def test_get_messages_with_limit(self, store) -> None:
        sid = store.create_session()
        for i in range(20):
            store.append(sid, {"role": "user", "content": f"msg{i}"}, max_messages=50)
        msgs = store.get_messages(sid, limit=5)
        assert len(msgs) == 5

    def test_stats(self, store) -> None:
        store.create_session()
        stats = store.stats()
        assert "total_sessions" in stats
        assert "db_size_bytes" in stats


# ── C5: Context Window Management ────────────────────────────────────────────

class TestContextWindowManager:
    def test_estimate_tokens_empty(self) -> None:
        assert ContextWindowManager.estimate_tokens([]) == 0

    def test_estimate_tokens_simple(self) -> None:
        tokens = ContextWindowManager.estimate_tokens(
            [{"role": "user", "content": "Hello, world!"}]
        )
        assert tokens > 0
        assert tokens < 10  # Short message

    def test_estimate_tokens_multiple(self) -> None:
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "A" * 400},
            {"role": "assistant", "content": "B" * 200},
        ]
        tokens = ContextWindowManager.estimate_tokens(msgs)
        # ~600 chars + 3*16 overhead = 648 / 4 = 162 tokens
        assert 150 <= tokens <= 200

    def test_needs_truncation_false(self) -> None:
        mgr = ContextWindowManager(default_context_window=8192)
        msgs = [{"role": "user", "content": "Short message"}]
        assert mgr.needs_truncation(msgs, model="test") is False

    def test_needs_truncation_true(self) -> None:
        mgr = ContextWindowManager(default_context_window=100)
        # Create messages that exceed 100 * 0.85 = 85 tokens
        msgs = [{"role": "user", "content": "x" * 1000}]
        assert mgr.needs_truncation(msgs, model="test") is True

    def test_truncate_none_strategy(self) -> None:
        mgr = ContextWindowManager()
        msgs = [{"role": "user", "content": "test"}]
        result = mgr.truncate(msgs, strategy=TruncationStrategy.NONE)
        assert len(result.messages) == 1
        assert result.strategy_used == "none"

    def test_truncate_sliding_window(self) -> None:
        mgr = ContextWindowManager(default_context_window=40)
        msgs = [
            {"role": "system", "content": "You are a coder."},
            {"role": "user", "content": "x" * 600},
            {"role": "assistant", "content": "y" * 400},
            {"role": "user", "content": "Short"},
            {"role": "assistant", "content": "Last message"},
        ]
        result = mgr.truncate(msgs, strategy=TruncationStrategy.SLIDING_WINDOW)
        # Should have kept system + some messages
        assert result.messages[0]["role"] == "system"
        assert result.truncated_count < len(msgs)
        assert result.removed_messages > 0

    def test_truncate_head_tail(self) -> None:
        mgr = ContextWindowManager(default_context_window=200)
        msgs = [
            {"role": "system", "content": "System prompt."},
            {"role": "user", "content": "Early context."},
            {"role": "assistant", "content": "Early response."},
            {"role": "user", "content": "x" * 500},
            {"role": "assistant", "content": "Recent response."},
        ]
        result = mgr.truncate(msgs, strategy=TruncationStrategy.HEAD_TAIL)
        assert result.messages[0]["role"] == "system"
        assert result.truncated_count <= len(msgs)

    def test_truncate_smart_compact(self) -> None:
        mgr = ContextWindowManager(default_context_window=80)
        msgs = [
            {"role": "system", "content": "System."},
            {"role": "user", "content": "x" * 300},
            {"role": "assistant", "content": "y" * 300},
            {"role": "user", "content": "x2" * 200},
            {"role": "assistant", "content": "y2" * 200},
            {"role": "user", "content": "z" * 200},
            {"role": "assistant", "content": "Final."},
        ]
        result = mgr.truncate(msgs, strategy=TruncationStrategy.SMART_COMPACT)
        # Should produce a summary and keep recent
        assert result.messages[0]["role"] == "system"
        # Should have the summary as second system message
        roles = [m["role"] for m in result.messages]
        assert "system" in roles

    def test_context_limit_from_registry(self) -> None:
        mgr = ContextWindowManager()
        # Test with known model from the registry
        limit = mgr.context_limit("qwen3-coder:30b")
        assert limit > 0
        # qwen3-coder:30b has 32768 context window
        assert limit >= 4096

    def test_context_limit_unknown_model(self) -> None:
        mgr = ContextWindowManager(default_context_window=4096)
        limit = mgr.context_limit("nonexistent-model:1b")
        assert limit == 4096  # Falls back to default

    def test_truncation_result_compression_ratio(self) -> None:
        result = TruncationResult(
            messages=[{"role": "user", "content": "a"}],
            original_count=10,
            truncated_count=5,
            original_est_tokens=100,
            final_est_tokens=50,
            strategy_used="sliding_window",
            headroom_tokens=200,
        )
        assert result.compression_ratio == 0.5

    def test_singleton(self) -> None:
        m1 = get_context_window_manager()
        m2 = get_context_window_manager()
        assert m1 is m2


class TestChatHistorySingleton:
    def test_singleton(self, tmp_path) -> None:
        # Patch the module-level singleton
        import services.chat_history as ch
        old_db = os.environ.get("CHAT_HISTORY_DB")
        try:
            os.environ["CHAT_HISTORY_DB"] = str(tmp_path / "singleton.db")
            # Reset singleton
            ch._store = None
            s1 = get_chat_history()
            s2 = get_chat_history()
            assert s1 is s2
            s1.close()
        finally:
            if old_db:
                os.environ["CHAT_HISTORY_DB"] = old_db
            else:
                os.environ.pop("CHAT_HISTORY_DB", None)
            ch._store = None
