"""packages/runs/reference_workflows/models.py — typed outputs of the reference workflows."""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class FailureClass(str, Enum):
    """The five classes a failed CI test is sorted into (brief, workflow B)."""

    APPLICATION_DEFECT = "application_defect"
    FLAKY_TEST = "flaky_test"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"
    ENVIRONMENT_ISSUE = "environment_issue"
    INCONCLUSIVE = "inconclusive"


class FailureFinding(BaseModel):
    """One failed test, its class, the reason and the log lines that prove it."""

    test: str
    classification: FailureClass
    reason: str
    evidence: list[str] = Field(default_factory=list)


class QualityReport(BaseModel):
    """The structured report workflow B produces; every failure is classified."""

    pipeline: str
    total_failures: int
    findings: list[FailureFinding]
    counts: dict[str, int] = Field(default_factory=dict)
    verdict_note: str = ""


class AgentAssessment(BaseModel):
    """What one QA agent of workflow C reported (``None`` counts mean no test result)."""

    agent: str
    status: Literal["completed", "failed"]
    tests_passed: int | None = None
    tests_failed: int | None = None
    detail: str = ""


class ConsolidatedAssessment(BaseModel):
    """Workflow C's joined result; a failed agent is marked, never hidden."""

    overall: Literal["pass", "fail", "partial"]
    agents: list[AgentAssessment]
    failed_agents: list[str] = Field(default_factory=list)


class DraftPullRequest(BaseModel):
    """The draft PR description of workflow A. It is a document: nothing is opened or merged."""

    title: str
    draft: Literal[True] = True
    acceptance_criteria: list[str]
    implementation_summary: str
    tests: list[str]
    evidence_links: list[str]
    merge: Literal["blocked: a human merges"] = "blocked: a human merges"
    deploy: Literal["blocked: needs a durable approval"] = "blocked: needs a durable approval"
