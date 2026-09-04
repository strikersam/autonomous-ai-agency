"""tests/test_jit_harness.py — Tests for JIT harness system."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestHarnessProtocols:
    """Test protocol dataclasses."""

    def test_generated_harness_creation(self):
        from agent.jit_harness.protocols import GeneratedHarness

        harness = GeneratedHarness(
            name="test_harness",
            files={"memory.py": "class MemoryStrategy: pass"},
            task_description="Test task",
            meta_prompt="prompt",
            meta_response="response",
        )
        assert harness.name == "test_harness"
        assert "memory.py" in harness.files
        assert harness.to_dict()["name"] == "test_harness"

    def test_selection_result_creation(self):
        from agent.jit_harness.protocols import GeneratedHarness, SelectionResult

        harness = GeneratedHarness(
            name="test_harness",
            files={"memory.py": "class MemoryStrategy: pass"},
            task_description="Test task",
            meta_prompt="prompt",
            meta_response="response",
        )
        result = SelectionResult(
            selected_harness=harness,
            all_candidates=[harness],
            scores={"test_harness": 1.0},
            selector_type="judge",
            selection_reason="Best score",
        )
        assert result.selected_harness.name == "test_harness"
        assert result.selector_type == "judge"

    def test_execution_result_creation(self):
        from agent.jit_harness.protocols import ExecutionResult

        result = ExecutionResult(
            success=True,
            final_answer="Done",
            score=1.0,
            trajectory=[],
        )
        assert result.success is True
        assert result.score == 1.0


class TestHarnessGenerator:
    """Test harness generation."""

    @pytest.fixture
    def generator(self):
        from agent.jit_harness.generator import HarnessGenerator
        return HarnessGenerator(
            meta_model="test-model",
            meta_base_url="http://localhost:8000/v1",
            meta_api_key="test-key",
        )

    def test_generator_initialization(self, generator):
        assert generator.meta_model == "test-model"
        assert generator.meta_base_url == "http://localhost:8000/v1"
        assert generator.meta_api_key == "test-key"
        assert generator.reference_mode == "desc"

    def test_build_reference_block_desc_mode(self, generator):
        block = generator._build_reference_block("desc", 3)
        assert "Agent harness catalogue" in block
        assert "plan_and_execute" in block
        assert "flash_searcher" in block

    def test_build_reference_block_code_mode(self, generator):
        block = generator._build_reference_block("code", 2)
        assert "Agent harness examples (full source)" in block
        assert "plan_and_execute" in block

    def test_build_user_prompt(self, generator):
        task = "Test task"
        ref_block = "Reference block"
        prompt = generator._build_user_prompt(task, ref_block, 0)
        assert "Test task" in prompt
        assert "Reference block" in prompt
        assert "Your task" in prompt


class TestHarnessSelector:
    """Test harness selection."""

    @pytest.fixture
    def selector(self):
        from agent.jit_harness.selector import HarnessSelector
        return HarnessSelector(
            selector_type="judge",
            judge_model="test-judge",
            judge_base_url="http://localhost:8000/v1",
            judge_api_key="test-key",
        )

    def test_selector_initialization(self, selector):
        assert selector.selector_type == "judge"
        assert selector.judge_model == "test-judge"

    def test_summarize_harness(self, selector):
        from agent.jit_harness.protocols import GeneratedHarness

        harness = GeneratedHarness(
            name="test_harness",
            files={
                "memory.py": "class MemoryStrategy:\n    pass",
                "planning.py": "class PlanningStrategy:\n    pass",
            },
            task_description="Test task",
            meta_prompt="prompt",
            meta_response="response",
        )
        summary = selector._summarize_harness(harness)
        assert "MemoryStrategy" in summary
        assert "PlanningStrategy" in summary

    def test_fallback_selection(self, selector):
        from agent.jit_harness.protocols import GeneratedHarness

        h1 = GeneratedHarness(
            name="h1", files={}, task_description="", meta_prompt="", meta_response=""
        )
        h2 = GeneratedHarness(
            name="h2", files={}, task_description="", meta_prompt="", meta_response=""
        )
        result = selector._fallback_selection([h1, h2])
        assert result.selected_harness.name == "h1"
        assert result.selector_type == "fallback"

    @pytest.mark.asyncio
    async def test_select_judge_success(self, selector):
        from agent.jit_harness.protocols import GeneratedHarness

        h1 = GeneratedHarness(
            name="h1", files={}, task_description="Task", meta_prompt="", meta_response=""
        )
        h2 = GeneratedHarness(
            name="h2", files={}, task_description="Task", meta_prompt="", meta_response=""
        )

        with patch("openai.AsyncOpenAI") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_response = AsyncMock()
            mock_response.choices = [AsyncMock()]
            mock_response.choices[0].message.content = '{"h1": 0.9, "h2": 0.5}'
            mock_client.chat.completions.create.return_value = mock_response

            result = await selector.select("Task", [h1, h2])

            assert result.selected_harness.name == "h1"
            assert result.scores["h1"] == 0.9
            assert result.selector_type == "judge"


class TestHarnessExecutor:
    """Test harness execution."""

    @pytest.fixture
    def executor(self, tmp_path):
        from agent.jit_harness.executor import HarnessExecutor
        return HarnessExecutor(
            workspace_root=str(tmp_path),
            execution_model="test-model",
            execution_base_url="http://localhost:8000/v1",
            execution_api_key="test-key",
        )

    def test_executor_initialization(self, executor, tmp_path):
        assert executor.workspace_root == str(tmp_path)
        assert executor.execution_model == "test-model"

    @pytest.mark.asyncio
    async def test_execute_missing_strategy_classes(self, executor, tmp_path):
        from agent.jit_harness.protocols import GeneratedHarness

        harness = GeneratedHarness(
            name="bad_harness",
            files={
                "memory.py": "# no class",
                "planning.py": "# no class",
                "action.py": "# no class",
                "tool_policy.py": "# no class",
                "prompt.yaml": "{}",
            },
            task_description="Test task",
            meta_prompt="",
            meta_response="",
        )

        result = await executor.execute(harness, "Test task")
        assert result.success is False
        assert "Missing required strategy classes" in result.error


class TestJITPipeline:
    """Test end-to-end JIT pipeline."""

    @pytest.fixture
    def pipeline(self, tmp_path):
        from agent.jit_harness.pipeline import JITHarnessPipeline
        return JITHarnessPipeline(
            meta_model="test-model",
            meta_base_url="http://localhost:8000/v1",
            meta_api_key="test-key",
            num_candidates=2,
            selector_type="judge",
            judge_model="test-judge",
            judge_base_url="http://localhost:8000/v1",
            judge_api_key="test-key",
            execution_model="test-model",
            execution_base_url="http://localhost:8000/v1",
            execution_api_key="test-key",
            workspace_root=str(tmp_path),
        )

    def test_pipeline_initialization(self, pipeline):
        assert pipeline.num_candidates == 2
        assert pipeline.generator is not None
        assert pipeline.selector is not None
        assert pipeline.executor is not None

    @pytest.mark.asyncio
    async def test_health_check(self, pipeline):
        with patch("openai.AsyncOpenAI") as mock_client:
            mock_client.return_value.chat.completions.create = AsyncMock()
            health = await pipeline.health_check()
            assert "generator" in health
            assert "executor" in health

    @pytest.mark.asyncio
    async def test_run_no_candidates(self, pipeline):
        # Mock generator to return empty list
        pipeline.generator.generate = AsyncMock(return_value=[])

        result = await pipeline.run("Test task")
        assert result.metadata.get("error") == "No candidates generated"
        assert len(result.generated_candidates) == 0


class TestCLI:
    """Test CLI argument parsing."""

    def test_parse_args_with_task(self):
        from agent.jit_harness.cli import parse_args
        import sys

        # Mock sys.argv
        old_argv = sys.argv
        sys.argv = ["cli.py", "Test task", "--num-candidates", "5"]
        try:
            args = parse_args()
            assert args.task == "Test task"
            assert args.num_candidates == 5
        finally:
            sys.argv = old_argv

    def test_parse_args_with_task_option(self):
        from agent.jit_harness.cli import parse_args
        import sys

        old_argv = sys.argv
        sys.argv = ["cli.py", "--task", "Test task", "--meta-model", "gpt-4"]
        try:
            args = parse_args()
            assert args.task_opt == "Test task"
            assert args.meta_model == "gpt-4"
        finally:
            sys.argv = old_argv


class TestIntegration:
    """Integration-style tests (mocked external calls)."""

    @pytest.mark.asyncio
    async def test_full_pipeline_mocked(self, tmp_path):
        """Test full pipeline with all external calls mocked."""
        from agent.jit_harness.pipeline import JITHarnessPipeline
        from agent.jit_harness.protocols import GeneratedHarness

        pipeline = JITHarnessPipeline(
            meta_model="test-model",
            meta_base_url="http://localhost:8000/v1",
            meta_api_key="test-key",
            num_candidates=2,
            selector_type="judge",
            judge_model="test-judge",
            judge_base_url="http://localhost:8000/v1",
            judge_api_key="test-key",
            execution_model="test-model",
            execution_base_url="http://localhost:8000/v1",
            execution_api_key="test-key",
            workspace_root=str(tmp_path),
        )

        # Mock generator
        candidates = [
            GeneratedHarness(
                name=f"candidate_{i}",
                files={
                    "memory.py": "class MemoryStrategy:\n    pass",
                    "planning.py": "class PlanningStrategy:\n    pass",
                    "action.py": "class ActionStrategy:\n    pass",
                    "tool_policy.py": "class ToolPolicyStrategy:\n    pass",
                    "prompt.yaml": "system_prompt: 'Test'",
                },
                task_description="Test task",
                meta_prompt="",
                meta_response="",
            )
            for i in range(2)
        ]
        pipeline.generator.generate = AsyncMock(return_value=candidates)

        # Mock selector
        from agent.jit_harness.protocols import SelectionResult
        selection = SelectionResult(
            selected_harness=candidates[0],
            all_candidates=candidates,
            scores={"candidate_0": 0.9, "candidate_1": 0.5},
            selector_type="judge",
            selection_reason="Test",
        )
        pipeline.selector.select = AsyncMock(return_value=selection)

        # Mock executor
        from agent.jit_harness.protocols import ExecutionResult
        execution = ExecutionResult(
            success=True,
            final_answer="Done",
            score=1.0,
            trajectory=[],
            tokens_used=100,
            duration_s=1.0,
        )
        pipeline.executor.execute = AsyncMock(return_value=execution)

        result = await pipeline.run("Test task")

        assert len(result.generated_candidates) == 2
        assert result.selection_result.selected_harness.name == "candidate_0"
        assert result.execution_result.success is True
        assert result.execution_result.score == 1.0
        assert result.metadata["num_candidates"] == 2