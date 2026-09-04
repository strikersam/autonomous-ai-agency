"""agent/jit_harness/selector.py — Harness selection via logprobs or judge model."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from agent.jit_harness.protocols import GeneratedHarness, HarnessSelectorProtocol, SelectionResult

log = logging.getLogger(__name__)


# Judge prompt for harness evaluation
JUDGE_SYSTEM_PROMPT = """You are an expert evaluator of agent architectures.

You will be given a task and several candidate harnesses (agent architectures).
Score each harness from 0.0 to 1.0 based on how well its design matches the task.

Consider:
1. Task-structure fit — does the architecture match the task's demands?
2. Tool selection — does it expose the right tools at the right steps?
3. Memory strategy — does it handle context appropriately for this task?
4. Planning approach — is the planning depth appropriate?
5. Innovation — does it go beyond the reference baselines?

Output JSON: {{"harness_name": score, ...}} with one entry per harness.
"""


JUDGE_USER_TEMPLATE = """Task:
{task}

Candidate Harnesses:
{harness_summaries}

Score each harness from 0.0 to 1.0. Output JSON only.
"""


@dataclass
class HarnessSelector(HarnessSelectorProtocol):
    """Selects the best harness from candidates."""

    selector_type: str = "judge"  # "judge" or "logprob"
    judge_model: str = "gpt-4o-mini"
    judge_base_url: str = "https://api.openai.com/v1"
    judge_api_key: Optional[str] = None
    judge_temperature: float = 0.0
    judge_max_tokens: int = 1024

    def __post_init__(self):
        if self.judge_api_key is None:
            self.judge_api_key = os.environ.get("JIT_JUDGE_API_KEY") or os.environ.get("OPENAI_API_KEY")

    async def select(
        self,
        task: str,
        candidates: list[GeneratedHarness],
        **kwargs,
    ) -> SelectionResult:
        """Select the best harness from candidates."""
        if not candidates:
            raise ValueError("No candidates to select from")

        if self.selector_type == "logprob":
            return await self._select_logprob(task, candidates, **kwargs)
        else:
            return await self._select_judge(task, candidates, **kwargs)

    async def _select_judge(
        self,
        task: str,
        candidates: list[GeneratedHarness],
        **kwargs,
    ) -> SelectionResult:
        """Select using a judge LLM."""
        try:
            from openai import AsyncOpenAI
        except ImportError:
            log.error("openai package not installed")
            return self._fallback_selection(candidates)

        client = AsyncOpenAI(
            base_url=self.judge_base_url,
            api_key=self.judge_api_key,
        )

        # Build harness summaries for the judge
        harness_summaries = []
        for h in candidates:
            summary = self._summarize_harness(h)
            harness_summaries.append(f"### {h.name}\n{summary}")

        user_prompt = JUDGE_USER_TEMPLATE.format(
            task=task,
            harness_summaries="\n\n".join(harness_summaries),
        )

        try:
            response = await client.chat.completions.create(
                model=self.judge_model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.judge_temperature,
                max_tokens=self.judge_max_tokens,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            scores = json.loads(content)

            # Find best
            best_name = max(scores, key=scores.get)
            best_harness = next(h for h in candidates if h.name == best_name)

            log.info("Judge selected %s with score %.3f", best_name, scores[best_name])

            return SelectionResult(
                selected_harness=best_harness,
                all_candidates=candidates,
                scores=scores,
                selector_type="judge",
                selection_reason=f"Judge model scored {best_name} highest ({scores[best_name]:.3f})",
                metadata={"judge_model": self.judge_model, "judge_response": content},
            )

        except Exception as exc:
            log.exception("Judge selection failed, falling back")
            return self._fallback_selection(candidates)

    async def _select_logprob(
        self,
        task: str,
        candidates: list[GeneratedHarness],
        **kwargs,
    ) -> SelectionResult:
        """Select using logprobs from the meta-model (requires local model with prompt_logprobs)."""
        # This requires the meta-model to be a local model that exposes logprobs
        # For now, fall back to first candidate
        log.warning("Logprob selection not fully implemented, using first candidate")
        return self._fallback_selection(candidates)

    def _summarize_harness(self, harness: GeneratedHarness) -> str:
        """Create a compact summary of a harness for the judge."""
        parts = []
        for filename in ["memory.py", "planning.py", "action.py", "tool_policy.py"]:
            content = harness.files.get(filename, "")
            # Extract class names and key methods
            lines = content.split("\n")
            class_lines = [l for l in lines if l.strip().startswith("class ")]
            if class_lines:
                parts.append(f"{filename}: {class_lines[0].strip()}")
        return "\n".join(parts) or "No summary available"

    def _fallback_selection(self, candidates: list[GeneratedHarness]) -> SelectionResult:
        """Fallback: pick first candidate."""
        return SelectionResult(
            selected_harness=candidates[0],
            all_candidates=candidates,
            scores={candidates[0].name: 1.0},
            selector_type="fallback",
            selection_reason="Fallback to first candidate (selection failed)",
            metadata={},
        )