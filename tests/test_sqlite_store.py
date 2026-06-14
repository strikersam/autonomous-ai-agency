"""tests/test_sqlite_store.py — Unit tests for the SQLite storage adapter.

These tests run entirely in-memory (":memory:" path) with no external services.
"""
from __future__ import annotations

import asyncio
import pytest
from db.sqlite_store import SQLiteStore, _Collection, _COLLECTIONS


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
    from db.sqlite_store import SQLiteStore
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
