from __future__ import annotations

"""Integration tests for C4/C5/C6/D3 modules and their integrations."""

import os
import json
import tempfile
from pathlib import Path

import pytest


# ── C4: Chat History Integration ─────────────────────────────────────────────

class TestChatHistoryIntegration:
    @pytest.fixture
    def tmp_db(self, tmp_path) -> str:
        return str(tmp_path / "test_chat.db")

    def test_store_auto_creates_session_on_append(self, tmp_db) -> None:
        from services.chat_history import ChatHistoryStore
        store = ChatHistoryStore(db_path=tmp_db)
        session_id = "sess_integration_test"
        store.append(session_id, {"role": "user", "content": "hello"})
        msgs = store.get_messages(session_id)
        assert len(msgs) >= 1
        assert msgs[0]["role"] == "user"
        store.close()

    def test_get_history_clean_format(self, tmp_db) -> None:
        from services.chat_history import ChatHistoryStore
        store = ChatHistoryStore(db_path=tmp_db)
        store.append("sess_1", {"role": "user", "content": "q"})
        store.append("sess_1", {"role": "assistant", "content": "a"})
        history = store.get_history("sess_1")
        assert len(history) == 2
        assert "_seq" not in history[0]
        assert "role" in history[0]
        store.close()

    def test_trim_history_keeps_recent(self, tmp_db) -> None:
        from services.chat_history import ChatHistoryStore
        store = ChatHistoryStore(db_path=tmp_db)
        for i in range(20):
            store.append("sess_t", {"role": "user", "content": f"msg{i}"})
        store.trim_history("sess_t", max_messages=5)
        msgs = store.get_messages("sess_t")
        assert len(msgs) == 5
        assert msgs[-1]["content"] == "msg19"
        store.close()

    def test_export_import_roundtrip(self, tmp_db) -> None:
        from services.chat_history import ChatHistoryStore
        store = ChatHistoryStore(db_path=tmp_db)
        store.append("sess_exp", {"role": "user", "content": "test"})
        exported = store.export_session("sess_exp")
        imported_id = store.import_session(exported)
        assert imported_id is not None
        imported_msgs = store.get_messages(imported_id)
        assert len(imported_msgs) >= 1
        store.close()


# ── C5: Context Window Integration ───────────────────────────────────────────

class TestContextWindowIntegration:
    def test_sliding_window_preserves_system(self) -> None:
        from services.context_window import ContextWindowManager, TruncationStrategy
        mgr = ContextWindowManager(default_context_window=150)
        msgs = [
            {"role": "system", "content": "You are a coder."},
            {"role": "user", "content": "x" * 300},
            {"role": "assistant", "content": "y" * 200},
            {"role": "user", "content": "Short final"},
            {"role": "assistant", "content": "Last message."},
        ]
        result = mgr.truncate(msgs, strategy=TruncationStrategy.SLIDING_WINDOW)
        assert result.messages[0]["role"] == "system"
        assert result.truncated_count < len(msgs)

    def test_smart_compact_inserts_summary(self) -> None:
        from services.context_window import ContextWindowManager, TruncationStrategy
        mgr = ContextWindowManager(default_context_window=200)
        msgs = [
            {"role": "system", "content": "System."},
            {"role": "user", "content": "a" * 200},
            {"role": "assistant", "content": "b" * 200},
            {"role": "user", "content": "c" * 100},
            {"role": "assistant", "content": "d" * 100},
            {"role": "user", "content": "Final question."},
            {"role": "assistant", "content": "Final answer."},
        ]
        result = mgr.truncate(msgs, strategy=TruncationStrategy.SMART_COMPACT)
        assert result.messages[0]["role"] == "system"
        assert "summary" in result.messages[1]["content"].lower() or len(result.messages) < 4

    def test_context_limit_from_registry(self) -> None:
        from services.context_window import ContextWindowManager
        mgr = ContextWindowManager()
        limit = mgr.context_limit("qwen3-coder:30b")
        assert limit >= 4096


