"""Storage backends for the durable run tests: memory, a real ``MongoStore`` over the
hermetic Motor fake, and a real file backed ``SQLiteStore``.

``open_pair`` returns two handles on the *same* database, standing in for two
processes (memory has no second process, so it returns the same handle twice).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from packages.storage.mongo import MongoStore
from packages.storage.sqlite import SQLiteStore
from tests._fake_motor import FakeMotorDb

BACKENDS = ("memory", "mongo", "sqlite")
SHARED_BACKENDS = ("mongo", "sqlite")


def mongo_store(shared: FakeMotorDb) -> MongoStore:
    """A real ``MongoStore`` whose lazy Motor database is the hermetic fake."""
    store = MongoStore()
    store._get_db = lambda: shared  # type: ignore[method-assign]
    return store


@asynccontextmanager
async def open_pair(kind: str, tmp_path: Path) -> AsyncIterator[tuple[Any, Any]]:
    """Two db handles on one database for *kind* (``None`` for memory)."""
    if kind == "memory":
        yield None, None
        return
    if kind == "mongo":
        shared = FakeMotorDb()
        yield mongo_store(shared), mongo_store(shared)
        return
    path = str(tmp_path / "runs.db")
    a, b = SQLiteStore(path), SQLiteStore(path)
    # Open the two connections one after the other: SQLiteStore's first connect
    # switches the file to WAL, and two first connects racing on a brand new file
    # can fail with "database is locked" (pre-existing, startup only).
    await a._get_conn()
    await b._get_conn()
    try:
        yield a, b
    finally:
        await a.close()
        await b.close()
