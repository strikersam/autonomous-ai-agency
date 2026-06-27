"""tests/test_crispy_run_history.py — N4 acceptance: WorkflowEngine.crispy_run_history().

Roadmap item N4: promote ``crispy_workflow`` from EXPERIMENTAL → stable in
``features/matrix.py``. Promotion must be backed by *data*, not a flag flip.
This test pins the metric that surfaces the burn-in evidence.

The metric aggregates from the existing ``workflow_runs`` + ``workflow_events``
tables — no new schema. We build a tiny fixture DB, log a few synthetic runs
+ events, and assert the aggregation shape + correctness.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture()
def tmp_db(tmp_path):
    db = tmp_path / "test.db"
    art = tmp_path / "artifacts"
    ws = tmp_path / "workspaces"
    art.mkdir()
    ws.mkdir()
    return db, art, ws


def _make_engine(tmp_db):
    db, art, ws = tmp_db
    with patch.dict(os.environ, {"CRISPY_WORKSPACE_ROOT": str(ws)}):
        from workflow.engine import WorkflowEngine
        return WorkflowEngine(
            ollama_base="http://localhost:11434",
            db_path=str(db),
            artifacts_root=str(art),
            workspace_root=str(ws),
        )


def _make_run(engine, run_id, status="done"):
    """Insert a minimal run directly via _save."""
    from workflow.models import WorkflowRun, WorkflowBuildRequest, _now
    import asyncio
    req = WorkflowBuildRequest(request="test request body", title="test")
    # Use the public create_run so the run is properly persisted + event logged
    run = asyncio.run(engine.create_run(req))
    # Override its run_id and status for the test
    run.run_id = run_id
    run.status = status
    engine._save(run)
    return run


def test_crispy_run_history_empty_when_no_runs(tmp_db):
    """An engine with no runs must return zero-everywhere, not raise."""
    engine = _make_engine(tmp_db)
    history = engine.crispy_run_history()
    assert history["total_runs"] == 0
    assert history["completed_runs"] == 0
    assert history["failed_runs"] == 0
    assert history["cancelled_runs"] == 0
    assert history["success_rate"] == 0.0
    assert history["phase_outcomes"] == {}
    assert history["last_failure_reasons"] == []
    assert history["window_days"] is None


def test_crispy_run_history_counts_run_statuses(tmp_db):
    """Run-level counts (total/completed/failed/cancelled) come from
    workflow_runs.status — the canonical source for run outcomes."""
    import asyncio
    engine = _make_engine(tmp_db)

    # Insert three runs: 1 done, 1 failed, 1 cancelled
    from workflow.models import WorkflowBuildRequest
    req = WorkflowBuildRequest(request="test request body", title="t")

    r1 = asyncio.run(engine.create_run(req))
    r1.status = "done"
    engine._save(r1)

    r2 = asyncio.run(engine.create_run(req))
    r2.status = "failed"
    engine._save(r2)

    r3 = asyncio.run(engine.create_run(req))
    r3.status = "cancelled"
    engine._save(r3)

    history = engine.crispy_run_history()
    assert history["total_runs"] == 3
    assert history["completed_runs"] == 1
    assert history["failed_runs"] == 1
    assert history["cancelled_runs"] == 1
    # success_rate = completed / total = 1/3 ≈ 0.3333
    assert history["success_rate"] == pytest.approx(0.3333, abs=0.001)


def test_crispy_run_history_aggregates_phase_outcomes(tmp_db):
    """Phase-level outcomes (complete/failed counts per phase_type) come from
    the workflow_events table's phase_complete + phase_failed events."""
    import asyncio
    engine = _make_engine(tmp_db)
    from workflow.models import WorkflowBuildRequest
    req = WorkflowBuildRequest(request="test request body", title="t")
    run = asyncio.run(engine.create_run(req))

    # Log three phase events: 2 complete + 1 failed
    engine._log_event(run.run_id, "phase_complete", {"phase": "design"})
    engine._log_event(run.run_id, "phase_complete", {"phase": "code"})
    engine._log_event(
        run.run_id, "phase_failed",
        {"phase": "verify", "error": "AssertionError: 1 != 2"},
    )

    history = engine.crispy_run_history()
    po = history["phase_outcomes"]
    assert po["design"] == {"complete": 1, "failed": 0}
    assert po["code"] == {"complete": 1, "failed": 0}
    assert po["verify"] == {"complete": 0, "failed": 1}
    # The failed phase must appear in last_failure_reasons
    assert any("verify" in r and "AssertionError" in r for r in history["last_failure_reasons"])


def test_crispy_run_history_caps_failure_reasons_at_5(tmp_db):
    """Only the 5 most recent failure reasons are kept — keeps the response
    payload bounded when the engine has a long failure history."""
    import asyncio
    engine = _make_engine(tmp_db)
    from workflow.models import WorkflowBuildRequest
    req = WorkflowBuildRequest(request="test request body", title="t")
    run = asyncio.run(engine.create_run(req))

    # Log 10 phase_failed events
    for i in range(10):
        engine._log_event(
            run.run_id, "phase_failed",
            {"phase": "verify", "error": f"error #{i}"},
        )

    history = engine.crispy_run_history()
    assert len(history["last_failure_reasons"]) == 5
    # The most recent 5 should be errors #5..#9
    reasons_text = " ".join(history["last_failure_reasons"])
    assert "error #9" in reasons_text
    assert "error #0" not in reasons_text


def test_crispy_run_history_returns_window_days(tmp_db):
    """window_days is the age of the oldest run in days — used to gate the
    burn-in criteria (e.g. 'must have >=7 days of evidence')."""
    import asyncio
    from datetime import datetime, timezone, timedelta
    engine = _make_engine(tmp_db)
    from workflow.models import WorkflowBuildRequest
    req = WorkflowBuildRequest(request="test request body", title="t")
    run = asyncio.run(engine.create_run(req))

    # Manually backdate the run's created_at to 10 days ago via DB update
    old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    with engine._connect() as conn:
        conn.execute(
            "UPDATE workflow_runs SET created_at=? WHERE run_id=?",
            (old_ts, run.run_id),
        )
        conn.commit()

    history = engine.crispy_run_history()
    assert history["window_days"] is not None
    assert history["window_days"] >= 9  # allow a tiny clock-skew margin
