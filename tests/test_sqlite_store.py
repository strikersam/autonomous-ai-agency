"""tests/test_sqlite_store.py — Unit tests for the SQLite storage adapter.

These tests run entirely in-memory (":memory:" path) with no external services.
"""
from __future__ import annotations

import asyncio
import pytest
from packages.storage.sqlite import SQLiteStore, _Collection, _COLLECTIONS


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(db_path=str(tmp_path / "test.db"))


# ── find_one / insert_one ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_insert_and_find_one(store):
    result = await store.users.insert_one({"email": "alice@example.com", "role": "admin"})
    assert result.inserted_id

    user = await store.users.find_one({"email": "alice@example.com"})
    assert user is not None
    assert user["email"] == "alice@example.com"
    assert user["role"] == "admin"


@pytest.mark.asyncio
async def test_find_one_returns_none_for_miss(store):
    doc = await store.users.find_one({"email": "nobody@example.com"})
    assert doc is None


@pytest.mark.asyncio
async def test_find_one_by_id(store):
    r = await store.users.insert_one({"email": "bob@example.com"})
    doc = await store.users.find_one({"_id": r.inserted_id})
    assert doc is not None
    assert doc["email"] == "bob@example.com"


# ── update_one ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_one_set(store):
    await store.users.insert_one({"email": "carol@example.com", "role": "user"})
    result = await store.users.update_one(
        {"email": "carol@example.com"},
        {"$set": {"role": "admin"}}
    )
    assert result.matched_count == 1
    doc = await store.users.find_one({"email": "carol@example.com"})
    assert doc["role"] == "admin"


@pytest.mark.asyncio
async def test_update_one_upsert(store):
    result = await store.users.update_one(
        {"email": "new@example.com"},
        {"$set": {"role": "user"}},
        upsert=True
    )
    assert result.modified_count == 1
    doc = await store.users.find_one({"email": "new@example.com"})
    assert doc is not None


@pytest.mark.asyncio
async def test_update_one_push(store):
    await store.users.insert_one({"email": "dan@example.com", "tags": []})
    await store.users.update_one({"email": "dan@example.com"}, {"$push": {"tags": "beta"}})
    doc = await store.users.find_one({"email": "dan@example.com"})
    assert "beta" in doc["tags"]


@pytest.mark.asyncio
async def test_update_one_inc(store):
    await store.users.insert_one({"email": "eve@example.com", "login_count": 0})
    await store.users.update_one({"email": "eve@example.com"}, {"$inc": {"login_count": 1}})
    doc = await store.users.find_one({"email": "eve@example.com"})
    assert doc["login_count"] == 1


# ── update_many ──────────────────────────────────────────────────────────────
# Regression: _Collection had no update_many() at all — any Motor-style caller
# (e.g. backend/server.py clearing every OTHER provider's is_default flag
# before setting the new one) got a bare AttributeError. On the production
# STORAGE_BACKEND=sqlite deployment this made "Set default" on the Providers
# page 500 unconditionally, and since the write never actually happened, the
# default provider could never change from whatever was set at seed time.

@pytest.mark.asyncio
async def test_update_many_set_matches_all(store):
    await store.users.insert_one({"email": "a@example.com", "role": "user"})
    await store.users.insert_one({"email": "b@example.com", "role": "user"})
    await store.users.insert_one({"email": "c@example.com", "role": "admin"})

    result = await store.users.update_many({"role": "user"}, {"$set": {"role": "member"}})
    assert result.matched_count == 2
    assert result.modified_count == 2

    a = await store.users.find_one({"email": "a@example.com"})
    b = await store.users.find_one({"email": "b@example.com"})
    c = await store.users.find_one({"email": "c@example.com"})
    assert a["role"] == "member"
    assert b["role"] == "member"
    assert c["role"] == "admin", "non-matching document must be untouched"


@pytest.mark.asyncio
async def test_update_many_no_match_returns_zero(store):
    result = await store.users.update_many({"email": "nobody@example.com"}, {"$set": {"role": "x"}})
    assert result.matched_count == 0
    assert result.modified_count == 0


