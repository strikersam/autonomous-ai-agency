"""Why the 2026-08-01 backlog never drained, despite a fix already existing.

Production logged this on every cron tick while serving 503s:

    Force-cleanup: total=1178 deleted=0 deduped=0

Two independent defects kept that number pinned. Both are fixed here, and each
test below fails against the previous code.

1. ``nuclear_cleanup`` cleaned the wrong collection. The scheduler persists to
   ``agent_schedules`` (``agent/schedule_store.py::_COLLECTION``), but the
   resolver tried ``db.schedules`` first — and on MongoDB that returns a
   lazily-created collection object rather than ``None``, so it always won.
   Every ``delete_many`` ran against an empty collection and the summary
   reported a clean sweep. The boot sweep had been a no-op for its whole life,
   which is why a documented fix for the earlier 2,873-row incident never
   actually took effect.

2. ``force_cleanup`` — the per-tick sweep — could not expire an unfired
   one-shot. It removed run-once jobs only once ``run_count > 0``. A one-shot
   whose cron minute has already passed never fires, so its count stays 0
   forever; its name is unique so the dedup pass skips it, and it carries no
   "agency" tag for the stuck-task rule. Immortal by construction, one row at
   a time.

Together those explain ``deleted=0 deduped=0`` next to a four-digit total.
"""
from __future__ import annotations

import time

import pytest

from packages.scheduler.scheduler import AgentScheduler


def _stamp(age_seconds: float = 0.0) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - age_seconds))


class _FakePersistence:
    """In-memory ScheduleStore stand-in (sync upsert/remove/load_all)."""

    def __init__(self, docs: list[dict] | None = None) -> None:
        self.docs: dict[str, dict] = {d["job_id"]: d for d in (docs or [])}

    def load_all(self) -> list[dict]:
        return list(self.docs.values())

    def upsert(self, doc: dict) -> None:
        self.docs[doc.get("job_id", doc.get("id", ""))] = doc

    def remove(self, job_id: str) -> None:
        self.docs.pop(job_id, None)


def _one_shot(job_id: str, *, age_days: float, run_count: int = 0) -> dict:
    """A uniquely-named run-once row — the shape that piled up."""
    return {
        "job_id": job_id,
        "name": f"fix: issue {job_id}",   # unique, so dedup-by-name cannot help
        "cron": "17 3 1 1 *",             # a minute in the past; never fires again
        "tags": ["run-once"],
        "run_count": run_count,
        "created_at": _stamp(age_days * 24 * 3600),
    }


# ── The per-tick sweep can now expire unfired one-shots ──────────────────────


@pytest.mark.asyncio
async def test_force_cleanup_expires_one_shots_that_will_never_fire():
    """The exact production shape: unique names, run_count 0, cleanup at zero."""
    store = _FakePersistence([_one_shot(f"job_{i}", age_days=30) for i in range(50)])
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    assert summary["total"] == 50
    assert summary["expired"] == 50, (
        f"unfired one-shots survived the sweep again: {summary}"
    )
    assert store.load_all() == [], "the backlog must actually leave the store"


@pytest.mark.asyncio
async def test_a_recent_one_shot_is_left_alone():
    """Expiry must not eat a one-shot that has not had its moment yet."""
    store = _FakePersistence([
        _one_shot("job_fresh", age_days=0),
        _one_shot("job_stale", age_days=30),
    ])
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    remaining = {d["job_id"] for d in store.load_all()}
    assert remaining == {"job_fresh"}, f"wrong row removed: {summary}"


@pytest.mark.asyncio
async def test_an_unreadable_created_at_is_never_treated_as_ancient():
    """A timestamp we cannot parse must not authorise a delete."""
    bad = _one_shot("job_bad", age_days=30)
    bad["created_at"] = "not-a-timestamp"
    missing = _one_shot("job_missing", age_days=30)
    del missing["created_at"]

    store = _FakePersistence([bad, missing])
    sched = AgentScheduler(persistence=store)
    try:
        await sched.force_cleanup()
    finally:
        sched.shutdown()

    assert len(store.load_all()) == 2, "an unparseable date must fail closed"


def _every_minute_one_shot(job_id: str, *, age_seconds: float, run_count: int = 0) -> dict:
    """An agency-directive-shaped row: cron="* * * * *", uniquely named."""
    return {
        "job_id": job_id,
        "name": f"agency: directive {job_id}",
        "cron": "* * * * *",
        "tags": ["run-once", "agency"],
        "run_count": run_count,
        "created_at": _stamp(age_seconds),
    }


@pytest.mark.asyncio
async def test_force_cleanup_expires_every_minute_orphans_fast():
    """2026-08-03: the 7-day fallback let a live crash loop regrow the backlog
    from a fresh purge to 1137 rows (1075 agency-prefixed) in ~5.5 hours,
    re-triggering the OOM restart cycle it was meant to prevent. Every one of
    those rows was cron="* * * * *" — a pattern that gets a fresh fire chance
    every 60s, so missing many in a row is provable death, not a guess."""
    store = _FakePersistence([_every_minute_one_shot("job_stuck", age_seconds=900)])
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    assert summary["expired"] == 1, f"every-minute orphan survived: {summary}"
    assert store.load_all() == []


@pytest.mark.asyncio
async def test_a_fresh_every_minute_one_shot_gets_its_chance_first():
    """Must not delete a same-pattern row that hasn't had time to fire yet."""
    store = _FakePersistence([_every_minute_one_shot("job_new", age_seconds=5)])
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    assert summary["expired"] == 0
    assert {d["job_id"] for d in store.load_all()} == {"job_new"}


