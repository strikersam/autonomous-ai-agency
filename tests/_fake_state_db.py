"""Hermetic in-memory stand-in for a Motor database, for state-persistence tests."""
from __future__ import annotations

import asyncio
from typing import Any


def _match(doc: dict, query: dict) -> bool:
    for key, cond in query.items():
        val = doc.get(key)
        if isinstance(cond, dict):
            for op, arg in cond.items():
                if op == "$gt" and not (val is not None and val > arg):
                    return False
                if op == "$gte" and not (val is not None and val >= arg):
                    return False
        elif val != cond:
            return False
    return True


class _Cursor:
    def __init__(self, docs: list[dict]) -> None:
        self._docs = docs

    async def to_list(self, length: int | None = None) -> list[dict]:
        return list(self._docs[:length] if length else self._docs)


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[Any, dict] = {}
        self.fail = False
        self.calls: list[str] = []
        self.indexes: list[tuple[Any, dict]] = []
        self.index_fail = False

    def _enter(self, op: str) -> None:
        self.calls.append(op)
        if self.fail:
            raise RuntimeError("db down")

    async def find_one(self, query: dict, *a: Any, **k: Any) -> dict | None:
        self._enter("find_one")
        return next((dict(d) for d in self.docs.values() if _match(d, query)), None)

    def find(self, query: dict, *a: Any, **k: Any) -> _Cursor:
        self._enter("find")
        return _Cursor([dict(d) for d in self.docs.values() if _match(d, query)])

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        self._enter("update_one")
        doc = next((d for d in self.docs.values() if _match(d, query)), None)
        if doc is None:
            if not upsert:
                return
            doc = {k: v for k, v in query.items() if not isinstance(v, dict)}
            doc.update(update.get("$setOnInsert", {}))
            self.docs[doc["_id"]] = doc
        for k, v in update.get("$set", {}).items():
            doc[k] = v
        for k, v in update.get("$inc", {}).items():
            doc[k] = doc.get(k, 0) + v

    async def replace_one(self, query: dict, doc: dict, upsert: bool = False) -> None:
        self._enter("replace_one")
        self.docs[doc["_id"]] = dict(doc)

    async def delete_one(self, query: dict) -> Any:
        self._enter("delete_one")
        for key, d in list(self.docs.items()):
            if _match(d, query):
                del self.docs[key]
                return type("R", (), {"deleted_count": 1})()
        return type("R", (), {"deleted_count": 0})()

    async def create_index(self, keys: Any, **kwargs: Any) -> None:
        self.calls.append("create_index")
        if self.index_fail:
            raise RuntimeError("no index perms")
        self.indexes.append((keys, kwargs))

    def writes(self) -> int:
        return len([c for c in self.calls if c in ("update_one", "replace_one", "delete_one")])


class FakeDB:
    """One shared database; several 'workers' (store instances) see the same collections."""

    def __init__(self) -> None:
        self._cols: dict[str, FakeCollection] = {}

    def __getattr__(self, name: str) -> FakeCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._cols.setdefault(name, FakeCollection())


def install(monkeypatch: Any, db: FakeDB | None = None) -> FakeDB:
    """Point ``backend.server.get_db`` at *db* and reset persistence bookkeeping."""
    from packages.storage import state_persistence

    state_persistence.reset()
    db = db or FakeDB()
    monkeypatch.setattr("backend.server.get_db", lambda: db)
    return db


async def drain() -> None:
    """Await every fire-and-forget persistence task."""
    from packages.storage import state_persistence

    while state_persistence._pending:
        await asyncio.gather(*list(state_persistence._pending), return_exceptions=True)
    await asyncio.sleep(0)
