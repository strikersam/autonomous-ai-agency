"""agent/jit_harness/generator.py — Harness generation via meta-model."""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.jit_harness.protocols import GeneratedHarness, HarnessGeneratorProtocol

log = logging.getLogger(__name__)


# Default meta-model generation prompt
META_SYSTEM_PROMPT = """You are a meta-agent that writes complete agent harnesses.

A harness is a set of 5 Python files that implement an agent architecture:
- memory.py: MemoryStrategy — what the agent remembers and how it's rebuilt per step
- planning.py: PlanningStrategy — whether there's a plan and how it's revised
- action.py: ActionStrategy — how a step becomes a tool call or final answer
- tool_policy.py: ToolPolicyStrategy — which tools are offered at each step
- prompt.yaml: The prompts these modules render

Each class must be constructible as Cls(prompts=parsed_prompt_yaml) with a
fallback to Cls() for components that don't accept prompts.

The protocols are defined in scripts/kernel/protocols.py:
- BaseMemory: initialize, build_context, update, update_plan, update_summary
- BasePlanning: init_plan, should_replan, update_plan, get_directive
- BaseAction: run
- BaseToolPolicy: initialize, select_tools, get_skills_prompt

Shared types in scripts/kernel/types.py:
- Message, StepRecord, MemoryView, ToolSelection, Directive, RunResult
- PlanState, SummaryState, TaskInput, RuntimeContext

Write COMPLETE, runnable code. Include all imports. No stubs. No TODOs.
The harness will be executed against a task by an execution model.

Output format: a JSON object with one key per file, containing the file content.
Required keys: "memory.py", "planning.py", "action.py", "tool_policy.py", "prompt.yaml"
"""


# Reference harness descriptions (from harness_factory/descriptions/)
REFERENCE_DESCRIPTIONS = {
    "plan_and_execute": """Linear ReAct. Emits an ordered 3–7 step roadmap up front, then works it. The minimal baseline.""",
    "flash_searcher": """A planning call decomposes the task into a DAG of subtasks; execution follows dependency order.""",
    "agentfold": """DAG planning plus AgentFold-style context folding, so long trajectories stay inside the window.""",
    "resum": """Linear ReAct with ReSum-style token-budgeted summarisation of the trajectory.""",
    "hiagent": """Flat ReAct, no explicit plan; leans on a structured working memory instead.""",
    "memobrain": """Marker-based ReAct with a dependency-aware reasoning memory.""",
    "deepagent": """Flat, plan-free tool use over a marker protocol rather than JSON tool calls.""",
    "gam": """DAG planning coupled with Generative Agent Memory.""",
    "roma": """Recursive decomposition — for tasks with several semi-independent goals.""",
    "aggagent": """Two stages: explore broadly, then adjudicate the findings into an answer.""",
    "oagent": """Runs several independent solution paths and votes.""",
}


@dataclass
class HarnessGenerator(HarnessGeneratorProtocol):
    """Generates agent harnesses using a meta-model via OpenAI-compatible API."""

    meta_model: str = "gpt-4o"
    meta_base_url: str = "https://api.openai.com/v1"
    meta_api_key: Optional[str] = None
    meta_temperature: float = 0.7
    max_tokens: int = 32768
    timeout: float = 120.0

    # Reference material
    reference_mode: str = "desc"  # "desc" or "code"
    reference_k: int = 3
    reference_seed: Optional[int] = None

    def __post_init__(self):
        if self.meta_api_key is None:
            self.meta_api_key = os.environ.get("JIT_META_API_KEY") or os.environ.get("OPENAI_API_KEY")

    async def generate(
        self,
        task: str,
        num_candidates: int = 3,
        reference_mode: Optional[str] = None,
        reference_k: Optional[int] = None,
        **kwargs,
    ) -> list[GeneratedHarness]:
        """Generate N candidate harnesses for a task."""
        ref_mode = reference_mode or self.reference_mode
        ref_k = reference_k or self.reference_k

        # Build reference material
        ref_block = self._build_reference_block(ref_mode, ref_k)

        candidates = []
        for i in range(num_candidates):
            # Vary temperature slightly for diversity
            temp = self.meta_temperature + (i * 0.1)
            harness = await self._generate_one(task, ref_block, candidate_id=i, temperature=temp, **kwargs)
            if harness:
                candidates.append(harness)

        return candidates

    async def _generate_one(
        self,
        task: str,
        ref_block: str,
        candidate_id: int,
        temperature: float,
        **kwargs,
    ) -> Optional[GeneratedHarness]:
        """Generate a single harness candidate."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            log.error("openai package not installed")
            return None

        client = AsyncOpenAI(
            base_url=self.meta_base_url,
            api_key=self.meta_api_key,
            timeout=self.timeout,
        )

        # Build the generation prompt
        user_prompt = self._build_user_prompt(task, ref_block, candidate_id)

        try:
            response = await client.chat.completions.create(
                model=self.meta_model,
                messages=[
                    {"role": "system", "content": META_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Parse JSON response
            files = json.loads(content)

            # Validate required files
            required = ["memory.py", "planning.py", "action.py", "tool_policy.py", "prompt.yaml"]
            for req in required:
                if req not in files:
                    log.warning("Generated harness missing required file: %s", req)
                    return None

            harness = GeneratedHarness(
                name=f"jit_harness_{uuid.uuid4().hex[:8]}",
                files=files,
                task_description=task,
                meta_prompt=user_prompt,
                meta_response=content,
                tokens_used=tokens_used,
                metadata={
                    "candidate_id": candidate_id,
                    "temperature": temperature,
                    "model": self.meta_model,
                },
            )
            log.info("Generated harness candidate %d: %s (%d tokens)", candidate_id, harness.name, tokens_used)
            return harness

        except Exception as exc:
            log.exception("Failed to generate harness candidate %d", candidate_id)
            return None

    def _build_reference_block(self, mode: str, k: int) -> str:
        """Build reference material for the meta-model prompt."""
        if mode == "code":
            # In code mode, we'd load full source from harness_factory/harnesses/
            # For now, use descriptions with a note
            refs = list(REFERENCE_DESCRIPTIONS.items())[:k]
            block = "### 3. Agent harness examples (full source):\n\n"
            for name, desc in refs:
                block += f"#### {name}\n{desc}\n\n[Full source code would be shown here]\n\n"
            return block
        else:
            # Description mode (default)
            refs = list(REFERENCE_DESCRIPTIONS.items())
            block = "### 3. Agent harness catalogue (descriptions, no code):\n\n"
            for name, desc in refs:
                block += f"- **{name}**: {desc}\n"
            return block

    def _build_user_prompt(self, task: str, ref_block: str, candidate_id: int) -> str:
        """Build the user prompt for harness generation."""
        return f"""Task to solve:
{task}

{ref_block}

### 4. Your task
Design a novel agent architecture specialized for this task. Be creative — the reference
harnesses are starting points, not constraints. Your harness should exploit the specific
structure of this task.

Output a JSON object with exactly these 5 keys:
- "memory.py"
- "planning.py" 
- "action.py"
- "tool_policy.py"
- "prompt.yaml"

Each value is the complete file content as a string. Escape newlines as \\n in JSON.
"""

    async def health_check(self) -> bool:
        """Check if the meta-model endpoint is available."""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                base_url=self.meta_base_url,
                api_key=self.meta_api_key,
                timeout=10.0,
            )
            # Try a minimal request
            await client.chat.completions.create(
                model=self.meta_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception:
            return False