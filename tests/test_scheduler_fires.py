"""Agency jobs must actually fire in production.

Regression: apscheduler was never a declared dependency, so the production
image had no cron engine. AgentScheduler silently skipped registering jobs and
every CEO directive since 2026-10-09 was scheduled and never run.
"""
from __future__ import annotations

import asyncio

import pytest


def test_apscheduler_is_installed_and_the_scheduler_registers_jobs():
    from packages.scheduler import scheduler as mod

    assert mod._HAS_APSCHEDULER, "apscheduler must be installed (requirements.txt)"
    s = mod.AgentScheduler()
    try:
        job = s.create(name="t", cron="* * * * *", instruction="noop")
        assert s._aps is not None
        assert s._aps.get_job(job.job_id) is not None
    finally:
        s.shutdown()


@pytest.mark.parametrize("req", ["requirements.txt", "backend/requirements.txt"])
def test_requirements_declare_apscheduler(req):
    """Both files: production (render.yaml → Dockerfile.backend) installs
    backend/requirements.txt, so declaring it only at the root fixed nothing."""
    from pathlib import Path

    text = Path(__file__).resolve().parents[1].joinpath(req).read_text()
    assert any(line.lower().startswith("apscheduler") for line in text.splitlines())


def test_production_image_installs_the_backend_requirements():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    assert "dockerfilePath: ./Dockerfile.backend" in root.joinpath("render.yaml").read_text()
    assert "backend/requirements.txt" in root.joinpath("Dockerfile.backend").read_text()


@pytest.mark.asyncio
async def test_scheduled_runs_execute_one_at_a_time(monkeypatch):
    import backend.server as server
    import services.workflow_orchestrator as wo

    running = 0
    peak = 0

    class _Orch:
        async def execute(self, req):
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.05)
            running -= 1
            return type("Run", (), {"run_id": "r"})()

    monkeypatch.setattr(wo, "get_workflow_orchestrator", lambda: _Orch())
    jobs = [type("Job", (), {"job_id": f"j{i}", "instruction": "x"})() for i in range(4)]
    await asyncio.gather(*(server._scheduler_on_fire(j) for j in jobs))
    assert peak == 1
