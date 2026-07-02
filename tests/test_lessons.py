"""Tests for agent/lessons.py — the failure-lesson learning loop."""
import agent.lessons as lessons_mod
from agent.lessons import LessonStore, record_step_failures, recent_lessons_block


def _fresh_store(tmp_path, monkeypatch):
    store = LessonStore(db_path=tmp_path / "lessons.db")
    monkeypatch.setattr(lessons_mod, "_store", store)
    return store


def test_record_and_recall(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    store.record(phase="tool_selection", issue="Tool selection failed after 3 attempts", goal="fix bug")
    recent = store.recent()
    assert len(recent) == 1
    assert recent[0]["phase"] == "tool_selection"


def test_dedupe_increments_hits(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    for _ in range(3):
        store.record(phase="execute", issue="Executor did not produce an applicable file update.")
    recent = store.recent()
    assert len(recent) == 1
    assert recent[0]["hits"] == 3


def test_empty_issue_ignored(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    store.record(phase="execute", issue="   ")
    assert store.recent() == []


def test_record_step_failures_only_failed(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch)
    record_step_failures("goal", [
        {"status": "applied", "issues": []},
        {"status": "failed", "failure_phase": "verify", "issues": ["tests failed: 2 assertions"]},
        {"status": "failed", "issues": []},  # no issue text → generic lesson
    ])
    recent = lessons_mod._get_store().recent()
    assert len(recent) == 2
    phases = {r["phase"] for r in recent}
    assert "verify" in phases


def test_block_format_and_empty(tmp_path, monkeypatch):
    _fresh_store(tmp_path, monkeypatch)
    assert recent_lessons_block() == ""
    record_step_failures("g", [{"status": "failed", "failure_phase": "plan", "issues": ["planning: bad JSON"]}])
    block = recent_lessons_block()
    assert "avoid repeating" in block
    assert "[plan] planning: bad JSON" in block


def test_never_raises(monkeypatch):
    class Broken:
        def recent(self, limit=5):
            raise RuntimeError("db gone")
    monkeypatch.setattr(lessons_mod, "_store", Broken())
    assert recent_lessons_block() == ""
    record_step_failures("g", [{"status": "failed", "issues": ["x"]}])  # must not raise
