"""packages/intelligence/verifier.py — Output verification.

Verifies that task output meets the stated requirements before
accepting it as complete. Inspired by OpenMythos (verification,
consensus) and anywhere-agents (self-validation).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("intelligence.verifier")


@dataclass
class VerificationResult:
    """Result of verifying task output."""
    passed: bool
    checks_passed: int = 0
    checks_total: int = 0
    failures: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class Verifier:
    """Verifies task output against requirements.

    Checks:
    1. Output is non-empty
    2. Output addresses the goal (keyword overlap)
    3. Output meets minimum quality (length, structure)
    4. No error indicators in output
    """

    def __init__(self, min_output_length: int = 10) -> None:
        self.min_output_length = min_output_length

    async def verify(
        self,
        goal: str,
        output: str,
        requirements: list[str] | None = None,
        context: str = "",
    ) -> VerificationResult:
        """Verify that output meets the goal + requirements.

        Args:
            goal: What the task was trying to accomplish
            output: The actual output produced
            requirements: Specific requirements to check (optional)
            context: Additional context

        Returns:
            VerificationResult with pass/fail + details
        """
        requirements = requirements or []
        failures: list[str] = []
        suggestions: list[str] = []
        checks_passed = 0
        checks_total = 0

        # Check 1: Non-empty output
        checks_total += 1
        if not output or len(output.strip()) == 0:
            failures.append("Output is empty")
        else:
            checks_passed += 1

        # Check 2: Minimum length
        checks_total += 1
        if len(output.strip()) < self.min_output_length:
            failures.append(f"Output too short ({len(output.strip())} chars, minimum {self.min_output_length})")
        else:
            checks_passed += 1

        # Check 3: Goal relevance (keyword overlap)
        checks_total += 1
        goal_words = set(goal.lower().split())
        output_words = set(output.lower().split())
        overlap = len(goal_words & output_words)
        if goal_words and overlap == 0:
            failures.append("Output doesn't contain any keywords from the goal")
            suggestions.append("Ensure the output directly addresses the stated goal")
        else:
            checks_passed += 1

        # Check 4: No error indicators
        checks_total += 1
        error_indicators = ["error:", "traceback", "exception", "failed:", "null", "undefined"]
        output_lower = output.lower()
        found_errors = [e for e in error_indicators if e in output_lower]
        if found_errors:
            failures.append(f"Error indicators in output: {found_errors}")
            suggestions.append("Review and fix the errors before accepting output")
        else:
            checks_passed += 1

        # Check 5: Requirements (if specified)
        for req in requirements:
            checks_total += 1
            req_words = set(req.lower().split())
            if req_words & output_words:
                checks_passed += 1
            else:
                failures.append(f"Requirement not met: {req}")

        passed = checks_passed == checks_total
        result = VerificationResult(
            passed=passed,
            checks_passed=checks_passed,
            checks_total=checks_total,
            failures=failures,
            suggestions=suggestions,
        )
        log.info(
            "Verification: passed=%s (%d/%d checks), goal=%r",
            passed, checks_passed, checks_total, goal[:80],
        )
        return result
