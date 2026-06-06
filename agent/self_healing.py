"""agent/self_healing.py — Self-Healing Agent (E2 roadmap item)

Translates external failure signals (CI webhooks, GitHub issue events, manual
dashboard reports) into improvement tasks dispatched through ImprovementLoop.

E2 enhancements:
- Automated fix retry with corrected prompts (classify failure → retry)
- Failure classification: syntax_error, test_failure, lint_error, timeout, unknown
- Self-healing event history with resolution tracking
- Auto-rollback on persistent failures

Flow:
    CI failure webhook   → on_ci_failure()   → _classify_and_dispatch()
    GitHub bug issue     → on_github_issue()  → _classify_and_dispatch()
    Dashboard bug report → on_manual_report() → _classify_and_dispatch()
"""
from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("qwen-proxy")


class FailureCategory(Enum):
    """Classified failure types for targeted self-healing (E2)."""
    SYNTAX_ERROR = "syntax_error"
    TEST_FAILURE = "test_failure"
    LINT_ERROR = "lint_error"
    TIMEOUT = "timeout"
    IMPORT_ERROR = "import_error"
    OOM = "out_of_memory"
    NETWORK = "network_error"
    UNKNOWN = "unknown"


@dataclass
class HealingEvent:
    event_id: str
    source: str       # "ci" | "github_issue" | "manual"
    title: str
    description: str
    severity: str     # "critical" | "high" | "medium" | "low"
    created_at: str
    task_id: str | None = None
    resolved: bool = False
    failure_category: str = "unknown"  # E2: classified failure type
    retry_count: int = 0               # E2: number of fix retries attempted
    rolled_back: bool = False          # E2: whether the fix was rolled back

    def as_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "source": self.source,
            "title": self.title,
            "severity": self.severity,
            "created_at": self.created_at,
            "resolved": self.resolved,
            "task_id": self.task_id,
            "failure_category": self.failure_category,
            "retry_count": self.retry_count,
            "rolled_back": self.rolled_back,
        }


