"""agent/jit_harness/executor.py — Execute a generated harness via the agent runtime."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import shutil
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent.jit_harness.protocols import ExecutionResult, GeneratedHarness, HarnessExecutorProtocol

log = logging.getLogger(__name__)


@dataclass
class HarnessExecutor(HarnessExecutorProtocol):
    """Executes a generated harness against a task."""

    workspace_root: Optional[str] = None
    max_steps: int = 40
    model_call_budget: Optional[int] = None
    trace_dir: Optional[str] = None
    execution_model: str = "gpt-4o"
    execution_base_url: str = "https://api.openai.com/v1"
    execution_api_key: Optional[str] = None

    def __post_init__(self):
        if self.execution_api_key is None:
            self.execution_api_key = os.environ.get("JIT_EXEC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if self.workspace_root is None:
            self.workspace_root = tempfile.mkdtemp(prefix="jit_exec_")

    async def execute(
        self,
        harness: GeneratedHarness,
        task: str,
        **kwargs,
    ) -> ExecutionResult:
        """Execute the harness against a task."""
        start_time = time.time()
        exec_dir = Path(self.workspace_root) / harness.name
        exec_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Write harness files to execution directory
            await self._write_harness(harness, exec_dir)

            # Load and run the harness via the kernel runtime
            result = await self._run_harness(exec_dir, harness, task, **kwargs)

            duration = time.time() - start_time
            return ExecutionResult(
                success=result.get("success", False),
                final_answer=result.get("answer", ""),
                score=result.get("score", 0.0),
                trajectory=result.get("trajectory", []),
                error=result.get("error"),
                tokens_used=result.get("tokens_used", 0),
                duration_s=duration,
                metadata=result.get("metadata", {}),
            )

        except Exception as exc:
            log.exception("Harness execution failed")
            return ExecutionResult(
                success=False,
                final_answer="",
                score=0.0,
                trajectory=[],
                error=str(exc),
                duration_s=time.time() - start_time,
            )

    async def _write_harness(self, harness: GeneratedHarness, exec_dir: Path) -> None:
        """Write harness files to execution directory."""
        # Write the 5 harness files
        for filename, content in harness.files.items():
            (exec_dir / filename).write_text(content, encoding="utf-8")

        # Create __init__.py to make it importable
        (exec_dir / "__init__.py").write_text(
            f'"""Generated harness: {harness.name}"""\n', encoding="utf-8"
        )

        log.debug("Wrote harness to %s", exec_dir)

    async def _run_harness(
        self,
        exec_dir: Path,
        harness: GeneratedHarness,
        task: str,
        **kwargs,
    ) -> dict:
        """Run the harness using the agent runtime."""
        # Add execution directory to Python path
        sys.path.insert(0, str(exec_dir))

        try:
            # Import the harness modules
            memory_mod = self._import_module(exec_dir, "memory")
            planning_mod = self._import_module(exec_dir, "planning")
            action_mod = self._import_module(exec_dir, "action")
            tool_policy_mod = self._import_module(exec_dir, "tool_policy")
            prompt_data = self._load_prompt_yaml(exec_dir / "prompt.yaml")

            # Get the strategy classes
            MemoryStrategy = getattr(memory_mod, "MemoryStrategy", None)
            PlanningStrategy = getattr(planning_mod, "PlanningStrategy", None)
            ActionStrategy = getattr(action_mod, "ActionStrategy", None)
            ToolPolicyStrategy = getattr(tool_policy_mod, "ToolPolicyStrategy", None)

            if not all([MemoryStrategy, PlanningStrategy, ActionStrategy, ToolPolicyStrategy]):
                raise RuntimeError("Missing required strategy classes in harness")

            # Create runtime config
            config = {
                "harness": harness.name,
                "model": {
                    "model_id": self.execution_model,
                    "base_url": self.execution_base_url,
                    "api_key": self.execution_api_key,
                },
                "tools": kwargs.get("tools", []),
                "execution": {
                    "max_steps": self.max_steps,
                    "model_call_budget": self.model_call_budget,
                },
            }

            # Create and run the agent runtime
            from scripts.kernel.runtime import AgentRuntime

            runtime = AgentRuntime(
                config=config,
                trace_dir=self.trace_dir,
            )

            # Replace the default strategies with the generated ones
            runtime.memory = MemoryStrategy(prompts=prompt_data)
            runtime.planning = PlanningStrategy(prompts=prompt_data)
            runtime.action = ActionStrategy(prompts=prompt_data)
            runtime.tool_policy = ToolPolicyStrategy(prompts=prompt_data)

            # Run the task
            result = await asyncio.to_thread(runtime.run, task)

            # Convert RunResult to dict
            return {
                "success": result.terminated_reason == "final_answer",
                "answer": str(result.answer) if result.answer else "",
                "score": 1.0 if result.terminated_reason == "final_answer" else 0.0,
                "trajectory": [s.dict() for s in result.trajectory],
                "tokens_used": result.metadata.get("total_token_count", 0),
                "metadata": result.metadata,
            }

        except Exception as exc:
            log.exception("Failed to run harness")
            return {
                "success": False,
                "answer": "",
                "score": 0.0,
                "trajectory": [],
                "error": str(exc),
                "tokens_used": 0,
                "metadata": {},
            }
        finally:
            # Clean up path
            if str(exec_dir) in sys.path:
                sys.path.remove(str(exec_dir))

    def _import_module(self, exec_dir: Path, module_name: str):
        """Import a module from the execution directory."""
        module_path = exec_dir / f"{module_name}.py"
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load {module_name} from {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _load_prompt_yaml(self, path: Path) -> dict:
        """Load prompt.yaml as a dict."""
        import yaml
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}

    async def cleanup(self) -> None:
        """Clean up execution workspace."""
        if self.workspace_root and os.path.exists(self.workspace_root):
            shutil.rmtree(self.workspace_root, ignore_errors=True)