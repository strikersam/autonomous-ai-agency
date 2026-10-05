"""tests/test_internal_agent_did_work.py — the adapter's "did real work" gate.

Runs the real ``InternalAgentAdapter.execute`` with a stubbed runner, so the
assertions track the code. (This file used to re-implement the gate with a 0.5
step ratio while the adapter required 1.0, so it passed whatever the code did.)

The adapter reports success only when every planned step applied, or when a
zero-step analysis run produced a real report, and never on a BLOCKED judge.
"""
from __future__ import annotations

import tempfile

import pytest

from runtimes.adapters import internal_agent
from runtimes.base import TaskSpec


def _steps(applied: int, failed: int, files: tuple[str, ...] = ()) -> list[dict]:
    ok = [{"status": "applied", "changed_files": list(files)} for _ in range(applied)]
    return ok + [{"status": "failed", "changed_files": []} for _ in range(failed)]


async def _run(monkeypatch, steps: list[dict], report: str = "", verdict: str = "") -> bool:
    async def _fake_run(self, *args, **kwargs):  # noqa: ANN001
        return {"steps": steps, "report": report, "judge": {"verdict": verdict}}

    # Patch the class the adapter imported: other tests reload agent.loop.
    monkeypatch.setattr(internal_agent.AgentRunner, "run", _fake_run)
    with tempfile.TemporaryDirectory() as tmp:
        adapter = internal_agent.InternalAgentAdapter({"workspace_root": tmp})
        result = await adapter.execute(TaskSpec(task_id="t", instruction="x", workspace_path=tmp))
    return result.success


@pytest.mark.parametrize(
    ("steps", "report", "verdict", "expected"),
    [
        (_steps(1, 21), "", "", False),                       # the production bug case
        (_steps(9, 1), "", "", False),                        # any failed step fails the run
        (_steps(4, 6, ("foo.py",)), "", "", False),           # changed files don't excuse failures
        (_steps(10, 0), "", "", True),                        # every step applied
        (_steps(3, 0, ("foo.py",)), "", "", True),
        ([], "This is a detailed analysis report.", "", True),  # analysis-only run
        ([], "short", "", False),
        ([], "", "", False),
        (_steps(10, 0), "", "BLOCKED", False),                # judge veto
        ([], "A" * 100, "BLOCKED", False),
    ],
)
async def test_did_work_gate(monkeypatch, steps, report, verdict, expected):
    assert await _run(monkeypatch, steps, report, verdict) is expected
