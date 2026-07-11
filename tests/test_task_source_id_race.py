"""tests/test_task_source_id_race.py — TaskStore.create() concurrency safety.

Covers the follow-up fix to the ceo_direct/portfolio dedup work: the
check-then-insert in TaskStore.create() is race-prone by itself (two
concurrent callers can both pass find_by_source_id before either commits).
In Mongo mode this is closed by a unique+sparse index on source_id plus
DuplicateKeyError handling in create(); these tests simulate the losing
side of that race with a mocked Mongo collection.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tasks.models import Task
from tasks.store import TaskStore, _is_duplicate_key_error


class _FakeDuplicateKeyError(Exception):
    """Stand-in for pymongo.errors.DuplicateKeyError (E11000)."""


def _mock_mongo_db():
    db = MagicMock()
    coll = MagicMock()
    db.__getitem__ = MagicMock(return_value=coll)
    return db, coll


def test_is_duplicate_key_error_matches_by_class_name():
    exc = _FakeDuplicateKeyError("E11000 duplicate key error collection: tasks index: source_id_1")
    assert _is_duplicate_key_error(exc) is True


def test_is_duplicate_key_error_matches_by_message_substring():
    class SomeOtherError(Exception):
        pass
    exc = SomeOtherError("E11000 duplicate key error")
    assert _is_duplicate_key_error(exc) is True


def test_is_duplicate_key_error_false_for_unrelated_error():
    assert _is_duplicate_key_error(ValueError("bad input")) is False


@pytest.mark.asyncio
async def test_create_recovers_from_lost_race_via_duplicate_key_error():
    """Simulates the losing side of a create-create race for the same
    source_id: the pre-insert find_by_source_id check misses (the winner
    hasn't committed yet), insert_one() then raises a duplicate-key error
    (as the unique index would once the winner's insert has landed), and
    create() must resolve to the winner's task instead of raising."""
    db, coll = _mock_mongo_db()
    store = TaskStore(db=db)

    winner = Task(owner_id="system", title="Winner", source="ceo_direct", source_id="owner/repo#1")
    loser = Task(owner_id="system", title="Loser", source="ceo_direct", source_id="owner/repo#1")

    # First find_by_source_id call (pre-insert check): miss — the winner's
    # insert hasn't committed yet from this caller's point of view. Second
    # call (post-DuplicateKeyError recovery): hit — the winner has since
    # landed in Mongo.
    find_calls = {"n": 0}

    async def _find_one(query, *_a, **_kw):
        find_calls["n"] += 1
        if find_calls["n"] == 1:
            return None
        return winner.model_dump()

    coll.find_one = AsyncMock(side_effect=_find_one)
    coll.insert_one = AsyncMock(side_effect=_FakeDuplicateKeyError("E11000 duplicate key error"))

    result_task = await store.create(loser)

    assert find_calls["n"] == 2
    assert result_task.task_id == winner.task_id
    assert result_task.title == "Winner"


@pytest.mark.asyncio
async def test_create_reraises_non_duplicate_errors():
    """A genuine DB error (not a duplicate-key race) must still propagate —
    create() only swallows the specific duplicate-key case."""
    db, coll = _mock_mongo_db()
    store = TaskStore(db=db)
    task = Task(owner_id="system", title="X", source="ceo_direct", source_id="owner/repo#9")

    coll.find_one = AsyncMock(return_value=None)
    coll.insert_one = AsyncMock(side_effect=ConnectionError("mongo unreachable"))

    with pytest.raises(ConnectionError):
        await store.create(task)


@pytest.mark.asyncio
async def test_create_without_source_id_reraises_duplicate_key_error():
    """A duplicate-key error on a task with no source_id (e.g. a task_id
    collision, which should never happen but must not be silently eaten)
    is re-raised rather than resolved via find_by_source_id."""
    db, coll = _mock_mongo_db()
    store = TaskStore(db=db)
    task = Task(owner_id="system", title="No source_id")
    assert task.source_id is None

    coll.insert_one = AsyncMock(side_effect=_FakeDuplicateKeyError("E11000 duplicate key error"))

    with pytest.raises(_FakeDuplicateKeyError):
        await store.create(task)
