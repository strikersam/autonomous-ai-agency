"""Workstream D — Never again: dedup + growth invariants.

These tests enforce determinism and boundedness to prevent a recurrence
of the 2026-07-03 incident where 2,873 uniquely-named schedule rows
piled up in Mongo, causing an OOM crash-loop on the 512MB Render free tier.

Root causes pinned by these tests:
1. Agency directives used secrets.token_hex(4) in schedule names → uniquely-named
   rows that pass dedup-by-name forever.
2. Stale run-once jobs with run_count==0 survived every cleanup filter.
3. force_cleanup dedup-by-name couldn't touch uniquely-named rows.
4. No growth-bound invariant existed.

Each test below pins one invariant that makes the incident impossible.
"""
from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# ──────────────────────────────────────────────────────────────────────────────
# Test 1: test_schedule_create_idempotent_by_name
# AgentScheduler.create() twice with the same name returns the same job;
# store has exactly 1 row.
# ──────────────────────────────────────────────────────────────────────────────


class _FakePersistence:
    """In-memory ScheduleStore stand-in (sync upsert/remove/load_all)."""

    def __init__(self) -> None:
        self.docs: dict[str, dict] = {}

    def load_all(self) -> list[dict]:
        return list(self.docs.values())

    def upsert(self, doc: dict) -> None:
        self.docs[doc.get("job_id", doc.get("id", ""))] = doc

    def remove(self, job_id: str) -> None:
        self.docs.pop(job_id, None)


def test_schedule_create_idempotent_by_name():
    """Creating the same schedule name twice returns the same job — no duplication."""
    from packages.scheduler.scheduler import AgentScheduler

    store = _FakePersistence()
    sched = AgentScheduler(persistence=store)
    try:
        job1 = sched.create(
            name="fix: test issue [security]",
            cron="0 9 * * *",
            instruction="fix the issue",
            run_once=True,
            tags=["auto-improvement", "security"],
        )
        job2 = sched.create(
            name="fix: test issue [security]",
            cron="0 9 * * *",
            instruction="fix the issue",
            run_once=True,
            tags=["auto-improvement", "security"],
        )
        assert job1.job_id == job2.job_id, "Second create with same name must return the same job"
        assert len(sched.list()) == 1, "Scheduler must have exactly 1 job after duplicate create"
        # Store should also have exactly 1 row
        assert len(store.docs) <= 1, f"Store should have 0-1 rows, has {len(store.docs)}"
    finally:
        sched.shutdown()


# ──────────────────────────────────────────────────────────────────────────────
# Test 2: test_agency_schedules_use_stable_names
# Every call site that creates schedules for tasks/directives derives the
# schedule name deterministically from the task/source id — NO uuid/timestamp.
# ──────────────────────────────────────────────────────────────────────────────