@pytest.mark.asyncio
async def test_update_many_ne_clears_default_flag(store):
    """The exact query shape backend/server.py's provider "Set default" uses:
    clear is_default off every OTHER provider before setting it on the chosen one."""
    await store.providers.insert_one({"provider_id": "deepseek", "is_default": True})
    await store.providers.insert_one({"provider_id": "moonshot", "is_default": False})

    await store.providers.update_many(
        {"provider_id": {"$ne": "moonshot"}}, {"$set": {"is_default": False}}
    )
    await store.providers.update_one(
        {"provider_id": "moonshot"}, {"$set": {"is_default": True}}
    )

    deepseek = await store.providers.find_one({"provider_id": "deepseek"})
    moonshot = await store.providers.find_one({"provider_id": "moonshot"})
    assert deepseek["is_default"] is False
    assert moonshot["is_default"] is True


# ── delete_one ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_one(store):
    await store.users.insert_one({"email": "frank@example.com"})
    result = await store.users.delete_one({"email": "frank@example.com"})
    assert result.deleted_count == 1
    assert await store.users.find_one({"email": "frank@example.com"}) is None


@pytest.mark.asyncio
async def test_delete_one_miss_returns_zero(store):
    result = await store.users.delete_one({"email": "ghost@example.com"})
    assert result.deleted_count == 0


# ── find (cursor) ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_find_returns_all(store):
    await store.users.insert_one({"email": "g1@example.com", "role": "user"})
    await store.users.insert_one({"email": "g2@example.com", "role": "user"})
    await store.users.insert_one({"email": "g3@example.com", "role": "admin"})
    docs = await store.users.find({"role": "user"}).to_list(None)
    assert len(docs) == 2


@pytest.mark.asyncio
async def test_find_sort_and_limit(store):
    for i in range(5):
        await store.activity_log.insert_one({"user_id": "u1", "action": f"act{i}", "created_at": f"2026-01-0{i+1}"})
    docs = await store.activity_log.find({}).sort("created_at", -1).limit(2).to_list(None)
    assert len(docs) == 2
    assert docs[0]["created_at"] > docs[1]["created_at"]


@pytest.mark.asyncio
async def test_find_async_iteration(store):
    await store.wiki_pages.insert_one({"slug": "s1", "user_id": "u1"})
    await store.wiki_pages.insert_one({"slug": "s2", "user_id": "u1"})
    collected = []
    async for doc in store.wiki_pages.find({"user_id": "u1"}):
        collected.append(doc)
    assert len(collected) == 2


# ── count_documents ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_count_documents(store):
    await store.providers.insert_one({"provider_id": "ollama", "user_id": "u1"})
    await store.providers.insert_one({"provider_id": "nim", "user_id": "u1"})
    count = await store.providers.count_documents({"user_id": "u1"})
    assert count == 2


@pytest.mark.asyncio
async def test_count_documents_empty_query_fast_path(store):
    """Unfiltered count uses the SELECT COUNT(*) fast path and must match the
    number of inserted rows exactly (no off-by-one, no row materialisation)."""
    assert await store.providers.count_documents({}) == 0
    await store.providers.insert_one({"provider_id": "a", "user_id": "u1"})
    await store.providers.insert_one({"provider_id": "b", "user_id": "u2"})
    await store.providers.insert_one({"provider_id": "c", "user_id": "u2"})
    assert await store.providers.count_documents({}) == 3
    # Filtered count still goes through the Python _match path and is unaffected.
    assert await store.providers.count_documents({"user_id": "u2"}) == 2


@pytest.mark.asyncio
async def test_estimated_document_count(store):
    """estimated_document_count mirrors an unfiltered count_documents."""
    assert await store.providers.estimated_document_count() == 0
    await store.providers.insert_one({"provider_id": "a"})
    await store.providers.insert_one({"provider_id": "b"})
    assert await store.providers.estimated_document_count() == 2
    assert (
        await store.providers.estimated_document_count()
        == await store.providers.count_documents({})
    )


# ── query operators ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_query_ne(store):
    await store.users.insert_one({"email": "h1@example.com", "role": "user"})
    await store.users.insert_one({"email": "h2@example.com", "role": "admin"})
    docs = await store.users.find({"role": {"$ne": "admin"}}).to_list(None)
    emails = [d["email"] for d in docs]
    assert "h1@example.com" in emails
    assert "h2@example.com" not in emails


