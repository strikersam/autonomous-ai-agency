from __future__ import annotations

"""Tests for P0 roadmap items: ★2 Sub-Agent Configs, ★3 Reasoning Budget, A2 ReAct Loop."""

import os
from pathlib import Path

import pytest

from agent.models import SubAgentConfig
from agent.react_loop import ReactScratchpad, parse_react_response, build_react_prompt
from agent.loop import _REASONING_BUDGET_MAP


# ── ★2 Sub-Agent Configs ──────────────────────────────────────────────────────

class TestSubAgentConfig:
    def test_minimal_config(self) -> None:
        cfg = SubAgentConfig(role="editor")
        assert cfg.role == "editor"
        assert cfg.model == ""
        assert cfg.tool_names == []
        assert cfg.instruction == ""
        assert cfg.max_steps == 5

    def test_full_config(self) -> None:
        cfg = SubAgentConfig(
            role="file_picker",
            model="qwen3-coder:7b",
            tool_names=["read_file", "search_code", "list_files"],
            instruction="You are a file picker.",
            max_steps=3,
        )
        assert cfg.model == "qwen3-coder:7b"
        assert len(cfg.tool_names) == 3
        assert cfg.max_steps == 3

    def test_keyed_by_role(self) -> None:
        """Sub-agent configs can be keyed by role name for lookup."""
        cfgs = [
            SubAgentConfig(role="file_picker", model="qwen3-coder:7b"),
            SubAgentConfig(role="editor", model="qwen3-coder:30b"),
        ]
        by_role = {c.role: c for c in cfgs}
        assert by_role["file_picker"].model == "qwen3-coder:7b"
        assert by_role["editor"].model == "qwen3-coder:30b"

    def test_empty_tool_names_means_all_tools(self) -> None:
        cfg = SubAgentConfig(role="planner")
        assert cfg.tool_names == []  # empty = allow all tools


# ── ★3 Reasoning Budget ───────────────────────────────────────────────────────


class TestReasoningBudget:
    def test_budget_mapping_keys(self) -> None:
        assert set(_REASONING_BUDGET_MAP.keys()) == {"low", "medium", "high", "max"}

    def test_low_budget(self) -> None:
        assert _REASONING_BUDGET_MAP["low"] == 512

    def test_medium_budget(self) -> None:
        assert _REASONING_BUDGET_MAP["medium"] == 2048

    def test_high_budget(self) -> None:
        assert _REASONING_BUDGET_MAP["high"] == 8192

    def test_max_is_unbounded(self) -> None:
        assert _REASONING_BUDGET_MAP["max"] == -1

    def test_budget_injected_when_positive(self) -> None:
        """thinking_token_budget should only be injected when > 0."""
        assert _REASONING_BUDGET_MAP["high"] > 0
        assert _REASONING_BUDGET_MAP["low"] > 0
        assert _REASONING_BUDGET_MAP["max"] == -1  # unbounded → not injected


# ── A2 ReAct Loop ─────────────────────────────────────────────────────────────

class TestReactScratchpad:
    def test_empty_scratchpad(self) -> None:
        sp = ReactScratchpad()
        assert len(sp.entries) == 0
        assert sp.to_prompt_context() == ""

    def test_record_thought_action_observation(self) -> None:
        sp = ReactScratchpad()
        sp.record_thought("I should read the file first")
        sp.record_action("read_file", {"path": "main.py"})
        sp.record_observation("def main(): pass")
        assert len(sp.entries) == 3
        assert sp.entries[0]["type"] == "thought"
        assert sp.entries[1]["type"] == "action"
        assert sp.entries[2]["type"] == "observation"

    def test_to_prompt_context_includes_recent_entries(self) -> None:
        sp = ReactScratchpad()
        sp.record_thought("Step 1")
        sp.record_action("read_file", {"path": "a.py"})
        sp.record_observation("content")
        ctx = sp.to_prompt_context()
        assert "Thought: Step 1" in ctx
        assert "Action: read_file" in ctx
        assert "Observation: content" in ctx

    def test_to_prompt_context_truncates_old_entries(self) -> None:
        sp = ReactScratchpad()
        for i in range(20):
            sp.record_thought(f"Thought {i}")
        ctx = sp.to_prompt_context(max_entries=5)
        assert "Thought 15" in ctx
        assert "Thought 0" not in ctx

    def test_to_dict_serializes(self) -> None:
        sp = ReactScratchpad()
        sp.record_thought("test")
        d = sp.to_dict()
        assert "entries" in d
        assert "duration_ms" in d
        assert len(d["entries"]) == 1

    def test_clear_resets(self) -> None:
        sp = ReactScratchpad()
        sp.record_thought("test")
        sp.clear()
        assert len(sp.entries) == 0


class TestParseReactResponse:
    def test_parse_thought_and_action(self) -> None:
        text = "Thought: I should read the file\nAction: read_file({\"path\": \"main.py\"})"
        result = parse_react_response(text)
        assert result is not None
        assert result["thought"] == "I should read the file"
        assert result["tool"] == "read_file"

    def test_parse_final_answer(self) -> None:
        text = "Thought: Done\nFinal Answer: The step was completed successfully"
        result = parse_react_response(text)
        assert result is not None
        assert result["final"] == "The step was completed successfully"

    def test_parse_no_match_returns_none(self) -> None:
        result = parse_react_response("some random text")
        assert result is None


class TestBuildReactPrompt:
    def test_includes_goal_and_step(self) -> None:
        sp = ReactScratchpad()
        step = {"id": 1, "description": "Test step", "files": ["x.py"]}
        prompt = build_react_prompt(
            goal="Fix bugs",
            step=step,
            scratchpad=sp,
            tool_descriptions="read_file, write_file",
        )
        assert "Fix bugs" in prompt
        assert "Test step" in prompt
        assert "read_file" in prompt
        assert "Thought:" in prompt
        assert "Action:" in prompt
        assert "Final Answer:" in prompt

    def test_includes_scratchpad_trace(self) -> None:
        sp = ReactScratchpad()
        sp.record_thought("previous thought")
        prompt = build_react_prompt(
            goal="Test", step={}, scratchpad=sp, tool_descriptions=""
        )
        assert "previous thought" in prompt


# ── vLLM Backend Registration ─────────────────────────────────────────────────

class TestVllmBackend:
    def test_vllm_is_in_registry(self) -> None:
        from router.registry import get_registry
        registry = get_registry()
        assert "vllm:default" in registry

    def test_vllm_has_openai_compat_tag(self) -> None:
        from router.registry import get_registry
        registry = get_registry()
        cap = registry["vllm:default"]
        assert "openai-compat" in cap.tags

    def test_vllm_has_reasoning_strength(self) -> None:
        from router.registry import get_registry
        registry = get_registry()
        cap = registry["vllm:default"]
        assert "reasoning" in cap.strengths
