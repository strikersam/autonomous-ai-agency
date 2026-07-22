"""Tests for agent/verification_strategies.py (cross_verify + race)."""
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


def test_cross_verify_passes_when_clean():
    result = {"status": "completed", "issues": [], "steps": [{"status": "applied", "issues": []}]}
    factory = lambda: StubRunner(result)
    out = asyncio.run(
        vs.cross_verify(instruction="do thing", changed_files=["a.py"], runner_factory=factory)
    )
    assert out["cross_verified"] is True
    assert out["issues"] == []


def test_cross_verify_fails_when_issues_found():
    result = {"status": "completed", "issues": [], "steps": [{"status": "applied", "issues": ["looks wrong"]}]}
    factory = lambda: StubRunner(result)
    out = asyncio.run(
        vs.cross_verify(instruction="do thing", changed_files=["admin_auth.py"], runner_factory=factory)
    )
    assert out["cross_verified"] is False
    assert "looks wrong" in out["issues"]


def test_cross_verify_handles_runner_exception():
    def factory():
        raise RuntimeError("boom")

    out = asyncio.run(
        vs.cross_verify(instruction="do thing", changed_files=[], runner_factory=factory)
    )
    assert out["cross_verified"] is False
    assert "cross_verify_error" in out["issues"][0]


def test_score_attempt_heuristic_perfect_run():
    result = {"status": "completed", "steps": [{"status": "applied", "issues": []}]}
    assert vs._score_attempt(result) == 1.0


def test_score_attempt_heuristic_failed_run():
    assert vs._score_attempt({"status": "failed"}) == 0.0


def test_race_requires_positive_n():
    async def factory():
        return StubRunner({})

    with pytest.raises(ValueError):
        asyncio.run(vs.race(instruction="x", runner_factory=lambda: StubRunner({}), n=0))


def test_race_picks_the_best_scoring_attempt(monkeypatch):
    good = {"status": "completed", "steps": [{"status": "applied", "issues": []}]}
    bad = {"status": "failed", "steps": []}
    attempts = iter([StubRunner(bad), StubRunner(good)])

    async def fake_score(result, instruction):
        return vs._score_attempt(result)

    monkeypatch.setattr(vs, "_score_result", fake_score)

    out = asyncio.run(
        vs.race(instruction="build the thing", runner_factory=lambda: next(attempts), n=2)
    )
    assert out["winner"] == good
    assert out["scores"][out["winner_index"]] == 1.0
