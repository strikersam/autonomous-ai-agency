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


def _seed_loud_unrelated(store):
    for n in range(6):
        for _ in range(3):
            store.record(phase="execute", issue=f"Docker build step {n} ran out of disk")
    store.record(phase="verify", issue="Sitemap XML failed schema validation for canonical URLs")


def test_query_surfaces_relevant_lesson_beyond_evidence_top_n(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    _seed_loud_unrelated(store)
    assert "Sitemap" not in recent_lessons_block(limit=5)
    block = recent_lessons_block(limit=5, query="regenerate the sitemap with canonical URLs")
    lines = block.splitlines()[1:]
    assert len(lines) == 5
    assert "Sitemap XML failed" in lines[0]


def test_query_without_match_keeps_evidence_order(tmp_path, monkeypatch):
    store = _fresh_store(tmp_path, monkeypatch)
    _seed_loud_unrelated(store)
    assert recent_lessons_block(limit=5, query="zzz qqq") == recent_lessons_block(limit=5)
