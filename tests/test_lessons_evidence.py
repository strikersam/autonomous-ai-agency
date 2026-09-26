"""Lessons are weighed by evidence, not just counted (agent/lessons.py).

Regression for lessons that outranked everything forever: recall sorted by raw
``hits``, so a failure recorded 40 times months ago buried last week's failures,
and a later successful run on the same goal never weakened the lesson.
"""
from __future__ import annotations

import sqlite3
import time

import pytest

from agent import lessons
from agent.lessons import LessonStore, record_run_success

_DAY = 86400.0


@pytest.fixture()
def store(tmp_path, monkeypatch):
    s = LessonStore(tmp_path / "lessons.db")
    monkeypatch.setattr(lessons, "_store", s)
    return s


def _age(store: LessonStore, lesson_prefix: str, days: float) -> None:
    with store._connect() as conn:
        conn.execute(
            "UPDATE lessons SET updated_at = ? WHERE lesson LIKE ?",
            (time.time() - days * _DAY, f"{lesson_prefix}%"),
        )


def test_recent_failures_outrank_stale_frequent_ones(store):
    for _ in range(8):
        store.record(phase="execute", issue="old import error", goal="g1")
    _age(store, "old", 70)  # 5 half-lives: 8 hits weigh 0.25
    store.record(phase="verify", issue="fresh assertion failure", goal="g2")
    store.record(phase="verify", issue="fresh assertion failure", goal="g2")
    assert [r["lesson"] for r in store.recent(2)] == [
        "fresh assertion failure", "old import error",
    ]


def test_success_on_the_same_goal_retires_the_lesson(store):
    store.record(phase="execute", issue="patch did not apply", goal="fix login")
    store.record(phase="execute", issue="unrelated failure", goal="other goal")
    record_run_success("fix login", [{"status": "applied"}, {"status": "ok"}])
    assert [r["lesson"] for r in store.recent(10)] == ["unrelated failure"]


def test_a_recurring_lesson_needs_as_many_successes_to_retire(store):
    for _ in range(3):
        store.record(phase="execute", issue="flaky network", goal="deploy")
    record_run_success("deploy", [{"status": "ok"}])
    live = store.recent(10)
    assert live[0]["hits"] == 3 and live[0]["resolved"] == 1
    record_run_success("deploy", [{"status": "ok"}])
    record_run_success("deploy", [{"status": "ok"}])
    assert store.recent(10) == []


@pytest.mark.parametrize(
    "steps",
    [
        [{"status": "ok"}, {"status": "failed"}],
        [{"status": "skipped"}],
        [],
    ],
)
def test_partial_failed_or_empty_runs_do_not_count_as_success(store, steps):
    store.record(phase="execute", issue="still broken", goal="g")
    record_run_success("g", steps)
    assert store.recent(1)[0]["resolved"] == 0


def test_existing_store_gains_the_resolved_column(tmp_path):
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE lessons (signature TEXT PRIMARY KEY, phase TEXT NOT NULL, "
            "lesson TEXT NOT NULL, goal TEXT NOT NULL DEFAULT '', "
            "hits INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL)"
        )
        conn.execute(
            "INSERT INTO lessons VALUES ('sig', 'execute', 'kept', 'g', 2, ?)",
            (time.time(),),
        )
    assert LessonStore(db).recent(1)[0] == {
        "signature": "sig", "phase": "execute", "lesson": "kept", "hits": 2, "resolved": 0,
    }