@pytest.mark.asyncio
async def test_query_in(store):
    await store.users.insert_one({"email": "i1@example.com", "role": "user"})
    await store.users.insert_one({"email": "i2@example.com", "role": "power_user"})
    await store.users.insert_one({"email": "i3@example.com", "role": "admin"})
    docs = await store.users.find({"role": {"$in": ["user", "power_user"]}}).to_list(None)
    assert len(docs) == 2


@pytest.mark.asyncio
async def test_query_or(store):
    await store.users.insert_one({"email": "j1@example.com", "role": "user"})
    await store.users.insert_one({"email": "j2@example.com", "role": "admin"})
    docs = await store.users.find({"$or": [{"role": "user"}, {"role": "admin"}]}).to_list(None)
    assert len(docs) == 2


# ── replace_one ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_replace_one(store):
    await store.users.insert_one({"email": "k@example.com", "role": "user", "name": "Old"})
    await store.users.replace_one({"email": "k@example.com"}, {"email": "k@example.com", "name": "New"})
    doc = await store.users.find_one({"email": "k@example.com"})
    assert doc["name"] == "New"
    assert doc.get("role") is None


# ── distinct ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_distinct(store):
    await store.users.insert_one({"email": "l1@example.com", "role": "user"})
    await store.users.insert_one({"email": "l2@example.com", "role": "user"})
    await store.users.insert_one({"email": "l3@example.com", "role": "admin"})
    roles = await store.users.distinct("role")
    assert set(roles) == {"user", "admin"}


# ── db/ package import ────────────────────────────────────────────────────────

def test_get_store_returns_sqlite(monkeypatch, tmp_path):
    import os
    monkeypatch.setenv("STORAGE_BACKEND", "sqlite")
    monkeypatch.setenv("SQLITE_DB_PATH", str(tmp_path / "test.db"))
    import db
    db.reset_store()
    store = db.get_store()
    from packages.storage.sqlite import SQLiteStore
    assert isinstance(store, SQLiteStore)
    db.reset_store()


# ── subscript access (Mongo-compatibility) ────────────────────────────────────
# Regression: SQLiteStore exposed collections only via attribute access
# (__getattr__), so Mongo-style subscript access — db["tasks"], used by
# TaskStore/AgentStore — raised "TypeError: 'SQLiteStore' object is not
# subscriptable" under STORAGE_BACKEND=sqlite, crash-looping the TaskDispatcher
# and failing the Browser E2E job.

@pytest.mark.asyncio
async def test_subscript_access_returns_collection(store) -> None:
    """db['tasks'] must work like db.tasks (motor exposes both)."""
    attr_coll = store.tasks
    item_coll = store["tasks"]
    assert type(item_coll) is type(attr_coll)
    # round-trips through the subscript-accessed collection
    await item_coll.insert_one({"task_id": "t1", "status": "todo"})
    doc = await store["tasks"].find_one({"task_id": "t1"})
    assert doc and doc["status"] == "todo"


@pytest.mark.asyncio
async def test_taskstore_works_on_sqlite_backend(store) -> None:
    """TaskStore(db=SQLiteStore) must not raise 'not subscriptable'.

    This is the exact path the TaskDispatcher exercises (list_pending) that
    crash-looped in the Browser E2E backend container."""
    from tasks.store import TaskStore
    ts = TaskStore(db=store)
    # list_pending hits self._db["tasks"].find(...)
    pending = await ts.list_pending(limit=5)
    assert pending == []

# ── B608 SQL injection guard regression tests ──────────────────────────────

@pytest.mark.asyncio
async def test_non_whitelisted_table_rejected(tmp_path):
    """B608 guard: _Collection.__init__ must reject names outside _COLLECTIONS.

    Prevents SQL injection via dynamic table names in the f-string SQL paths
    (find/insert/update/delete/aggregate) of _Collection. Includes a realistic
    SQLi payload to confirm the guard catches what the f-string would interpolate.
    """
    store = SQLiteStore(str(tmp_path / "test.db"))
    # Benign non-whitelisted name
    with pytest.raises(ValueError, match="refusing to bind to non-whitelisted table"):
        _Collection(store, "malicious_table")
    # Realistic SQLi payload — the exact kind of string that would be catastrophic
    # if interpolated into the f-string SQL in _all_docs / insert_one / etc.
    with pytest.raises(ValueError, match="refusing to bind to non-whitelisted table"):
        _Collection(store, "users; DROP TABLE users;--")
    # Attribute-access path must also fail closed
    with pytest.raises(AttributeError, match="refusing to bind to non-whitelisted table"):
        store.__getattr__("users; DROP TABLE users;--")

