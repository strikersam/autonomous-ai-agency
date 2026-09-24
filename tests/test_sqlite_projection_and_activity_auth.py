"""Two leaks found in the 2026-09-23 QA pass.

* ``packages/storage/sqlite.py`` ignored the ``projection`` argument of
  ``find``/``find_one``. On SQLite (dev / self-hosted), ``GET /api/keys`` sent
  every key's ``secret_hash`` to the browser despite ``{"secret_hash": 0}``,
  and list endpoints shipped the chat ``messages`` / wiki ``content`` they
  exclude on Mongo.
* ``@app.get("/api/activity")`` decorated the raw ``_get_activity_impl``, so
  the authenticated, cached ``get_activity`` wrapper was dead code and anyone
  could read the feed — which carries other users' run prompts and errors.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from packages.storage.sqlite import SQLiteStore


@pytest.fixture()
async def store(tmp_path):
    s = SQLiteStore(str(tmp_path / "proj.db"))
    await s.api_keys.insert_one({"key_id": "k1", "email": "a@b.c", "secret_hash": "$2b$12$x", "created_at": "2"})
    await s.api_keys.insert_one({"key_id": "k2", "email": "d@e.f", "secret_hash": "$2b$12$y", "created_at": "1"})
    return s


@pytest.mark.asyncio
async def test_find_exclusion_projection_drops_the_field(store) -> None:
    rows = await store.api_keys.find({}, {"secret_hash": 0}).sort("created_at", -1).to_list(10)
    assert [r["key_id"] for r in rows] == ["k1", "k2"]
    assert all("secret_hash" not in r for r in rows)
    assert all("_id" in r for r in rows)


@pytest.mark.asyncio
async def test_find_inclusion_projection_keeps_only_named_fields(store) -> None:
    rows = await store.api_keys.find({}, {"_id": 0, "key_id": 1}).sort("created_at", 1).to_list(10)
    assert rows == [{"key_id": "k2"}, {"key_id": "k1"}]


@pytest.mark.asyncio
async def test_find_one_applies_projection(store) -> None:
    row = await store.api_keys.find_one({"key_id": "k1"}, {"secret_hash": 0, "_id": 0})
    assert "secret_hash" not in row and "_id" not in row
    assert (row["key_id"], row["email"]) == ("k1", "a@b.c")


@pytest.mark.asyncio
async def test_find_without_projection_is_unchanged(store) -> None:
    row = await store.api_keys.find_one({"key_id": "k2"})
    assert row["secret_hash"] == "$2b$12$y"


def test_activity_feed_requires_auth() -> None:
    from backend.server import app

    resp = TestClient(app, raise_server_exceptions=False).get("/api/activity")
    assert resp.status_code == 401
