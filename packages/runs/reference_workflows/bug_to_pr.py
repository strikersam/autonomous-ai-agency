"""packages/runs/reference_workflows/bug_to_pr.py — workflow A: bug to verified pull request.

issue -> triage -> coding -> test execution -> independent verifier -> draft PR
artifact -> human approval pause. Deterministic: the "agents" read fixtures. The
workflow never merges and never deploys; the draft step probes both guards
(``agent/autonomy_gate`` for the merge, a durable approval for a deploy) and
fails if either is open.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from agent.autonomy_gate import AutonomyViolation, assert_agent_can_merge
from packages.runs.composition import (ChildJob, ChildOutcome, CompositionSpec, Step,
                                       StepCondition)
from packages.runs.reference_workflows.common import StepDispatcher, verdict
from packages.runs.reference_workflows.models import DraftPullRequest
from packages.runs.side_effects import ReleaseNotApproved, require_release_approval
from packages.runs.store import RunStore


class BugFixture(BaseModel):
    """The issue, what the coding agent changed and what the test run reported."""

    issue_id: str = "BUG-101"
    title: str = "Cart total ignores discount codes"
    body: str = "Applying SAVE10 leaves the total unchanged."
    acceptance_criteria: list[str] = Field(default_factory=lambda: [
        "A valid discount code lowers the cart total", "An invalid code leaves the total unchanged"])
    changed_files: list[str] = Field(default_factory=lambda: ["cart/totals.py", "tests/test_totals.py"])
    summary: str = "Apply the discount before tax in cart.totals.compute_total."
    tests_ran: bool = True
    tests_passed: int | None = 12
    tests_failed: int | None = 0


def _tests_defects(tests: dict | None) -> list[str]:
    if not tests or not tests.get("ran"):
        return ["no test result recorded: the change is unproven"]
    if tests.get("failed") is None or tests.get("passed") is None:
        return ["test result is incomplete (missing pass or fail count)"]
    defects = []
    if tests["failed"]:
        defects.append(f"{tests['failed']} test(s) failed")
    if not tests["passed"]:
        defects.append("no test passed")
    return defects


class BugToPrWorkflow:
    """Spec plus executor of workflow A over one run store."""

    def __init__(self, runs: RunStore, fixture: BugFixture | None = None) -> None:
        self.fixture = fixture or BugFixture()
        self.executor = StepDispatcher(runs, {
            "triage": self._triage, "coding": self._coding, "tests": self._tests,
            "verify": self._verify, "draft_pr": self._draft_pr})
        self._runs = runs

    @staticmethod
    def spec(*, company_id: str | None = None, owner_id: str | None = None) -> CompositionSpec:
        """The composition: a fail fast sequence that ends parked at human approval."""
        return CompositionSpec(name="reference.bug_to_pr", company_id=company_id, owner_id=owner_id,
                               steps=[
            Step(key="triage", title="Triage the issue", agent_id="triage"),
            Step(key="coding", title="Write the fix", agent_id="coder"),
            Step(key="tests", title="Execute the tests", agent_id="test-runner"),
            Step(key="verify", title="Independent verification", agent_id="verifier"),
            Step(key="draft_pr", title="Draft the pull request", agent_id="pr-writer",
                 when=StepCondition(step="verify", outcome="succeeded")),
            Step(key="human_approval", kind="approval", title="Human reviews the draft PR")])

    async def _triage(self, job: ChildJob) -> ChildOutcome:
        f = self.fixture
        return ChildOutcome(success=True, output={
            "issue_id": f.issue_id, "severity": "medium", "acceptance_criteria": f.acceptance_criteria})

    async def _coding(self, job: ChildJob) -> ChildOutcome:
        f = self.fixture
        return ChildOutcome(success=True, output={"changed_files": f.changed_files,
                                                  "summary": f.summary})

    async def _tests(self, job: ChildJob) -> ChildOutcome:
        f = self.fixture
        out = {"ran": f.tests_ran, "passed": f.tests_passed, "failed": f.tests_failed}
        link = await self.executor.store_json(job, "test-results.json", out)
        # Running the tests is this step's job; judging the result is the verifier's.
        return ChildOutcome(success=True, output={**out, "evidence": link})

    async def _verify(self, job: ChildJob) -> ChildOutcome:
        triage, coding = job.prior.get("triage") or {}, job.prior.get("coding") or {}
        tests = job.prior.get("tests")
        defects = _tests_defects(tests)
        if not triage.get("acceptance_criteria"):
            defects.append("no acceptance criteria from triage")
        if not coding.get("changed_files"):
            defects.append("the coding step changed no file")
        checked = ["triage produced acceptance criteria", "coding listed changed files",
                   "test result read from the test step's evidence"]
        return verdict(checked, defects, [(tests or {}).get("evidence", "no test evidence")])

    async def _guards(self, run_id: str) -> dict[str, str]:
        """Probe the merge and deploy guards; both must refuse."""
        try:
            assert_agent_can_merge(agent_initiated=True)
            merge = "OPEN"
        except AutonomyViolation:
            merge = "blocked"
        try:
            await require_release_approval(run_id, "deploy", {"issue": self.fixture.issue_id},
                                           {"env": "production"}, store=self._runs)
            deploy = "OPEN"
        except ReleaseNotApproved:
            deploy = "blocked"
        return {"merge": merge, "deploy": deploy}

    async def _draft_pr(self, job: ChildJob) -> ChildOutcome:
        guards = await self._guards(job.parent_run_id)
        if "OPEN" in guards.values():
            return ChildOutcome(success=False, error=f"release guard open: {guards}")
        prior = job.prior
        tests = prior["tests"]
        pr = DraftPullRequest(
            title=f"[{self.fixture.issue_id}] {self.fixture.title}",
            acceptance_criteria=prior["triage"]["acceptance_criteria"],
            implementation_summary=prior["coding"]["summary"],
            tests=[f"{tests['passed']} passed, {tests['failed']} failed"],
            evidence_links=[tests["evidence"]])
        body = pr.model_dump()
        link = await self.executor.store_json(job, "draft-pull-request.json", body)
        return ChildOutcome(success=True, output={"draft_pr": link, "guards": guards})
