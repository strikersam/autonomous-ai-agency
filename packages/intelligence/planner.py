"""packages/intelligence/planner.py — Task decomposition + planning.

Decomposes complex tasks into executable steps, selects the right tool
for each step, and creates an execution plan that the agent follows.

Design inspired by OpenMythos (task decomposition, planning) and
anywhere-agents (agent orchestration), implemented natively using the
existing packages/ai/ + packages/tools/ architecture.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from packages.ai.registry import model_for_role
from packages.tools.registry import get_tool_registry

log = logging.getLogger("intelligence.planner")


@dataclass
class PlanStep:
    """A single step in an execution plan."""
    id: str
    description: str
    tool_name: str | None = None  # Which tool to use (None = LLM reasoning)
    tool_kwargs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)  # Step IDs this depends on
    expected_output: str = ""
    status: str = "pending"  # pending, in_progress, completed, failed, skipped
    result: Any = None
    error: str | None = None


@dataclass
class ExecutionPlan:
    """A plan for executing a complex task."""
    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    created_at: str = ""
    model: str = ""
    provider: str = ""

    @property
    def is_complete(self) -> bool:
        return all(s.status in ("completed", "skipped") for s in self.steps)

    @property
    def next_step(self) -> PlanStep | None:
        """Find the next executable step (all dependencies completed)."""
        completed = {s.id for s in self.steps if s.status == "completed"}
        for step in self.steps:
            if step.status == "pending":
                if all(dep in completed for dep in step.depends_on):
                    return step
        return None


class Planner:
    """Decomposes tasks into executable plans.

    Uses the LLM to decompose a goal into steps, then matches each step
    to the best available tool from the ToolRegistry.
    """

    def __init__(self, provider: str | None = None) -> None:
        self.provider = provider
        self._registry = get_tool_registry()

    async def create_plan(self, goal: str, context: str = "") -> ExecutionPlan:
        """Create an execution plan for a goal.

        Args:
            goal: What the user wants to accomplish
            context: Additional context (conversation history, prior knowledge)

        Returns:
            An ExecutionPlan with steps to execute
        """
        # Get available tools for the LLM to choose from
        available_tools = self._registry.schemas()
        tool_descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in available_tools
        )

        # Build the planning prompt
        prompt = self._build_planning_prompt(goal, context, tool_descriptions)

        # Call the LLM to decompose the task
        from packages.ai.brain import resolve_active_brain
        brain = await resolve_active_brain()
        model = brain.model or model_for_role("planner", self.provider)

        # For now, create a simple single-step plan
        # (Full LLM-based decomposition will be added in the next iteration)
        plan = ExecutionPlan(
            goal=goal,
            steps=[
                PlanStep(
                    id="step-1",
                    description=goal,
                    tool_name=None,  # LLM reasoning
                    expected_output="Completed task",
                )
            ],
            model=model,
            provider=brain.provider_id,
        )

        log.info("Plan created: goal=%r, steps=%d", goal, len(plan.steps))
        return plan

    def _build_planning_prompt(
        self, goal: str, context: str, tool_descriptions: str
    ) -> str:
        """Build the LLM prompt for task decomposition."""
        return f"""You are a task planner. Decompose the following goal into executable steps.

Goal: {goal}

Context: {context}

Available tools:
{tool_descriptions}

Create a plan with clear steps. For each step, specify:
1. What to do
2. Which tool to use (or "reasoning" for LLM-only steps)
3. What the expected output is

Respond in JSON format:
{{"steps": [{{"description": "...", "tool": "...", "expected_output": "..."}}]}}
"""

    async def refine_plan(
        self, plan: ExecutionPlan, feedback: str
    ) -> ExecutionPlan:
        """Refine a plan based on execution feedback.

        Called when a step fails or the agent identifies a better approach.
        """
        log.info("Refining plan: goal=%r, feedback=%r", plan.goal, feedback[:100])
        # Mark failed steps as needing retry
        for step in plan.steps:
            if step.status == "failed":
                step.status = "pending"
                step.error = None
        return plan
