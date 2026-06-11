"""tests/test_harness_adapter.py — Tests for ECC cross-harness adapter."""
from __future__ import annotations

import pytest


class TestHarnessAdapter:
    """Harness detection, normalization, and registration."""

    @pytest.fixture
    def adapter(self):
        from agents.harness_adapter import (
            get_harness_adapter,
            _adapter as _ad_singleton,
        )
        _backup = _ad_singleton
        import agents.harness_adapter as mod
        mod._adapter = None
        ad = get_harness_adapter()
        yield ad
        mod._adapter = _backup

    def test_catalog_has_entries(self):
        from agents.harness_adapter import HARNESS_CATALOG
        assert len(HARNESS_CATALOG) >= 8
        assert "claude_code" in HARNESS_CATALOG
        assert "cursor" in HARNESS_CATALOG
        assert "telegram" in HARNESS_CATALOG

    def test_register_and_deregister(self, adapter):
        adapter.register_active("claude_code")
        assert "claude_code" in adapter.active_harness_ids
        adapter.deregister("claude_code")
        assert "claude_code" not in adapter.active_harness_ids

    def test_register_unknown_harness_logs_warning(self, adapter, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            adapter.register_active("nonexistent")
        assert "Unknown harness" in caplog.text

    def test_detect_claude_code_by_ua(self, adapter):
        headers = {"user-agent": "claude-code/1.0.0"}
        result = adapter.detect_harness(headers)
        assert result == "claude_code"

    def test_detect_cursor_by_ua(self, adapter):
        headers = {"user-agent": "Cursor/0.48.0"}
        result = adapter.detect_harness(headers)
        assert result == "cursor"

    def test_detect_by_explicit_header(self, adapter):
        headers = {"x-harness-id": "aider"}
        result = adapter.detect_harness(headers)
        assert result == "aider"

    def test_detect_unknown_returns_none(self, adapter):
        headers = {"user-agent": "curl/8.0"}
        result = adapter.detect_harness(headers)
        assert result is None

    def test_normalize_request_copies_common_fields(self, adapter):
        raw = {"messages": [{"role": "user", "content": "hi"}], "model": "test-model", "temperature": 0.7}
        normalized = adapter.normalize_request("cursor", raw)
        assert normalized["harness"] == "cursor"
        assert normalized["messages"] == raw["messages"]
        assert normalized["model"] == "test-model"

    def test_model_hint(self, adapter):
        hint = adapter.model_hint("claude_code")
        assert hint == "claude-sonnet-4-6"

    def test_supports_feature(self, adapter):
        assert adapter.supports_feature("cursor", "streaming") is True
        assert adapter.supports_feature("zed", "multi_step") is False

    def test_as_dict(self, adapter):
        adapter.register_active("cursor")
        d = adapter.as_dict()
        assert d["catalog_size"] >= 8
        assert d["active_harnesses"]
        assert any(h["harness_id"] == "cursor" for h in d["active_harnesses"])


class TestHarnessRegistry:
    """Harness session tracking and metrics."""

    @pytest.fixture
    def registry(self):
        from services.harness_registry import (
            get_harness_registry,
            _registry as _reg_singleton,
        )
        _backup = _reg_singleton
        import services.harness_registry as mod
        mod._registry = None
        reg = get_harness_registry()
        yield reg
        mod._registry = _backup

    def test_register_and_close_session(self, registry):
        record = registry.register_session("cursor", "sess-1", "qwen3-coder:30b")
        assert record.harness_id == "cursor"
        assert record.session_id == "sess-1"

        registry.close_session("sess-1", tasks_completed=3, success=True)
        metrics = registry.get_metrics("cursor")
        assert metrics["total_sessions"] == 1
        assert metrics["total_tasks"] == 3

    def test_get_metrics_all(self, registry):
        registry.register_session("cursor", "s1")
        registry.register_session("claude_code", "s2")
        registry.close_session("s1", tasks_completed=1, success=True)
        registry.close_session("s2", tasks_completed=2, success=False)

        all_metrics = registry.get_metrics()
        assert "cursor" in all_metrics
        assert "claude_code" in all_metrics

    def test_active_harnesses(self, registry):
        registry.register_session("cursor", "s1")
        registry.register_session("telegram", "s2")
        active = registry.active_harnesses
        assert "cursor" in active
        assert "telegram" in active

    def test_close_nonexistent_session_no_error(self, registry):
        registry.close_session("no-such-session")  # must not raise

    def test_as_dict(self, registry):
        registry.register_session("cursor", "s1")
        d = registry.as_dict()
        assert "cursor" in d["active_harnesses"]
        assert d["active_sessions"] >= 1
