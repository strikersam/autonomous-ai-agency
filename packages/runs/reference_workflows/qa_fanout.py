"""packages/runs/reference_workflows/qa_fanout.py — workflow C: parallel QA fan out.

coordinator -> regression, accessibility, api/smoke (parallel group, policy CONTINUE so
one agent failing does not stop the rest, at most ``RUNS_MAX_PARALLEL`` at once) ->
aggregator -> independent verifier -> consolidated assessment. A failed agent is marked
in the assessment, never dropped. The verifier fails when a completed agent has no test
result, or when the claimed overall result is not what the evidence supports.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from packages.runs.composition import (ChildJob, ChildOutcome, CompositionSpec, FailurePolicy,
                                       Step)
from packages.runs.reference_workflows.common import StepDispatcher, verdict
from packages.runs.reference_workflows.models import AgentAssessment, ConsolidatedAssessment
from packages.runs.store import RunStore

AGENTS = ("regression", "accessibility", "api_smoke")


class AgentFixture(BaseModel):
    """What one QA agent does: fail outright, or report counts (``None`` = no result)."""

    fails: bool = False
    passed: int | None = 10
    failed: int | None = 0


class QaFixture(BaseModel):
    """Per agent behaviour; the default is three green agents."""

    agents: dict[str, AgentFixture] = Field(default_factory=lambda: {a: AgentFixture() for a in AGENTS})


def overall_of(agents: list[AgentAssessment]) -> str:
    """The overall result the evidence supports."""
    if any(a.status == "failed" for a in agents):
        return "partial"
    if any(a.tests_failed for a in agents):
        return "fail"
    return "pass"


def assessment_defects(result: ConsolidatedAssessment) -> list[str]:
    """What is wrong with *result* judged against its own agent evidence."""
    defects = [f"{a.agent}: completed with no test result" for a in result.agents
               if a.status == "completed" and (a.tests_passed is None or a.tests_failed is None)]
    defects += [f"{a.agent}: reported as failed but is not listed in failed_agents"
                for a in result.agents if a.status == "failed" and a.agent not in result.failed_agents]
    if {a.agent for a in result.agents} != set(AGENTS):
        defects.append("an expected agent is missing from the assessment")
    if result.overall != overall_of(result.agents):
        defects.append(f"overall {result.overall!r} is not supported by the agent evidence")
    return defects


class QaFanoutWorkflow:
    """Spec plus executor of workflow C over one run store."""

    def __init__(self, runs: RunStore, fixture: QaFixture | None = None) -> None:
        self.fixture = fixture or QaFixture()
        steps = {"coordinator": self._coordinator, "aggregate": self._aggregate, "verify": self._verify}
        steps.update({a: self._agent(a) for a in AGENTS})
        self.executor = StepDispatcher(runs, steps)  # type: ignore[arg-type]

    @staticmethod
    def spec(*, company_id: str | None = None, owner_id: str | None = None) -> CompositionSpec:
        """coordinator, then a parallel CONTINUE group, then aggregator and verifier."""
        return CompositionSpec(name="reference.qa_fanout", company_id=company_id, owner_id=owner_id,
                               steps=[
            Step(key="coordinator", title="Plan the QA pass", agent_id="qa-coordinator"),
            Step(key="fanout", kind="group", mode="parallel", policy=FailurePolicy.CONTINUE, steps=[
                Step(key=a, title=f"{a} checks", agent_id=f"qa-{a}") for a in AGENTS]),
            Step(key="aggregate", title="Join the results", agent_id="qa-aggregator"),
            Step(key="verify", title="Independent verification", agent_id="verifier")])

    async def _coordinator(self, job: ChildJob) -> ChildOutcome:
        return ChildOutcome(success=True, output={"plan": list(AGENTS)})

    def _agent(self, name: str):  # noqa: ANN202 - a closure per agent
        async def run(job: ChildJob) -> ChildOutcome:
            cfg = self.fixture.agents[name]
            if cfg.fails:
                return ChildOutcome(success=False, error=f"{name} agent crashed")
            return ChildOutcome(success=True, output={"passed": cfg.passed, "failed": cfg.failed})
        return run

    async def _aggregate(self, job: ChildJob) -> ChildOutcome:
        rows = []
        for name in AGENTS:
            got = job.prior.get(name)
            if got is None:
                rows.append(AgentAssessment(agent=name, status="failed",
                                            detail="no successful result was recorded"))
            else:
                rows.append(AgentAssessment(agent=name, status="completed",
                                            tests_passed=got.get("passed"), tests_failed=got.get("failed")))
        result = ConsolidatedAssessment(overall=overall_of(rows), agents=rows,  # type: ignore[arg-type]
                                        failed_agents=[r.agent for r in rows if r.status == "failed"])
        link = await self.executor.store_json(job, "consolidated-assessment.json",
                                              result.model_dump(mode="json"))
        return ChildOutcome(success=True, output={"assessment": result.model_dump(mode="json"),
                                                  "artifact": link})

    async def _verify(self, job: ChildJob) -> ChildOutcome:
        agg = job.prior.get("aggregate") or {}
        try:
            result = ConsolidatedAssessment.model_validate(agg.get("assessment"))
        except ValidationError:
            return verdict(["assessment parsed"], ["the assessment is missing or malformed"], [])
        return verdict(["every agent has a result or is marked failed", "overall matches evidence"],
                       assessment_defects(result), [agg.get("artifact", "")])