@pytest.mark.asyncio
async def test_whitelisted_collections_accepted(tmp_path):
    """B608 guard: all collections in _COLLECTIONS must still be instantiable."""
    store = SQLiteStore(str(tmp_path / "test.db"))
    for name in _COLLECTIONS:
        col = _Collection(store, name)
        assert col._name == name, f"_name should equal {name!r}"


@pytest.mark.asyncio
async def test_mcp_servers_collection_whitelisted(store):
    """Regression: GET /api/mcp/servers 500'd in sqlite mode because
    'mcp_servers' was missing from _COLLECTIONS — get_db().mcp_servers raised
    AttributeError ('refusing to bind to non-whitelisted table'). Exercise the
    exact endpoint access pattern (find by user_id, sort created_at, async-iter)."""
    assert "mcp_servers" in _COLLECTIONS
    await store.mcp_servers.insert_one({"user_id": "u1", "name": "ctx7", "created_at": 1})
    rows = [s async for s in store.mcp_servers.find({"user_id": "u1"}).sort("created_at", 1)]
    assert len(rows) == 1
    assert rows[0]["name"] == "ctx7"


@pytest.mark.asyncio
async def test_scan_and_workflow_collections_whitelisted(store):
    """website_scans / repo_scans / workflows are read via get_db() for company
    tech-stack inference; without whitelisting they raised AttributeError (caught
    + silently degraded) in sqlite mode. They must be real, queryable collections."""
    for name in ("website_scans", "repo_scans", "workflows"):
        assert name in _COLLECTIONS
    await store.website_scans.insert_one({"company_id": "c1", "status": "success", "completed_at": 2})
    got = await store.website_scans.find_one({"company_id": "c1", "status": "success"})
    assert got is not None and got["completed_at"] == 2
    await store.workflows.insert_one({"company_id": "c1", "is_active": True, "name": "wf"})
    active = [w async for w in store.workflows.find({"company_id": "c1", "is_active": True})]
    assert len(active) == 1


@pytest.mark.asyncio
async def test_read_pool_serves_concurrent_reads(store):
    """The WAL read pool must satisfy many concurrent reads without serializing
    them on the single writer connection. Proves reads use pooled connections
    distinct from the writer, and that a write concurrent with reads is safe."""
    await store.tasks.insert_one({"task_id": "t1", "user_id": "u1", "status": "todo"})

    async def reader() -> int:
        rows = await store.tasks.find({"user_id": "u1"}).to_list()
        return len(rows)

    async def writer() -> None:
        for i in range(5):
            await store.tasks.insert_one(
                {"task_id": f"w{i}", "user_id": "u1", "status": "todo"}
            )

    # 20 concurrent reads racing against a burst of writes — must not deadlock,
    # error, or raise "database is locked".
    results = await asyncio.gather(writer(), *[reader() for _ in range(20)])
    read_counts = results[1:]
    assert all(c >= 1 for c in read_counts)

    # The pool was actually built and is sized per SQLITE_READ_POOL_SIZE.
    assert store._read_pool is not None
    assert store._read_pool.qsize() == store._read_pool_size


