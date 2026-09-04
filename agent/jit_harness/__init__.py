"""agent/jit_harness — Just-in-Time Harness Generation

Inspired by JIT-Agent: a meta-model writes a complete agent harness per task,
then the best harness is selected and executed.

This module provides:
- HarnessGenerator: generates N candidate harnesses via a meta-model
- HarnessSelector: picks the best harness via logprobs or judge model
- HarnessExecutor: runs the selected harness through the agent runtime
- JITHarnessPipeline: end-to-end pipeline combining all three
"""

from __future__ import annotations

from .generator import HarnessGenerator, GeneratedHarness
from .selector import HarnessSelector, SelectionResult
from .executor import HarnessExecutor, ExecutionResult
from .protocols import (
    HarnessGeneratorProtocol,
    HarnessSelectorProtocol,
    HarnessExecutorProtocol,
)
from .pipeline import JITHarnessPipeline, PipelineResult

__all__ = [
    "HarnessGenerator",
    "GeneratedHarness",
    "HarnessSelector",
    "SelectionResult",
    "HarnessExecutor",
    "ExecutionResult",
    "HarnessGeneratorProtocol",
    "HarnessSelectorProtocol",
    "HarnessExecutorProtocol",
    "JITHarnessPipeline",
    "PipelineResult",
]