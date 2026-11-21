"""packages/runs/reference_workflows — three deterministic reference workflows.

They are ``CompositionSpec``s run by the existing ``Composer`` with fixture driven
executors (no network, no LLM): A bug to verified PR, B QA pipeline investigation,
C parallel QA fan out. They prove the platform end to end; they add no engine.
"""
from __future__ import annotations

from packages.runs.reference_workflows.bug_to_pr import BugFixture, BugToPrWorkflow
from packages.runs.reference_workflows.models import (AgentAssessment, ConsolidatedAssessment,
                                                      DraftPullRequest, FailureClass,
                                                      FailureFinding, QualityReport)
from packages.runs.reference_workflows.qa_fanout import QaFanoutWorkflow, QaFixture
from packages.runs.reference_workflows.qa_investigation import CiFailure, QaInvestigationWorkflow

__all__ = ["AgentAssessment", "BugFixture", "BugToPrWorkflow", "CiFailure", "ConsolidatedAssessment",
           "DraftPullRequest", "FailureClass", "FailureFinding", "QaFanoutWorkflow", "QaFixture",
           "QaInvestigationWorkflow", "QualityReport"]
