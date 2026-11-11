"""The workflow run's status must always be one its own type declares.

`workflow/engine.py` used to assign `run.status = "report"` for the final
report phase — a value `WorkflowStatus` does not contain — and never wrote the
declared `reviewing`/`verifying` states. These tests pin the fixed behaviour:
the run follows execute -> review -> verify -> executing per slice, a phase
that is not a run status never becomes one, and a failed report phase is no
longer overwritten as DONE.
"""
from __future__ import annotations

import asyncio
from typing import get_args

import pytest

from packages.lifecycle import get_machine
from workflow.engine import WorkflowEngine
from workflow.models import (
    Artifact,
    CheckRun,
    Phase,
    Slice,
    WorkflowRun,
    WorkflowStatus,
)

RUN_ID = "wf_lifecycle"


class RecordingRunner:
    """A PhaseRunner stand-in that records the run status at each stage."""

    def __init__(self, engine: WorkflowEngine, *, fail_report: bool = False) -> None:
        self.engine = engine
        self.fail_report = fail_report
        self.seen: list[tuple[str, str]] = []

    def _status(self, run_id: str) -> str:
        run = self.engine.get(run_id)
        assert run is not None
        return run.status

    async def run_phase(self, *, run_id: str, phase: str, request: str,
                        routing: object, prior_artifacts: list[Artifact]) -> Artifact:
        self.seen.append((phase, self._status(run_id)))
        if self.fail_report and phase == "report":
            raise RuntimeError("report phase failed")
        return _artifact(run_id, phase, f"{phase}.md")

    async def run_slice_execute(self, *, run_id: str, sl: Slice, routing: object,
                                prior_artifacts: list[Artifact]) -> Artifact:
        self.seen.append(("execute", self._status(run_id)))
        return _artifact(run_id, "execute", "slice.md")

    async def run_slice_review(self, *, run_id: str, sl: Slice, routing: object,
                               slice_artifact: Artifact) -> Artifact:
        self.seen.append(("review", self._status(run_id)))
        return _artifact(run_id, "review", "review.md")

    async def run_slice_verify(self, *, run_id: str, sl: Slice, routing: object,
                               workspace_root: str | None = None) -> CheckRun:
        self.seen.append(("verify", self._status(run_id)))
        return CheckRun(
            check_id="chk_test",
            slice_id=sl.slice_id,
            run_id=run_id,
            commands=["true"],
            exit_code=0,
            passed=True,
        )


def _artifact(run_id: str, phase: str, name: str) -> Artifact:
    return Artifact(
        artifact_id=f"art_{phase}",
        run_id=run_id,
        phase=phase,
        name=name,
        path=f"/fake/{name}",
        size_bytes=1,
    )


@pytest.fixture()
def engine(tmp_path, monkeypatch) -> WorkflowEngine:
    monkeypatch.setenv("CRISPY_WORKSPACE_ROOT", str(tmp_path / "ws"))
    engine = WorkflowEngine(
        ollama_base="http://localhost:11434",
        db_path=str(tmp_path / "workflow.db"),
        artifacts_root=str(tmp_path / "artifacts"),
        workspace_root=str(tmp_path / "ws"),
    )
    engine._swarm = None
    return engine


def _seed(engine: WorkflowEngine, *, status: str = "executing") -> str:
    run = WorkflowRun(
        run_id=RUN_ID,
        title="lifecycle",
        request="test the run lifecycle",
        status=status,  # type: ignore[arg-type]
        phases=[
            Phase(
                phase_id="ph_report",
                run_id=RUN_ID,
                name="report",
                agent_role="architect",
            )
        ],
        slices=[
            Slice(
                slice_id="sl_1",
                run_id=RUN_ID,
                index=1,
                title="slice",
                description="one slice",
            )
        ],
    )
    engine._save(run)
    return RUN_ID


def test_slice_follows_execute_review_verify_and_returns_to_executing(engine) -> None:
    run_id = _seed(engine)
    runner = RecordingRunner(engine)
    engine._phase_runner = runner  # type: ignore[assignment]

    asyncio.run(engine._execute_slice(run_id, "sl_1"))

    assert [stage for stage, _ in runner.seen] == ["execute", "review", "verify"]
    assert [status for _, status in runner.seen] == ["executing", "reviewing", "verifying"]
    assert engine.get(run_id).status == "executing"
    declared = set(get_args(WorkflowStatus))
    assert all(status in declared for _, status in runner.seen)


def test_report_phase_never_becomes_a_run_status(engine) -> None:
    run_id = _seed(engine)
    runner = RecordingRunner(engine)
    engine._phase_runner = runner  # type: ignore[assignment]

    asyncio.run(engine._run_single_phase(run_id, "report"))

    assert ("report", "executing") in runner.seen
    assert engine.get(run_id).status == "executing"
    assert engine.get(run_id).phase_by_type("report").status == "done"


def test_failed_report_phase_is_not_overwritten_as_done(engine) -> None:
    run_id = _seed(engine)
    engine._phase_runner = RecordingRunner(engine, fail_report=True)  # type: ignore[assignment]

    asyncio.run(engine._run_post_gate(run_id))

    run = engine.get(run_id)
    assert run.status == "failed"
    assert run.phase_by_type("report").status == "failed"


def test_status_guard_refuses_an_undeclared_move_without_raising(engine) -> None:
    run_id = _seed(engine, status="done")

    assert engine._set_run_status(run_id, "pending") is False
    assert engine.get(run_id).status == "done"


def test_declared_lifecycle_covers_every_move_the_engine_makes() -> None:
    machine = get_machine("workflow_run")
    for source, target in (
        ("executing", "reviewing"),
        ("reviewing", "verifying"),
        ("verifying", "executing"),
        ("done", "executing"),
        ("failed", "executing"),
    ):
        assert machine.can(source, target), f"{source} -> {target} must be declared"
    assert "report" not in machine.states