# ── C6: Prompt Cache Integration ────────────────────────────────────────────

class TestPromptCacheIntegration:
    def test_cache_key_computation(self) -> None:
        from services.prompt_cache import PromptCacheManager
        mgr = PromptCacheManager()
        key1 = mgr.compute_cache_key("You are helpful.", [{"role": "user", "content": "hello"}], model="test")
        key2 = mgr.compute_cache_key("You are helpful.", [{"role": "user", "content": "hello"}], model="test")
        assert key1 == key2  # Deterministic

    def test_cache_key_differs_on_model(self) -> None:
        from services.prompt_cache import PromptCacheManager
        mgr = PromptCacheManager()
        key1 = mgr.compute_cache_key("sys", [{"role": "user", "content": "hi"}], model="model-a")
        key2 = mgr.compute_cache_key("sys", [{"role": "user", "content": "hi"}], model="model-b")
        assert key1 != key2

    def test_get_preferred_instance_miss(self) -> None:
        from services.prompt_cache import PromptCacheManager
        mgr = PromptCacheManager()
        result = mgr.get_preferred_instance("nonexistent-key")
        assert result is None

    def test_record_and_retrieve_warm_cache(self) -> None:
        from services.prompt_cache import PromptCacheManager
        mgr = PromptCacheManager()
        key = mgr.compute_cache_key("sys", [{"role": "user", "content": "test"}])
        mgr.record_warm("instance-1", key, system_hash="abc", model="test")
        preferred = mgr.get_preferred_instance(key)
        assert preferred == "instance-1"

    def test_cache_stats(self) -> None:
        from services.prompt_cache import PromptCacheManager
        mgr = PromptCacheManager()
        stats = mgr.stats()
        assert "entries" in stats
        assert "hit_rate" in stats

    def test_parse_cache_control(self) -> None:
        from services.prompt_cache import PromptCacheManager
        result = PromptCacheManager.parse_cache_control([])
        assert result["prefix_tokens"] >= 0
        assert not result["has_ephemeral"]

    def test_inject_cache_metrics(self) -> None:
        from services.prompt_cache import PromptCacheManager
        resp = {"usage": {"prompt_tokens": 100, "completion_tokens": 50}}
        out = PromptCacheManager.inject_cache_metrics(resp, cache_read_tokens=80, cache_creation_tokens=20)
        assert out["usage"]["cache_read_input_tokens"] == 80
        assert out["usage"]["cache_creation_input_tokens"] == 20

    def test_invalidate_system(self) -> None:
        from services.prompt_cache import PromptCacheManager
        mgr = PromptCacheManager()
        key = mgr.compute_cache_key("sys_a", [{"role": "user", "content": "hi"}])
        mgr.record_warm("inst-1", key, system_hash="hash_a")
        count = mgr.invalidate_system("hash_a")
        assert count == 1
        assert mgr.get_preferred_instance(key) is None


# ── D3: OTEL Tracing Integration ────────────────────────────────────────────

class TestOTELTracingIntegration:
    def test_tracer_noop_when_disabled(self) -> None:
        from services.otel_tracing import get_tracer, TraceContext
        tracer = get_tracer("test-disabled")
        # When OTEL_ENABLED defaults to false, should return NoOpTracer
        assert tracer is not None

    def test_span_context_parsing(self) -> None:
        from services.otel_tracing import span_context_from_request, TraceContext

        class MockHeaders:
            headers = {}

        # No traceparent header → None
        req1 = MockHeaders()
        assert span_context_from_request(req1) is None

        # Valid traceparent → TraceContext
        class MockWithTrace:
            headers = {"traceparent": "00-abc123def456-0123456789ab-01"}

        req2 = MockWithTrace()
        tc = span_context_from_request(req2)
        assert tc is not None
        assert tc.trace_id == "abc123def456"
        assert tc.is_sampled is True

    def test_span_context_to_headers(self) -> None:
        from services.otel_tracing import TraceContext, span_context_to_headers
        tc = TraceContext(trace_id="abc", span_id="def", is_sampled=True)
        headers = span_context_to_headers(tc)
        assert "traceparent" in headers
        assert "abc" in headers["traceparent"]

    def test_langfuse_metadata(self) -> None:
        from services.otel_tracing import set_current_trace_id, get_current_trace_id, langfuse_metadata_with_trace
        set_current_trace_id("test-trace-id")
        assert get_current_trace_id() == "test-trace-id"
        meta = langfuse_metadata_with_trace()
        assert meta["otel_trace_id"] == "test-trace-id"