@pytest.mark.asyncio
async def test_a_daily_low_priority_fix_job_is_not_caught_by_the_fast_path():
    """A "0 9 * * *" run-once row legitimately waits up to ~24h for its one
    scheduled window (agent/improvement_loop.py's _LOW_CRON) — the fast path
    must be scoped to "* * * * *" only, or this gets deleted before it can
    ever fire."""
    daily = _every_minute_one_shot("job_daily", age_seconds=900)
    daily["cron"] = "0 9 * * *"
    store = _FakePersistence([daily])
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    assert summary["expired"] == 0
    assert {d["job_id"] for d in store.load_all()} == {"job_daily"}


@pytest.mark.asyncio
async def test_a_fired_one_shot_is_still_removed_by_the_original_rule():
    """The pre-existing behaviour has to survive the new branch above it."""
    store = _FakePersistence([_one_shot("job_fired", age_days=0, run_count=1)])
    sched = AgentScheduler(persistence=store)
    try:
        summary = await sched.force_cleanup()
    finally:
        sched.shutdown()

    assert summary["deleted"] == 1
    assert store.load_all() == []


@pytest.mark.asyncio
async def test_a_stubborn_backlog_is_reported_at_warning(caplog):
    """The previous failure was invisible: four digits at INFO beside two zeroes."""
    # Recurring rows, so nothing above can remove them.
    docs = [
        {
            "job_id": f"job_{i}",
            "name": f"company:acme-{i}:scan",
            "cron": "0 * * * *",
            "tags": [],
            "run_count": 3,
            "created_at": _stamp(),
        }
        for i in range(250)
    ]
    store = _FakePersistence(docs)
    sched = AgentScheduler(persistence=store)
    try:
        with caplog.at_level("WARNING"):
            await sched.force_cleanup()
    finally:
        sched.shutdown()

    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("backlog is not draining" in w for w in warnings), (
        f"a 250-schedule backlog must escalate, got: {warnings}"
    )
    assert any("company=250" in w for w in warnings), (
        "the warning must name the source prefix so it can be traced"
    )


# ── The boot sweep now targets the collection schedules actually live in ─────


@pytest.mark.asyncio
async def test_nuclear_cleanup_targets_the_schedule_collection():
    """It cleaned `db.schedules`, which on Mongo is a real but empty collection.

    The resolver's first branch always succeeded, so every delete ran against
    nothing and the summary still looked healthy.
    """
    from packages.scheduler.cleanup import nuclear_cleanup
    from agent.schedule_store import _COLLECTION

    class _Collection:
        def __init__(self, docs):
            self.docs = docs

        async def count_documents(self, _q):
            return len(self.docs)

        async def delete_many(self, query):
            before = len(self.docs)
            tags = (query.get("tags") or {}).get("$in") or []
            keep = []
            for d in self.docs:
                run_count = d.get("run_count", 0)
                matches = bool(tags) and any(t in (d.get("tags") or []) for t in tags)
                if "run_count" in query and isinstance(query["run_count"], dict):
                    matches = matches and run_count > query["run_count"].get("$gt", -1)
                elif query.get("run_count") == 0:
                    matches = matches and run_count == 0
                if matches:
                    continue
                keep.append(d)
            self.docs[:] = keep

            class _R:
                deleted_count = before - len(keep)
            return _R()

        def aggregate(self, _pipeline):
            async def _empty():
                return
                yield  # pragma: no cover
            return _empty()

    schedules = _Collection([
        {"job_id": "j1", "name": "fix: a", "tags": ["run-once"], "run_count": 1},
        {"job_id": "j2", "name": "fix: b", "tags": ["run-once"], "run_count": 2},
    ])
    decoy = _Collection([])

    class _Db:
        def __getitem__(self, name):
            return schedules if name == _COLLECTION else decoy

    summary = await nuclear_cleanup(_Db())

    # ``total`` is recomputed after the deletes, so it reports what remains.
    assert summary["deleted_run_once"] == 2, (
        "nuclear_cleanup swept the wrong collection — it must read "
        f"{_COLLECTION!r}, where the scheduler actually persists. Against the "
        "previous resolver this is 0: db.schedules answered first and was empty."
    )
    assert schedules.docs == [], "the real collection must be the one emptied"
    assert summary["total"] == 0


def test_agent_schedules_stays_out_of_the_generic_sqlite_allowlist():
    """Adding it looks like a fix and is a worse bug.

    ``packages/storage/sqlite.py`` and ``agent/schedule_store.py`` both default
    to ``.data/agency.db``. ``_init_schema()`` creates every allowlisted name
    as ``(id, data)``; the scheduler's table is ``(job_id, doc, updated_at)``.
    Whichever initialises first wins the CREATE TABLE IF NOT EXISTS, so
    allowlisting it can leave schedule persistence writing into a table
    without its columns — breaking the scheduler outright, rather than merely
    leaving the boot sweep inert on SQLite.
    """
    from packages.storage.sqlite import _COLLECTIONS
    from agent.schedule_store import _COLLECTION

    assert _COLLECTION not in _COLLECTIONS, (
        f"{_COLLECTION!r} must not be in the generic collection allowlist — "
        "the two stores share a database file and disagree on the schema"
    )


def test_the_collection_name_comes_from_the_store_not_a_literal():
    """Guard the drift that caused this: two files naming the same collection."""
    from pathlib import Path
    from agent.schedule_store import _COLLECTION

    assert _COLLECTION == "agent_schedules"
    source = Path("packages/scheduler/cleanup.py").read_text()
    assert "from agent.schedule_store import _COLLECTION" in source, (
        "cleanup.py must take the collection name from the store that owns it"
    )