@pytest.mark.asyncio
async def test_read_pool_disabled_for_memory_db():
    """In-memory DBs are private per connection, so the pool must be disabled and
    reads fall back to the writer connection (otherwise reads see an empty DB)."""
    store = SQLiteStore(db_path=":memory:")
    try:
        assert store._pool_enabled is False
        await store.users.insert_one({"email": "a@b.com", "role": "user"})
        got = await store.users.find_one({"email": "a@b.com"})
        assert got is not None and got["role"] == "user"
        # No separate pool was created.
        assert store._read_pool is None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_read_after_write_is_consistent(store):
    """A read issued after a committed write must observe it, even though reads
    go through a different (pooled) connection than the writer."""
    await store.tasks.insert_one({"task_id": "rw1", "user_id": "u9", "status": "todo"})
    # Pooled read sees the committed insert.
    assert await store.tasks.find_one({"task_id": "rw1"}) is not None
    # Update (read-modify-write via the writer connection) then pooled read.
    await store.tasks.update_one({"task_id": "rw1"}, {"$set": {"status": "done"}})
    got = await store.tasks.find_one({"task_id": "rw1"})
    assert got is not None and got["status"] == "done"


# ── SQL push-down on indexed columns ──────────────────────────────────────────
# Equality / $in conditions on indexed columns (user_id, status, …) are pushed
# into the SQL WHERE so the index does the filtering instead of pulling +
# JSON-decoding every row and scanning in Python. The Python _match still runs
# afterwards, so the result must be byte-for-byte identical to the old full scan.

from packages.storage.sqlite import _push_down_where  # noqa: E402


def test_push_down_builds_where_for_indexed_equality():
    """Indexed-column equality becomes a parameterised WHERE clause."""
    where, params = _push_down_where("tasks", {"user_id": "u1", "status": "todo"})
    assert "WHERE" in where
    assert where.count("?") == 2
    assert params == ["u1", "todo"]


def test_push_down_pushes_in_operator():
    """$in over an indexed column becomes a parameterised IN (...) clause."""
    where, params = _push_down_where("tasks", {"status": {"$in": ["todo", "doing"]}})
    assert "status IN (?, ?)" in where
    assert params == ["todo", "doing"]


def test_push_down_ignores_non_indexed_and_operators():
    """Non-indexed fields, $or, $ne, and None values are left to Python _match."""
    # Non-indexed field on the tasks table (only user_id/status are indexed).
    assert _push_down_where("tasks", {"priority": "high"}) == ("", [])
    # Top-level operators are never pushed.
    assert _push_down_where("tasks", {"$or": [{"status": "todo"}]}) == ("", [])
    # Range / $ne operators on an indexed column are not equality — not pushed.
    assert _push_down_where("tasks", {"status": {"$ne": "todo"}}) == ("", [])
    # None equality is ambiguous (missing field stored as "") — not pushed.
    assert _push_down_where("tasks", {"status": None}) == ("", [])


@pytest.mark.asyncio
async def test_push_down_results_match_full_scan(store):
    """End-to-end: pushed-down queries return exactly what the Python filter
    would, including the mixed indexed + non-indexed case where the WHERE only
    narrows and _match finishes the job."""
    await store.tasks.insert_one({"task_id": "a", "user_id": "u1", "status": "todo", "priority": "high"})
    await store.tasks.insert_one({"task_id": "b", "user_id": "u1", "status": "todo", "priority": "low"})
    await store.tasks.insert_one({"task_id": "c", "user_id": "u1", "status": "done", "priority": "high"})
    await store.tasks.insert_one({"task_id": "d", "user_id": "u2", "status": "todo", "priority": "high"})

    # Pure indexed equality (fully pushed).
    rows = await store.tasks.find({"user_id": "u1", "status": "todo"}).to_list(None)
    assert {r["task_id"] for r in rows} == {"a", "b"}

    # Indexed $in.
    rows = await store.tasks.find({"status": {"$in": ["todo", "done"]}, "user_id": "u1"}).to_list(None)
    assert {r["task_id"] for r in rows} == {"a", "b", "c"}

    # Mixed: indexed (pushed) + non-indexed (Python-filtered).
    rows = await store.tasks.find({"user_id": "u1", "priority": "high"}).to_list(None)
    assert {r["task_id"] for r in rows} == {"a", "c"}

    # count_documents goes through the same path.
    assert await store.tasks.count_documents({"user_id": "u1", "status": "todo"}) == 2


@pytest.mark.asyncio
async def test_push_down_missing_field_not_dropped(store):
    """A row missing an indexed field must never be dropped for a query that
    doesn't constrain that field — the WHERE must only narrow on constrained
    columns. Guards against the push-down excluding a real match."""
    await store.tasks.insert_one({"task_id": "x", "user_id": "u1"})  # no status
    rows = await store.tasks.find({"user_id": "u1"}).to_list(None)
    assert {r["task_id"] for r in rows} == {"x"}


