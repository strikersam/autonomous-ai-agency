"""packages/runs/reference_workflows/common.py — helpers shared by the three workflows."""
from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from packages.runs.artifacts import ArtifactStore
from packages.runs.composition import ChildJob, ChildOutcome
from packages.runs.store import RunStore
from tasks.verification import TaskVerification

VERIFIER_ID = "verifier:reference-workflow"
StepFn = Callable[[ChildJob], Awaitable[ChildOutcome]]


def verdict(checked: list[str], defects: list[str], evidence: list[str]) -> ChildOutcome:
    """A verifier step result: PASS only when there is no defect, FAIL (step fails) otherwise."""
    passed = not defects
    report = TaskVerification(verdict="PASS" if passed else "FAIL", verifier=VERIFIER_ID,
                              checked=checked, defects_found=defects, evidence=evidence)
    return ChildOutcome(success=passed, output=report.model_dump(),
                        error=None if passed else "; ".join(defects)[:500])


def artifact_link(run_id: str, artifact_id: str) -> str:
    """The API path an evidence link points at."""
    return f"/api/runs/{run_id}/artifacts/{artifact_id}"


class StepDispatcher:
    """A ``ChildExecutor`` that routes each step key to a coroutine; unknown keys fail."""

    def __init__(self, runs: RunStore, steps: dict[str, StepFn]) -> None:
        self.runs = runs
        self.artifacts = ArtifactStore(runs)
        self._steps = steps
        self.calls: list[str] = []

    async def __call__(self, job: ChildJob) -> ChildOutcome:
        self.calls.append(job.step.key)
        fn = self._steps.get(job.step.key)
        if fn is None:
            return ChildOutcome(success=False, error=f"no executor for step {job.step.key!r}")
        return await fn(job)

    async def store_json(self, job: ChildJob, name: str, payload: dict[str, Any]) -> str:
        """Store *payload* as a JSON artifact on the composition's root run; return its link."""
        ref = await self.artifacts.put(job.parent_run_id, name, json.dumps(payload, indent=2),
                                       mime_type="application/json", agent_id=job.step.key)
        return artifact_link(job.parent_run_id, ref.artifact_id)