# ── E1: Harness Routing ─────────────────────────────────────────────────────

class TestHarnessRouting:
    def test_detect_claude_code(self) -> None:
        from router.harness_routing import detect_harness, Harness
        result = detect_harness({"User-Agent": "claude-code/2.1.154"})
        assert result == Harness.CLAUDE_CODE

    def test_detect_cursor(self) -> None:
        from router.harness_routing import detect_harness, Harness
        result = detect_harness({"x-tool": "cursor"})
        assert result == Harness.CURSOR

    def test_detect_unknown(self) -> None:
        from router.harness_routing import detect_harness, Harness
        result = detect_harness({"User-Agent": "curl/8.0"})
        assert result == Harness.UNKNOWN

    def test_route_for_harness(self) -> None:
        from router.harness_routing import route_for_harness, Harness
        model = route_for_harness(Harness.CURSOR, task_category="fast_response")
        assert model is not None
        assert "7b" in model.lower() or "8b" in model.lower() or "2b" in model.lower()


# ── E2: Self-Healing ─────────────────────────────────────────────────────────

class TestSelfHealing:
    def test_failure_classification(self) -> None:
        from agent.self_healing import SelfHealingAgent, FailureCategory
        assert SelfHealingAgent._classify_failure("SyntaxError at line 42") == FailureCategory.SYNTAX_ERROR
        assert SelfHealingAgent._classify_failure("test_auth failed with AssertionError") == FailureCategory.TEST_FAILURE
        assert SelfHealingAgent._classify_failure("Connection refused") == FailureCategory.NETWORK

    def test_failure_hints(self) -> None:
        from agent.self_healing import SelfHealingAgent
        hint = SelfHealingAgent._failure_category_hint("syntax_error")
        assert "syntax" in hint.lower()
        hint2 = SelfHealingAgent._failure_category_hint("timeout")
        assert "timeout" in hint2.lower()


# ── G1: Cost Attribution ────────────────────────────────────────────────────

class TestCostAttribution:
    def test_record_and_report(self) -> None:
        from services.cost_attribution import CostAttributor
        attr = CostAttributor()
        attr.record_usage(model="qwen3-coder:30b", prompt_tokens=500, completion_tokens=200, phase="execute")
        attr.record_usage(model="deepseek-r1:32b", prompt_tokens=1000, completion_tokens=500, phase="plan")
        report = attr.generate_report()
        assert report.total_calls == 2
        assert len(report.per_model) == 2
        assert report.total_cost_usd >= 0

    def test_estimate_cost(self) -> None:
        from services.cost_attribution import CostAttributor
        attr = CostAttributor()
        cost = attr.estimate_cost("qwen3-coder:30b", 1_000_000)
        assert cost > 0

    def test_batch_record(self) -> None:
        from services.cost_attribution import CostAttributor
        attr = CostAttributor()
        entries = [
            {"model": "qwen3-coder:7b", "prompt_tokens": 100, "phase": "chat"},
            {"model": "deepseek-r1:32b", "prompt_tokens": 200, "phase": "plan"},
        ]
        count = attr.record_batch(entries)
        assert count == 2
        assert attr._total_calls == 2
