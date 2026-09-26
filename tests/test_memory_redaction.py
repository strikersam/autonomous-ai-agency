"""Every agent memory store redacts secrets and PII before it writes to disk.

Regression for a gap where failed-step error text — the raw material of
``agent/lessons.py`` — was persisted verbatim, so a token echoed in a git or
HTTP error landed in ``.data/lessons.db`` (CLAUDE.md rule 6).
"""
from __future__ import annotations

import sqlite3

from agent.lessons import LessonStore
from agent.persistent_memory import PersistentMemoryStore
from agent.procedural_memory import ProceduralMemoryStore
from agent.user_memory import UserMemoryStore
from packages.security.redact import redact_secrets

_TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2"
_URI = "mongodb+srv://admin:hunter2pass@cluster0.example.net/db"


def _dump(db_path) -> str:
    with sqlite3.connect(db_path) as conn:
        rows = []
        for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            rows.extend(str(r) for r in conn.execute(f"SELECT * FROM {table}"))  # noqa: S608
    return "\n".join(rows)


def test_redact_secrets_covers_tokens_uris_and_cards():
    out = redact_secrets(f"push failed {_TOKEN} via {_URI} card 4111 1111 1111 1111")
    assert _TOKEN not in out
    assert "hunter2pass" not in out
    assert "4111 1111 1111 1111" not in out
    assert "cluster0.example.net" in out  # host stays visible for debugging


def test_redact_secrets_leaves_plain_text_alone():
    text = "tests failed in tests/test_router.py: assert 3 == 4"
    assert redact_secrets(text) == text
    assert redact_secrets("") == ""


def test_lesson_store_never_persists_a_token(tmp_path):
    db = tmp_path / "lessons.db"
    store = LessonStore(str(db))
    store.record(phase="execute", issue=f"git push rejected: {_TOKEN}", goal=f"use {_URI}")
    raw = _dump(db)
    assert _TOKEN not in raw
    assert "hunter2pass" not in raw
    assert store.recent(1)[0]["lesson"].startswith("git push rejected")


def test_persistent_memory_never_persists_a_token(tmp_path):
    db = tmp_path / "pm.db"
    store = PersistentMemoryStore(db)
    store.save("u1", "deploy", f"token={_TOKEN}")
    assert _TOKEN not in _dump(db)
    store.close()


def test_user_memory_never_persists_a_token(tmp_path):
    db = tmp_path / "um.db"
    UserMemoryStore(db).save("u1", "k", f"my key is {_TOKEN}")
    assert _TOKEN not in _dump(db)


def test_procedural_memory_redacts_before_storing():
    mem = ProceduralMemoryStore()
    mem.record_success(
        goal_summary="deploy",
        step_description=f"push with {_TOKEN}",
        action_summary=f"connected to {_URI}",
    )
    stored = mem._records[0]
    assert _TOKEN not in stored.step_description
    assert "hunter2pass" not in stored.action_summary
