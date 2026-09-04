"""agent/jit_harness/pipeline.py — End-to-end JIT harness pipeline."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.jit_harness.generator import HarnessGenerator
from agent.jit_harness.selector import HarnessSelector
from agent.jit_harness.executor import HarnessExecutor
from agent.jit_harness.protocols import (
    GeneratedHarness,
    SelectionResult,
    ExecutionResult,
)

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete result of a JIT harness pipeline run."""

    task: str
    generated_candidates: list[GeneratedHarness] = field(default_factory=list)
    selection_result: Optional[SelectionResult] = None
    execution_result: Optional[ExecutionResult] = None
    total_duration_s: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "generated_candidates": [h.to_dict() for h in self.generated_candidates],
            "selection_result": self.selection_result.to_dict() if self.selection_result else None,
            "execution_result": self.execution_result.to_dict() if self.execution_result else None,
            "total_duration_s": self.total_duration_s,
            "metadata": self.metadata,
        }


class JITHarnessPipeline:
    """
    End-to-end JIT harness pipeline:
    1. Generate N candidate harnesses via meta-model
    2. Select best harness via judge or logprobs
    3. Execute selected harness against the task
    """

    def __init__(
        self,
        # Generator config
        meta_model: str = "gpt-4o",
        meta_base_url: str = "https://api.openai.com/v1",
        meta_api_key: Optional[str] = None,
        meta_temperature: float = 0.7,
        meta_max_tokens: int = 32768,
        num_candidates: int = 3,
        reference_mode: str = "desc",
        reference_k: int = 3,
        # Selector config
        selector_type: str = "judge",
        judge_model: str = "gpt-4o-mini",
        judge_base_url: str = "https://api.openai.com/v1",
        judge_api_key: Optional[str] = None,
        # Executor config
        execution_model: str = "gpt-4o",
        execution_base_url: str = "https://api.openai.com/v1",
        execution_api_key: Optional[str] = None,
        max_steps: int = 40,
        model_call_budget: Optional[int] = None,
        workspace_root: Optional[str] = None,
        trace_dir: Optional[str] = None,
    ):
        self.generator = HarnessGenerator(
            meta_model=meta_model,
            meta_base_url=meta_base_url,
            meta_api_key=meta_api_key,
            meta_temperature=meta_temperature,
            max_tokens=meta_max_tokens,
            reference_mode=reference_mode,
            reference_k=reference_k,
        )
        self.selector = HarnessSelector(
            selector_type=selector_type,
            judge_model=judge_model,
            judge_base_url=judge_base_url,
            judge_api_key=judge_api_key,
        )
        self.executor = HarnessExecutor(
            workspace_root=workspace_root,
            max_steps=max_steps,
            model_call_budget=model_call_budget,
            trace_dir=trace_dir,
            execution_model=execution_model,
            execution_base_url=execution_base_url,
            execution_api_key=execution_api_key,
        )
        self.num_candidates = num_candidates

    async def run(
        self,
        task: str,
        num_candidates: Optional[int] = None,
        **kwargs,
    ) -> PipelineResult:
        """Run the full JIT pipeline for a task."""
        start_time = time.time()
        n = num_candidates or self.num_candidates

        log.info("Starting JIT pipeline for task: %s...", task[:80])

        # Phase 1: Generate candidates
        log.info("Phase 1: Generating %d harness candidates...", n)
        candidates = await self.generator.generate(task, num_candidates=n, **kwargs)

        if not candidates:
            return PipelineResult(
                task=task,
                total_duration_s=time.time() - start_time,
                metadata={"error": "No candidates generated"},
            )

        log.info("Generated %d candidates", len(candidates))

        # Phase 2: Select best
        log.info("Phase 2: Selecting best harness...")
        selection = await self.selector.select(task, candidates, **kwargs)
        log.info("Selected: %s (%.3f)", selection.selected_harness.name, 
                 selection.scores.get(selection.selected_harness.name, 0))

        # Phase 3: Execute
        log.info("Phase 3: Executing selected harness...")
        execution = await self.executor.execute(selection.selected_harness, task, **kwargs)
        log.info("Execution complete: success=%s, score=%.3f", execution.success, execution.score)

        duration = time.time() - start_time

        return PipelineResult(
            task=task,
            generated_candidates=candidates,
            selection_result=selection,
            execution_result=execution,
            total_duration_s=duration,
            metadata={
                "num_candidates": len(candidates),
                "selector_type": selection.selector_type,
                "selected_harness": selection.selected_harness.name,
            },
        )

    async def health_check(self) -> dict[str, bool]:
        """Check health of all components."""
        return {
            "generator": await self.generator.health_check(),
            "executor": True,  # Executor uses local runtime
        }

    async def cleanup(self) -> None:
        """Clean up resources."""
        await self.executor.cleanup()