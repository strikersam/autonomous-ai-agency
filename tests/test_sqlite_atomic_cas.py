"""Single statement SQLite helpers: insert if absent, compare and set, increment and get."""
from __future__ import annotations

import asyncio

import pytest

from packages.storage import sqlite_atomic
from packages.storage.sqlite import SQLiteStore


@pytest.fixture
async def two_stores(tmp_path):
    path = str(tmp_path / "cas.db")
    a, b = SQLiteStore(path), SQLiteStore(path)
    await a._get_conn()  # first connects one at a time (see tests/_runs_backends.py)
    await b._get_conn()
    yield a, b
    await a.close()
    await b.close()


async def test_insert_if_absent_inserts_once_and_fills_indexed_columns(two_stores):
    a, _ = two_stores
    assert await sqlite_atomic.insert_if_absent(a.runs, "r1", {"state": "queued", "task_id": "t"}) is True
    assert await sqlite_atomic.insert_if_absent(a.runs, "r1", {"state": "running"}) is False
    doc = await a.runs.find_one({"_id": "r1"})
    assert doc["state"] == "queued" and doc["_id"] == "r1"
    # The pushed down WHERE on the indexed column finds it, so the column was filled.
    assert [d["_id"] for d in await a.runs.find({"state": "queued"}).to_list(None)] == ["r1"]


async def test_concurrent_inserts_from_two_processes_admit_exactly_one(two_stores):
    a, b = two_stores
    results = await asyncio.gather(*(
        sqlite_atomic.insert_if_absent((a if i % 2 else b).task_run_leases, "k", {"holder": f"h{i}"})
        for i in range(10)
    ))
    assert results.count(True) == 1


async def test_compare_and_set_applies_only_when_every_condition_holds(two_stores):
    a, _ = two_stores
    await sqlite_atomic.insert_if_absent(a.runs, "r1", {"state": "running", "lease_token": 2})
    assert await sqlite_atomic.compare_and_set(a.runs, "r1", {"lease_token": 1}, {"state": "failed"}) is False
    assert await sqlite_atomic.compare_and_set(a.runs, "r1", {"lease_token": 2}, {"state": "failed"}) is True
    assert (await a.runs.find_one({"_id": "r1"}))["state"] == "failed"
    # The indexed column moved with the JSON field.
    assert await a.runs.find({"state": "running"}).to_list(None) == []
    assert await sqlite_atomic.compare_and_set(a.runs, "missing", {}, {"state": "x"}) is False


async def test_none_means_missing_and_lt_and_any_of(two_stores):
    a, _ = two_stores
    await sqlite_atomic.insert_if_absent(a.task_run_leases, "k", {"holder": "h", "expires_at": 100.0})
    assert await sqlite_atomic.compare_and_set(a.task_run_leases, "k", {"token": None}, {"token": 1})
    alt = [{"expires_at": ("lt", 50.0)}, {"holder": "other"}]
    assert not await sqlite_atomic.compare_and_set(a.task_run_leases, "k", {}, {"holder": "x"}, any_of=alt)
    alt = [{"expires_at": ("lt", 150.0)}, {"holder": "other"}]
    assert await sqlite_atomic.compare_and_set(a.task_run_leases, "k", {"token": 1}, {"holder": "x"}, any_of=alt)
    assert (await a.task_run_leases.find_one({"_id": "k"}))["holder"] == "x"


async def test_values_keep_their_json_types_and_quotes_are_data(two_stores):
    a, _ = two_stores
    await sqlite_atomic.insert_if_absent(a.runs, "r1", {"state": "x"})
    hostile = "x'); DROP TABLE runs; --"
    ok = await sqlite_atomic.compare_and_set(
        a.runs, "r1", {"state": "x"},
        {"cancel_requested": True, "retry_history": [{"n": 1}], "budget": {"usd": 1.5}, "phase": hostile},
    )
    assert ok
    doc = await a.runs.find_one({"_id": "r1"})
    assert doc["cancel_requested"] is True
    assert doc["retry_history"] == [{"n": 1}] and doc["budget"] == {"usd": 1.5}
    assert doc["phase"] == hostile
    assert await sqlite_atomic.compare_and_set(a.runs, "r1", {"cancel_requested": True}, {"phase": "p"})


async def test_unsafe_field_names_and_conditions_are_refused(two_stores):
    a, _ = two_stores
    with pytest.raises(ValueError):
        await sqlite_atomic.compare_and_set(a.runs, "r1", {}, {"a') --": 1})
    with pytest.raises(ValueError):
        await sqlite_atomic.compare_and_set(a.runs, "r1", {"x.y": 1}, {"a": 1})
    with pytest.raises(ValueError):
        await sqlite_atomic.compare_and_set(a.runs, "r1", {"a": ("gt", 1)}, {"a": 1})
    with pytest.raises(ValueError):
        await sqlite_atomic.increment_and_get(a.runs, "r1", "bad field")


async def test_increment_and_get_never_hands_out_the_same_number(two_stores):
    a, b = two_stores
    await sqlite_atomic.insert_if_absent(a.runs, "r1", {"op_seq": 0})
    values = await asyncio.gather(*(
        sqlite_atomic.increment_and_get((a if i % 2 else b).runs, "r1", "op_seq") for i in range(20)
    ))
    assert sorted(values) == list(range(1, 21))
    assert await sqlite_atomic.increment_and_get(a.runs, "missing", "op_seq") is None
