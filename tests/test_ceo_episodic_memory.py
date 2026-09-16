"""Tests for CEO episodic memory: ledger.recent_decisions + prompt rendering."""
from __future__ import annotations

import agent.agency as agency
from services.ceo_ledger import CEOLedger, GoalRecord


def _ledger(monkeypatch) -> CEOLedger:
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    return CEOLedger(sqlite_path=":memory:")


def test_recent_decisions_returns_only_terminal_goals(monkeypatch):
    led = _ledger(monkeypatch)
    led.upsert(GoalRecord(goal_id="g1", goal="Ship pricing page",
                          state="closed", verdict="done, verified"))
    led.upsert(GoalRecord(goal_id="g2", goal="Explore risky refactor",
                          state="abandoned", verdict="budget exhausted"))
    led.upsert(GoalRecord(goal_id="g3", goal="Still running work",
                          state="open"))

    decisions = led.recent_decisions(limit=8)
    goals = {d["goal"] for d in decisions}
    assert "Ship pricing page" in goals
    assert "Explore risky refactor" in goals
    assert "Still running work" not in goals  # open goals are skipped
    states = {d["state"] for d in decisions}
    assert states == {"closed", "abandoned"}


def test_recent_decisions_respects_limit(monkeypatch):
    led = _ledger(monkeypatch)
    for i in range(10):
        led.upsert(GoalRecord(goal_id=f"g{i}", goal=f"goal {i}",
                              state="closed", verdict="ok"))
    assert len(led.recent_decisions(limit=3)) == 3


def test_recent_decisions_carries_verdict(monkeypatch):
    led = _ledger(monkeypatch)
    led.upsert(GoalRecord(goal_id="g1", goal="thing",
                          state="closed", verdict="a clear verdict"))
    [d] = led.recent_decisions(limit=8)
    assert d["verdict"] == "a clear verdict"


def test_build_ceo_prompt_renders_past_decisions():
    state = {
        "improvement_loop": {},
        "past_decisions": [
            {"goal": "Ship pricing page", "state": "closed",
             "verdict": "done, verified", "updated_at": 1.0},
            {"goal": "Risky refactor", "state": "abandoned",
             "verdict": "budget exhausted", "updated_at": 2.0},
        ],
    }
    prompt = agency._build_ceo_prompt(state, cycle=5)
    assert "## Past Decisions" in prompt
    assert "Ship pricing page" in prompt
    assert "budget exhausted" in prompt
    assert "✓" in prompt and "✗" in prompt


def test_build_ceo_prompt_omits_block_without_decisions():
    prompt = agency._build_ceo_prompt({"improvement_loop": {}}, cycle=1)
    assert "## Past Decisions" not in prompt