# ── tasks find push-down: ORDER BY + LIMIT in SQL ─────────────────────────────

@pytest.mark.asyncio
async def test_tasks_find_sorted_limit_pushdown(store):
    """A fully-pushable owner_id query with sort+limit returns the correct page
    (SQL ORDER BY + LIMIT path), newest-first."""
    for i, oid in enumerate(["u1", "u1", "system", "u2", "u1"]):
        await store.tasks.insert_one(
            {"task_id": f"t{i}", "owner_id": oid, "status": "todo",
             "created_at": f"2026-06-21T0{i}:00:00"}
        )
    q = {"owner_id": {"$in": ["u1", "system"]}}
    rows = await store.tasks.find(q).sort("created_at", -1).limit(2).to_list(None)
    assert [r["task_id"] for r in rows] == ["t4", "t2"]
    # skip + limit paging stays correct
    rows2 = await store.tasks.find(q).sort("created_at", -1).skip(1).limit(2).to_list(None)
    assert [r["task_id"] for r in rows2] == ["t2", "t1"]
    # u2 task never leaks into the u1/system page
    assert "t3" not in {r["task_id"] for r in rows + rows2}


@pytest.mark.asyncio
async def test_tasks_find_nonpushable_query_falls_back(store):
    """A query touching a non-indexed field (priority) is NOT fully pushable, so
    it must fall back to the Python path and still filter + sort correctly."""
    await store.tasks.insert_one({"task_id": "a", "owner_id": "u1", "priority": "high",
                                  "created_at": "2026-01-01T00:00:00"})
    await store.tasks.insert_one({"task_id": "b", "owner_id": "u1", "priority": "low",
                                  "created_at": "2026-01-02T00:00:00"})
    rows = await store.tasks.find({"owner_id": "u1", "priority": "high"}) \
        .sort("created_at", -1).to_list(None)
    assert [r["task_id"] for r in rows] == ["a"]


@pytest.mark.asyncio
async def test_migration_backfills_new_indexed_column(tmp_path):
    """Opening a legacy tasks table that predates the owner_id index column must
    auto-add the column and backfill it from the JSON blob, so push-down queries
    by owner_id work immediately."""
    import aiosqlite
    import json as _json

    db = str(tmp_path / "legacy.db")
    conn = await aiosqlite.connect(db)
    # Legacy schema: no owner_id column.
    await conn.execute(
        "CREATE TABLE tasks (id TEXT PRIMARY KEY, data TEXT NOT NULL, "
        "user_id TEXT, status TEXT)"
    )
    doc = {"_id": "t1", "task_id": "t1", "owner_id": "system", "status": "todo",
           "created_at": "2026-01-01T00:00:00"}
    await conn.execute(
        "INSERT INTO tasks (id, data, user_id, status) VALUES (?, ?, ?, ?)",
        ("t1", _json.dumps(doc), "", "todo"),
    )
    await conn.commit()
    await conn.close()

    store = SQLiteStore(db_path=db)
    rows = await store.tasks.find({"owner_id": {"$in": ["system"]}}) \
        .sort("created_at", -1).to_list(None)
    assert [r["task_id"] for r in rows] == ["t1"]
    await store.close()


@pytest.mark.asyncio
async def test_agent_specs_collection_is_whitelisted(store):
    """Regression: agent_specs must be usable on the SQLite backend, not just
    Mongo — services/spec_store.py's persist_plan_spec() previously hit an
    AttributeError here (agent_specs missing from _COLLECTIONS), which was
    swallowed and silently skipped the approval gate when
    AGENT_SPEC_APPROVAL_REQUIRED=true on a SQLite-backed deployment."""
    assert "agent_specs" in _COLLECTIONS
    result = await store.agent_specs.insert_one(
        {"spec_id": "s1", "goal": "g", "status": "pending"}
    )
    assert result.inserted_id
    doc = await store.agent_specs.find_one({"spec_id": "s1"})
    assert doc is not None and doc["status"] == "pending"
