"""tests/test_bootstrap_source_id_index.py — _ensure_tasks_source_id_unique_index.

Follow-up fix: TaskStore.create()'s source_id dedup is a check-then-insert
race. Closing it with a unique+sparse Mongo index is only safe if building
that index is isolated from the rest of ensure_bootstrap()'s single
try/except — otherwise a deploy that already has duplicate source_id tasks
(the exact state this fix exists to clean up) would raise there and abort
seed_admin()/seed_default_providers()/task-store wiring too.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("JWT_SECRET", "test-secret-for-tests-only")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("ADMIN_PASSWORD", "test-password-for-tests-only")

with patch("motor.motor_asyncio.AsyncIOMotorClient") as mock_client:
    mock_client_instance = MagicMock()
    mock_client_instance.get_database.return_value = MagicMock()
    mock_client.return_value = mock_client_instance
    import backend.server as server

import pytest


@pytest.mark.asyncio
async def test_index_build_failure_does_not_raise(monkeypatch):
    """A unique-index build against a collection with pre-existing
    duplicate source_id values raises in real Mongo — the helper must
    catch and log that, not propagate it (which would otherwise abort
    the rest of ensure_bootstrap())."""
    fake_db = MagicMock()
    fake_tasks = MagicMock()
    fake_tasks.create_index = AsyncMock(side_effect=Exception("E11000 duplicate key error"))
    fake_db.tasks = fake_tasks
    monkeypatch.setattr(server, "get_db", lambda: fake_db)

    async def _fake_heal():
        return {"deleted": 0, "backfilled": 0, "total_scanned": 0}
    monkeypatch.setattr("services.self_heal._heal_task_duplicates", _fake_heal)

    # Must not raise.
    await server._ensure_tasks_source_id_unique_index()
    fake_tasks.create_index.assert_awaited_once_with("source_id", unique=True, sparse=True)


@pytest.mark.asyncio
async def test_dedup_pass_runs_before_index_build(monkeypatch):
    """The proactive dedup pass must run before the index-build attempt,
    so a first-deploy-with-existing-duplicates has the best chance of the
    index succeeding without a second restart."""
    call_order: list[str] = []

    fake_db = MagicMock()
    fake_tasks = MagicMock()

    async def _create_index(*_a, **_kw):
        call_order.append("index")
    fake_tasks.create_index = _create_index
    fake_db.tasks = fake_tasks
    monkeypatch.setattr(server, "get_db", lambda: fake_db)

    async def _fake_heal():
        call_order.append("dedup")
        return {"deleted": 2, "backfilled": 1, "total_scanned": 5}
    monkeypatch.setattr("services.self_heal._heal_task_duplicates", _fake_heal)

    await server._ensure_tasks_source_id_unique_index()
    assert call_order == ["dedup", "index"]


@pytest.mark.asyncio
async def test_dedup_failure_does_not_block_index_attempt(monkeypatch):
    """If the proactive dedup pass itself fails (e.g. store not wired up
    yet), the index build must still be attempted — self-heal's periodic
    loop will retry the dedup regardless."""
    fake_db = MagicMock()
    fake_tasks = MagicMock()
    fake_tasks.create_index = AsyncMock()
    fake_db.tasks = fake_tasks
    monkeypatch.setattr(server, "get_db", lambda: fake_db)

    async def _fake_heal():
        raise RuntimeError("store not ready")
    monkeypatch.setattr("services.self_heal._heal_task_duplicates", _fake_heal)

    await server._ensure_tasks_source_id_unique_index()
    fake_tasks.create_index.assert_awaited_once_with("source_id", unique=True, sparse=True)


@pytest.mark.asyncio
async def test_index_build_success_path(monkeypatch):
    fake_db = MagicMock()
    fake_tasks = MagicMock()
    fake_tasks.create_index = AsyncMock()
    fake_db.tasks = fake_tasks
    monkeypatch.setattr(server, "get_db", lambda: fake_db)

    async def _fake_heal():
        return {"deleted": 0, "backfilled": 0, "total_scanned": 0}
    monkeypatch.setattr("services.self_heal._heal_task_duplicates", _fake_heal)

    await server._ensure_tasks_source_id_unique_index()
    fake_tasks.create_index.assert_awaited_once_with("source_id", unique=True, sparse=True)