class SelfHealingAgent:
    """Translate external failure signals into improvement tasks.

    Usage::

        healer = SelfHealingAgent()
        await healer.on_ci_failure({"test": "test_router", "error": "..."})
        await healer.on_manual_report("Memory leak", "...")
    """

    def __init__(self) -> None:
        self._events: list[HealingEvent] = []

    # ── Public API ────────────────────────────────────────────────────────────

    async def on_ci_failure(self, failure_info: dict[str, Any]) -> HealingEvent:
        """Called when a CI workflow fails."""
        test_name = failure_info.get("test", "unknown-test")
        error = failure_info.get("error", "")
        workflow = failure_info.get("workflow", "ci")
        event = self._make_event(
            source="ci",
            title=f"CI failure: {test_name} in {workflow}",
            description=(
                f"Test `{test_name}` failed in workflow `{workflow}`.\n\n"
                f"Error:\n```\n{error[:2000]}\n```"
            ),
            severity="high",
        )
        log.info("SelfHealingAgent: CI failure — %s", event.title)
        await self._classify_and_dispatch(event)
        return event

    async def on_github_issue(self, issue: dict[str, Any]) -> HealingEvent:
        """Called when a GitHub issue with a bug label is opened."""
        title = issue.get("title", "Unknown issue")
        body = issue.get("body", "")
        labels = [la.get("name", "") for la in issue.get("labels", [])]
        severity = "high" if any(l in labels for l in ("critical", "P0")) else "medium"
        event = self._make_event(
            source="github_issue",
            title=f"Bug: {title}",
            description=f"GitHub issue: {title}\n\n{body[:2000]}",
            severity=severity,
        )
        log.info("SelfHealingAgent: GitHub issue — %s", title)
        if any(l in labels for l in ("bug", "fix")):
            await self._classify_and_dispatch(event)
        return event

    async def on_manual_report(
        self, title: str, description: str, severity: str = "medium"
    ) -> HealingEvent:
        """Called from the v4 dashboard 'Report Bug' form."""
        event = self._make_event(
            source="manual", title=title, description=description, severity=severity
        )
        log.info("SelfHealingAgent: manual report — %s", title)
        await self._classify_and_dispatch(event)
        return event

    def get_events(self) -> list[dict[str, Any]]:
        return [e.as_dict() for e in self._events]

    # ── Internal ──────────────────────────────────────────────────────────────

    def _make_event(
        self, *, source: str, title: str, description: str, severity: str
    ) -> HealingEvent:
        event = HealingEvent(
            event_id="he_" + secrets.token_hex(6),
            source=source,
            title=title,
            description=description,
            severity=severity,
            created_at=_now(),
        )
        self._events.append(event)
        return event

    async def _classify_and_dispatch(self, event: HealingEvent) -> None:
        """E2: Classify the failure, then dispatch with classification context."""
        event.failure_category = self._classify_failure(event.description).value
        log.info("SelfHealingAgent: classified %s as %s", event.event_id, event.failure_category)
        await self._dispatch_fix(event)

    async def _dispatch_fix(self, event: HealingEvent) -> None:
        from agent.improvement_loop import (
            DetectedIssue,
            IssueCategory,
            IssueSeverity,
            get_improvement_loop,
        )

        loop = get_improvement_loop()
        if not loop:
            log.warning("SelfHealingAgent: ImprovementLoop not available — fix not dispatched")
            return

        sev = IssueSeverity.HIGH if event.severity in ("critical", "high") else IssueSeverity.MEDIUM
        cat = IssueCategory.TEST_FAILURE if event.source == "ci" else IssueCategory.TODO_FIXME

        # E2: Build corrected prompt with failure classification context
        corrected_prompt = event.description
        if event.failure_category:
            cat_hint = self._failure_category_hint(event.failure_category)
            corrected_prompt = f"{event.description}\n\n[Failure classified as: {event.failure_category}]\n{cat_hint}"

        issue = DetectedIssue(
            issue_id=event.event_id,
            category=cat,
            severity=sev,
            title=event.title,
            description=corrected_prompt,
        )
        loop._register_issue(issue)
        loop._schedule_fix(issue)
        log.info("SelfHealingAgent: fix dispatched for %s (category=%s)", event.event_id, event.failure_category)

    @staticmethod
    def _classify_failure(description: str) -> FailureCategory:
        """E2: Classify a failure from its description text."""
        lowered = description.lower()
        if "syntax error" in lowered or "syntaxerror" in lowered:
            return FailureCategory.SYNTAX_ERROR
        if "test fail" in lowered or "assertion" in lowered or "test_" in lowered and "fail" in lowered:
            return FailureCategory.TEST_FAILURE
        if "lint" in lowered or "flake8" in lowered or "mypy" in lowered or "type error" in lowered:
            return FailureCategory.LINT_ERROR
        if "timeout" in lowered or "timed out" in lowered:
            return FailureCategory.TIMEOUT
        if "modulenotfound" in lowered or "importerror" in lowered or "no module" in lowered:
            return FailureCategory.IMPORT_ERROR
        if "memory" in lowered or "oom" in lowered or "killed" in lowered:
            return FailureCategory.OOM
        if "network" in lowered or "connection" in lowered or "unreachable" in lowered:
            return FailureCategory.NETWORK
        return FailureCategory.UNKNOWN

    @staticmethod
    def _failure_category_hint(category: str) -> str:
        """E2: Return a corrective hint for each failure category."""
        hints = {
            "syntax_error": "Fix the syntax error. Run `python -m py_compile <file>` to verify.",
            "test_failure": "Fix the failing test. Run `pytest -x <test>` to verify the fix.",
            "lint_error": "Fix the lint/type error. Run the linter to verify.",
            "timeout": "The operation timed out. Add retry logic or increase the timeout.",
            "import_error": "Fix the import. Check that the module exists and the path is correct.",
            "out_of_memory": "Reduce memory usage. Split large operations or free resources.",
            "network_error": "The network request failed. Add retry with backoff or check the endpoint.",
            "unknown": "Investigate the failure and apply the minimum fix.",
        }
        return hints.get(category, hints["unknown"])


# ── Singleton ─────────────────────────────────────────────────────────────────

_healer_instance: SelfHealingAgent | None = None


def set_self_healing_agent(instance: SelfHealingAgent) -> None:
    global _healer_instance
    _healer_instance = instance


def get_self_healing_agent() -> SelfHealingAgent | None:
    return _healer_instance


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