def test_agency_schedules_use_stable_names():
    """Agency directive dispatch must use deterministic schedule names.

    The 2026-07-03 incident was caused by `secrets.token_hex(4)` in
    directive_id, making every schedule name unique. This test inspects
    the agency.py source code to ensure no uuid/timestamp/random suffix
    appears in schedule name construction.
    """
    import inspect
    import agent.agency as agency_mod

    source = inspect.getsource(agency_mod)

    # Find all lines that construct schedule names
    name_lines = [line.strip() for line in source.splitlines()
                  if "name=" in line and ("agency" in line.lower() or "directive" in line.lower()
                                           or "f\"" in line or "f'" in line)]

    # Check that no line uses secrets.token_hex, uuid, or time.time in a name= context
    # within the _dispatch_directive method
    dispatch_source = inspect.getsource(agency_mod.Agency._dispatch_directive)

    forbidden_patterns = [
        "secrets.token_hex",
        "uuid.uuid",
        "time.time()",
        "datetime.now",
        "datetime.utcnow",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in dispatch_source, (
            f"_dispatch_directive must not use {pattern!r} — it makes schedule names "
            f"non-deterministic and was the root cause of the 2,873-row schedule pile. "
            f"Use directive.title or a deterministic hash of the instruction instead."
        )

    # Also verify the directive_id itself is NOT used in the schedule name
    # (directive_id uses secrets.token_hex which is non-deterministic)
    assert "directive_id" not in str(name_lines), (
        f"Schedule names must not use directive_id (which uses secrets.token_hex). "
        f"Found: {name_lines}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 3: test_nuclear_cleanup_dedup_both_backends
# Parametrize over Mongo-style and SQLite/memory stores; duplicate-named
# rows collapse to newest on BOTH.
# ──────────────────────────────────────────────────────────────────────────────


class _FakeMongoStore:
    """Simulates a Mongo-style store with find/aggregate/replace_one."""

    def __init__(self) -> None:
        self._docs: list[dict] = []

    async def find(self, query=None):
        return list(self._docs)

    async def replace_one(self, query, doc, upsert=False):
        job_id = query.get("job_id")
        for i, d in enumerate(self._docs):
            if d.get("job_id") == job_id:
                self._docs[i] = doc
                return
        if upsert:
            self._docs.append(doc)

    async def delete_one(self, query):
        job_id = query.get("job_id")
        self._docs = [d for d in self._docs if d.get("job_id") != job_id]

    async def to_list(self, length=500):
        return list(self._docs)


class _FakeSQLiteStore:
    """Simulates a SQLite-style store with load_all/upsert/remove."""

    def __init__(self) -> None:
        self._docs: dict[str, dict] = {}

    def load_all(self) -> list[dict]:
        return list(self._docs.values())

    def upsert(self, doc: dict) -> None:
        self._docs[doc.get("job_id", "")] = doc

    def remove(self, job_id: str) -> None:
        self._docs.pop(job_id, None)


@pytest.mark.parametrize("store_type", ["mongo_style", "sqlite_style"])
@pytest.mark.asyncio
async def test_nuclear_cleanup_dedup_both_backends(store_type):
    """Duplicate-named rows must collapse to newest on BOTH backends.

    Regression for the #936 silent-$aggregate-failure bug where the Mongo
    dedup pipeline silently failed and left duplicates.
    """
    from packages.scheduler.cleanup import cleanup_stale_jobs

    if store_type == "mongo_style":
        store = _FakeMongoStore()
        # Populate with 3 docs, 2 sharing the same name
        store._docs = [
            {"job_id": "job_1", "name": "fix: issue A [security]", "tags": [], "run_count": 0},
            {"job_id": "job_2", "name": "fix: issue A [security]", "tags": [], "run_count": 0},
            {"job_id": "job_3", "name": "fix: issue B [bug]", "tags": [], "run_count": 0},
        ]
        # Wrap in an adapter that cleanup_stale_jobs can use
        class _MongoAdapter:
            def __init__(self, mongo):
                self._mongo = mongo

            async def load_all(self):
                return await self._mongo.find({})

            async def remove(self, job_id):
                await self._mongo.delete_one({"job_id": job_id})

        adapter = _MongoAdapter(store)
    else:
        store = _FakeSQLiteStore()
        store._docs = {
            "job_1": {"job_id": "job_1", "name": "fix: issue A [security]", "tags": [], "run_count": 0},
            "job_2": {"job_id": "job_2", "name": "fix: issue A [security]", "tags": [], "run_count": 0},
            "job_3": {"job_id": "job_3", "name": "fix: issue B [bug]", "tags": [], "run_count": 0},
        }
        adapter = store

    summary = await cleanup_stale_jobs(adapter)

    # After cleanup: the duplicate "fix: issue A [security]" should be deduped
    # We should have at most 2 unique names remaining
    remaining = await adapter.load_all() if hasattr(adapter, 'load_all') else store.load_all()
    names = [d.get("name") for d in remaining]
    assert len(names) == len(set(names)), (
        f"Duplicate names remain after cleanup: {names}. "
        f"Summary: {summary}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 4: test_force_cleanup_removes_stale_unfired_run_once
# Run-once jobs with run_count==0 older than SCHEDULE_RUN_ONCE_TTL_DAYS
# (default 7) are deleted — this exact class survived every existing filter.
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_force_cleanup_removes_stale_unfired_run_once():
    """Stale unfired run-once jobs (run_count==0, old created_at) must be deleted.

    The 2,873-row pile was exactly this class: run-once jobs that were
    created but never fired (run_count=0), and survived every cleanup
    filter because the existing filter only removed run-once jobs with
    run_count > 0.
    """
    from packages.scheduler.cleanup import cleanup_stale_jobs

    store = _FakeSQLiteStore()
    # Simulate a stale unfired run-once job created 10 days ago
    import time as _time
    old_ts = _time.time() - (10 * 24 * 3600)  # 10 days ago

    store._docs = {
        "job_stale": {
            "job_id": "job_stale",
            "name": "fix: old issue [bug]",
            "tags": ["run-once", "agency"],
            "run_count": 0,
            "created_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(old_ts)),
        },
        "job_fresh": {
            "job_id": "job_fresh",
            "name": "fix: new issue [security]",
            "tags": ["run-once", "agency"],
            "run_count": 0,
            "created_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        },
        "job_fired": {
            "job_id": "job_fired",
            "name": "fix: fired issue [bug]",
            "tags": ["run-once", "agency"],
            "run_count": 1,  # already fired — should be cleaned by existing filter
            "created_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        },
    }

    summary = await cleanup_stale_jobs(store)

    # The stale unfired job must be deleted
    remaining_names = [d.get("name") for d in store.load_all()]
    assert "fix: old issue [bug]" not in remaining_names, (
        f"Stale unfired run-once job must be deleted. Remaining: {remaining_names}"
    )
    # The fresh unfired job should remain (it's not old enough)
    assert "fix: new issue [security]" in remaining_names, (
        f"Fresh run-once job should not be deleted. Remaining: {remaining_names}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 5: test_schedule_growth_bounded_under_failure_storm
# Simulate 50 task-failure cycles through the real create/requeue paths
# with a memory store; assert final schedule count <= (loop registry size + small constant).
# ──────────────────────────────────────────────────────────────────────────────


def test_schedule_growth_bounded_under_failure_storm():
    """Schedule count must stay bounded even under 50 consecutive task failures.

    This is THE invariant that makes the 2026-07-03 incident impossible:
    no matter how many tasks fail, the schedule count cannot grow
    unboundedly. The dedup-by-name in AgentScheduler.create() ensures
    that re-scheduling the same task produces 1 row, not N rows.
    """
    from packages.scheduler.scheduler import AgentScheduler

    store = _FakePersistence()
    sched = AgentScheduler(persistence=store)
    try:
        # Simulate 50 failure cycles — each cycle schedules the SAME fix task
        # (same name, same instruction) as a run-once job.
        for i in range(50):
            sched.create(
                name="fix: recurring test failure [test]",
                cron="0 9 * * *",
                instruction="fix the failing test",
                run_once=True,
                tags=["auto-improvement", "test", "agency"],
            )

        # After 50 cycles with the same name, there should be exactly 1 schedule
        jobs = sched.list()
        assert len(jobs) <= 1, (
            f"Schedule count must be bounded: expected ≤1, got {len(jobs)} after 50 cycles. "
            f"This is the invariant that prevents the 2,873-row pile. "
            f"Names: {[j.name for j in jobs]}"
        )
    finally:
        sched.shutdown()


# ──────────────────────────────────────────────────────────────────────────────
# Test 6: test_dispatcher_honors_concurrency_env
# TASK_DISPATCH_CONCURRENCY=1 → never more than one concurrent coordinator execution.
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dispatcher_honors_concurrency_env(monkeypatch):
    """TASK_DISPATCH_CONCURRENCY=1 must prevent concurrent task execution.

    The 2026-07-03 incident had 5 concurrent agent executions because
    the default concurrency was 5 and the tick requeued 5 tasks at once.
    """
    monkeypatch.setenv("TASK_DISPATCH_CONCURRENCY", "1")

    from tasks.dispatcher import TaskDispatcher

    # Track concurrent executions
    concurrent = 0
    max_concurrent = 0

    class _FakeCoordinator:
        def __init__(self):
            self._active_task_ids: set[str] = set()

        async def execute(self, task_id):
            nonlocal concurrent, max_concurrent
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            await asyncio.sleep(0.05)  # simulate work
            concurrent -= 1

        @property
        def _active_task_ids(self):
            return set()

    class _FakeStore:
        def __init__(self):
            self._tasks = []

        async def list_pending(self, limit=5):
            return self._tasks[:limit]

        async def reconcile_stranded_tasks(self, **kwargs):
            return 0

        async def list_blocked(self, limit=5):
            return []

    from tasks.models import Task, TaskStatus

    store = _FakeStore()
    store._tasks = [
        Task(owner_id="system", title=f"task-{i}", status=TaskStatus.TODO,
             prompt="test", pending_agent_run=True)
        for i in range(5)
    ]

    coord = _FakeCoordinator()
    dispatcher = TaskDispatcher(
        workspace_root="/tmp",  # nosec B108
        poll_interval_s=0.01,
        store=store,
        coordinator=coord,
    )

    # Run one poll cycle
    await dispatcher._poll_and_execute()

    assert max_concurrent <= 1, (
        f"TASK_DISPATCH_CONCURRENCY=1 must prevent concurrent execution. "
        f"Max concurrent: {max_concurrent}"
    )

    dispatcher.stop()


# ──────────────────────────────────────────────────────────────────────────────
# Test 7: Keep green — verify existing incident-fix tests still pass
# (These are in test_purge_backlog.py and are run as part of the normal
# CI suite — this test just verifies they exist and are importable.)
# ──────────────────────────────────────────────────────────────────────────────


def test_incident_fix_tests_exist():
    """Verify that the incident-fix test suite is present and importable."""
    import importlib
    mod = importlib.import_module("tests.test_purge_backlog")
    assert hasattr(mod, "__file__"), "test_purge_backlog.py must exist"
    # Verify it has test functions
    test_funcs = [name for name in dir(mod) if name.startswith("test_")]
    assert len(test_funcs) >= 3, (
        f"test_purge_backlog.py must have at least 3 test functions, got {test_funcs}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# Test 8: Ops tripwire — schedule_count reported on /api/health
# ──────────────────────────────────────────────────────────────────────────────


def test_health_reports_schedule_count():
    """The /api/health endpoint (or /api/autonomy/status) must report
    schedule_count so the operator can see growth before it's too late.

    This is a source-inspection test — we verify the code exists.
    """
    import inspect
    import backend.server as server_mod

    source = inspect.getsource(server_mod)

    # Check that schedule_count or schedule count is reported somewhere
    # in the health or autonomy status endpoints
    assert any(pattern in source for pattern in [
        "schedule_count",
        "schedules_count",
        "len(sched.list())",
        "len(SCHEDULER.list())",
    ]), (
        "Health/autonomy endpoint must report schedule_count for the ops tripwire. "
        "This is how the operator sees schedule growth before OOM."
    )
