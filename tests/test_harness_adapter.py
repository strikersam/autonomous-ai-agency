"""Tests for harness adapter (cross-harness support inspired by ECC)"""

import pytest

from agents.harness_adapter import (
    HarnessAdapter,
    HarnessCapabilities,
    HarnessType,
    detect_harness,
)


class TestHarnessAdapter:
    """Test harness normalization and denormalization"""

    def test_detect_harness_default(self, monkeypatch):
        """Should default to claude_code when no harness detected"""
        # Clear environment
        monkeypatch.delenv("CURSOR_SESSION_ID", raising=False)
        monkeypatch.delenv("ZED_SOCKET", raising=False)
        monkeypatch.delenv("VSCODE_PID", raising=False)
        
        harness = detect_harness()
        assert harness == HarnessType.CLAUDE_CODE

    def test_detect_harness_cursor(self, monkeypatch):
        """Should detect Cursor from environment"""
        monkeypatch.setenv("CURSOR_SESSION_ID", "cursor_123")
        
        harness = detect_harness()
        assert harness == HarnessType.CURSOR

    def test_detect_harness_zed(self, monkeypatch):
        """Should detect Zed from environment"""
        monkeypatch.delenv("CURSOR_SESSION_ID", raising=False)
        monkeypatch.setenv("ZED_SOCKET", "/tmp/zed.sock")
        
        harness = detect_harness()
        assert harness == HarnessType.ZED

    def test_harness_initialization_valid(self):
        """Should initialize with valid harness type"""
        adapter = HarnessAdapter(HarnessType.CLAUDE_CODE)
        assert adapter.harness == HarnessType.CLAUDE_CODE

    def test_harness_initialization_string(self):
        """Should accept string harness names"""
        adapter = HarnessAdapter("claude_code")
        assert adapter.harness == HarnessType.CLAUDE_CODE

    def test_harness_initialization_invalid_defaults(self):
        """Should default to claude_code on invalid harness"""
        adapter = HarnessAdapter("invalid_harness")
        assert adapter.harness == HarnessType.CLAUDE_CODE

    def test_capabilities_claude_code(self):
        """Should have correct capabilities for Claude Code"""
        adapter = HarnessAdapter(HarnessType.CLAUDE_CODE)
        
        assert adapter.supports_streaming() is True
        assert adapter.get_model_preference() == "reasoning"
        assert adapter.get_max_context() == 50 * 1024 * 1024

    def test_capabilities_cursor(self):
        """Should have correct capabilities for Cursor"""
        adapter = HarnessAdapter(HarnessType.CURSOR)
        
        assert adapter.supports_streaming() is True
        assert adapter.get_model_preference() == "speed"
        assert adapter.get_max_context() == 25 * 1024 * 1024

    def test_capabilities_codex(self):
        """Should have correct capabilities for Codex"""
        adapter = HarnessAdapter(HarnessType.CODEX)
        
        assert adapter.supports_streaming() is False
        assert adapter.get_model_preference() == "completion"
        assert adapter.get_max_context() == 10 * 1024 * 1024

    def test_normalize_request_claude_code(self):
        """Should normalize Claude Code request"""
        adapter = HarnessAdapter(HarnessType.CLAUDE_CODE)
        
        request = {"messages": [{"role": "user", "content": "hello"}]}
        normalized = adapter.normalize_request(request)
        
        assert normalized["harness"] == "claude_code"
        assert normalized["context_type"] == "workspace"
        assert "messages" in normalized

    def test_normalize_request_cursor(self):
        """Should normalize Cursor request"""
        adapter = HarnessAdapter(HarnessType.CURSOR)
        
        request = {
            "messages": [{"role": "user", "content": "hello"}],
            "context": {"active_tabs": ["main.py", "test.py"]},
        }
        normalized = adapter.normalize_request(request)
        
        assert normalized["harness"] == "cursor"
        assert normalized["context_type"] == "editor_tabs"

    def test_denormalize_response_claude_code(self):
        """Should denormalize Claude Code response"""
        adapter = HarnessAdapter(HarnessType.CLAUDE_CODE)
        
        response = {"content": "response text"}
        denormalized = adapter.denormalize_response(response)
        
        # Should return unchanged for Claude Code
        assert denormalized == response

    def test_harness_capabilities_enum(self):
        """Should have capabilities defined for all harnesses"""
        for harness_type in HarnessType:
            assert harness_type in HarnessCapabilities.HARNESS_FEATURES

    def test_all_harnesses_have_model_preference(self):
        """All harnesses should have model preference"""
        for harness_type in HarnessType:
            adapter = HarnessAdapter(harness_type)
            preference = adapter.get_model_preference()
            assert preference in ["reasoning", "speed", "completion", "balanced"]

    def test_all_harnesses_have_max_context(self):
        """All harnesses should have max context defined"""
        for harness_type in HarnessType:
            adapter = HarnessAdapter(harness_type)
            max_ctx = adapter.get_max_context()
            assert max_ctx > 0
            assert max_ctx <= 100 * 1024 * 1024  # Reasonable upper bound


class TestHarnessCapabilities:
    """Test harness capability declarations"""

    def test_streaming_preferences(self):
        """Verify streaming capability distribution"""
        streaming_harnesses = [
            HarnessType.CLAUDE_CODE,
            HarnessType.CURSOR,
            HarnessType.OPENCODE,
            HarnessType.GEMINI,
            HarnessType.ZED,
            HarnessType.GITHUB_COPILOT,
        ]
        
        non_streaming = [HarnessType.CODEX]
        
        for harness in streaming_harnesses:
            caps = HarnessCapabilities.HARNESS_FEATURES[harness]
            assert caps["supports_streaming"] is True
        
        for harness in non_streaming:
            caps = HarnessCapabilities.HARNESS_FEATURES[harness]
            assert caps["supports_streaming"] is False

    def test_context_source_declared(self):
        """Each harness should declare its context source"""
        for harness, caps in HarnessCapabilities.HARNESS_FEATURES.items():
            assert "context_source" in caps
            assert caps["context_source"] in [
                "workspace_tree",
                "editor_open_tabs",
                "current_file",
                "buffer",
                "project_root",
                "editor_buffer",
                "vscode_context",
            ]
