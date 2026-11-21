"""packages/runs/reference_workflows/qa_investigation.py — workflow B: QA pipeline investigation.

failed CI -> pipeline investigator -> quality analyst -> evidence aggregator ->
independent verifier -> structured ``QualityReport``. The agents are deterministic
rules over fixture CI logs. The verifier fails a report whose classification is not
backed by log evidence, and a failed pipeline that carries no failure record.
"""
from __future__ import annotations

import re
from collections import Counter

from pydantic import BaseModel, Field, ValidationError

from packages.runs.composition import ChildJob, ChildOutcome, CompositionSpec, Step
from packages.runs.reference_workflows.common import StepDispatcher, verdict
from packages.runs.reference_workflows.models import FailureClass, FailureFinding, QualityReport
from packages.runs.store import RunStore

_RULES: list[tuple[FailureClass, re.Pattern[str], str]] = [
    (FailureClass.INFRASTRUCTURE_FAILURE, re.compile(
        r"ECONNRESET|runner (lost|disconnected)|no space left|OOMKilled|HTTP 50[234]", re.I),
     "the runner or a service it depends on failed"),
    (FailureClass.ENVIRONMENT_ISSUE, re.compile(
        r"ModuleNotFoundError|missing environment variable|version mismatch|command not found", re.I),
     "the job environment is misconfigured"),
    (FailureClass.APPLICATION_DEFECT, re.compile(r"AssertionError|expected .+ (got|but was)", re.I),
     "an assertion about the application's behaviour failed"),
]


class CiFailure(BaseModel):
    """One failed test in the fixture CI run. ``retry_passed``: did a rerun pass (None: not rerun)."""

    test: str
    log: list[str] = Field(default_factory=list)
    retry_passed: bool | None = None


class CiPipeline(BaseModel):
    """A fixture CI run."""

    name: str = "ci/main"
    status: str = "failed"
    failures: list[CiFailure] = Field(default_factory=lambda: [
        CiFailure(test="test_checkout_total", log=["AssertionError: expected 90 got 100"]),
        CiFailure(test="test_search_debounce", log=["TimeoutError: waited 1s"], retry_passed=True),
        CiFailure(test="test_upload", log=["ECONNRESET talking to artifact cache"]),
        CiFailure(test="test_pdf_export", log=["ModuleNotFoundError: No module named 'fitz'"]),
        CiFailure(test="test_mystery", log=["Segfault (core dumped)"])])


def classify(failure: CiFailure) -> tuple[FailureClass, str]:
    """Deterministic classification of one failure; unknown evidence is inconclusive."""
    if failure.retry_passed:
        return FailureClass.FLAKY_TEST, "failed, then passed on an unchanged rerun"
    text = "\n".join(failure.log)
    for klass, pattern, why in _RULES:
        if pattern.search(text):
            return klass, why
    return FailureClass.INCONCLUSIVE, "the log does not identify a cause"


def report_defects(report: QualityReport, investigated: list[str], pipeline_status: str) -> list[str]:
    """What is wrong with *report* judged against the investigator's failure list."""
    defects: list[str] = []
    if pipeline_status == "failed" and not investigated:
        defects.append("the pipeline failed but no failure record exists")
    covered = {f.test for f in report.findings}
    defects += [f"failure {t} is not classified" for t in investigated if t not in covered]
    defects += [f"{f.test}: classified {f.classification.value} with no log evidence"
                for f in report.findings
                if f.classification is not FailureClass.INCONCLUSIVE and not f.evidence]
    if report.total_failures != len(report.findings) or sum(report.counts.values()) != len(report.findings):
        defects.append("report counts do not match its findings")
    return defects


class QaInvestigationWorkflow:
    """Spec plus executor of workflow B over one run store."""

    def __init__(self, runs: RunStore, pipeline: CiPipeline | None = None) -> None:
        self.pipeline = pipeline or CiPipeline()
        self.executor = StepDispatcher(runs, {
            "investigate": self._investigate, "analyse": self._analyse,
            "aggregate": self._aggregate, "verify": self._verify})

    @staticmethod
    def spec(*, company_id: str | None = None, owner_id: str | None = None) -> CompositionSpec:
        """A fail fast sequence of four steps."""
        return CompositionSpec(name="reference.qa_investigation", company_id=company_id,
                               owner_id=owner_id, steps=[
            Step(key="investigate", title="Read the CI logs", agent_id="pipeline-investigator"),
            Step(key="analyse", title="Classify each failure", agent_id="quality-analyst"),
            Step(key="aggregate", title="Assemble the report", agent_id="evidence-aggregator"),
            Step(key="verify", title="Independent verification", agent_id="verifier")])

    async def _investigate(self, job: ChildJob) -> ChildOutcome:
        p = self.pipeline
        return ChildOutcome(success=True, output={
            "pipeline": p.name, "status": p.status,
            "failures": [f.model_dump() for f in p.failures]})

    async def _analyse(self, job: ChildJob) -> ChildOutcome:
        rows = []
        for raw in job.prior["investigate"]["failures"]:
            failure = CiFailure.model_validate(raw)
            klass, why = classify(failure)
            rows.append({"test": failure.test, "classification": klass.value, "reason": why,
                         "evidence": failure.log if klass is not FailureClass.INCONCLUSIVE else []})
        return ChildOutcome(success=True, output={"rows": rows})

    async def _aggregate(self, job: ChildJob) -> ChildOutcome:
        findings = [FailureFinding.model_validate(r) for r in job.prior["analyse"]["rows"]]
        counts = Counter(f.classification.value for f in findings)
        report = QualityReport(pipeline=job.prior["investigate"]["pipeline"],
                               total_failures=len(findings), findings=findings, counts=dict(counts))
        link = await self.executor.store_json(job, "quality-report.json", report.model_dump(mode="json"))
        return ChildOutcome(success=True, output={"report": report.model_dump(mode="json"),
                                                  "artifact": link})

    async def _verify(self, job: ChildJob) -> ChildOutcome:
        inv = job.prior.get("investigate") or {}
        try:
            report = QualityReport.model_validate((job.prior.get("aggregate") or {}).get("report"))
        except ValidationError:
            return verdict(["report parsed as a QualityReport"], ["the report is missing or malformed"], [])
        defects = report_defects(report, [f["test"] for f in inv.get("failures", [])],
                                 inv.get("status", ""))
        link = (job.prior.get("aggregate") or {}).get("artifact", "")
        return verdict(["every failure classified", "classifications carry log evidence",
                        "counts match findings"], defects, [link])
