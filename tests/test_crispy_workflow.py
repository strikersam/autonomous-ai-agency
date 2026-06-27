"""tests/test_crispy_workflow.py — CRISPY workflow engine hardening tests.

Tests for the phase-sequence enforcement, workspace isolation, and abort-
on-failure behaviour added as part of roadmap item 3c.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from workflow.models import (
    Artifact,
    ModelRoutingConfig,
    Phase,
    PhaseSequenceError,
    WorkflowBuildRequest,
    WorkflowRun,
    _now,
)


@pytest.fixture()
def tmp_db(tmp_path):
    """Provide isolated DB + artifact + workspace paths."""
    db = tmp_path / "test.db"
    art = tmp_path / "artifacts"
    ws = tmp_path / "workspaces"
    art.mkdir()
    ws.mkdir()
    return db, art, ws


def _make_engine(tmp_db):
    """Create a WorkflowEngine with isolated storage."""
    db, art, ws = tmp_db
    with patch.dict(os.environ, {"CRISPY_WORKSPACE_ROOT": str(ws)}):
        from workflow.engine import WorkflowEngine
        return WorkflowEngine(
            ollama_base="http://localhost:11434",
            db_path=str(db),
            artifacts_root=str(art),
            workspace_root=str(ws),
        )


def _fake_artifact(run_id: str, phase: str, name: str) -> Artifact:
    return Artifact(
        artifact_id=f"art_{phase}",
        run_id=run_id,
        phase=phase,
        name=name,
        path=f"/fake/{name}",
        content_hash="abc",
        size_bytes=42,
    )


# ── Phase-sequence enforcement ───────────────────────────────────────────────


class TestPhaseSequence:
    def test_first_phase_has_no_predecessor(self, tmp_db):
        engine = _make_engine(tmp_db)
        run = WorkflowRun(
            run_id="wf_test1",
            title="test",
            request="test request",
            phases=[
                Phase(phase_id="ph_0", run_id="wf_test1", name="context", agent_role="scout"),
            ],
        )
        engine._check_phase_sequence(run, "context")

    def test_second_phase_blocked_when_first_pending(self, tmp_db):
        engine = _make_engine(tmp_db)
        run = WorkflowRun(
            run_id="wf_test2",
            title="test",
            request="test request",
            phases=[
                Phase(phase_id="ph_0", run_id="wf_test2", name="context", status="pending", agent_role="scout"),
                Phase(phase_id="ph_1", run_id="wf_test2", name="research", status="pending", agent_role="scout"),
            ],
        )
        with pytest.raises(PhaseSequenceError) as exc_info:
            engine._check_phase_sequence(run, "research")
        assert "context" in str(exc_info.value)
        assert "pending" in str(exc_info.value)

    def test_second_phase_allowed_when_first_done(self, tmp_db):
        engine = _make_engine(tmp_db)
        run = WorkflowRun(
            run_id="wf_test3",
            title="test",
            request="test request",
            phases=[
                Phase(phase_id="ph_0", run_id="wf_test3", name="context", status="done", agent_role="scout"),
                Phase(phase_id="ph_1", run_id="wf_test3", name="research", status="pending", agent_role="scout"),
            ],
        )
        engine._check_phase_sequence(run, "research")

    def test_phase_blocked_when_predecessor_failed(self, tmp_db):
        engine = _make_engine(tmp_db)
        run = WorkflowRun(
            run_id="wf_test4",
            title="test",
            request="test request",
            phases=[
                Phase(phase_id="ph_0", run_id="wf_test4", name="context", status="failed", agent_role="scout"),
                Phase(phase_id="ph_1", run_id="wf_test4", name="research", status="pending", agent_role="scout"),
            ],
        )
        with pytest.raises(PhaseSequenceError) as exc_info:
            engine._check_phase_sequence(run, "research")
        assert "failed" in str(exc_info.value)

    def test_plan_phase_requires_structure_done(self, tmp_db):
        engine = _make_engine(tmp_db)
        run = WorkflowRun(
            run_id="wf_test5",
            title="test",
            request="test request",
            phases=[
                Phase(phase_id="ph_0", run_id="wf_test5", name="context", status="done", agent_role="scout"),
                Phase(phase_id="ph_1", run_id="wf_test5", name="research", status="done", agent_role="scout"),
                Phase(phase_id="ph_2", run_id="wf_test5", name="investigate", status="done", agent_role="scout"),
                Phase(phase_id="ph_3", run_id="wf_test5", name="structure", status="running", agent_role="architect"),
                Phase(phase_id="ph_4", run_id="wf_test5", name="plan", status="pending", agent_role="architect"),
            ],
        )
        with pytest.raises(PhaseSequenceError):
            engine._check_phase_sequence(run, "plan")


# ── PhaseSequenceError ───────────────────────────────────────────────────────


class TestPhaseSequenceError:
    def test_error_attributes(self):
        err = PhaseSequenceError("research", "context", "pending")
        assert err.phase == "research"
        assert err.predecessor == "context"
        assert err.predecessor_status == "pending"
        assert "research" in str(err)
        assert "context" in str(err)


# ── Workspace isolation ──────────────────────────────────────────────────────


class TestWorkspaceIsolation:
    def test_each_run_gets_own_workspace(self, tmp_db):
        engine = _make_engine(tmp_db)
        _, _, ws = tmp_db

        async def _create_two():
            with patch.object(engine, "_run_pre_gate_phases", new_callable=AsyncMock):
                r1 = await engine.create_run(WorkflowBuildRequest(request="implement task A with full details", title="A"))
                r2 = await engine.create_run(WorkflowBuildRequest(request="implement task B with full details", title="B"))
            return r1, r2

        r1, r2 = asyncio.get_event_loop().run_until_complete(_create_two())

        assert r1.workspace_root != r2.workspace_root
        assert r1.run_id in r1.workspace_root
        assert r2.run_id in r2.workspace_root
        assert Path(r1.workspace_root).is_dir()
        assert Path(r2.workspace_root).is_dir()

    def test_explicit_workspace_root_is_respected(self, tmp_db):
        engine = _make_engine(tmp_db)

        async def _create():
            with patch.object(engine, "_run_pre_gate_phases", new_callable=AsyncMock):
                return await engine.create_run(
                    WorkflowBuildRequest(
                        request="implement task C with full details",
                        title="C",
                        workspace_root="/custom/path",
                    )
                )

        run = asyncio.get_event_loop().run_until_complete(_create())
        assert run.workspace_root == "/custom/path"


# ── Abort on failure ─────────────────────────────────────────────────────────


class TestAbortOnFailure:
    def test_pre_gate_aborts_after_failed_phase(self, tmp_db):
        engine = _make_engine(tmp_db)

        call_log = []

        original_run_single = engine._run_single_phase

        async def _tracking_run_single(run_id, phase_type):
            call_log.append(phase_type)
            if phase_type == "research":
                with engine._lock:
                    run = engine._runs[run_id]
                    phase = run.phase_by_type(phase_type)
                    if phase:
                        phase.status = "failed"
                        phase.error = "simulated failure"
                    run.status = "failed"
                    engine._save(run)
                return
            with engine._lock:
                run = engine._runs[run_id]
                phase = run.phase_by_type(phase_type)
                if phase:
                    phase.status = "done"
                    phase.finished_at = _now()
                engine._save(run)

        engine._run_single_phase = _tracking_run_single

        async def _test():
            with patch.object(engine, "_run_pre_gate_phases", wraps=engine._run_pre_gate_phases):
                run = WorkflowRun(
                    run_id="wf_abort",
                    title="abort test",
                    request="test",
                    status="pending",
                    phases=[
                        Phase(phase_id=f"ph_{i}", run_id="wf_abort", name=p, agent_role="scout")
                        for i, p in enumerate(["context", "research", "investigate", "structure", "plan"])
                    ],
                )
                engine._save(run)
                await engine._run_pre_gate_phases("wf_abort")

        asyncio.get_event_loop().run_until_complete(_test())

        assert "context" in call_log
        assert "research" in call_log
        assert "investigate" not in call_log
        assert "structure" not in call_log
        assert "plan" not in call_log
