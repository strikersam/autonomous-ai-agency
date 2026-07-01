"""packages/intelligence/self_improve.py — Controlled self-improvement.

Agents review completed work, evaluate failures, and suggest improvements.
All changes require explicit approval before modifying production behaviour.

Inspired by anywhere-agents (self-improvement) and OpenMythos (reflection),
implemented natively using the existing packages/ architecture.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from packages.intelligence.reflector import Reflection
from packages.knowledge.store import get_knowledge_store

log = logging.getLogger("intelligence.self_improve")


@dataclass
class ImprovementSuggestion:
    """A suggested improvement (requires approval before action)."""
    id: str
    category: str  # "prompt", "workflow", "knowledge", "config"
    description: str
    rationale: str
    impact: str  # "low", "medium", "high"
    approved: bool = False
    applied: bool = False
    created_at: str = ""


class SelfImprover:
    """Controlled self-improvement mechanism.

    Reviews completed work and suggests improvements. All suggestions
    require explicit approval before any production changes are made.

    Improvement categories:
    1. Prompt improvements — better system prompts based on what worked
    2. Workflow improvements — better step ordering or tool selection
    3. Knowledge improvements — new knowledge entries from lessons learned
    4. Config improvements — better model/provider selection for specific tasks
    """

    def __init__(self) -> None:
        self._suggestions: list[ImprovementSuggestion] = []
        self._knowledge = get_knowledge_store()

    async def review_task(
        self,
        goal: str,
        output: str,
        reflection: Reflection,
        errors: list[str] | None = None,
    ) -> list[ImprovementSuggestion]:
        """Review a completed task and suggest improvements.

        Args:
            goal: What the task was trying to accomplish
            output: The actual output produced
            reflection: Quality assessment from the Reflector
            errors: Any errors that occurred

        Returns:
            List of improvement suggestions (all unapproved)
        """
        errors = errors or []
        suggestions: list[ImprovementSuggestion] = []

        # 1. If quality is low, suggest prompt improvement
        if reflection.quality_score < 0.5:
            suggestions.append(ImprovementSuggestion(
                id=f"sugg_{len(self._suggestions)}",
                category="prompt",
                description=f"Improve the prompt for tasks like: {goal[:100]}",
                rationale=f"Quality score was {reflection.quality_score:.0%} — below 50%",
                impact="medium",
            ))

        # 2. If errors occurred, suggest workflow improvement
        if errors:
            suggestions.append(ImprovementSuggestion(
                id=f"sugg_{len(self._suggestions) + 1}",
                category="workflow",
                description=f"Add error handling for: {errors[0][:100]}",
                rationale=f"Task failed with: {errors[0][:100]}",
                impact="high",
            ))

        # 3. If task succeeded with high quality, create knowledge
        if reflection.quality_score > 0.8 and not errors:
            suggestions.append(ImprovementSuggestion(
                id=f"sugg_{len(self._suggestions) + 2}",
                category="knowledge",
                description=f"Save successful approach as reusable knowledge: {goal[:100]}",
                rationale="High-quality output — pattern worth remembering",
                impact="low",
            ))

        # 4. If retry was needed, suggest config improvement
        if reflection.should_retry:
            suggestions.append(ImprovementSuggestion(
                id=f"sugg_{len(self._suggestions) + 3}",
                category="config",
                description="Consider using a different model or provider for this task type",
                rationale="Task required retry — current model may not be optimal",
                impact="medium",
            ))

        self._suggestions.extend(suggestions)
        log.info("Self-improvement review: %d suggestions for goal=%r", len(suggestions), goal[:80])
        return suggestions

    def approve(self, suggestion_id: str) -> bool:
        """Approve a suggestion for implementation."""
        for s in self._suggestions:
            if s.id == suggestion_id:
                s.approved = True
                log.info("Suggestion approved: %s", s.id)
                return True
        return False

    async def apply_approved(self) -> list[str]:
        """Apply all approved suggestions. Returns list of applied IDs."""
        applied = []
        for s in self._suggestions:
            if s.approved and not s.applied:
                await self._apply_suggestion(s)
                s.applied = True
                applied.append(s.id)
        if applied:
            log.info("Applied %d approved suggestions", len(applied))
        return applied

    async def _apply_suggestion(self, suggestion: ImprovementSuggestion) -> None:
        """Apply a single approved suggestion."""
        if suggestion.category == "knowledge":
            # Save as long-term knowledge
            await self._knowledge.remember(
                suggestion.description,
                source="self_improvement",
                agent_id="system",
                tags=["improvement", suggestion.category],
                long_term=True,
            )
            log.info("Knowledge saved from suggestion: %s", suggestion.id)
        # Other categories (prompt, workflow, config) require manual implementation
        # — logged for the operator to review

    def pending_suggestions(self) -> list[ImprovementSuggestion]:
        """Return all unapproved suggestions."""
        return [s for s in self._suggestions if not s.approved]

    def all_suggestions(self) -> list[ImprovementSuggestion]:
        """Return all suggestions."""
        return list(self._suggestions)


# Singleton
_improver: SelfImprover | None = None


def get_self_improver() -> SelfImprover:
    """Return the global self-improver singleton."""
    global _improver
    if _improver is None:
        _improver = SelfImprover()
    return _improver
