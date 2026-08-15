"""tests/test_force_cleanup_conditional_delete.py

Covers two changes to the scheduler cleanup path:

  * #1208 — the ``force_cleanup()``-vs-``_fire()`` race. Both run-once
    expiration paths read a snapshot where ``run_count == 0`` and then delete,
    but a concurrent ``_fire()`` (APScheduler fires on a background thread) can
    increment ``run_count`` in between. ``ScheduleStore.delete_if_unfired_run_once``
    re-checks the condition atomically at delete time, and
    ``_expire_run_once_orphan`` prefers it so a row that has begun firing wins
    the race and is left for the already-fired rule.

  * #1207 — consolidating the four inline removal branches behind
    ``_remove_job`` so a *failed* durable delete is no longer miscounted as a
    removal on any of them (previously only the every-minute orphan path got
    that guarantee).
"""
from __future__ import annotations

import threading

import pytest

from agent.schedule_store import ScheduleStore
from packages.scheduler.scheduler import AgentScheduler


def _memory_store(docs: dict | None = None) -> ScheduleStore:
    """A ScheduleStore forced into its in-memory (non-durable) mode."""
    store = ScheduleStore.__new__(ScheduleStore)
    store._mem = dict(docs or {})
    store._mode = "memory"
    store._lock = threading.Lock()
    return store


# ── ScheduleStore.delete_if_unfired_run_once (unit) ──────────────────────────


class TestConditionalDeleteStore:
    def test_deletes_unfired_run_once(self):
        store = _memory_store({"j": {"job_id": "j", "tags": ["run-once"], "run_count": 0}})
        assert store.delete_if_unfired_run_once("j") is True
        assert store.load_all() == []

    def test_missing_run_count_treated_as_unfired(self):
        store = _memory_store({"j": {"job_id": "j", "tags": ["run-once"]}})
        assert store.delete_if_unfired_run_once("j") is True
        assert store.load_all() == []

    def test_keeps_already_fired_run_once(self):
        store = _memory_store({"j": {"job_id": "j", "tags": ["run-once"], "run_count": 1}})
        assert store.delete_if_unfired_run_once("j") is False
        assert len(store.load_all()) == 1

    def test_keeps_non_run_once(self):
        store = _memory_store({"j": {"job_id": "j", "tags": ["agency"], "run_count": 0}})
        assert store.delete_if_unfired_run_once("j") is False
        assert len(store.load_all()) == 1

    def test_missing_row_returns_false(self):
        store = _memory_store({})
        assert store.delete_if_unfired_run_once("nope") is False


# ── force_cleanup prefers the conditional delete (#1208) ─────────────────────


class _RaceLostPersistence:
    """Store whose conditional delete always loses the race (as if _fire() had
    already incremented run_count). ``remove`` would still succeed — the point
    is that the conditional path must be taken and must NOT fall back to it."""

    def __init__(self, docs: list[dict]) -> None:
        self.docs = {d["job_id"]: d for d in docs}
        self.unconditional_removes: list[str] = []

    def load_all(self) -> list[dict]:
        return list(self.docs.values())

    def upsert(self, doc: dict) -> None:
        self.docs[doc["job_id"]] = doc

    def remove(self, job_id: str) -> None:
        self.unconditional_removes.append(job_id)
        self.docs.pop(job_id, None)

    def delete_if_unfired_run_once(self, job_id: str) -> bool:
        return False  # the row started firing first


class _RaceWonPersistence(_RaceLostPersistence):
    def delete_if_unfired_run_once(self, job_id: str) -> bool:
        return self.docs.pop(job_id, None) is not None


def _orphan(job_id: str) -> dict:
    return {
        "job_id": job_id,
        "name": f"agency: directive {job_id}",
        "cron": "* * * * *",
        "tags": ["run-once", "agency"],
        "run_count": 0,
        "created_at": "2000-01-01T00:00:00Z",  # ancient — eligible by age
    }


@pytest.mark.asyncio
async def test_orphan_that_started_firing_is_not_expired():
    store = _RaceLostPersistence([_orphan("job_racing")])
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    assert summary["expired"] == 0, f"a row that began firing was miscounted: {summary}"
    assert store.unconditional_removes == [], (
        "must use the conditional delete, never fall back to an unconditional remove"
    )
    assert "job_racing" in store.docs, "the firing row must be left in the store"


@pytest.mark.asyncio
async def test_orphan_still_unfired_is_expired_via_conditional_delete():
    store = _RaceWonPersistence([_orphan("job_dead")])
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    assert summary["expired"] == 1
    assert store.docs == {}


# ── #1207: a failed durable delete is not miscounted on ANY branch ───────────


class _FlakyPersistence:
    """Every removal path fails at the durable store."""

    def __init__(self, docs: list[dict]) -> None:
        self.docs = {d["job_id"]: d for d in docs}

    def load_all(self) -> list[dict]:
        return list(self.docs.values())

    def upsert(self, doc: dict) -> None:
        self.docs[doc["job_id"]] = doc

    def remove(self, job_id: str) -> None:
        raise RuntimeError("simulated durable-store failure")


@pytest.mark.asyncio
async def test_failed_delete_not_counted_on_fired_dedup_and_stuck_paths():
    docs = [
        {"job_id": "fired", "name": "fix: a", "tags": ["run-once"], "run_count": 2,
         "cron": "17 3 1 1 *", "created_at": "2000-01-01T00:00:00Z"},
        {"job_id": "stuck", "name": "agency: x", "tags": ["agency"], "run_count": 15,
         "cron": "* * * * *", "created_at": "2000-01-01T00:00:00Z"},
        {"job_id": "dup1", "name": "same", "tags": [], "run_count": 3,
         "cron": "0 * * * *", "created_at": "2000-01-01T00:00:00Z"},
        {"job_id": "dup2", "name": "same", "tags": [], "run_count": 3,
         "cron": "0 * * * *", "created_at": "2000-01-01T00:00:00Z"},
    ]
    store = _FlakyPersistence(docs)
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    # Every branch's durable delete raised, so nothing may be counted as removed
    # and every row must still be present (the previous inline branches swallowed
    # the error and incremented the counter anyway).
    assert summary["deleted"] == 0, f"failed deletes miscounted: {summary}"
    assert summary["deduped"] == 0, f"failed dedup miscounted: {summary}"
    assert {d["job_id"] for d in store.load_all()} == {"fired", "stuck", "dup1", "dup2"}
