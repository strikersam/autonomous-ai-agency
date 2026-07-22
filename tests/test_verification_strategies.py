"""Tests for agent/verification_strategies.py (cross_verify + race).

AgentRunner.run() returns {"goal", "plan", "steps": [...], "commits", ...}
with NO top-level "status" or "changed_files" key — those live per-step
(each entry in "steps" has its own "status"/"issues"/"changed_files").
Fixtures here deliberately mirror that real shape (see agent/loop.py's
run()) rather than a simplified shape, since a mismatch here previously hid
a real bug: cross_verify() used to read result.get("status"), which never
exists on a real AgentRunner result, so it always evaluated to "always fail"
against the real object despite passing against a hand-shaped stub.
"""
from __future__ import annotations

import asyncio

import pytest

from agent import verification_strategies as vs


def test_touches_risky_module_matches_known_files():
    assert vs.touches_risky_module(["admin_auth.py"]) is True
    assert vs.touches_risky_module(["agent/tools.py"]) is True
    assert vs.touches_risky_module(["services/key_store.py"]) is True
    assert vs.touches_risky_module(["services/auth_session.py"]) is True


def test_touches_risky_module_false_for_unrelated_files():
    assert vs.touches_risky_module(["frontend/src/App.js", "README.md"]) is False


class StubRunner:
    def __init__(self, result: dict):
        self._result = result

    async def run(self, **kwargs):
        return self._result


def _agent_result(steps: list[dict], **extra) -> dict:
    """Shape a fixture the way the real AgentRunner.run() actually returns."""
    return {"goal": "g", "plan": {}, "steps": steps, "commits": [], "summary": "", **extra}


def test_cross_verify_passes_on_a_real_shaped_clean_review():
    result = _agent_result([{"status": "applied", "issues": [], "changed_files": []}])
    factory = lambda: StubRunner(result)
    out = asyncio.run(
        vs.cross_verify(instruction="do thing", changed_files=["a.py"], runner_factory=factory)
    )
    assert out["cross_verified"] is True
    assert out["issues"] == []


def test_cross_verify_fails_when_issues_found():
    result = _agent_result([{"status": "applied", "issues": ["looks wrong"], "changed_files": []}])
    factory = lambda: StubRunner(result)
    out = asyncio.run(
        vs.cross_verify(instruction="do thing", changed_files=["admin_auth.py"], runner_factory=factory)
    )
    assert out["cross_verified"] is False
    assert "looks wrong" in out["issues"]


def test_cross_verify_fails_when_a_review_step_failed():
    result = _agent_result([{"status": "failed", "issues": [], "description": "check auth flow"}])
    factory = lambda: StubRunner(result)
    out = asyncio.run(
        vs.cross_verify(instruction="do thing", changed_files=["admin_auth.py"], runner_factory=factory)
    )
    assert out["cross_verified"] is False
    assert any("review step failed" in i for i in out["issues"])


def test_cross_verify_flags_unexpected_writes_despite_readonly_instruction():
    """The review instruction asks the agent not to modify files, but nothing
    in AgentRunner enforces that — a review agent that writes anyway must be
    treated as a finding, not silently accepted as a clean pass."""
    result = _agent_result([{"status": "applied", "issues": [], "changed_files": ["admin_auth.py"]}])
    factory = lambda: StubRunner(result)
    out = asyncio.run(
        vs.cross_verify(instruction="do thing", changed_files=["admin_auth.py"], runner_factory=factory)
    )
    assert out["cross_verified"] is False
    assert any("modified files" in i for i in out["issues"])


def test_cross_verify_handles_runner_exception():
    def factory():
        raise RuntimeError("boom")

    out = asyncio.run(
        vs.cross_verify(instruction="do thing", changed_files=[], runner_factory=factory)
    )
    assert out["cross_verified"] is False
    assert "cross_verify_error" in out["issues"][0]


def test_score_attempt_heuristic_perfect_run():
    result = _agent_result([{"status": "applied", "issues": []}])
    assert vs._score_attempt(result) == 1.0


def test_score_attempt_heuristic_no_steps_is_neutral_not_status_dependent():
    """Regression: _score_attempt used to branch on a top-level "status" key
    that AgentRunner.run() never sets, so a zero-step run always scored 0.1
    regardless of what actually happened. Confirm it no longer reads that
    phantom key by checking a couple of shapes score identically."""
    assert vs._score_attempt(_agent_result([])) == 0.1
    assert vs._score_attempt(_agent_result([], extra_field="whatever")) == 0.1


def test_score_attempt_error_sentinel_scores_zero():
    """The "error" sentinel is set by race()'s own _attempt() wrapper when
    the runner raises before producing a result — not something AgentRunner
    itself returns."""
    assert vs._score_attempt({"status": "error", "error": "boom"}) == 0.0


def test_race_requires_positive_n():
    with pytest.raises(ValueError):
        asyncio.run(vs.race(instruction="x", runner_factory=lambda: StubRunner({}), n=0))


def test_race_picks_the_best_scoring_attempt(monkeypatch):
    good = _agent_result([{"status": "applied", "issues": []}])
    bad = {"status": "error", "error": "boom"}
    attempts = iter([StubRunner(bad), StubRunner(good)])

    async def fake_score(result, instruction):
        return vs._score_attempt(result)

    monkeypatch.setattr(vs, "_score_result", fake_score)

    out = asyncio.run(
        vs.race(instruction="build the thing", runner_factory=lambda: next(attempts), n=2)
    )
    assert out["winner"] == good
    assert out["scores"][out["winner_index"]] == 1.0


def test_race_attempt_exception_scores_zero_via_error_sentinel():
    def bad_factory():
        raise RuntimeError("network down")

    out = asyncio.run(vs.race(instruction="x", runner_factory=bad_factory, n=1))
    assert out["attempts"][0]["status"] == "error"
    assert out["scores"][0] == 0.0
