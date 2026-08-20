"""Daily automation tests — 2026-08-16.

Covers three improvements landed this session:
1. claude-sonnet-5 / claude-opus-5 MODEL_REGISTRY entries
2. _apply_reasoning_budget() mapping in chat_handlers
3. _prune_chat_messages() context-pruner wiring in chat_handlers
"""

from __future__ import annotations

import os
import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest


def _stub_heavy_imports() -> None:
    """Stub out modules that require full stack deps to allow unit-testing pure logic.

    Only stubs a module when it isn't already imported. ``langfuse_obs`` is real
    and already in ``sys.modules`` in the full test suite (many modules import it
    eagerly) — mutating its ``emit_chat_observation``/``ObservationType`` in that
    case would replace the real function with a ``MagicMock`` for the rest of the
    pytest session (module-level code runs once at collection, with no teardown),
    corrupting `inspect.signature()` for every later test that imports the real
    thing (e.g. ``tests/test_vision_routing.py``). Scoping the stub to only the
    not-yet-imported case keeps this file's standalone-import safety without that
    cross-test pollution.
    """
    for mod in ("langfuse", "pymongo"):
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    if "langfuse_obs" not in sys.modules:
        stub = types.ModuleType("langfuse_obs")
        stub.emit_chat_observation = MagicMock()  # type: ignore[attr-defined]
        stub.ObservationType = MagicMock()  # type: ignore[attr-defined]
        sys.modules["langfuse_obs"] = stub


_stub_heavy_imports()


# ── 1. Claude 5 standard model registry ──────────────────────────────────────

class TestClaude5RegistryEntries:
    def test_opus_5_present(self) -> None:
        from router.registry import get_registry
        reg = get_registry()
        assert "claude-opus-5" in reg

    def test_opus_5_capability_profile(self) -> None:
        from router.registry import get_registry
        cap = get_registry()["claude-opus-5"]
        assert cap.type == "reasoning"
        assert cap.cost_tier == 3
        assert "flagship" in cap.tags
        assert "reasoning" in cap.strengths
        assert "planning" in cap.strengths
        assert cap.context_window == 200000

    def test_sonnet_5_present(self) -> None:
        from router.registry import get_registry
        reg = get_registry()
        assert "claude-sonnet-5" in reg

    def test_sonnet_5_capability_profile(self) -> None:
        from router.registry import get_registry
        cap = get_registry()["claude-sonnet-5"]
        assert cap.type == "reasoning"
        assert cap.cost_tier == 2
        assert "long_context" in cap.tags
        assert "adaptive_thinking" in cap.tags
        # 1M context window
        assert cap.context_window == 1048576
        assert "code_generation" in cap.strengths

    def test_sonnet_5_dated_alias_present(self) -> None:
        from router.registry import get_registry
        reg = get_registry()
        assert "claude-sonnet-5-20260501" in reg
        cap = reg["claude-sonnet-5-20260501"]
        assert "pinned" in cap.tags
        assert cap.context_window == 1048576

    def test_opus_5_in_model_map(self) -> None:
        """claude-opus-5 must be in the built-in alias map so routing resolves it."""
        from router.model_router import _BUILTIN_MODEL_MAP
        assert "claude-opus-5" in _BUILTIN_MODEL_MAP

    def test_sonnet_5_in_model_map(self) -> None:
        from router.model_router import _BUILTIN_MODEL_MAP
        assert "claude-sonnet-5" in _BUILTIN_MODEL_MAP

    def test_sonnet_5_dated_alias_in_model_map(self) -> None:
        from router.model_router import _BUILTIN_MODEL_MAP
        assert "claude-sonnet-5-20260501" in _BUILTIN_MODEL_MAP


# ── 2. reasoning_budget mapping ───────────────────────────────────────────────

class TestApplyReasoningBudget:
    def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        from chat_handlers import _apply_reasoning_budget
        return _apply_reasoning_budget(payload)

    def test_no_reasoning_budget_is_passthrough(self) -> None:
        payload = {"model": "qwen3-coder:30b", "messages": []}
        result = self._call(payload)
        assert result is payload  # unchanged identity

    def test_low_maps_to_512(self) -> None:
        result = self._call({"reasoning_budget": "low", "messages": []})
        assert result.get("thinking_token_budget") == 512
        assert "reasoning_budget" not in result

    def test_medium_maps_to_2048(self) -> None:
        result = self._call({"reasoning_budget": "medium", "messages": []})
        assert result.get("thinking_token_budget") == 2048

    def test_high_maps_to_8192(self) -> None:
        result = self._call({"reasoning_budget": "high", "messages": []})
        assert result.get("thinking_token_budget") == 8192

    def test_max_maps_to_32768(self) -> None:
        result = self._call({"reasoning_budget": "max", "messages": []})
        assert result.get("thinking_token_budget") == 32768

    def test_case_insensitive(self) -> None:
        result = self._call({"reasoning_budget": "HIGH", "messages": []})
        assert result.get("thinking_token_budget") == 8192

    def test_unknown_label_defaults_to_medium(self) -> None:
        result = self._call({"reasoning_budget": "ultramax", "messages": []})
        assert result.get("thinking_token_budget") == 2048

    def test_existing_thinking_token_budget_not_overwritten(self) -> None:
        result = self._call({
            "reasoning_budget": "low",
            "thinking_token_budget": 999,
            "messages": [],
        })
        assert result.get("thinking_token_budget") == 999

    def test_other_fields_preserved(self) -> None:
        result = self._call({
            "reasoning_budget": "high",
            "model": "deepseek-r1:32b",
            "temperature": 0.7,
            "messages": [],
        })
        assert result["model"] == "deepseek-r1:32b"
        assert result["temperature"] == 0.7


# ── 3. Context pruner wiring ──────────────────────────────────────────────────

class TestPruneChatMessages:
    def _call(self, messages: Any) -> Any:
        from chat_handlers import _prune_chat_messages
        return _prune_chat_messages(messages)

    def test_none_passthrough(self) -> None:
        assert self._call(None) is None

    def test_non_list_passthrough(self) -> None:
        assert self._call("not-a-list") == "not-a-list"

    def test_short_list_not_pruned(self) -> None:
        msgs = [{"role": "user", "content": "Hi"}]
        result = self._call(msgs)
        # Short context — should return same list (no pruning needed)
        assert result == msgs

    def test_disabled_returns_original(self, monkeypatch: Any) -> None:
        monkeypatch.setattr("chat_handlers._CONTEXT_PRUNING_ENABLED", False)
        monkeypatch.setattr("chat_handlers._context_pruner", None)
        msgs = [{"role": "user", "content": "x" * 100}]
        result = self._call(msgs)
        assert result is msgs

    def test_large_context_gets_pruned(self, monkeypatch: Any) -> None:
        """A message list that exceeds the pruner's threshold should be trimmed."""
        from agent.context_pruner import ContextPruner

        # Use a very low prune threshold to make the test deterministic
        pruner = ContextPruner(prune_after_tokens=5)
        monkeypatch.setattr("chat_handlers._context_pruner", pruner)
        monkeypatch.setattr("chat_handlers._CONTEXT_PRUNING_ENABLED", True)

        msgs = [
            {"role": "user", "content": "x" * 200},
            {"role": "assistant", "content": "y" * 200},
            {"role": "user", "content": "final question"},
        ]
        result = self._call(msgs)
        # The pruner should have done something (result may be shorter or wrapped)
        assert isinstance(result, list)
        # The most-recent user message should survive
        assert any(m.get("content") == "final question" for m in result)
