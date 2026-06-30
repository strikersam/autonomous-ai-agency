"""packages/intelligence/reflector.py — Self-evaluation + improvement.

Evaluates the quality of completed work and suggests improvements.
Inspired by OpenMythos (reflection, self-critique) and anywhere-agents
(self-improvement), implemented natively.

The reflector never modifies production behaviour directly — it produces
suggestions that require explicit approval before action.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("intelligence.reflector")


@dataclass
class Reflection:
    """Result of reflecting on completed work."""
    quality_score: float  # 0.0 - 1.0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    should_retry: bool = False
    retry_reason: str = ""


class Reflector:
    """Evaluates completed work and suggests improvements.

    The reflector is called after each task or step to:
    1. Assess output quality
    2. Identify what went well
    3. Identify what could be improved
    4. Suggest specific improvements
    5. Decide if a retry is warranted

    All suggestions require explicit approval before modifying production.
    """

    def __init__(self, quality_threshold: float = 0.7) -> None:
        self.quality_threshold = quality_threshold

    async def reflect(
        self,
        goal: str,
        output: str,
        context: str = "",
        errors: list[str] | None = None,
    ) -> Reflection:
        """Reflect on completed work.

        Args:
            goal: What was the task trying to accomplish
            output: The actual output produced
            context: Additional context (plan, prior steps)
            errors: Any errors that occurred during execution

        Returns:
            A Reflection with quality assessment + suggestions
        """
        errors = errors or []

        # Simple heuristic evaluation (LLM-based evaluation will be added)
        quality = self._heuristic_quality(goal, output, errors)

        reflection = Reflection(
            quality_score=quality,
            should_retry=(quality < self.quality_threshold) and (bool(errors) or not output),
            retry_reason=f"Quality {quality:.0%} below threshold {self.quality_threshold:.0%}"
            if quality < self.quality_threshold
            else "",
        )

        if quality >= self.quality_threshold:
            reflection.strengths.append("Output meets quality threshold")
        else:
            reflection.weaknesses.append(f"Quality {quality:.0%} below threshold")

        if errors:
            reflection.weaknesses.extend(errors[:3])

        log.info(
            "Reflection: quality=%.0f%%, retry=%s, goal=%r",
            quality * 100, reflection.should_retry, goal[:80],
        )
        return reflection

    def _heuristic_quality(
        self, goal: str, output: str, errors: list[str]
    ) -> float:
        """Simple heuristic quality assessment.

        Full implementation will use LLM-based evaluation.
        """
        if not output:
            return 0.0
        if errors:
            return 0.3
        # Basic checks: output length, goal relevance
        score = 0.5  # Base score
        if len(output) > 50:
            score += 0.2
        if len(output) > 200:
            score += 0.1
        if any(word in output.lower() for word in goal.lower().split()[:3]):
            score += 0.2
        return min(score, 1.0)

    async def suggest_improvements(
        self, reflection: Reflection, historical: list[Reflection] | None = None
    ) -> list[str]:
        """Suggest specific improvements based on reflection + history.

        Args:
            reflection: Current reflection
            historical: Past reflections on similar tasks

        Returns:
            List of improvement suggestions (require approval to implement)
        """
        suggestions = list(reflection.suggestions)

        if historical:
            # Learn from patterns in past failures
            failure_count = sum(1 for r in historical if r.should_retry)
            if failure_count > 2:
                suggestions.append(
                    "This task type has failed multiple times — "
                    "consider revising the approach or prompt"
                )

        return suggestions
